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
    ret_type: str
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
