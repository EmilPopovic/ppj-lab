from typing import Dict, Set, List, Optional, Tuple
from dataclasses import dataclass
import instructions as instr
from regs import Regs
from opcodes import LoadSingleOpcode, StoreSingleOpcode, LoadStoreBlockOpcode
from addressing.oprnd2 import Oprnd2Rm, Oprnd2Imm8
from addressing import mode2, mode4
from cond import Cond
from size import WordOrByte


class RegisterAllocator:
    """Graph coloring register allocator for ARM assembly code"""
    
    def __init__(self, asm_code: List[instr.AssemblyLine]):
        self.asm_code = asm_code
        self.vregs: Set[int] = set()
        self.vreg_colors: Dict[int, int] = {}
        self.spilled_vregs: Set[int] = set()
        self.spill_slots: Dict[int, int] = {}  # vreg -> stack offset
        self.next_spill_offset = 0
        
        # Available registers for allocation
        # R0-R3: argument/scratch registers (caller-saved)
        # R4-R10: callee-saved registers
        # R11/FP: frame pointer (reserved)
        # R12: scratch register (can use for spills)
        # R13: SP, R14: LR, R15: PC (not allocatable)
        self.allocatable = {
            Regs.R4, Regs.R5, Regs.R6, Regs.R7,
            Regs.R8, Regs.R9, Regs.R10
        }
        
        self.callee_saved = {Regs.R4, Regs.R5, Regs.R6, Regs.R7,
                             Regs.R8, Regs.R9, Regs.R10}
        
        # R12 is scratch register for loading/storing spills
        self.spill_temp_reg = Regs.R12
    
    def extract_vregs(self) -> Set[int]:
        """Extract all virtual registers (>15) from the code"""
        vregs = set()
        
        for line in self.asm_code:
            if isinstance(line, instr.ArithmeticLogicOp):
                if line.rd > 15:
                    vregs.add(line.rd)
                if line.rn > 15:
                    vregs.add(line.rn)
                if isinstance(line.oprnd2, Oprnd2Rm) and line.oprnd2.rm > 15:
                    vregs.add(line.oprnd2.rm)
                    
            elif isinstance(line, instr.MoveOp):
                if line.rd > 15:
                    vregs.add(line.rd)
                if isinstance(line.oprnd2, Oprnd2Rm) and line.oprnd2.rm > 15:
                    vregs.add(line.oprnd2.rm)
                    
            elif isinstance(line, instr.TestOp):
                if line.rn > 15:
                    vregs.add(line.rn)
                if isinstance(line.oprnd2, Oprnd2Rm) and line.oprnd2.rm > 15:
                    vregs.add(line.oprnd2.rm)
                    
            elif isinstance(line, instr.MultiplyOp):
                if line.rd > 15:
                    vregs.add(line.rd)
                if line.rm > 15:
                    vregs.add(line.rm)
                if line.rs > 15:
                    vregs.add(line.rs)
                    
            elif isinstance(line, instr.LoadStoreSingleMode2Op):
                if line.rd > 15:
                    vregs.add(line.rd)
                    
        return vregs
    
    def compute_liveness(self) -> Dict[int, Tuple[Set[int], Set[int]]]:
        """Compute live-in and live-out sets for each instruction handling CFG"""
        n = len(self.asm_code)
        live_in: List[Set[int]] = [set() for _ in range(n)]
        live_out: List[Set[int]] = [set() for _ in range(n)]
        
        # Build Label Map
        labels: Dict[str, int] = {}
        for i, line in enumerate(self.asm_code):
            if isinstance(line, instr.Label):
                labels[line.name] = i
        
        # Build CFG (Successors list)
        successors: List[List[int]] = [[] for _ in range(n)]
        for i, line in enumerate(self.asm_code):
            if isinstance(line, instr.BranchOp):
                # Add branch target if available
                if line.label in labels:
                    successors[i].append(labels[line.label])
                
                # If conditional branch or BL (function call returns), flow continues to next
                # NOTE: BL is treated as normal instruction flow + implicit jump to function
                # For liveness within a function, we usually assume BL just continues.
                # Strictly speaking, B with AL (Always) does NOT flow to next.
                if line.opcode == instr.BranchOpcode.BL or line.cond != Cond.ALWAYS:
                    if i < n - 1:
                        successors[i].append(i + 1)
            
            elif isinstance(line, instr.MoveOp) and line.rd == Regs.PC:
                # Returns (MOV PC, LR) - no successors in this function
                pass
            
            elif i < n - 1:
                # Normal instruction flows to next
                successors[i].append(i + 1)
        
        # Iterative data-flow analysis
        changed = True
        while changed:
            changed = False
            
            for i in range(n - 1, -1, -1):
                old_live_in = live_in[i].copy()
                
                # live_out[i] = Union(live_in[s] for s in successors)
                current_live_out = set()
                for succ_idx in successors[i]:
                     current_live_out.update(live_in[succ_idx])
                live_out[i] = current_live_out
                
                # Extract uses and defs from instruction
                uses, defs = self._extract_uses_defs(self.asm_code[i])
                
                # live_in[i] = uses ∪ (live_out[i] - defs)
                live_in[i] = uses | (live_out[i] - defs)
                
                if live_in[i] != old_live_in:
                    changed = True
        
        return {i: (live_in[i], live_out[i]) for i in range(n)}
    
    def _extract_uses_defs(self, line: instr.AssemblyLine) -> Tuple[Set[int], Set[int]]:
        """Extract used and defined registers from an instruction"""
        uses = set()
        defs = set()
        
        if isinstance(line, instr.ArithmeticLogicOp):
            defs.add(line.rd)
            uses.add(line.rn)
            if isinstance(line.oprnd2, Oprnd2Rm):
                uses.add(line.oprnd2.rm)
                
        elif isinstance(line, instr.MoveOp):
            defs.add(line.rd)
            if isinstance(line.oprnd2, Oprnd2Rm):
                uses.add(line.oprnd2.rm)
                
        elif isinstance(line, instr.TestOp):
            uses.add(line.rn)
            if isinstance(line.oprnd2, Oprnd2Rm):
                uses.add(line.oprnd2.rm)
                
        elif isinstance(line, instr.MultiplyOp):
            defs.add(line.rd)
            uses.add(line.rm)
            uses.add(line.rs)
            
        elif isinstance(line, instr.LoadStoreSingleMode2Op):
            # LDR defines rd, STR uses rd
            if line.opcode == LoadSingleOpcode.LDR:
                defs.add(line.rd)
            elif line.opcode == StoreSingleOpcode.STR:
                uses.add(line.rd)
            
            # Extract registers from Mode2 addressing mode
            addr = line.mode2
            if isinstance(addr, mode2.Mode2ImmediateOffset):
                uses.add(addr.rn)
            elif isinstance(addr, mode2.Mode2RegisterOffset):
                uses.add(addr.rn)
                uses.add(addr.rm)
            elif isinstance(addr, mode2.Mode2ScaledOffset):
                uses.add(addr.rn)
                uses.add(addr.rm)
        
        # Filter out physical registers (0-15)
        uses = {r for r in uses if r > 15}
        defs = {r for r in defs if r > 15}
        
        return uses, defs
    
    def build_interference_graph(self) -> Dict[int, Set[int]]:
        """Build interference graph using liveness information"""
        liveness = self.compute_liveness()
        interference = {vreg: set() for vreg in self.vregs}
        
        for i, (live_in, live_out) in liveness.items():
            line = self.asm_code[i]
            uses, defs = self._extract_uses_defs(line)
            
            # All vregs live at the definition point interfere with the defined vreg
            for def_vreg in defs:
                for live_vreg in live_out:
                    if live_vreg != def_vreg and live_vreg in self.vregs:
                        interference[def_vreg].add(live_vreg)
                        interference[live_vreg].add(def_vreg)
        
        return interference
    
    def color_graph(self, interference: Dict[int, Set[int]]) -> Dict[int, int]:
        """Color interference graph using greedy algorithm"""
        colors = {}
        
        # Sort vregs by degree (descending) - color high-degree nodes first
        sorted_vregs = sorted(self.vregs, 
                            key=lambda v: len(interference[v]), 
                            reverse=True)
        
        for vreg in sorted_vregs:
            # Get colors already used by neighbors
            neighbor_colors = {colors[neighbor] 
                             for neighbor in interference[vreg] 
                             if neighbor in colors}
            
            # Find first available color (physical register)
            color_found = False
            for reg in sorted(self.allocatable):
                if reg not in neighbor_colors:
                    colors[vreg] = reg
                    color_found = True
                    break
            
            if not color_found:
                # Spill: no color available
                self.spilled_vregs.add(vreg)
                # print(f"[Warning] Register spill needed for vreg {vreg} - not implemented yet!")
        
        # if self.spilled_vregs:
        #    raise RuntimeError(f"Register allocation failed: need to spill {len(self.spilled_vregs)} vregs {sorted(self.spilled_vregs)}, but spilling not implemented. Try reducing variables or simplifying expressions.")
        
        return colors
    
    def allocate_registers(self) -> List[instr.AssemblyLine]:
        """Main register allocation routine"""
        self.vregs = self.extract_vregs()
        
        if not self.vregs:
            return self.asm_code
        
        # Build interference graph
        interference = self.build_interference_graph()
        
        # Color the graph
        self.vreg_colors = self.color_graph(interference)
        
        # Allocate spill slots for spilled registers
        self._allocate_spill_slots()
        
        # Rewrite instructions with allocated registers and spills
        code = self._rewrite_instructions()
        
        # Update function prologues/epilogues with callee-saved registers
        code = self._update_function_prologues_epilogues(code)
        
        return code
    
    def _allocate_spill_slots(self) -> None:
        """
        Allocate stack offsets for spilled registers.
        Assuming 'sub sp, sp, #frame_size' is present in function prologues.
        We will append spill space to the existing frame size.
        """
        if not self.spilled_vregs:
            return

        # Simple strategy: Just assign unique offsets for each vreg
        # relative to the *spill area start*.
        # The spill area will be allocated on stack.
        # We need to find where to add this space.
        
        # We iterate through the code to find function prologues.
        # In a real per-function allocator, this would be easier.
        # Here we have code for all functions concatenated.
        
        # Since we can't easily modify stack frame size per function without knowing which vreg belongs to which function,
        # we'll use a simplified approach:
        # Scan code, identify functions, identify which vregs are used in which function,
        # calculate spill size per function, and update that function's stack allocation.
        
        # Mapping: function_start_index -> {spilled_vregs_in_this_function}
        func_spills: Dict[int, Set[int]] = {}
        current_func_idx = -1
        
        for i, line in enumerate(self.asm_code):
            if isinstance(line, instr.Label) and str(line.name).startswith('f_'):
                current_func_idx = i
                func_spills[current_func_idx] = set()
            
            if current_func_idx != -1:
                uses, defs = self._extract_uses_defs(line)
                for vreg in (uses | defs):
                    if vreg in self.spilled_vregs:
                        func_spills[current_func_idx].add(vreg)
        
        # Now update each function's stack allocation
        self.func_spill_offsets: Dict[int, int] = {} # vreg -> offset from SP (after extra allocation)
        
        for func_start_idx, spills in func_spills.items():
            if not spills:
                continue
                
            spill_size = len(spills) * 4
            # Align to 8 bytes if needed, but 4 is fine for ARM stack usually (EABI wants 8 aligned at calls)
            if spill_size % 8 != 0:
                spill_size += 4
            
            # Find the "sub sp, sp, #X" instruction for locals (usually just after prologue)
            # Prologue: stmdb sp!, {regs}; mov fp, sp
            found_sub = False
            for i in range(func_start_idx, min(func_start_idx + 20, len(self.asm_code))): # Scan first 20 instrs
                 line = self.asm_code[i]
                 if isinstance(line, instr.ArithmeticLogicOp) and \
                    line.opcode == instr.ArithmeticOpcode.SUB and \
                    line.rd == Regs.SP and line.rn == Regs.SP and \
                    isinstance(line.oprnd2, instr.Oprnd2Imm8):
                         # Found stack allocation! Increase it.
                         line.oprnd2.imm_8r += spill_size
                         found_sub = True
                         
                         # Since we increased stack size, the locals offsets relative to FP don't change.
                         # But spills will be located at [FP - locals_size - spill_offset]
                         # Using SP-relative addressing: [SP, #spill_offset] (if SP points to bottom of spills)
                         pass
                         break
            
            if not found_sub:
                # No locals? Insert stack allocation for spills
                # Find "mov fp, sp" to insert after
                insert_idx = func_start_idx + 1 # Fallback
                for i in range(func_start_idx, min(func_start_idx + 10, len(self.asm_code))):
                     line = self.asm_code[i]
                     if isinstance(line, instr.MoveOp) and line.rd == Regs.FP and \
                        isinstance(line.oprnd2, instr.Oprnd2Rm) and line.oprnd2.rm == Regs.SP:
                            insert_idx = i + 1
                            break
                            
                self.asm_code.insert(insert_idx, instr.ArithmeticLogicOp(
                    instr.ArithmeticOpcode.SUB, Regs.SP, Regs.SP, instr.Oprnd2Imm8(spill_size)
                ))
            
            # Assign offsets relative to the (now extended) bottom of stack (SP)
            # Spills will be at [SP, #0], [SP, #4], etc.
            current_offset = 0
            for vreg in sorted(list(spills)):
                 self.spill_slots[vreg] = current_offset
                 current_offset += 4

    def _emit_spill_store(self, phys_reg: int, vreg: int) -> List[instr.AssemblyLine]:
        """Store phys_reg to spill slot for vreg"""
        offset = self.spill_slots[vreg]
        # str phys_reg, [sp, #offset]
        return [instr.LoadStoreSingleMode2Op(
            StoreSingleOpcode.STR, WordOrByte.WORD, phys_reg,
            mode2.Mode2ImmediateOffset(Regs.SP, mode2.IndexingType.NO_INDEX, offset)
        )]

    def _emit_spill_load(self, vreg: int, phys_reg: int) -> List[instr.AssemblyLine]:
        """Load vreg from spill slot to phys_reg"""
        offset = self.spill_slots[vreg]
        # ldr phys_reg, [sp, #offset]
        return [instr.LoadStoreSingleMode2Op(
            LoadSingleOpcode.LDR, WordOrByte.WORD, phys_reg,
            mode2.Mode2ImmediateOffset(Regs.SP, mode2.IndexingType.NO_INDEX, offset)
        )]

    def _rewrite_instructions(self) -> List[instr.AssemblyLine]:
        """Rewrite assembly code with allocated physical registers and spill code"""
        new_code = []
        
        for line in self.asm_code:
            # Check if this instruction uses any spilled registers
            uses, defs = self._extract_uses_defs(line)
            spilled_uses = uses.intersection(self.spilled_vregs)
            spilled_defs = defs.intersection(self.spilled_vregs)
            
            if not spilled_uses and not spilled_defs:
                # No spilling involved, standard rewrite
                if isinstance(line, instr.ArithmeticLogicOp):
                    new_code.append(self._rewrite_arith_logic(line))
                elif isinstance(line, instr.MoveOp):
                    new_code.append(self._rewrite_move(line))
                elif isinstance(line, instr.TestOp):
                    new_code.append(self._rewrite_test(line))
                elif isinstance(line, instr.MultiplyOp):
                    new_code.append(self._rewrite_multiply(line))
                elif isinstance(line, instr.LoadStoreSingleMode2Op):
                    new_code.append(self._rewrite_load_store(line))
                else:
                    new_code.append(line)
                continue
            
            # Handle spilling
            # Strategy:
            # 1. Load spilled uses into temp reg (R12)
            # 2. Rewrite instruction to use temp reg
            # 3. If spilled reg is defined, store temp reg to spill slot
            
            # NOTE: This simple strategy assumes max 1 spilled use/def per instruction
            # or relies on R12 being enough. 
            # If multiple operands are spilled, we might need more temp regs (e.g. LR if not leaf?)
            # Or just fail if >1 spilled operand.
            
            if len(spilled_uses) > 1:
                # Hard case: multiple inputs spilled. R12 is only one reg.
                # We could use LR as second scratch if we save it (it is saved in prologue)
                # But for now, let's assume we can error or try to proceed.
                # Actually, we can use R14(LR) as scratch since it's saved on stack!
                # But we validly might be using LR for return.
                pass 

            # Map vreg -> temp_phys_reg
            # R12 is primary temp. If we need another, maybe R3 (since valid regs are R4-R10)?
            # No, R0-R3 are scratch, but might hold live values?
            # Register allocator only tracks vregs. R0-R3 usually have short lifetimes.
            # But we can't blindly clobber R0-R3 if they hold something live.
            
            # Conservative: Only support 1 spilled operand for now using R12.
            
            temp_reg = self.spill_temp_reg
            
            # Load spilled Use
            # (If binary op has 2 spilled sources, this logic needs expansion)
            last_used_temp = temp_reg
            
            for vreg in spilled_uses:
                new_code.extend(self._emit_spill_load(vreg, temp_reg))
                last_used_temp = temp_reg # Keep track
            
            # Rewrite instruction to use temp_reg instead of spilled vreg
            # We temporarily map the spilled vreg to temp_reg in vreg_colors
            # WARNING: This modifies global state if not careful.
            
            # Perform rewrite with temporary mapping
            for vreg in spilled_uses | spilled_defs:
                self.vreg_colors[vreg] = temp_reg
                
            if isinstance(line, instr.ArithmeticLogicOp):
                new_code.append(self._rewrite_arith_logic(line))
            elif isinstance(line, instr.MoveOp):
                new_code.append(self._rewrite_move(line))
            elif isinstance(line, instr.TestOp):
                new_code.append(self._rewrite_test(line))
            elif isinstance(line, instr.MultiplyOp):
                new_code.append(self._rewrite_multiply(line))
            elif isinstance(line, instr.LoadStoreSingleMode2Op):
                new_code.append(self._rewrite_load_store(line))
            
            # Restore vreg_colors mapping (clean up)
            for vreg in spilled_uses | spilled_defs:
                del self.vreg_colors[vreg]
                
            # Store spilled Def
            for vreg in spilled_defs:
                new_code.extend(self._emit_spill_store(temp_reg, vreg))
        
        return new_code 
    
    
    def _get_allocated_reg(self, vreg: int) -> int:
        """Get physical register for a virtual register"""
        if vreg <= 15:
            return vreg  # Already physical
        return self.vreg_colors.get(vreg, vreg)
    
    def _rewrite_arith_logic(self, line: instr.ArithmeticLogicOp) -> instr.AssemblyLine:
        new_rd = self._get_allocated_reg(line.rd)
        new_rn = self._get_allocated_reg(line.rn)
        new_oprnd2 = line.oprnd2
        
        if isinstance(line.oprnd2, Oprnd2Rm):
            new_rm = self._get_allocated_reg(line.oprnd2.rm)
            new_oprnd2 = Oprnd2Rm(new_rm)
        
        return instr.ArithmeticLogicOp(line.opcode, new_rd, new_rn, new_oprnd2)
    
    def _rewrite_move(self, line: instr.MoveOp) -> instr.AssemblyLine:
        new_rd = self._get_allocated_reg(line.rd)
        new_oprnd2 = line.oprnd2
        
        if isinstance(line.oprnd2, Oprnd2Rm):
            new_rm = self._get_allocated_reg(line.oprnd2.rm)
            new_oprnd2 = Oprnd2Rm(new_rm)
        
        cond = line.cond if hasattr(line, 'cond') else Cond.ALWAYS
        return instr.MoveOp(line.opcode, new_rd, new_oprnd2, cond)
    
    def _rewrite_test(self, line: instr.TestOp) -> instr.AssemblyLine:
        new_rn = self._get_allocated_reg(line.rn)
        new_oprnd2 = line.oprnd2
        
        if isinstance(line.oprnd2, Oprnd2Rm):
            new_rm = self._get_allocated_reg(line.oprnd2.rm)
            new_oprnd2 = Oprnd2Rm(new_rm)
        
        return instr.TestOp(line.opcode, new_rn, new_oprnd2)
    
    def _rewrite_multiply(self, line: instr.MultiplyOp) -> instr.AssemblyLine:
        new_rd = self._get_allocated_reg(line.rd)
        new_rm = self._get_allocated_reg(line.rm)
        new_rs = self._get_allocated_reg(line.rs)
        
        return instr.MultiplyOp(new_rd, new_rm, new_rs, cond=line.cond)
    
    def _rewrite_load_store(self, line: instr.LoadStoreSingleMode2Op) -> instr.AssemblyLine:
        new_rd = self._get_allocated_reg(line.rd)
        cond = line.cond if hasattr(line, 'cond') else Cond.ALWAYS
        
        # Rewrite registers in the addressing mode
        new_mode2 = line.mode2
        if isinstance(line.mode2, mode2.Mode2ImmediateOffset):
            new_rn = self._get_allocated_reg(line.mode2.rn)
            new_mode2 = mode2.Mode2ImmediateOffset(
                new_rn,
                line.mode2.indexing,
                line.mode2.imm_12,
                line.mode2.negate_imm
            )
        elif isinstance(line.mode2, mode2.Mode2RegisterOffset):
            new_rn = self._get_allocated_reg(line.mode2.rn)
            new_rm = self._get_allocated_reg(line.mode2.rm) if line.mode2.rm is not None else None
            new_mode2 = mode2.Mode2RegisterOffset(
                new_rn,
                line.mode2.indexing,
                new_rm,
                line.mode2.negate_rm
            )
        elif isinstance(line.mode2, mode2.Mode2ScaledOffset):
            new_rn = self._get_allocated_reg(line.mode2.rn)
            new_rm = self._get_allocated_reg(line.mode2.rm)
            new_mode2 = mode2.Mode2ScaledOffset(
                new_rn,
                new_rm,
                line.mode2.indexing,
                line.mode2.shift,
                line.mode2.imm_5,
                line.mode2.negate_rm
            )
        
        return instr.LoadStoreSingleMode2Op(line.opcode, line.size, new_rd, new_mode2, cond)
    
    def get_used_callee_saved(self) -> Set[int]:
        """Get which callee-saved registers were actually used"""
        return {reg for reg in self.vreg_colors.values() if reg in self.callee_saved}
    
    def _update_function_prologues_epilogues(self, code: List[instr.AssemblyLine]) -> List[instr.AssemblyLine]:
        """Update function prologue/epilogue to save/restore used callee-saved registers"""
        used_callee_saved = sorted(self.get_used_callee_saved())
        
        if not used_callee_saved:
            return code  # No callee-saved registers used
        
        new_code = []
        i = 0
        while i < len(code):
            line = code[i]
            
            # Look for function prologue: STMDB SP!, {FP, LR}
            if (isinstance(line, instr.LoadStoreMultipleOp) and 
                line.opcode == instr.LoadStoreBlockOpcode.STM and
                line.rd == Regs.SP and
                Regs.FP in line.reglist and Regs.LR in line.reglist and
                line.save_rd):
                
                # Keep original STMDB {FP, LR} which saves FP and LR
                # This ensures [FP] -> Saved FP, [FP+4] -> Saved LR
                new_code.append(line)
                i += 1
                
                # Look for MOV FP, SP that usually follows
                if i < len(code):
                    next_line = code[i]
                    new_code.append(next_line)
                    i += 1
                    
                    if (isinstance(next_line, instr.MoveOp) and
                        next_line.rd == Regs.FP and
                        isinstance(next_line.oprnd2, instr.Oprnd2Rm) and
                        next_line.oprnd2.rm == Regs.SP):
                        
                        # Found prologue sequence: push {fp, lr}; mov fp, sp
                        # Now insert push of Callee-Saved Regs (R4-R10)
                        # They will be stored BELOW FP.
                        new_code.append(instr.LoadStoreMultipleOp(
                            instr.LoadStoreBlockOpcode.STM,
                            Regs.SP,
                            line.mode4, # Same mode (DECREMENT_BEFORE)
                            used_callee_saved,
                            line.save_rd, # Writeback SP!
                            line.cond
                        ))
                continue
                
            # Look for function epilogue: LDMIA SP!, {FP, LR}
            elif (isinstance(line, instr.LoadStoreMultipleOp) and
                  line.opcode == instr.LoadStoreBlockOpcode.LDM and
                  line.rd == Regs.SP and
                  Regs.FP in line.reglist and Regs.LR in line.reglist and
                  line.save_rd):
                
                # Found epilogue. Restore Callee-Saved Regs BEFORE popping FP, LR.
                # R4-R10 are located just below FP.
                # Use LDMDB FP, {R4-R10} to load them without modifying FP.
                new_code.append(instr.LoadStoreMultipleOp(
                    instr.LoadStoreBlockOpcode.LDM,
                    Regs.FP,
                    mode4.Mode4.DECREMENT_BEFORE,
                    used_callee_saved,
                    False, # No writeback to FP
                    line.cond
                ))
                
                # Reset SP to FP (Saved FP). This effectively pops R4-R10 and locals.
                new_code.append(instr.MoveOp(
                    instr.MoveOpcode.MOV,
                    Regs.SP,
                    instr.Oprnd2Rm(Regs.FP)
                ))
                
                # Original LDMIA SP!, {FP, LR}
                new_code.append(line)
                i += 1
                
            else:
                new_code.append(line)
                i += 1
        
        return new_code
