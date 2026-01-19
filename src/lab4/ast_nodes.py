from dataclasses import dataclass
from typing import List, Optional, Any

from addressing import oprnd2
from addressing import mode4, mode2
from util import log
from type import Type
from scope import Symbol, Scope
from size import WordOrByte
import opcodes as op
import instructions as instr
from addressing.oprnd2 import Oprnd2, Oprnd2Imm8, Oprnd2Rm
from cond import Cond
from regs import Regs

next_vreg = 0
needs_div = False

class Expr:
    vreg: int

    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

@dataclass
class VarDecl:
    sym: Symbol
    vtype: Type
    bytes: int
    init: 'Optional[Expr] | List[Expr]' = None

class Stmt:
    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

@dataclass
class Block(Stmt):
    var_decls: List[VarDecl]
    stmts: List[Stmt]

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm = []
        for stmt in self.stmts:
            asm.extend(stmt.to_asm())
        return asm

@dataclass
class FuncDef:
    sym: Symbol
    ret_type: Type
    params: List[VarDecl]
    body: Block

    def enter(self) -> List[instr.AssemblyLine]:
        f_sym = self.sym
        code: List[instr.AssemblyLine] = [instr.Label(f'f_{f_sym.name}')]
        code.append(instr.LoadStoreMultipleOp(instr.LoadStoreBlockOpcode.STM, Regs.SP, mode4.Mode4.DECREMENT_BEFORE, [Regs.FP, Regs.LR], True))
        code.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.FP, oprnd2.Oprnd2Rm(Regs.SP)))
        code.append(instr.Comment(f'Entered {f_sym.name}'))
        return code
    
    def leave(self) -> List[instr.AssemblyLine]:
        f_sym = self.sym
        code: List[instr.AssemblyLine] = [instr.Comment(f'Leaving {f_sym.name}')]
        code.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.PC, oprnd2.Oprnd2Rm(Regs.LR)))
        return code

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm = []

        global next_vreg
        next_vreg = 0

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

@dataclass
class ConstStr(ConstExpr):
    value: str

@dataclass
class CharConst(ConstExpr):
    value: int

@dataclass
class Var(Expr):
    sym: Symbol

@dataclass
class Program:
    functions: List[FuncDef]
    globals: List[VarDecl]

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

            if left_is_const:
                expr.left = left_expr
                return expr

            if right_is_const:
                expr.right = right_expr
                return expr

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
            if glob.init is None:
                continue

            if isinstance(glob.init, Expr):
                glob.init = Program.fold_const(glob.init)
            else:
                for val in glob.init:
                    val = Program.fold_const(val)

        for func in self.functions:
            func.body

        return self

    def log(self) -> None:
        print_ast(self)

@dataclass
class If(Stmt):
    cond: Expr
    then_branch: Stmt
    else_branch: Optional[Stmt] = None

    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

@dataclass
class While(Stmt):
    before: Optional[Stmt]
    cond: Optional[Expr]
    body: Stmt

    def to_asm(self) -> List[instr.AssemblyLine]:
        label_loop = instr.Label()
        label_exit = instr.Label()

        asm: List[instr.AssemblyLine] = [label_loop]

        if self.before is not None:
            asm.extend(self.before.to_asm())

        if self.cond is not None:
            asm.extend(self.cond.to_asm())

        asm.extend(self.body.to_asm())

        asm.append(instr.BranchOp(op.BranchOpcode.B, label_loop.name, Cond.ALWAYS))
        asm.append(label_exit)

        return asm

@dataclass
class ExprStmt(Stmt):
    expr: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

@dataclass
class CtrlFlowStmt(Stmt):
    pass

@dataclass
class Break(CtrlFlowStmt):
    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

@dataclass
class Continue(CtrlFlowStmt):
    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

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
                if isinstance(self.expr, Var) and Scope.root_scope.get_symbol(self.expr.sym.name) is not None:
                    sym = Scope.root_scope.get_symbol(self.expr.sym.name)

                    assert sym is not None
                    assert sym.type is not None

                    size = WordOrByte.WORD
                    if sym.type.name == 'char':
                        size = WordOrByte.BYTE

                    asm.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, Regs.R0, mode2.Mode2Label(f'g_{sym.name}')))
                else:
                    asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Rm(self.expr.vreg)))

        asm.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.SP, oprnd2.Oprnd2Rm(Regs.FP)))
        asm.append(instr.LoadStoreMultipleOp(instr.LoadStoreBlockOpcode.LDM, Regs.SP, mode4.Mode4.INCREMENT_AFTER, [Regs.FP, Regs.LR], True))
        asm.append(instr.MoveOp(instr.MoveOpcode.MOV, Regs.PC, oprnd2.Oprnd2Rm(Regs.LR)))

        return asm

@dataclass
class BinOp(Expr):
    op: str
    left: Expr  # Var or ArrayAccess for assignment
    right: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm = self.left.to_asm()
        asm.extend(self.right.to_asm())

        global needs_div
        global next_vreg

        self.vreg = next_vreg
        next_vreg += 2

        if self.op == 'ADD':
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, self.vreg, self.left.vreg, Oprnd2Rm(self.right.vreg)))
        elif self.op == 'SUB':
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, self.vreg, self.left.vreg, Oprnd2Rm(self.right.vreg)))
        elif self.op == 'MUL':
            asm.append(instr.MultiplyOp(self.vreg, self.left.vreg, self.right.vreg))
        elif self.op == 'DIV':
            needs_div = True
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Rm(self.left.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R1, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.BranchOp(op.BranchOpcode.BL, '_f_divide', Cond.ALWAYS))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Rm(Regs.R0)))
        elif self.op == 'MOD':
            needs_div = True
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, Oprnd2Rm(self.left.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R1, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.BranchOp(op.BranchOpcode.BL, '_f_divide', Cond.ALWAYS))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Rm(Regs.R1)))
        elif self.op == 'AND':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.AND, self.vreg, self.left.vreg, Oprnd2Rm(self.right.vreg)))
        elif self.op == 'OR':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.ORR, self.vreg, self.left.vreg, Oprnd2Rm(self.right.vreg)))
        elif self.op == 'XOR':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.EOR, self.vreg, self.left.vreg, Oprnd2Rm(self.right.vreg)))

        elif self.op == 'EQ':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.EQUAL))
        elif self.op == 'NEQ':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.NOT_EQUAL))
        elif self.op == 'LT':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_LESS_THAN))
        elif self.op == 'GT':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_GREATER_THAN))
        elif self.op == 'LE':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_LESS_OR_EQUAL))
        elif self.op == 'GE':
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.SIGNED_GREATER_OR_EQUAL))

        elif self.op == 'LOG_AND':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.AND, self.vreg + 1, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.vreg, Oprnd2Rm(self.vreg + 1)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.NOT_EQUAL))
        elif self.op == 'LOG_OR':
            asm.append(instr.ArithmeticLogicOp(op.LogicOpcode.ORR, self.vreg + 1, self.left.vreg, Oprnd2Rm(self.right.vreg)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(0)))
            asm.append(instr.TestOp(op.TestOpcode.CMP, self.vreg, Oprnd2Rm(self.vreg + 1)))
            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.vreg, Oprnd2Imm8(1), Cond.EQUAL))

        elif self.op == 'ASSIGN':
            assert isinstance(self.left, Var) or  isinstance(self.left, ArrayAccess)

            # TODO: assign na globalnu varijablu
            ...

            asm.append(instr.MoveOp(op.MoveOpcode.MOV, self.left.vreg, Oprnd2Rm(self.right.vreg)))

        return asm


@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm = self.operand.to_asm()

        global next_vreg
        self.vreg = next_vreg
        next_vreg += 1

        if self.op == 'NEG':
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.RSB, self.vreg, self.operand.vreg, oprnd2.Oprnd2Imm8(0)))
        elif self.op in ['POSTFIX_INC', 'PREFIX_INC']:
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, self.vreg, self.vreg, Oprnd2Imm8(1)))
        elif self.op in ['POSTFIX_DEC', 'PREFIX_DEC']:
            asm.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, self.vreg, self.vreg, Oprnd2Imm8(1)))

        return asm


@dataclass
class Call(Expr):
    name: str
    args: List[Expr]

    def optimize(self) -> None:
        for arg in self.args:
            arg = Program.fold_const(arg)

@dataclass
class ArrayAccess(Expr):
    array: Expr
    index: Expr

    def optimize(self) -> None:
        # self.array = Program.fold_const(self.array)
        self.index = Program.fold_const(self.index)

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
