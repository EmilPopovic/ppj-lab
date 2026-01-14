from dataclasses import dataclass
from typing import List, Optional, Any

from type import Type

class Expr: pass

@dataclass
class VarDecl:
    name: str
    vtype: Type
    init: Optional[Expr] = None

class Stmt: pass

@dataclass
class Block(Stmt):
    stmts: List[Stmt]

@dataclass
class FuncDef:
    name: str
    ret_type: Type
    params: List[VarDecl]
    body: Block

@dataclass
class Program:
    functions: List[FuncDef]
    globals: List[VarDecl]

@dataclass
class Return(Stmt):
    expr: Optional[Expr]

@dataclass
class If(Stmt):
    cond: Expr
    then_branch: Stmt
    else_branch: Optional[Stmt] = None

@dataclass
class While(Stmt):
    cond: Expr
    body: Stmt

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class Assign(Stmt):
    target: Expr
    value: Expr

@dataclass
class Const(Expr):
    value: int

@dataclass
class CharConst(Expr):
    value: str

@dataclass
class Var(Expr):
    name: str

@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr

@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr

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
        print(f"{prefix}Program")
        if node.globals:
            print(f"{prefix}  Globals:")
            for g in node.globals:
                print_ast(g, indent + 2)
        if node.functions:
            print(f"{prefix}  Functions:")
            for f in node.functions:
                print_ast(f, indent + 2)
    
    elif isinstance(node, FuncDef):
        params_str = ", ".join(f"{p.name}: {p.vtype}" for p in node.params)
        print(f"{prefix}FuncDef: {node.name}({params_str}) -> {node.ret_type}")
        print_ast(node.body, indent + 1)
    
    elif isinstance(node, VarDecl):
        init_str = " = ..." if node.init else ""
        print(f"{prefix}VarDecl: {node.name}: {node.vtype}{init_str}")
        if node.init:
            print_ast(node.init, indent + 1)
    
    elif isinstance(node, Block):
        print(f"{prefix}Block")
        for stmt in node.stmts:
            print_ast(stmt, indent + 1)
    
    elif isinstance(node, Return):
        print(f"{prefix}Return")
        if node.expr:
            print_ast(node.expr, indent + 1)
    
    elif isinstance(node, If):
        print(f"{prefix}If")
        print(f"{prefix}  Condition:")
        print_ast(node.cond, indent + 2)
        print(f"{prefix}  Then:")
        print_ast(node.then_branch, indent + 2)
        if node.else_branch:
            print(f"{prefix}  Else:")
            print_ast(node.else_branch, indent + 2)
    
    elif isinstance(node, While):
        print(f"{prefix}While")
        print(f"{prefix}  Condition:")
        print_ast(node.cond, indent + 2)
        print(f"{prefix}  Body:")
        print_ast(node.body, indent + 2)
    
    elif isinstance(node, ExprStmt):
        print(f"{prefix}ExprStmt")
        print_ast(node.expr, indent + 1)
    
    elif isinstance(node, Assign):
        print(f"{prefix}Assign")
        print(f"{prefix}  Target:")
        print_ast(node.target, indent + 2)
        print(f"{prefix}  Value:")
        print_ast(node.value, indent + 2)
    
    elif isinstance(node, Const):
        print(f"{prefix}Const: {node.value}")
    
    elif isinstance(node, CharConst):
        print(f"{prefix}CharConst: '{node.value}'")
    
    elif isinstance(node, Var):
        print(f"{prefix}Var: {node.name}")
    
    elif isinstance(node, BinOp):
        print(f"{prefix}BinOp: {node.op}")
        print(f"{prefix}  Left:")
        print_ast(node.left, indent + 2)
        print(f"{prefix}  Right:")
        print_ast(node.right, indent + 2)
    
    elif isinstance(node, UnaryOp):
        print(f"{prefix}UnaryOp: {node.op}")
        print_ast(node.operand, indent + 1)
    
    elif isinstance(node, Call):
        print(f"{prefix}Call: {node.name}")
        if node.args:
            print(f"{prefix}  Args:")
            for arg in node.args:
                print_ast(arg, indent + 2)
    
    elif isinstance(node, ArrayAccess):
        print(f"{prefix}ArrayAccess")
        print(f"{prefix}  Array:")
        print_ast(node.array, indent + 2)
        print(f"{prefix}  Index:")
        print_ast(node.index, indent + 2)
    
    else:
        print(f"{prefix}{type(node).__name__}: {node}")
