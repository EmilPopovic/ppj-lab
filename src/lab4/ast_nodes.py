from dataclasses import dataclass
from typing import List, Optional, Any

from addressing import oprnd2
from util import log
from type import Type
from scope import Symbol
import opcodes as op
import instructions as instr
from addressing.oprnd2 import Oprnd2, Oprnd2Imm8, Oprnd2Rm
from cond import Cond

next_vreg = 0

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

@dataclass
class Program:
    functions: List[FuncDef]
    globals: List[VarDecl]

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
        return []

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
        return []

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
class BinOp(Expr):
    op: str
    left: Expr  # Var or ArrayAccess for assignment
    right: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        asm = self.left.to_asm()
        asm.extend(self.right.to_asm())

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
        # TODO:
            ...
        elif self.op == 'MOD':
        # TODO:
            ...

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
            ...
        elif self.op in ['POSTFIX_DEC', 'PREFIX_DEC']:
            ...
        
        return asm


@dataclass
class Call(Expr):
    name: str
    args: List[Expr]

@dataclass
class ArrayAccess(Expr):
    array: Expr
    index: Expr

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
