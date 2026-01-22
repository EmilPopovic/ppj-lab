from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Any, Tuple

from addressing import oprnd2
from addressing import mode4, mode2
import indexing
from util import log
from type import Type, FuncSignature
from scope import Symbol, Scope
from size import WordOrByte
import opcodes as op
import instructions as instr
from addressing.oprnd2 import Oprnd2, Oprnd2Imm8, Oprnd2Rm
from cond import Cond
from regs import Regs

next_vreg = 0
needs_div = False
root_scope: Optional[Scope] = None
loop_stack: List[Tuple[str, str]] = [] # (continue_label, break_label)


class ConstantFoldingVisitor:

    @staticmethod
    def visit_expr(expr: 'Expr') -> 'Expr':
        if isinstance(expr, BinOp):
            expr.left = ConstantFoldingVisitor.visit_expr(expr.left)
            expr.right = ConstantFoldingVisitor.visit_expr(expr.right)
        elif isinstance(expr, UnaryOp):
            expr.operand = ConstantFoldingVisitor.visit_expr(expr.operand)
        elif isinstance(expr, Call):
            expr.args = [ConstantFoldingVisitor.visit_expr(arg) for arg in expr.args]
        elif isinstance(expr, ArrayAccess):
            expr.array = ConstantFoldingVisitor.visit_expr(expr.array)
            expr.index = ConstantFoldingVisitor.visit_expr(expr.index)
        
        return Program.fold_const(expr)
    
    @staticmethod
    def visit_stmt(stmt: 'Stmt') -> 'Stmt':
        if isinstance(stmt, Block):
            stmt.var_decls = [ConstantFoldingVisitor.visit_var_decl(decl) for decl in stmt.var_decls]
            stmt.stmts = [ConstantFoldingVisitor.visit_stmt(s) for s in stmt.stmts]
        
        elif isinstance(stmt, If):
            stmt.cond = ConstantFoldingVisitor.visit_expr(stmt.cond)
            stmt.then_branch = ConstantFoldingVisitor.visit_stmt(stmt.then_branch)
            if stmt.else_branch:
                stmt.else_branch = ConstantFoldingVisitor.visit_stmt(stmt.else_branch)
        
        elif isinstance(stmt, While):
            if stmt.before:
                stmt.before = ConstantFoldingVisitor.visit_stmt(stmt.before)
            if stmt.cond:
                stmt.cond = ConstantFoldingVisitor.visit_expr(stmt.cond)
            stmt.body = ConstantFoldingVisitor.visit_stmt(stmt.body)
        
        elif isinstance(stmt, ExprStmt):
            stmt.expr = ConstantFoldingVisitor.visit_expr(stmt.expr)
        
        elif isinstance(stmt, Return):
            if stmt.expr:
                stmt.expr = ConstantFoldingVisitor.visit_expr(stmt.expr)
        
        return stmt
    
    @staticmethod
    def visit_var_decl(decl: VarDecl) -> VarDecl:
        if decl.init is None:
            return decl
        
        if isinstance(decl.init, Expr):
            decl.init = ConstantFoldingVisitor.visit_expr(decl.init)
        elif isinstance(decl.init, list):
            decl.init = [ConstantFoldingVisitor.visit_expr(expr) for expr in decl.init]
        
        return decl

class Expr:
    vreg: int

    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

    def optimize(self) -> None:
        return

@dataclass
class VarDecl:
    sym: Symbol
    vtype: Type
    bytes: int
    init: 'Optional[Expr] | List[Expr]' = None

class Stmt:
    def to_asm(self) -> List[instr.AssemblyLine]:
        return []
    
    def optimize(self) -> None:
        pass

@dataclass
class Block(Stmt):
    var_decls: List[VarDecl]
    stmts: List[Stmt]

    def to_asm(self) -> List[instr.AssemblyLine]:
        global next_vreg
        asm = []
        
        # Calculate stack space needed for local arrays
        stack_offset = 0
        for decl in self.var_decls:
            if decl.vtype.name == 'arr':
                # Local array - allocate on stack
                # Store the stack offset (negative from FP)
                stack_offset += decl.bytes
                decl.sym.stack_offset = -stack_offset
        
        # Allocate stack space if needed
        if stack_offset > 0:
            # Round up to 4-byte alignment
            stack_offset = (stack_offset + 3) & ~3
            asm.append(instr.ArithmeticLogicOp(
                op.ArithmeticOpcode.SUB,
                Regs.SP,
                Regs.SP,
                Oprnd2Imm8(stack_offset) if oprnd2.is_valid_arm_immediate(stack_offset) else Oprnd2Imm8(255)
            ))
            
            # For local arrays, compute their address (FP + offset) and store in a vreg
            # We must process initializations in one pass to assume declaration order for dependencies
            # But all arrays are already allocated on stack. We just need to compute their base address pointers.
            pass

        # Initialize local variables (scalars and arrays) in declaration order
        for decl in self.var_decls:
            if decl.vtype.name == 'arr':
                decl.sym.vreg = next_vreg
                next_vreg += 1
                # Calculate address: FP + stack_offset
                if oprnd2.is_valid_arm_immediate(abs(decl.sym.stack_offset)):
                    asm.append(instr.ArithmeticLogicOp(
                        op.ArithmeticOpcode.SUB,
                        decl.sym.vreg,
                        Regs.FP,
                        Oprnd2Imm8(abs(decl.sym.stack_offset))
                    ))
                else:
                    # Large offset
                    temp_vreg = next_vreg
                    next_vreg += 1
                    asm.append(instr.LoadStoreSingleMode2Op(
                        op.LoadSingleOpcode.LDR,
                        WordOrByte.WORD,
                        temp_vreg,
                        mode2.Mode2Immediate(abs(decl.sym.stack_offset))
                    ))
                    asm.append(instr.ArithmeticLogicOp(
                        op.ArithmeticOpcode.SUB,
                        decl.sym.vreg,
                        Regs.FP,
                        Oprnd2Rm(temp_vreg)
                    ))
                
                # Initialize local array elements if initializer list exists
                if decl.init and isinstance(decl.init, list):
                    elem_size = Type.sizeof(decl.vtype.nested_type)
                    size = WordOrByte.BYTE if elem_size == 1 else WordOrByte.WORD
                    
                    for i, init_expr in enumerate(decl.init):
                        # Evaluate the initialization expression
                        asm.extend(init_expr.to_asm())
                        
                        val_vreg = -1
                        if hasattr(init_expr, 'vreg'):
                            val_vreg = init_expr.vreg
                        elif isinstance(init_expr, (Const, CharConst)):
                            val_vreg = next_vreg
                            next_vreg += 1
                            if oprnd2.is_valid_arm_immediate(init_expr.value):
                                asm.append(instr.MoveOp(op.MoveOpcode.MOV, val_vreg, Oprnd2Imm8(init_expr.value)))
                            else:
                                asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, val_vreg, mode2.Mode2Immediate(init_expr.value)))
                        
                        # Store at array base + offset
                        offset = i * elem_size
                        if abs(offset) < 4096:
                            asm.append(instr.LoadStoreSingleMode2Op(
                                op.StoreSingleOpcode.STR,
                                size,
                                val_vreg,
                                mode2.Mode2ImmediateOffset(decl.sym.vreg, indexing.IndexingType.NO_INDEX, offset)
                            ))
                        else:
                            off_reg = next_vreg
                            next_vreg += 1
                            if oprnd2.is_valid_arm_immediate(offset):
                                asm.append(instr.MoveOp(op.MoveOpcode.MOV, off_reg, Oprnd2Imm8(offset)))
                            else:
                                asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, off_reg, mode2.Mode2Immediate(offset)))
                            
                            asm.append(instr.LoadStoreSingleMode2Op(
                                op.StoreSingleOpcode.STR,
                                size,
                                val_vreg,
                                mode2.Mode2RegisterOffset(decl.sym.vreg, indexing.IndexingType.NO_INDEX, off_reg)
                            ))
                    
                    # Zero-initialize the remaining elements
                    num_elements = decl.bytes // elem_size
                    if len(decl.init) < num_elements:
                        zero_vreg = next_vreg
                        next_vreg += 1
                        asm.append(instr.MoveOp(op.MoveOpcode.MOV, zero_vreg, Oprnd2Imm8(0)))
                        
                        for i in range(len(decl.init), num_elements):
                            offset = i * elem_size
                            if abs(offset) < 4096:
                                asm.append(instr.LoadStoreSingleMode2Op(
                                    op.StoreSingleOpcode.STR,
                                    size,
                                    zero_vreg,
                                    mode2.Mode2ImmediateOffset(decl.sym.vreg, indexing.IndexingType.NO_INDEX, offset)
                                ))
                            else:
                                off_reg = next_vreg
                                next_vreg += 1
                                if oprnd2.is_valid_arm_immediate(offset):
                                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, off_reg, Oprnd2Imm8(offset)))
                                else:
                                    asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, off_reg, mode2.Mode2Immediate(offset)))
                                
                                asm.append(instr.LoadStoreSingleMode2Op(
                                    op.StoreSingleOpcode.STR,
                                    size,
                                    zero_vreg,
                                    mode2.Mode2RegisterOffset(decl.sym.vreg, indexing.IndexingType.NO_INDEX, off_reg)
                                ))
                
                elif decl.init and isinstance(decl.init, ConstStr):
                    # String literal initialization for local char array
                    s_val = decl.init.value
                    
                    # Write characters + null terminator + zero padding up to array size
                    for i in range(decl.bytes):
                        char_val = 0
                        if i < len(s_val):
                            char_val = ord(s_val[i])
                        
                        val_vreg = next_vreg
                        next_vreg += 1
                        asm.append(instr.MoveOp(op.MoveOpcode.MOV, val_vreg, Oprnd2Imm8(char_val)))
                        
                        offset = i
                        if abs(offset) < 4096:
                            asm.append(instr.LoadStoreSingleMode2Op(
                                op.StoreSingleOpcode.STR,
                                WordOrByte.BYTE,
                                val_vreg,
                                mode2.Mode2ImmediateOffset(decl.sym.vreg, indexing.IndexingType.NO_INDEX, offset)
                            ))
                        else:
                            off_reg = next_vreg
                            next_vreg += 1
                            if oprnd2.is_valid_arm_immediate(offset):
                                asm.append(instr.MoveOp(op.MoveOpcode.MOV, off_reg, Oprnd2Imm8(offset)))
                            else:
                                asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, off_reg, mode2.Mode2Immediate(offset)))
                            
                            asm.append(instr.LoadStoreSingleMode2Op(
                                op.StoreSingleOpcode.STR,
                                WordOrByte.BYTE,
                                val_vreg,
                                mode2.Mode2RegisterOffset(decl.sym.vreg, indexing.IndexingType.NO_INDEX, off_reg)
                            ))
            else:
                # Scalar
                # Allocate a vreg for this local variable
                decl.sym.vreg = next_vreg
                next_vreg += 1
                
                if decl.init and isinstance(decl.init, Expr):
                    # Evaluate the initialization expression
                    asm.extend(decl.init.to_asm())
                    
                    # Move the result to the variable's vreg
                    if hasattr(decl.init, 'vreg'):
                        # Expression result is in a vreg
                        asm.append(instr.MoveOp(op.MoveOpcode.MOV, decl.sym.vreg, Oprnd2Rm(decl.init.vreg)))
                    elif isinstance(decl.init, Const):
                        # Constant value
                        if oprnd2.is_valid_arm_immediate(decl.init.value):
                            asm.append(instr.MoveOp(op.MoveOpcode.MOV, decl.sym.vreg, Oprnd2Imm8(decl.init.value)))
                        else:
                            asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, decl.sym.vreg, mode2.Mode2Immediate(decl.init.value)))
                    else:
                        asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, decl.sym.vreg, mode2.Mode2Immediate(decl.init.value)))
                elif isinstance(decl.init, Var):
                    # Variable reference - load from its vreg or from global
                    if hasattr(decl.init.sym, 'vreg'):
                        asm.append(instr.MoveOp(op.MoveOpcode.MOV, decl.sym.vreg, Oprnd2Rm(decl.init.sym.vreg)))
                    else:
                        # Global variable
                        size = WordOrByte.WORD
                        if decl.init.sym.type and decl.init.sym.type.name == 'char':
                            size = WordOrByte.BYTE
                        asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, decl.sym.vreg, mode2.Mode2Label(f'g_{decl.init.sym.name}')))
        
        for stmt in self.stmts:
            asm.extend(stmt.to_asm())
        return asm
    
    def optimize(self) -> None:
        for decl in self.var_decls:
            ConstantFoldingVisitor.visit_var_decl(decl)
        for stmt in self.stmts:
            stmt.optimize()

@dataclass
class FuncDef:
    sym: Symbol
    ret_type: Type
    params: List[VarDecl]
    body: Block | Stmt

    def enter(self) -> List[instr.AssemblyLine]:
        global next_vreg
        
        f_sym = self.sym
        code: List[instr.AssemblyLine] = [instr.Label(f'f_{f_sym.name}')]
        code.append(instr.LoadStoreMultipleOp(instr.LoadStoreBlockOpcode.STM, Regs.SP, mode4.Mode4.DECREMENT_BEFORE, [Regs.FP, Regs.LR], True))
        code.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.FP, oprnd2.Oprnd2Rm(Regs.SP)))
        code.append(instr.Comment(f'Entered {f_sym.name}'))
        
        # Copy parameters from argument registers to vregs to preserve them across calls
        arg_regs = [Regs.R0, Regs.R1, Regs.R2, Regs.R3]
        for i, param in enumerate(self.params):
            if i < 4:
                # Allocate a vreg for the parameter
                param.sym.vreg = next_vreg
                next_vreg += 1
                # Copy from argument register to vreg
                code.append(instr.MoveOp(instr.MoveOpcode.MOV, param.sym.vreg, oprnd2.Oprnd2Rm(arg_regs[i])))
            else:
                # Parameter is passed on stack
                # [FP]: Saved FP
                # [FP+4]: Saved LR
                # [FP+8]: 5th Argument (Index 4)
                # Offset = 8 + (i-4)*4
                offset = 8 + (i-4)*4
                param.sym.stack_offset = offset
        
        return code
    
    def leave(self) -> List[instr.AssemblyLine]:
        f_sym = self.sym
        code: List[instr.AssemblyLine] = [instr.Comment(f'Leaving {f_sym.name}')]
        
        # Standard epilogue even for implicit returns
        code.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.SP, oprnd2.Oprnd2Rm(Regs.FP)))
        code.append(instr.LoadStoreMultipleOp(instr.LoadStoreBlockOpcode.LDM, Regs.SP, mode4.Mode4.INCREMENT_AFTER, [Regs.FP, Regs.LR], True))
        code.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.PC, oprnd2.Oprnd2Rm(Regs.LR)))
        
        return code

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm = []

        global next_vreg
        next_vreg = 16

        asm.extend(self.enter())
        asm.extend(self.body.to_asm())

        last_instr = asm[-1]
        if (
                not (isinstance(last_instr, instr.MoveOp) and asm[-1].rd == Regs.PC)
                or isinstance(last_instr, instr.Comment)
                or isinstance(last_instr, instr.AssemblerDirective)
                or isinstance(last_instr, instr.Label)
        ):
            asm.extend(self.leave())

        return asm

@dataclass
class ConstExpr(Expr):
    pass

@dataclass
class Const(ConstExpr):
    value: int

    def to_asm(self) -> List[instr.AssemblyLine]:
        global next_vreg
        self.vreg = next_vreg
        next_vreg += 1
        
        asm = []
        if oprnd2.is_valid_arm_immediate(self.value):
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(self.value)))
        else:
            asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, self.vreg, mode2.Mode2Immediate(self.value)))
        return asm

@dataclass
class ConstStr(ConstExpr):
    value: str

@dataclass
class CharConst(ConstExpr):
    value: int

    def to_asm(self) -> List[instr.AssemblyLine]:
        global next_vreg
        self.vreg = next_vreg
        next_vreg += 1
        
        asm = []
        if oprnd2.is_valid_arm_immediate(self.value):
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(self.value)))
        else:
            asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, self.vreg, mode2.Mode2Immediate(self.value)))
        return asm

@dataclass
class Var(Expr):
    sym: Symbol
    
    def to_asm(self) -> List[instr.AssemblyLine]:
        if hasattr(self.sym, 'vreg'):
            self.vreg = self.sym.vreg
        return []

@dataclass
class Program:
    functions: List[FuncDef]
    globals: List[VarDecl]
    scope: Optional[Scope] = None

    @staticmethod
    def to_int32(value: int) -> int:
        value = value & 0xffff_ffff
        if value >= 0x8000_0000:
            return value - 0x1_0000_0000
        return value

    @staticmethod
    def to_int8(value: int) -> int:
        value = value & 0xff
        if value >= 0x80:
            return value - 0x100
        return value

    @staticmethod
    def _compare_values(op: str, left: Any, right: Any) -> Const:
        if op == 'EQ':
            return Const(1 if left == right else 0)
        elif op == 'NEQ':
            return Const(1 if left != right else 0)
        elif op == 'LT':
            return Const(1 if left < right else 0)
        elif op == 'GT':
            return Const(1 if left > right else 0)
        elif op == 'LE':
            return Const(1 if left <= right else 0)
        else:  # op == 'GE'
            return Const(1 if left >= right else 0)

    @staticmethod
    def fold_const(expr: Expr) -> Expr:
        if isinstance(expr, Const) or isinstance(expr, ConstStr) or isinstance(expr, CharConst):
            return expr
        
        elif isinstance(expr, Var):
            if expr.sym.type is None or not expr.sym.type.is_const:
                return expr
            elif expr.sym.const_val is not None:
                if expr.sym.type.name == 'int':
                    assert isinstance(expr.sym.const_val, int)
                    return Const(expr.sym.const_val)
                elif expr.sym.type.name == 'char':
                    assert isinstance(expr.sym.const_val, int)
                    return CharConst(expr.sym.const_val)
                elif expr.sym.type.name == 'arr':
                    assert isinstance(expr.sym.const_val, str)
                    return ConstStr(expr.sym.const_val)
            
        elif isinstance(expr, BinOp):
            left_expr = Program.fold_const(expr.left)
            left_is_const = isinstance(left_expr, Const) or isinstance(left_expr, CharConst) or isinstance(left_expr, ConstStr)

            right_expr = Program.fold_const(expr.right)
            right_is_const = isinstance(right_expr, Const) or isinstance(right_expr, CharConst) or isinstance(right_expr, ConstStr)

            expr.left = left_expr
            expr.right = right_expr

            if not left_is_const or not right_is_const:
                return expr

            left_val = None
            right_val = None
            is_char_op = False

            if isinstance(left_expr, Const):
                left_val = left_expr.value
            elif isinstance(left_expr, CharConst):
                left_val = left_expr.value if left_expr.value else 0
                is_char_op = True

            if isinstance(right_expr, Const):
                right_val = right_expr.value
            elif isinstance(right_expr, CharConst):
                right_val = right_expr.value if right_expr.value else 0
                is_char_op = is_char_op and isinstance(right_expr, CharConst)

            if isinstance(left_expr, ConstStr) and isinstance(right_expr, ConstStr):
                return Program._compare_values(expr.op, left_expr.value, right_expr.value)
            
            if left_val is None or right_val is None:
                return expr
            
            wrap = Program.to_int32 if is_char_op else Program.to_int32

            if expr.op == 'ADD':
                result = wrap(left_val + right_val)
            elif expr.op == 'SUB':
                result = wrap(left_val - right_val)
            elif expr.op == 'MUL':
                result = wrap(left_val * right_val)
            elif expr.op == 'DIV':
                if right_val == 0:
                    return expr
                result = left_val // right_val
            elif expr.op == 'MOD':
                if right_val == 0:
                    return expr
                result = left_val % right_val

            elif expr.op == 'AND':
                result = wrap(left_val & right_val)
            elif expr.op == 'OR':
                result = wrap(left_val | right_val)
            elif expr.op == 'XOR':
                result = wrap(left_val ^ right_val)

            elif expr.op in ('EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE'):
                return Program._compare_values(expr.op, left_val, right_val)
            
            elif expr.op == 'LOG_AND':
                return Const(1 if left_val and right_val else 0)
            elif expr.op == 'LOG_OR':
                return Const(1 if left_val or right_val else 0)
            
            else:
                return expr
            
            if is_char_op:
                return CharConst(result)
            else:
                return Const(result)
            
        elif isinstance(expr, UnaryOp):
            operand_expr = Program.fold_const(expr.operand)
            if operand_expr is None:
                return expr
            
            if isinstance(operand_expr, Const):
                val = operand_expr.value
                is_char = False
                wrap = Program.to_int32
            elif isinstance(operand_expr, CharConst):
                val = operand_expr.value if operand_expr.value else 0
                is_char = True
                wrap = Program.to_int8
            else:
                return expr
            
            if expr.op == 'NEG':
                result = wrap(-val)
            elif expr.op == 'PLUS':
                result = wrap(val)
            elif expr.op == 'BITNOT':
                result = wrap(~val)
            elif expr.op == 'LOGNOT':
                return Const(1 if not val else 0)
            else:
                return expr
            
            if is_char:
                return CharConst(result)
            else:
                return Const(result)
        
        return expr
    
    def optimize(self) -> 'Program':
        for glob in self.globals:
            ConstantFoldingVisitor.visit_var_decl(glob)
        
        # Optimize all function bodies
        for func in self.functions:
            func.body = ConstantFoldingVisitor.visit_stmt(func.body)
        
        return self

    def log(self) -> None:
        print_ast(self)

@dataclass
class If(Stmt):
    cond: Expr
    then_branch: Stmt
    else_branch: Optional[Stmt] = None

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm = []
        
        # Evaluate condition
        asm.extend(self.cond.to_asm())
        
        # Generate labels
        label_else = instr.Label()
        label_end = instr.Label()
        
        # Test condition and branch
        if hasattr(self.cond, 'vreg'):
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.cond.vreg, Oprnd2Imm8(0)))
        elif isinstance(self.cond, Const):
            # Constant condition - can optimize
            if self.cond.value == 0:
                # Condition is false, only generate else branch
                if self.else_branch:
                    asm.extend(self.else_branch.to_asm())
                return asm
            else:
                # Condition is true, only generate then branch
                asm.extend(self.then_branch.to_asm())
                return asm
        
        # Branch to else if condition is false (equal to zero)
        if self.else_branch:
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_else.name, Cond.EQUAL))
        else:
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_end.name, Cond.EQUAL))
        
        # Then branch
        asm.extend(self.then_branch.to_asm())
        
        if self.else_branch:
            # Jump over else branch
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_end.name, Cond.ALWAYS))
            
            # Else branch
            asm.append(label_else)
            asm.extend(self.else_branch.to_asm())
        
        # End label
        asm.append(label_end)
        
        return asm

    def optimize(self) -> None:
        self.cond = ConstantFoldingVisitor.visit_expr(self.cond)
        self.then_branch.optimize()
        if self.else_branch:
            self.else_branch.optimize()

@dataclass
class While(Stmt):
    before: Optional[Stmt]
    cond: Optional[Expr]
    body: Stmt
    step: Optional[Stmt] = None

    def to_asm(self) -> List[instr.AssemblyLine]:
        global next_vreg
        global loop_stack
        
        asm: List[instr.AssemblyLine] = []
        
        # For loop: execute 'before' (initialization) once outside the loop
        if self.before is not None:
            asm.extend(self.before.to_asm())
        
        label_loop = instr.Label()
        label_step = instr.Label()
        label_exit = instr.Label()
        
        asm.append(label_loop)
        
        # Check condition
        if self.cond is not None:
            # Evaluate condition
            cond_asm = self.cond.to_asm()
            asm.extend(cond_asm)
            
            # Get condition result into a register
            if hasattr(self.cond, 'vreg'):
                cond_vreg = self.cond.vreg
            else:
                # Shouldn't happen, but handle it
                cond_vreg = next_vreg
                next_vreg += 1
            
            # Compare condition to 0 and branch to exit if false
            asm.append(instr.TestOp(op.TestOpcode.CMP, cond_vreg, Oprnd2Imm8(0)))
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_exit.name, Cond.EQUAL))
        
        # Loop body
        # If we have a step, continue jumps to step label. Otherwise it jumps to loop start.
        continue_target = label_step.name if self.step else label_loop.name
        loop_stack.append((continue_target, label_exit.name))
        
        asm.extend(self.body.to_asm())
        
        loop_stack.pop()
        
        # Step (increment)
        if self.step:
            asm.append(label_step)
            asm.extend(self.step.to_asm())

        # Jump back to loop start
        asm.append(instr.BranchOp(op.BranchOpcode.B, label_loop.name, Cond.ALWAYS))
        asm.append(label_exit)

        return asm
    
    def optimize(self) -> None:
        if self.before:
            self.before.optimize()
        if self.cond:
            self.cond = ConstantFoldingVisitor.visit_expr(self.cond)
        self.body.optimize()
        if self.step:
            self.step.optimize()

@dataclass
class ExprStmt(Stmt):
    expr: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        return self.expr.to_asm()
    
    def optimize(self) -> None:
        """Optimize the expression in the statement."""
        self.expr = ConstantFoldingVisitor.visit_expr(self.expr)

@dataclass
class CtrlFlowStmt(Stmt):
    pass

@dataclass
class Break(CtrlFlowStmt):
    def to_asm(self) -> List[instr.AssemblyLine]:
        global loop_stack
        if loop_stack:
            _, break_label = loop_stack[-1]
            return [instr.BranchOp(op.BranchOpcode.B, break_label, Cond.ALWAYS)]
        return []
    
    def optimize(self) -> None:
        pass

@dataclass
class Continue(CtrlFlowStmt):
    def to_asm(self) -> List[instr.AssemblyLine]:
        global loop_stack
        if loop_stack:
            continue_label, _ = loop_stack[-1]
            return [instr.BranchOp(op.BranchOpcode.B, continue_label, Cond.ALWAYS)]
        return []
    
    def optimize(self) -> None:
        pass

@dataclass
class Return(CtrlFlowStmt):
    expr: Optional[Expr]

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm: List[instr.AssemblyLine]  = []

        if self.expr is not None:
            asm.extend(self.expr.to_asm())

            if isinstance(self.expr, Const) or isinstance(self.expr, CharConst):
                if oprnd2.is_valid_arm_immediate(self.expr.value):
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Imm8(self.expr.value)))
                else:
                    size = WordOrByte.WORD
                    if isinstance(self.expr, CharConst):
                        size = WordOrByte.BYTE

                    asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, Regs.R0, mode2.Mode2Immediate(self.expr.value)))
            else:
                if isinstance(self.expr, Var):
                    # Check if it's a local/parameter (has vreg) or global
                    if hasattr(self.expr.sym, 'vreg'):
                        asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Rm(self.expr.sym.vreg)))
                    else:
                        # Global variable
                        assert self.expr.sym.type is not None
                        size = WordOrByte.WORD
                        if self.expr.sym.type.name == 'char':
                            size = WordOrByte.BYTE
                        asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, Regs.R0, mode2.Mode2Label(f'g_{self.expr.sym.name}')))
                else:
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Rm(self.expr.vreg)))

        asm.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.SP, oprnd2.Oprnd2Rm(Regs.FP)))
        asm.append(instr.LoadStoreMultipleOp(instr.LoadStoreBlockOpcode.LDM, Regs.SP, mode4.Mode4.INCREMENT_AFTER, [Regs.FP, Regs.LR], True))
        asm.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.PC, oprnd2.Oprnd2Rm(Regs.LR)))

        return asm
    
    def optimize(self) -> None:
        if self.expr:
            self.expr = ConstantFoldingVisitor.visit_expr(self.expr)

@dataclass
class BinOp(Expr):
    op: str
    left: Expr  # Var or ArrayAccess for assignment
    right: Expr

    def _load_var_if_needed(self, expr: Expr, asm: List[instr.AssemblyLine]) -> int:
        global next_vreg
        
        if isinstance(expr, (Const, CharConst)):
            temp_vreg = next_vreg
            next_vreg += 1
            
            if oprnd2.is_valid_arm_immediate(expr.value):
                asm.append(instr.MoveOp(op.MoveOpcode.MOV, temp_vreg, Oprnd2Imm8(expr.value)))
            else:
                size = WordOrByte.WORD
                if isinstance(expr, CharConst):
                    size = WordOrByte.BYTE
                asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, temp_vreg, mode2.Mode2Immediate(expr.value)))
            
            expr.vreg = temp_vreg
            return temp_vreg
        
        if hasattr(expr, 'vreg'):
            return expr.vreg
        
        if isinstance(expr, Var):
            sym = expr.sym
            
            # If variable already has a vreg (local/parameter), use it
            if hasattr(sym, 'vreg'):
                expr.vreg = sym.vreg
                return sym.vreg
            
            # If variable is on stack (e.g. 5th+ parameter)
            if hasattr(sym, 'stack_offset'):
                temp_vreg = next_vreg
                next_vreg += 1
                asm.append(instr.LoadStoreSingleMode2Op(
                    op.LoadSingleOpcode.LDR,
                    WordOrByte.WORD,
                    temp_vreg,
                    mode2.Mode2ImmediateOffset(Regs.FP, mode2.IndexingType.NO_INDEX, sym.stack_offset)
                ))
                expr.vreg = temp_vreg
                return temp_vreg
            
            # Otherwise it's a global - load into a temp vreg
            temp_vreg = next_vreg
            next_vreg += 1
            
            assert sym.type is not None
            size = WordOrByte.WORD
            if sym.type.name == 'char':
                size = WordOrByte.BYTE
            asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, temp_vreg, mode2.Mode2Label(f'g_{sym.name}')))
            
            expr.vreg = temp_vreg
            return temp_vreg
        
        return expr.vreg if hasattr(expr, 'vreg') else 0

    def to_asm(self) -> List[instr.AssemblyLine]:
        global needs_div
        global next_vreg
        
        # Special handling for assignment - don't evaluate left side
        if self.op == 'ASSIGN':
            asm = []
            # Only evaluate the right-hand side
            asm.extend(self.right.to_asm())
            
            # Process assignment
            assert isinstance(self.left, Var) or isinstance(self.left, ArrayAccess)
            
            # Evaluate the right-hand side
            right_vreg = self._load_var_if_needed(self.right, asm)
            
            if isinstance(self.left, Var):
                # Assigning to a variable
                if hasattr(self.left.sym, 'vreg'):
                    # Local variable or parameter - assign to its vreg
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.left.sym.vreg, Oprnd2Rm(right_vreg)))
                    self.vreg = self.left.sym.vreg
                else:
                    # Global variable - store to memory
                    assert self.left.sym.type is not None
                    size = WordOrByte.BYTE if self.left.sym.type.name == 'char' else WordOrByte.WORD
                    
                    # Need to store to g_varname
                    # STR doesn't support label addressing directly, need base register
                    addr_vreg = next_vreg
                    next_vreg += 1
                    asm.append(instr.LoadStoreSingleMode2Op(
                        op.LoadSingleOpcode.LDR,
                        WordOrByte.WORD,
                        addr_vreg,
                        mode2.Mode2Label(f'=g_{self.left.sym.name}')
                    ))
                    asm.append(instr.LoadStoreSingleMode2Op(
                        op.StoreSingleOpcode.STR,
                        size,
                        right_vreg,
                        mode2.Mode2ImmediateOffset(addr_vreg, indexing.IndexingType.NO_INDEX, 0)
                    ))
                    self.vreg = right_vreg
                    
            elif isinstance(self.left, ArrayAccess):
                # Assigning to an array element
                # Need to compute the address and store
                array = self.left.array
                index = self.left.index
                
                assert isinstance(array, Var), "Only simple array variables supported"
                assert array.sym.type is not None
                assert array.sym.type.name == 'arr'
                assert array.sym.type.nested_type is not None
                
                elem_size = Type.sizeof(array.sym.type.nested_type)
                has_stack_offset = hasattr(array.sym, 'stack_offset')
                is_param = hasattr(array.sym, 'vreg') and not has_stack_offset
                
                # Handle constant index (simple case)
                if isinstance(index, Const):
                    offset = index.value * elem_size
                    size = WordOrByte.BYTE if elem_size == 1 else WordOrByte.WORD
                    
                    if has_stack_offset:
                        # Local array on stack - compute address from FP
                        base_vreg = next_vreg
                        next_vreg += 1
                        
                        offset_val = abs(array.sym.stack_offset)
                        if oprnd2.is_valid_arm_immediate(offset_val):
                            asm.append(instr.ArithmeticLogicOp(
                                op.ArithmeticOpcode.SUB,
                                base_vreg,
                                Regs.FP,
                                Oprnd2Imm8(offset_val)
                            ))
                        else:
                            temp_vreg = next_vreg
                            next_vreg += 1
                            asm.append(instr.LoadStoreSingleMode2Op(
                                op.LoadSingleOpcode.LDR,
                                WordOrByte.WORD,
                                temp_vreg,
                                mode2.Mode2Immediate(offset_val)
                            ))
                            asm.append(instr.ArithmeticLogicOp(
                                op.ArithmeticOpcode.SUB,
                                base_vreg,
                                Regs.FP,
                                Oprnd2Rm(temp_vreg)
                            ))
                        
                        # Store to array[index]
                        asm.append(instr.LoadStoreSingleMode2Op(
                            op.StoreSingleOpcode.STR,
                            size,
                            right_vreg,
                            mode2.Mode2ImmediateOffset(base_vreg, indexing.IndexingType.NO_INDEX, offset)
                        ))
                    elif is_param:
                        # Parameter array - use the vreg as base address
                        asm.append(instr.LoadStoreSingleMode2Op(
                            op.StoreSingleOpcode.STR,
                            size,
                            right_vreg,
                            mode2.Mode2ImmediateOffset(array.sym.vreg, indexing.IndexingType.NO_INDEX, offset)
                        ))
                    else:
                        # Global array - load base address first
                        addr_vreg = next_vreg
                        next_vreg += 1
                        asm.append(instr.LoadStoreSingleMode2Op(
                            op.LoadSingleOpcode.LDR,
                            WordOrByte.WORD,
                            addr_vreg,
                            mode2.Mode2Label(f'=g_{array.sym.name}')
                        ))
                        
                        # Store to array[index]
                        asm.append(instr.LoadStoreSingleMode2Op(
                            op.StoreSingleOpcode.STR,
                            size,
                            right_vreg,
                            mode2.Mode2ImmediateOffset(addr_vreg, indexing.IndexingType.NO_INDEX, offset)
                        ))
                else:
                    # Dynamic index - compute offset
                    asm.extend(index.to_asm())
                    index_vreg = self._load_var_if_needed(index, asm)
                    
                    # Calculate offset
                    if elem_size == 1:
                        offset_vreg = index_vreg
                    else:
                        offset_vreg = next_vreg
                        next_vreg += 1
                        elem_size_vreg = next_vreg
                        next_vreg += 1
                        if oprnd2.is_valid_arm_immediate(elem_size):
                            asm.append(instr.MoveOp(op.MoveOpcode.MOV, elem_size_vreg, Oprnd2Imm8(elem_size)))
                        else:
                            asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, elem_size_vreg, mode2.Mode2Immediate(elem_size)))
                        asm.append(instr.MultiplyOp(offset_vreg, index_vreg, elem_size_vreg))
                    
                    if has_stack_offset:
                        # Local array on stack - compute address from FP
                        base_vreg = next_vreg
                        next_vreg += 1
                        
                        offset_val = abs(array.sym.stack_offset)
                        if oprnd2.is_valid_arm_immediate(offset_val):
                            asm.append(instr.ArithmeticLogicOp(
                                op.ArithmeticOpcode.SUB,
                                base_vreg,
                                Regs.FP,
                                Oprnd2Imm8(offset_val)
                            ))
                        else:
                            temp_vreg = next_vreg
                            next_vreg += 1
                            asm.append(instr.LoadStoreSingleMode2Op(
                                op.LoadSingleOpcode.LDR,
                                WordOrByte.WORD,
                                temp_vreg,
                                mode2.Mode2Immediate(offset_val)
                            ))
                            asm.append(instr.ArithmeticLogicOp(
                                op.ArithmeticOpcode.SUB,
                                base_vreg,
                                Regs.FP,
                                Oprnd2Rm(temp_vreg)
                            ))
                        
                        # Add offset to base address
                        addr_vreg = next_vreg
                        next_vreg += 1
                        asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, addr_vreg, base_vreg, Oprnd2Rm(offset_vreg)))
                    elif is_param:
                        # Parameter array - add offset to parameter vreg
                        addr_vreg = next_vreg
                        next_vreg += 1
                        asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, addr_vreg, array.sym.vreg, Oprnd2Rm(offset_vreg)))
                    else:
                        # Global array - load base address then add offset
                        base_vreg = next_vreg
                        next_vreg += 1
                        asm.append(instr.LoadStoreSingleMode2Op(
                            op.LoadSingleOpcode.LDR,
                            WordOrByte.WORD,
                            base_vreg,
                            mode2.Mode2Label(f'=g_{array.sym.name}')
                        ))
                        
                        # Compute final address
                        addr_vreg = next_vreg
                        next_vreg += 1
                        asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, addr_vreg, base_vreg, Oprnd2Rm(offset_vreg)))
                    
                    # Store to computed address
                    size = WordOrByte.BYTE if elem_size == 1 else WordOrByte.WORD
                    asm.append(instr.LoadStoreSingleMode2Op(
                        op.StoreSingleOpcode.STR,
                        size,
                        right_vreg,
                        mode2.Mode2ImmediateOffset(addr_vreg, indexing.IndexingType.NO_INDEX, 0)
                    ))
                
                self.vreg = right_vreg
            
            return asm
        
        # Handle short-circuit logical operations separately
        if self.op == 'LOG_AND':
            # For AND: if left is false, skip right side
            asm = self.left.to_asm()
            left_vreg = self._load_var_if_needed(self.left, asm)
            
            self.vreg = next_vreg
            next_vreg += 1
            
            # Generate unique labels
            label_false = instr.Label()
            label_end = instr.Label()
            
            # Check if left is false (0)
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Imm8(0)))
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_false.name, Cond.EQUAL))
            
            # Left is true, evaluate right
            asm.extend(self.right.to_asm())
            right_vreg = self._load_var_if_needed(self.right, asm)
            
            # Result is right side (converted to boolean)
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, right_vreg, Oprnd2Imm8(0)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.NOT_EQUAL))
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_end.name, Cond.ALWAYS))
            
            # Left was false, result is false
            asm.append(label_false)
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            
            asm.append(label_end)
            return asm
            
        elif self.op == 'LOG_OR':
            # For OR: if left is true, skip right side
            asm = self.left.to_asm()
            left_vreg = self._load_var_if_needed(self.left, asm)
            
            self.vreg = next_vreg
            next_vreg += 1
            
            # Generate unique labels
            label_true = instr.Label()
            label_end = instr.Label()
            
            # Check if left is true (non-zero)
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Imm8(0)))
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_true.name, Cond.NOT_EQUAL))
            
            # Left is false, evaluate right
            asm.extend(self.right.to_asm())
            right_vreg = self._load_var_if_needed(self.right, asm)
            
            # Result is right side (converted to boolean)
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, right_vreg, Oprnd2Imm8(0)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.NOT_EQUAL))
            asm.append(instr.BranchOp(op.BranchOpcode.B, label_end.name, Cond.ALWAYS))
            
            # Left was true, result is true
            asm.append(label_true)
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1)))
            
            asm.append(label_end)
            return asm
        
        # Normal operations
        asm = self.left.to_asm()
        asm.extend(self.right.to_asm())

        self.vreg = next_vreg
        next_vreg += 2
        
        left_vreg = self._load_var_if_needed(self.left, asm)
        right_vreg = self._load_var_if_needed(self.right, asm)

        if self.op == 'ADD':
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, self.vreg, left_vreg, Oprnd2Rm(right_vreg)))
        elif self.op == 'SUB':
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, self.vreg, left_vreg, Oprnd2Rm(right_vreg)))
        elif self.op == 'MUL':
            asm.append(instr.MultiplyOp(self.vreg, left_vreg, right_vreg))
        elif self.op == 'DIV':
            needs_div = True
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Rm(left_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R1, Oprnd2Rm(right_vreg)))
            asm.append(instr.BranchOp(op.BranchOpcode.BL, '_f_divide', Cond.ALWAYS))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Rm(Regs.R0)))
        elif self.op == 'MOD':
            needs_div = True
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Rm(left_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R1, Oprnd2Rm(right_vreg)))
            asm.append(instr.BranchOp(op.BranchOpcode.BL, '_f_divide', Cond.ALWAYS))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Rm(Regs.R1)))
        elif self.op == 'AND':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.AND, self.vreg, left_vreg, Oprnd2Rm(right_vreg)))
        elif self.op == 'OR':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.ORR, self.vreg, left_vreg, Oprnd2Rm(right_vreg)))
        elif self.op == 'XOR':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.EOR, self.vreg, left_vreg, Oprnd2Rm(right_vreg)))

        elif self.op == 'EQ':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Rm(right_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.EQUAL))
        elif self.op == 'NEQ':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Rm(right_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.NOT_EQUAL))
        elif self.op == 'LT':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Rm(right_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_LESS_THAN))
        elif self.op == 'GT':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Rm(right_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_GREATER_THAN))
        elif self.op == 'LE' or self.op == 'LTE':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Rm(right_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_LESS_OR_EQUAL))
        elif self.op == 'GE' or self.op == 'GTE':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, left_vreg, Oprnd2Rm(right_vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_GREATER_OR_EQUAL))

        return asm

@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        global next_vreg
        asm = []
        
        if self.op == 'PLUS':
            asm.extend(self.operand.to_asm())
            self.vreg = self._load_var_if_needed(self.operand, asm)
        elif self.op == 'NEG':
            # Negation: 0 - operand
            asm.extend(self.operand.to_asm())
            operand_vreg = self._load_var_if_needed(self.operand, asm)
            
            self.vreg = next_vreg
            next_vreg += 1
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.RSB, self.vreg, operand_vreg, oprnd2.Oprnd2Imm8(0)))
            
        elif self.op == 'BITNOT':
            # Bitwise NOT: ~operand == MVN rd, operand
            asm.extend(self.operand.to_asm())
            operand_vreg = self._load_var_if_needed(self.operand, asm)
            
            self.vreg = next_vreg
            next_vreg += 1
            asm.append(instr.MoveOp(op.MoveOpcode.MVN, self.vreg, oprnd2.Oprnd2Rm(operand_vreg)))
        
        elif self.op == 'LOGNOT':
            # Logical NOT: !operand -> (operand == 0 ? 1 : 0)
            asm.extend(self.operand.to_asm())
            operand_vreg = self._load_var_if_needed(self.operand, asm)
            
            self.vreg = next_vreg
            next_vreg += 1
            
            # Compare with 0
            asm.append(instr.TestOp(op.TestOpcode.CMP, operand_vreg, oprnd2.Oprnd2Imm8(0)))
            # If equal (was 0), result is 1. If not equal (was non-zero), result is 0.
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, oprnd2.Oprnd2Imm8(0)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, oprnd2.Oprnd2Imm8(1), Cond.EQUAL))
            
        elif self.op in ['POSTFIX_INC', 'PREFIX_INC', 'POSTFIX_DEC', 'PREFIX_DEC']:
            # Increment/decrement operations
            # Need to modify the variable in place
            assert isinstance(self.operand, Var), "Can only increment/decrement variables"
            
            # Load current value
            asm.extend(self.operand.to_asm())
            var_vreg = self._load_var_if_needed(self.operand, asm)
            
            # For postfix, save old value to return it
            if self.op in ['POSTFIX_INC', 'POSTFIX_DEC']:
                old_value_vreg = next_vreg
                next_vreg += 1
                asm.append(instr.MoveOp(op.MoveOpcode.MOV, old_value_vreg, Oprnd2Rm(var_vreg)))
            
            # Compute new value (increment/decrement the variable's vreg directly for locals)
            if hasattr(self.operand.sym, 'vreg'):
                # Local variable or parameter - modify in place
                if self.op in ['POSTFIX_INC', 'PREFIX_INC']:
                    asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, self.operand.sym.vreg, self.operand.sym.vreg, Oprnd2Imm8(1)))
                else:
                    asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, self.operand.sym.vreg, self.operand.sym.vreg, Oprnd2Imm8(1)))
                
                # For prefix operations, result is the modified vreg
                if self.op in ['PREFIX_INC', 'PREFIX_DEC']:
                    self.vreg = self.operand.sym.vreg
                else:
                    self.vreg = old_value_vreg
            else:
                # Global variable - need to load, modify, and store back
                new_value_vreg = next_vreg
                next_vreg += 1
                
                if self.op in ['POSTFIX_INC', 'PREFIX_INC']:
                    asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, new_value_vreg, var_vreg, Oprnd2Imm8(1)))
                else:
                    asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, new_value_vreg, var_vreg, Oprnd2Imm8(1)))
                
                assert self.operand.sym.type is not None
                size = WordOrByte.BYTE if self.operand.sym.type.name == 'char' else WordOrByte.WORD
                
                addr_vreg = next_vreg
                next_vreg += 1
                asm.append(instr.LoadStoreSingleMode2Op(
                    op.LoadSingleOpcode.LDR,
                    WordOrByte.WORD,
                    addr_vreg,
                    mode2.Mode2Label(f'=g_{self.operand.sym.name}')
                ))
                asm.append(instr.LoadStoreSingleMode2Op(
                    op.StoreSingleOpcode.STR,
                    size,
                    new_value_vreg,
                    mode2.Mode2ImmediateOffset(addr_vreg, indexing.IndexingType.NO_INDEX, 0)
                ))
                
                # For prefix operations, result is new value; for postfix, result is old value
                if self.op in ['PREFIX_INC', 'PREFIX_DEC']:
                    self.vreg = new_value_vreg
                else:
                    self.vreg = old_value_vreg

        return asm
    
    def _load_var_if_needed(self, expr: Expr, asm: List[instr.AssemblyLine]) -> int:
        """Helper to load a variable if it's not already in a vreg"""
        global next_vreg
        
        if hasattr(expr, 'vreg'):
            return expr.vreg
        
        if isinstance(expr, Var):
            sym = expr.sym
            if hasattr(sym, 'vreg'):
                expr.vreg = sym.vreg
                return sym.vreg
            
            # Global variable - load it
            temp_vreg = next_vreg
            next_vreg += 1
            
            assert sym.type is not None
            size = WordOrByte.WORD
            if sym.type.name == 'char':
                size = WordOrByte.BYTE
            asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, temp_vreg, mode2.Mode2Label(f'g_{sym.name}')))
            
            expr.vreg = temp_vreg
            return temp_vreg
        
        return expr.vreg if hasattr(expr, 'vreg') else 0

    def optimize(self) -> None:
        self.operand = ConstantFoldingVisitor.visit_expr(self.operand)

@dataclass
class Call(Expr):
    name: str
    args: List[Expr]

    def to_asm(self) -> List[instr.AssemblyLine]:
        global next_vreg, root_scope
        
        asm: List[instr.AssemblyLine] = []
        
        arg_regs = [Regs.R0, Regs.R1, Regs.R2, Regs.R3]
        
        # 1. Expand arguments (evaluate expressions)
        # We need to evaluate all arguments before putting them in registers/stack
        # to avoid register clobbering if expression evaluation is complex.
        # But for now, let's stick to simple evaluation order.
        
        # Handle stack arguments (index >= 4) in REVERSE order
        stack_args = [arg for i, arg in enumerate(self.args) if i >= 4]
        stack_args_count = len(stack_args)
        
        for arg in reversed(stack_args):
            asm.extend(arg.to_asm())
            # Push argument to stack
            # Load into temp vreg if not already
            vreg = 0
            if isinstance(arg, (Const, CharConst)):
                vreg = next_vreg
                next_vreg += 1
                if oprnd2.is_valid_arm_immediate(arg.value):
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, vreg, Oprnd2Imm8(arg.value)))
                else:
                    asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, vreg, mode2.Mode2Immediate(arg.value)))
            elif hasattr(arg, 'vreg'):
                vreg = arg.vreg
            
            # Push vreg
            asm.append(instr.LoadStoreSingleMode2Op(
                op.StoreSingleOpcode.STR,
                WordOrByte.WORD,
                vreg,
                mode2.Mode2ImmediateOffset(Regs.SP, mode2.IndexingType.PREINDEX, -4)
            ))
            
        # Handle register arguments (0-3)
        for i, arg in enumerate(self.args):
            if i >= 4:
                break
            
            asm.extend(arg.to_asm())
            
            if isinstance(arg, (Const, CharConst)):
                if oprnd2.is_valid_arm_immediate(arg.value):
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, arg_regs[i], Oprnd2Imm8(arg.value)))
                else:
                    size = WordOrByte.WORD
                    if isinstance(arg, CharConst):
                        size = WordOrByte.BYTE
                    asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, arg_regs[i], mode2.Mode2Immediate(arg.value)))
            else:
                # Non-const argument - move from its vreg
                if hasattr(arg, 'vreg'):
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, arg_regs[i], Oprnd2Rm(arg.vreg)))
        
        asm.append(instr.BranchOp(op.BranchOpcode.BL, f'f_{self.name}', Cond.ALWAYS))
        
        # Clean up stack arguments
        if stack_args_count > 0:
            asm.append(instr.ArithmeticLogicOp(
                op.ArithmeticOpcode.ADD,
                Regs.SP,
                Regs.SP,
                Oprnd2Imm8(stack_args_count * 4)
            ))
        
        # Only capture return value if function returns non-void
        if root_scope:
            func_sym = root_scope.get_symbol(self.name)
            if func_sym and hasattr(func_sym, 'type') and isinstance(func_sym.type.nested_type, FuncSignature):
                ret_type = func_sym.type.nested_type.return_type
                if ret_type.name != 'void':
                    self.vreg = next_vreg
                    next_vreg += 1
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Rm(Regs.R0)))
        
        return asm

    def optimize(self) -> None:
        self.args = [ConstantFoldingVisitor.visit_expr(arg) for arg in self.args]

@dataclass
class ArrayAccess(Expr):
    array: Expr
    index: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        global next_vreg
        asm = []

        # Generate code for index expression
        asm.extend(self.index.to_asm())
        
        # Resolve index vreg
        index_vreg = -1
        if hasattr(self.index, 'vreg'):
            index_vreg = self.index.vreg
        
        # Determine element size
        assert isinstance(self.array, Var)
        assert self.array.sym.type is not None
        assert self.array.sym.type.name == 'arr'
        assert self.array.sym.type.nested_type is not None
        elem_size = Type.sizeof(self.array.sym.type.nested_type)
        
        # Calculate Base Address into base_vreg
        base_vreg = next_vreg
        next_vreg += 1
        
        # 1. Base Address Resolution
        if hasattr(self.array.sym, 'stack_offset'):
            offset = self.array.sym.stack_offset
            if offset > 0:
                # Parameter on Stack -> Load Pointer from [FP + offset]
                if abs(offset) < 4096:
                    asm.append(instr.LoadStoreSingleMode2Op(
                        op.LoadSingleOpcode.LDR,
                        WordOrByte.WORD,
                        base_vreg,
                        mode2.Mode2ImmediateOffset(Regs.FP, indexing.IndexingType.NO_INDEX, offset)
                    ))
                else:
                    # Large offset
                    off_reg = next_vreg
                    next_vreg += 1
                    asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, off_reg, mode2.Mode2Immediate(offset)))
                    asm.append(instr.LoadStoreSingleMode2Op(
                        op.LoadSingleOpcode.LDR,
                        WordOrByte.WORD,
                        base_vreg,
                        mode2.Mode2RegisterOffset(Regs.FP, indexing.IndexingType.NO_INDEX, off_reg)
                    ))
            else:
                # Local Array -> Address is FP - abs(offset)
                offset_val = abs(offset)
                if oprnd2.is_valid_arm_immediate(offset_val):
                    asm.append(instr.ArithmeticLogicOp(
                        op.ArithmeticOpcode.SUB,
                        base_vreg,
                        Regs.FP,
                        Oprnd2Imm8(offset_val)
                    ))
                else:
                    off_reg = next_vreg
                    next_vreg += 1
                    asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, off_reg, mode2.Mode2Immediate(offset_val)))
                    asm.append(instr.ArithmeticLogicOp(
                        op.ArithmeticOpcode.SUB,
                        base_vreg,
                        Regs.FP,
                        Oprnd2Rm(off_reg)
                    ))
        elif hasattr(self.array.sym, 'vreg'):
             # Parameter in Register -> Pointer in vreg
             asm.append(instr.MoveOp(op.MoveOpcode.MOV, base_vreg, Oprnd2Rm(self.array.sym.vreg)))
        else:
             # Global Array -> Load Address
             asm.append(instr.LoadStoreSingleMode2Op(
                op.LoadSingleOpcode.LDR,
                WordOrByte.WORD,
                base_vreg,
                mode2.Mode2Label(f'=g_{self.array.sym.name}')
            ))
            
        # 2. Final Address Calculation (Base + Index*Size)
        self.vreg = next_vreg
        next_vreg += 1
        size = WordOrByte.BYTE if elem_size == 1 else WordOrByte.WORD
        
        # Optimization: Constant Index
        if isinstance(self.index, Const) and abs(self.index.value * elem_size) < 4096:
            total_offset = self.index.value * elem_size
            asm.append(instr.LoadStoreSingleMode2Op(
                op.LoadSingleOpcode.LDR,
                size,
                self.vreg,
                mode2.Mode2ImmediateOffset(base_vreg, indexing.IndexingType.NO_INDEX, total_offset)
            ))
            return asm

        # General case (Dynamic index or Large Constant)
        
        # Handle index value
        final_index_vreg = -1
        if isinstance(self.index, Const):
             final_index_vreg = next_vreg
             next_vreg += 1
             if oprnd2.is_valid_arm_immediate(self.index.value):
                asm.append(instr.MoveOp(op.MoveOpcode.MOV, final_index_vreg, Oprnd2Imm8(self.index.value)))
             else:
                asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, final_index_vreg, mode2.Mode2Immediate(self.index.value)))
        else:
             final_index_vreg = index_vreg
        
        # Calculate offset in bytes
        offset_vreg = final_index_vreg
        if elem_size != 1:
             res_vreg = next_vreg
             next_vreg += 1
             size_reg = next_vreg
             next_vreg += 1
             asm.append(instr.MoveOp(op.MoveOpcode.MOV, size_reg, Oprnd2Imm8(elem_size)))
             asm.append(instr.MultiplyOp(res_vreg, final_index_vreg, size_reg))
             offset_vreg = res_vreg
        
        # LDR [base, offset_vreg]
        asm.append(instr.LoadStoreSingleMode2Op(
             op.LoadSingleOpcode.LDR,
             size,
             self.vreg,
             mode2.Mode2RegisterOffset(base_vreg, indexing.IndexingType.NO_INDEX, offset_vreg)
        ))
        
        return asm

    def optimize(self) -> None:
        self.array = ConstantFoldingVisitor.visit_expr(self.array)
        self.index = ConstantFoldingVisitor.visit_expr(self.index)

def print_ast(node: Any, indent: int = 0) -> None:
    prefix = "  " * indent
    
    if isinstance(node, Program):
        log(f"{prefix}Program")
        if node.globals:
            log(f"{prefix}  Globals:")
            for g in node.globals:
                print_ast(g, indent + 2)
        if node.functions:
            log(f"{prefix}  Functions:")
            for f in node.functions:
                print_ast(f, indent + 2)
    
    elif isinstance(node, FuncDef):
        params_str = ", ".join(f"{p.sym.name}: {p.vtype}" for p in node.params)
        log(f"{prefix}FuncDef: {node.sym.name}({params_str}) -> {node.ret_type}")
        print_ast(node.body, indent + 1)
    
    elif isinstance(node, VarDecl):
        init_str = " = ..." if node.init else ""
        if node.vtype.name == "arr":
            assert isinstance(node.vtype.nested_type, Type)
            log(f"{prefix}VarDecl: {node.sym.name}: {node.vtype}[{node.bytes // Type.sizeof(node.vtype.nested_type)}]{init_str}")
        else:
            log(f"{prefix}VarDecl: {node.sym.name}: {node.vtype}{init_str}")

        if node.init:
            if isinstance(node.init, Expr):
                print_ast(node.init, indent + 1)
            else:
                for i, expr in enumerate(node.init):
                    log(f"{prefix} [{i}]:")
                    print_ast(expr, indent + 2)
    
    elif isinstance(node, Block):
        log(f"{prefix}Block")
        for decl in node.var_decls:
            print_ast(decl, indent + 1)
        for stmt in node.stmts:
            print_ast(stmt, indent + 1)
    
    elif isinstance(node, Return):
        log(f"{prefix}Return")
        if node.expr:
            print_ast(node.expr, indent + 1)

    elif isinstance(node, Continue):
        log(f"{prefix}Continue")

    elif isinstance(node, Break):
        log(f"{prefix}Break")
    
    elif isinstance(node, If):
        log(f"{prefix}If")
        log(f"{prefix}  Condition:")
        print_ast(node.cond, indent + 2)
        log(f"{prefix}  Then:")
        print_ast(node.then_branch, indent + 2)
        if node.else_branch:
            log(f"{prefix}  Else:")
            print_ast(node.else_branch, indent + 2)
    
    elif isinstance(node, While):
        log(f"{prefix}While")
        if node.before:
            log(f"{prefix}  Before")
            print_ast(node.before, indent + 2)
        log(f"{prefix}  Condition:")
        print_ast(node.cond, indent + 2)
        log(f"{prefix}  Body:")
        print_ast(node.body, indent + 2)
    
    elif isinstance(node, ExprStmt):
        log(f"{prefix}ExprStmt")
        print_ast(node.expr, indent + 1)
    
    elif isinstance(node, Const):
        log(f"{prefix}Const: {node.value}")
    
    elif isinstance(node, CharConst):
        log(f"{prefix}CharConst: '{node.value}'")
    
    elif isinstance(node, ConstStr):
        log(f"{prefix}StrConst: '{node.value}'")
    
    elif isinstance(node, Var):
        log(f"{prefix}Var: {node.sym.name}")
    
    elif isinstance(node, BinOp):
        log(f"{prefix}BinOp: {node.op}")
        log(f"{prefix}  Left:")
        print_ast(node.left, indent + 2)
        log(f"{prefix}  Right:")
        print_ast(node.right, indent + 2)
    
    elif isinstance(node, UnaryOp):
        log(f"{prefix}UnaryOp: {node.op}")
        print_ast(node.operand, indent + 1)
    
    elif isinstance(node, Call):
        log(f"{prefix}Call: {node.name}")
        if node.args:
            log(f"{prefix}  Args:")
            for arg in node.args:
                print_ast(arg, indent + 2)
    
    elif isinstance(node, ArrayAccess):
        log(f"{prefix}ArrayAccess")
        log(f"{prefix}  Array:")
        print_ast(node.array, indent + 2)
        log(f"{prefix}  Index:")
        print_ast(node.index, indent + 2)
    
    else:
        log(f"{prefix}{type(node).__name__}: {node}")
