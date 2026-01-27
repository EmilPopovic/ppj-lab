from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Any

import instructions as instr
from util import log
from type import Type
from scope import Symbol, Scope
import opcodes as op
from regs import Regs
import addressing
from size import WordOrByte
from shift import ShiftType
from indexing import IndexingType
from cond import Cond
import math

needs_div = False

def PUSH_REG(reg: int) -> instr.LoadStoreSingleMode2Op:
    return instr.LoadStoreSingleMode2Op(op.StoreSingleOpcode.STR, WordOrByte.WORD, reg, addressing.Mode2ImmediateOffset(Regs.SP, IndexingType.PREINDEX, 4, negate_imm=True))

PUSH = PUSH_REG(Regs.R0)

def POP_REG(reg: int) -> instr.LoadStoreSingleMode2Op:
    return instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, reg, addressing.Mode2ImmediateOffset(Regs.SP, IndexingType.POSTINDEX, 4))
POP = POP_REG(Regs.R0)

def LOAD_WORD(const: int) -> instr.LoadStoreSingleMode2Op:
    return instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R0, addressing.Mode2Immediate(const))

def LOAD_BYTE(const: int) -> instr.LoadStoreSingleMode2Op:
    return instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.BYTE, Regs.R0, addressing.Mode2Immediate(const))

ENTER: List[instr.AssemblyLine] = [
    instr.LoadStoreMultipleOp(op.LoadStoreBlockOpcode.STM, Regs.SP, addressing.Mode4.DECREMENT_BEFORE, [Regs.FP, Regs.LR], True),
    instr.MoveOp(op.MoveOpcode.MOV, Regs.FP, addressing.Oprnd2Rm(Regs.SP))
]

LEAVE: List[instr.AssemblyLine] = [
    instr.MoveOp(op.MoveOpcode.MOV, Regs.SP, addressing.Oprnd2Rm(Regs.FP)),
    instr.LoadStoreMultipleOp(op.LoadStoreBlockOpcode.LDM, Regs.SP, addressing.Mode4.INCREMENT_AFTER, [Regs.FP, Regs.LR], True)
]

RETURN: List[instr.AssemblyLine] = [
    instr.MoveOp(op.MoveOpcode.MOV, Regs.SP, addressing.Oprnd2Rm(Regs.FP)),
    instr.LoadStoreMultipleOp(op.LoadStoreBlockOpcode.LDM, Regs.SP, addressing.Mode4.INCREMENT_AFTER, [Regs.FP, Regs.LR], True),
    instr.MoveOp(op.MoveOpcode.MOV, Regs.PC, addressing.Oprnd2Rm(Regs.LR))
]

def CALL(label: str) -> instr.BranchOp:
    return instr.BranchOp(op.BranchOpcode.BL, label, Cond.ALWAYS)

CMPZ = instr.TestOp(op.TestOpcode.CMP, Regs.R0, addressing.Oprnd2Imm8(0))

class OptimizationVisitor:

    @staticmethod
    def visit_expr(expr: 'Expr') -> 'Expr':
        if isinstance(expr, BinOp):
            expr.left = OptimizationVisitor.visit_expr(expr.left)
            expr.right = OptimizationVisitor.visit_expr(expr.right)
        elif isinstance(expr, UnaryOp):
            expr.operand = OptimizationVisitor.visit_expr(expr.operand)
        elif isinstance(expr, Call):
            expr.args = [OptimizationVisitor.visit_expr(arg) for arg in expr.args]
        elif isinstance(expr, ArrayAccess):
            expr.array = OptimizationVisitor.visit_expr(expr.array)
            expr.index = OptimizationVisitor.visit_expr(expr.index)

        return Program.fold_const(expr.scope, expr)

    @staticmethod
    def visit_stmt(stmt: 'Stmt', loop_stack: List['While']) -> 'Stmt':
        if isinstance(stmt, Block):
            stmt.var_decls = [OptimizationVisitor.visit_var_decl(decl) for decl in stmt.var_decls]
            stmt.stmts = [OptimizationVisitor.visit_stmt(s, loop_stack) for s in stmt.stmts]

        elif isinstance(stmt, If):
            stmt.cond = OptimizationVisitor.visit_expr(stmt.cond)
            stmt.then_branch = OptimizationVisitor.visit_stmt(stmt.then_branch, loop_stack)
            if stmt.else_branch:
                stmt.else_branch = OptimizationVisitor.visit_stmt(stmt.else_branch, loop_stack)

        elif isinstance(stmt, While):
            if stmt.before:
                stmt.before = OptimizationVisitor.visit_stmt(stmt.before, loop_stack)
            if stmt.cond:
                stmt.cond = OptimizationVisitor.visit_expr(stmt.cond)
            loop_stack.append(stmt)
            stmt.body = OptimizationVisitor.visit_stmt(stmt.body, loop_stack)
            loop_stack.pop()
            if stmt.step:
                stmt.step = OptimizationVisitor.visit_stmt(stmt.step, loop_stack)

        elif isinstance(stmt, ExprStmt):
            stmt.expr = OptimizationVisitor.visit_expr(stmt.expr)

        elif isinstance(stmt, Return):
            if stmt.expr:
                stmt.expr = OptimizationVisitor.visit_expr(stmt.expr)

        elif isinstance(stmt, Break):
            if loop_stack:
                stmt.loop = loop_stack[-1]

        elif isinstance(stmt, Continue):
            if loop_stack:
                stmt.loop = loop_stack[-1]

        return stmt

    @staticmethod
    def visit_var_decl(decl: 'VarDecl') -> 'VarDecl':
        if decl.init is None:
            return decl

        if isinstance(decl.init, Expr):
            decl.init = OptimizationVisitor.visit_expr(decl.init)
        elif isinstance(decl.init, list):
            decl.init = [OptimizationVisitor.visit_expr(expr) for expr in decl.init]

        return decl

@dataclass
class ASTNode:
    scope: Scope

class Expr(ASTNode):
    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

@dataclass
class VarDecl(ASTNode):
    sym: Symbol
    vtype: Type
    bytes: int
    init: 'Optional[Expr] | List[Expr]' = None

class Stmt(ASTNode):
    def to_asm(self) -> List[instr.AssemblyLine]:
        return []

@dataclass
class Block(Stmt):
    var_decls: List[VarDecl]
    stmts: List[Stmt]
    nesting_depth: int

    def to_asm(self) -> List[instr.AssemblyLine]:
        code = list(ENTER)

        if self.var_decls:
            offset = 0
            for var_decl in self.var_decls:
                var_decl.sym.frame_offset = offset
                offset += int(math.ceil(var_decl.bytes / 4)) * 4

            # TODO: what if offset can't fit in imm_8
            code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.SP, Regs.SP, addressing.Oprnd2Imm8(offset)))

            for var_decl in self.var_decls:
                if var_decl.init is None:
                    continue
                elif isinstance(var_decl.init, Expr):
                    code.extend(var_decl.init.to_asm())
                    code.append(POP)
                    code.append(instr.LoadStoreSingleMode2Op(op.StoreSingleOpcode.STR, WordOrByte.WORD, Regs.R0, addressing.Mode2ImmediateOffset(Regs.FP, IndexingType.NO_INDEX, offset, negate_imm=True)))
                else:  # array
                    assert isinstance(var_decl.vtype.nested_type, Type)
                    is_byte = var_decl.vtype.nested_type.name == 'char'
                    assert isinstance(var_decl.init, list)

                    elem_offset = var_decl.sym.frame_offset

                    for init in var_decl.init:
                        code.extend(init.to_asm())
                        code.append(POP)
                        code.append(instr.LoadStoreSingleMode2Op(op.StoreSingleOpcode.STR, WordOrByte.BYTE if is_byte else WordOrByte.WORD, Regs.R0, addressing.Mode2ImmediateOffset(Regs.FP, IndexingType.NO_INDEX, elem_offset, negate_imm=True)))
                        elem_offset += 1 if is_byte else 4

        for stmt in self.stmts:
            code.extend(stmt.to_asm())

        code.extend(LEAVE)
        return code

@dataclass
class FuncDef(ASTNode):
    sym: Symbol
    ret_type: Type
    params: List[VarDecl]
    body: Block | Stmt

    def to_asm(self) -> List[instr.AssemblyLine]:
        code: List[instr.AssemblyLine] = [instr.Label(f'f_{self.sym.name}')]
        code.extend(self.body.to_asm())
        code.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.PC, addressing.Oprnd2Rm(Regs.LR)))
        return code

@dataclass
class ConstExpr(Expr):
    pass

@dataclass
class Const(ConstExpr):
    value: int

    def to_asm(self) -> List[instr.AssemblyLine]:
        return [LOAD_WORD(self.value), PUSH]

@dataclass
class ConstStr(ConstExpr):
    value: str

@dataclass
class CharConst(ConstExpr):
    value: int

    def to_asm(self) -> List[instr.AssemblyLine]:
        return [LOAD_BYTE(self.value), PUSH]

@dataclass
class Var(Expr):
    sym: Symbol
    decl_dist: int
    is_global: bool

    def to_asm(self) -> List[instr.AssemblyLine]:
        code: List[instr.AssemblyLine] = []

        assert self.sym.type
        size = WordOrByte.BYTE if self.sym.type.name == 'char' else WordOrByte.WORD
        negate_offset = not self.sym.is_param

        if self.is_global:
            code.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, Regs.R0, addressing.Mode2Label(f'g_{self.sym.name}')))
            code.append(PUSH)
        else:
            assert self.sym.parent is not None
            depth_diff = self.scope.nesting_depth - self.sym.parent.nesting_depth
            if depth_diff == 0:
                code.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, size, Regs.R0, addressing.Mode2ImmediateOffset(Regs.FP, IndexingType.NO_INDEX, self.sym.frame_offset, negate_imm=negate_offset)))
                code.append(PUSH)
            else:
                loop_label = instr.Label()
                code.extend([
                    instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Rm(Regs.FP)),
                    instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R1, addressing.Mode2Immediate(depth_diff)),
                    loop_label,
                    instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R0, addressing.Mode2ImmediateOffset(Regs.R0, IndexingType.NO_INDEX, 4)),
                    instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.R1, Regs.R1, addressing.Oprnd2Imm8(1)),
                    instr.TestOp(op.TestOpcode.CMP, Regs.R1, addressing.Oprnd2Imm8(0)),
                    instr.BranchOp(op.BranchOpcode.B, loop_label.name, Cond.NOT_EQUAL),
                    instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R0, addressing.Mode2ImmediateOffset(Regs.R0, IndexingType.NO_INDEX, self.sym.frame_offset, negate_imm=negate_offset)),
                    PUSH
                ])

        return code

@dataclass
class Program(ASTNode):
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
    def _compare_values(scope: Scope, op: str, left: Any, right: Any) -> Const:
        if op == 'EQ':
            return Const(scope, 1 if left == right else 0)
        elif op == 'NEQ':
            return Const(scope, 1 if left != right else 0)
        elif op == 'LT':
            return Const(scope, 1 if left < right else 0)
        elif op == 'GT':
            return Const(scope, 1 if left > right else 0)
        elif op == 'LE':
            return Const(scope, 1 if left <= right else 0)
        else:  # op == 'GE'
            return Const(scope, 1 if left >= right else 0)

    @staticmethod
    def fold_const(scope: Scope, expr: Expr) -> Expr:
        if isinstance(expr, Const) or isinstance(expr, ConstStr) or isinstance(expr, CharConst):
            return expr

        elif isinstance(expr, Var):
            if expr.sym.type is None or not expr.sym.type.is_const:
                return expr
            elif expr.sym.const_val is not None:
                if expr.sym.type.name == 'int':
                    assert isinstance(expr.sym.const_val, int)
                    return Const(scope, expr.sym.const_val)
                elif expr.sym.type.name == 'char':
                    assert isinstance(expr.sym.const_val, int)
                    return CharConst(scope, expr.sym.const_val)
                elif expr.sym.type.name == 'arr':
                    assert isinstance(expr.sym.const_val, str)
                    return ConstStr(scope, expr.sym.const_val)

        elif isinstance(expr, BinOp):
            left_expr = Program.fold_const(scope, expr.left)
            left_is_const = isinstance(left_expr, Const) or isinstance(left_expr, CharConst) or isinstance(left_expr, ConstStr)

            right_expr = Program.fold_const(scope, expr.right)
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
                return Program._compare_values(scope, expr.op, left_expr.value, right_expr.value)

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
                return Program._compare_values(scope, expr.op, left_val, right_val)

            elif expr.op == 'LOG_AND':
                return Const(scope, 1 if left_val and right_val else 0)
            elif expr.op == 'LOG_OR':
                return Const(scope, 1 if left_val or right_val else 0)

            else:
                return expr

            if is_char_op:
                return CharConst(scope, result)
            else:
                return Const(scope, result)

        elif isinstance(expr, UnaryOp):
            operand_expr = Program.fold_const(scope, expr.operand)
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
                return Const(scope, 1 if not val else 0)
            else:
                return expr

            if is_char:
                return CharConst(scope, result)
            else:
                return Const(scope, result)

        return expr

    def optimize(self) -> 'Program':
        for glob in self.globals:
            OptimizationVisitor.visit_var_decl(glob)

        loop_stack: List[While] = []
        for func in self.functions:
            func.body = OptimizationVisitor.visit_stmt(func.body, loop_stack)

        return self

    def log(self) -> None:
        print_ast(self)

@dataclass
class If(Stmt):
    cond: Expr
    then_branch: Stmt
    else_branch: Optional[Stmt] = None

    def to_asm(self) -> List[instr.AssemblyLine]:
        code = self.cond.to_asm()
        code.append(POP)

        else_label: Optional[instr.Label] = instr.Label() if self.else_branch else None
        end_label: instr.Label = instr.Label()

        code.append(CMPZ)

        branch_if_false_label_name = else_label.name if else_label else end_label.name

        code.append(instr.BranchOp(op.BranchOpcode.B, branch_if_false_label_name, Cond.EQUAL))

        code.extend(self.then_branch.to_asm())

        if else_label and self.else_branch:
            code.append(else_label)
            code.extend(self.else_branch.to_asm())

        code.append(end_label)
        return code

@dataclass
class While(Stmt):
    before: Optional[Stmt]
    cond: Optional[Expr]
    body: Stmt
    step: Optional[Stmt] = None
    exit_label: Optional[instr.Label] = None
    step_label: Optional[instr.Label] = None

    def to_asm(self) -> List[instr.AssemblyLine]:
        code: List[instr.AssemblyLine] = self.before.to_asm() if self.before else []

        loop_label = instr.Label()
        code.append(loop_label)

        self.exit_label = instr.Label()
        self.step_label = instr.Label()

        if self.cond:
            code.extend(self.cond.to_asm())
            code.append(POP)
            code.extend([
                CMPZ,
                instr.BranchOp(op.BranchOpcode.BL, self.exit_label.name, Cond.EQUAL)
            ])

        code.extend(self.body.to_asm())

        code.append(self.step_label)

        if self.step:
            code.extend(self.step.to_asm())

        code.append(instr.BranchOp(op.BranchOpcode.B, loop_label.name, Cond.ALWAYS))
        code.append(self.exit_label)
        return code

@dataclass
class ExprStmt(Stmt):
    expr: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        code = self.expr.to_asm()
        code.append(POP)
        return code

@dataclass
class CtrlFlowStmt(Stmt):
    pass

@dataclass
class Break(CtrlFlowStmt):
    loop: Optional[While] = None

    def to_asm(self) -> List[instr.AssemblyLine]:
        assert self.loop and self.loop.exit_label
        return [instr.BranchOp(op.BranchOpcode.B, self.loop.exit_label.name, Cond.ALWAYS)]

@dataclass
class Continue(CtrlFlowStmt):
    loop: Optional[While] = None

    def to_asm(self) -> List[instr.AssemblyLine]:
        assert self.loop and self.loop.step_label
        return [instr.BranchOp(op.BranchOpcode.B, self.loop.step_label.name, Cond.ALWAYS)]

@dataclass
class Return(CtrlFlowStmt):
    expr: Optional[Expr]

    def to_asm(self) -> List[instr.AssemblyLine]:
        code = self.expr.to_asm() if self.expr else []
        if self.expr:
            code.append(POP)
        code.extend(RETURN)
        return code

@dataclass
class BinOp(Expr):
    op: str
    left: Expr  # Var or ArrayAccess for assignment
    right: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        """
        Stack machine approach for binary operations:

        For ASSIGN:
        1. Evaluate right-hand side (result pushed to stack)
        2. Pop value
        3. Store to left-hand side location (var or array element)
        4. Push the assigned value back (assignment is an expression)
        """
        code: List[instr.AssemblyLine] = []
        if self.op == 'ASSIGN':
            code = self.right.to_asm()
            code.append(POP)

            if isinstance(self.left, Var):
                target = self.left
                assert target.sym.type
                size = WordOrByte.BYTE if target.sym.type.name == 'char' else WordOrByte.WORD
                negate_offset = not target.sym.is_param

                if target.is_global:
                    code.append(instr.LoadStoreSingleMode2Op(op.StoreSingleOpcode.STR, size, Regs.R0, addressing.Mode2Label(f'g_{target.sym.name}')))
                else:
                    assert target.sym.parent is not None
                    depth_diff = self.scope.nesting_depth - target.sym.parent.nesting_depth
                    if depth_diff == 0:
                        code.append(instr.LoadStoreSingleMode2Op(op.StoreSingleOpcode.STR, size, Regs.R0, addressing.Mode2ImmediateOffset(Regs.FP, IndexingType.NO_INDEX, target.sym.frame_offset, negate_imm=negate_offset)))
                    else:
                        loop_label = instr.Label()
                        code.extend([
                            PUSH,
                            instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Rm(Regs.FP)),
                            instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R1, addressing.Mode2Immediate(depth_diff)),
                            loop_label,
                            instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R0, addressing.Mode2ImmediateOffset(Regs.R0, IndexingType.NO_INDEX, 4)),
                            instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.R1, Regs.R1, addressing.Oprnd2Imm8(1)),
                            instr.TestOp(op.TestOpcode.CMP, Regs.R1, addressing.Oprnd2Imm8(0)),
                            instr.BranchOp(op.BranchOpcode.B, loop_label.name, Cond.NOT_EQUAL),
                            POP_REG(Regs.R2),
                            instr.LoadStoreSingleMode2Op(op.StoreSingleOpcode.STR, size, Regs.R2, addressing.Mode2ImmediateOffset(Regs.R0, IndexingType.NO_INDEX, target.sym.frame_offset, negate_imm=negate_offset)),
                            instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Rm(Regs.R2)),
                        ])

            elif isinstance(self.left, ArrayAccess):
                code.append(PUSH)
                code.extend(self.left.addr_asm())
                code.append(POP_REG(Regs.R1))
                code.append(POP_REG(Regs.R2))
                code.append(instr.LoadStoreSingleMode2Op(op.StoreSingleOpcode.STR, self.left.elem_size(), Regs.R2, addressing.Mode2ImmediateOffset(Regs.R1, IndexingType.NO_INDEX, None)))
                code.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Rm(Regs.R2)))

            code.append(PUSH)
            return code

        elif self.op == 'LOG_AND':
            end_label = instr.Label()

            code.extend(self.left.to_asm())
            code.append(POP)
            code.extend([
                CMPZ,
                instr.BranchOp(op.BranchOpcode.B, end_label.name, Cond.EQUAL)
            ])

            code.extend(self.right.to_asm())
            code.append(POP)

            code.extend([
                CMPZ,
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.NOT_EQUAL)
            ])

            code.append(end_label)
            code.append(PUSH)

            return code

        elif self.op == 'LOG_OR':
            end_label = instr.Label()

            code.extend(self.left.to_asm())
            code.append(POP)
            code.extend([
                CMPZ,
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.NOT_EQUAL),
                instr.BranchOp(op.BranchOpcode.B, end_label.name, Cond.NOT_EQUAL)
            ])

            code.extend(self.right.to_asm())
            code.append(POP)

            code.extend([
                CMPZ,
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.NOT_EQUAL)
            ])

            code.append(end_label)
            code.append(PUSH)

            return code

        code.extend(self.left.to_asm())
        code.extend(self.right.to_asm())
        code.extend([POP_REG(Regs.R1), POP])
        
        global needs_div

        if self.op == 'ADD':
            code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.R1)))
        elif self.op == 'SUB':
            code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.R1)))
        elif self.op == 'MUL':
            code.append(instr.MultiplyOp(Regs.R0, Regs.R0, Regs.R1))
        elif self.op == 'DIV':
            code.append(instr.BranchOp(op.BranchOpcode.BL, '_f_divide', Cond.ALWAYS))
            needs_div = True
        elif self.op == 'MOD':
            code.append(instr.BranchOp(op.BranchOpcode.BL, '_f_divide', Cond.ALWAYS))
            code.append(PUSH_REG(Regs.R1))
            needs_div = True
            return code

        elif self.op == 'AND':
            code.append(instr.ArithmeticLogicOp(op.LogicOpcode.AND, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.R1)))
        elif self.op == 'OR':
            code.append(instr.ArithmeticLogicOp(op.LogicOpcode.ORR, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.R1)))
        elif self.op == 'XOR':
            code.append(instr.ArithmeticLogicOp(op.LogicOpcode.EOR, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.R1)))
        
        elif self.op == 'EQ':
            code.extend([
                instr.TestOp(op.TestOpcode.CMP, Regs.R0, addressing.Oprnd2Rm(Regs.R1)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(0)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.EQUAL)
            ])
        elif self.op == 'NEQ':
            code.extend([
                instr.TestOp(op.TestOpcode.CMP, Regs.R0, addressing.Oprnd2Rm(Regs.R1)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(0)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.NOT_EQUAL)
            ])
        elif self.op == 'LT':
            code.extend([
                instr.TestOp(op.TestOpcode.CMP, Regs.R0, addressing.Oprnd2Rm(Regs.R1)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(0)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.SIGNED_LESS_THAN)
            ])
        elif self.op == 'GT':
            code.extend([
                instr.TestOp(op.TestOpcode.CMP, Regs.R0, addressing.Oprnd2Rm(Regs.R1)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(0)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.SIGNED_GREATER_THAN)
            ])
        elif self.op == 'LTE':
            code.extend([
                instr.TestOp(op.TestOpcode.CMP, Regs.R0, addressing.Oprnd2Rm(Regs.R1)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(0)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.SIGNED_LESS_OR_EQUAL)
            ])
        elif self.op == 'GTE':
            code.extend([
                instr.TestOp(op.TestOpcode.CMP, Regs.R0, addressing.Oprnd2Rm(Regs.R1)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(0)),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.SIGNED_GREATER_OR_EQUAL)
            ])

        code.append(PUSH)
        return code

@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr

    def to_asm(self) -> List[instr.AssemblyLine]:
        code: List[instr.AssemblyLine] = [POP]

        if self.op == 'PLUS':
            return []
        elif self.op == 'NEG':
            code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.RSB, Regs.R0, Regs.R0, addressing.Oprnd2Imm8(0)))
        elif self.op == 'BITNOT':
            code.append(instr.MoveOp(op.MoveOpcode.MVN, Regs.R0, addressing.Oprnd2Rm(Regs.R0)))
        elif self.op == 'LOGNOT':
            code.extend([
                CMPZ,
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(0), Cond.NOT_EQUAL),
                instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Imm8(1), Cond.EQUAL)
            ])
        # TODO prefix and postfix are not correct
        elif self.op in ('PREFIX_INC', 'POSTFIX_INC'):
            code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.R0, Regs.R0, addressing.Oprnd2Imm8(1)))
        elif self.op in ('POSTFIX_DEC', 'POSTFIX_INC'):
            code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.R0, Regs.R0, addressing.Oprnd2Imm8(1)))

        code.append(PUSH)
        return code

@dataclass
class Call(Expr):
    name: str
    args: List[Expr]

    def to_asm(self) -> List[instr.AssemblyLine]:
        code = []
        for arg in self.args[::-1]:
            code.extend(arg.to_asm())

        code.append(instr.BranchOp(op.BranchOpcode.BL, f'f_{self.name}', Cond.ALWAYS))
        if self.args:
            code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.SP, Regs.SP, addressing.Oprnd2Imm8(len(self.args) * 4)))
        code.append(PUSH)

        return code

@dataclass
class ArrayAccess(Expr):
    array: Expr
    index: Expr

    def elem_size(self) -> WordOrByte:
        assert isinstance(self.array, Var)
        assert self.array.sym.type and isinstance(self.array.sym.type.nested_type, Type)
        return WordOrByte.BYTE if self.array.sym.type.nested_type.name == 'char' else WordOrByte.WORD

    def addr_asm(self) -> List[instr.AssemblyLine]:
        """Pushes the address of the element onto the stack."""
        assert isinstance(self.array, Var)
        target = self.array
        code: List[instr.AssemblyLine] = self.index.to_asm()
        code.append(POP)

        elem_bytes = 1 if self.elem_size() == WordOrByte.BYTE else 4
        if elem_bytes == 4:
            code.append(instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2ShiftImm5(Regs.R0, ShiftType.LSL, 2)))

        if target.is_global:
            code.extend([
                instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R1, addressing.Mode2Label(f'g_{target.sym.name}')),
                instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.R1)),
            ])
        else:
            assert target.sym.parent is not None
            negate_offset = not target.sym.is_param
            depth_diff = self.scope.nesting_depth - target.sym.parent.nesting_depth
            if depth_diff == 0:
                if negate_offset:
                    code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.RSB, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.FP)))
                    code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.R0, Regs.R0, addressing.Oprnd2Imm8(target.sym.frame_offset)))
                else:
                    code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.R0, Regs.R0, addressing.Oprnd2Rm(Regs.FP)))
                    code.append(instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.R0, Regs.R0, addressing.Oprnd2Imm8(target.sym.frame_offset)))
            else:
                loop_label = instr.Label()
                code.extend([
                    PUSH,
                    instr.MoveOp(op.MoveOpcode.MOV, Regs.R0, addressing.Oprnd2Rm(Regs.FP)),
                    instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R1, addressing.Mode2Immediate(depth_diff)),
                    loop_label,
                    instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.R0, addressing.Mode2ImmediateOffset(Regs.R0, IndexingType.NO_INDEX, 4)),
                    instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.R1, Regs.R1, addressing.Oprnd2Imm8(1)),
                    instr.TestOp(op.TestOpcode.CMP, Regs.R1, addressing.Oprnd2Imm8(0)),
                    instr.BranchOp(op.BranchOpcode.B, loop_label.name, Cond.NOT_EQUAL),
                    POP_REG(Regs.R1),
                ])
                if negate_offset:
                    code.extend([
                        instr.ArithmeticLogicOp(op.ArithmeticOpcode.RSB, Regs.R1, Regs.R1, addressing.Oprnd2Rm(Regs.R0)),
                        instr.ArithmeticLogicOp(op.ArithmeticOpcode.SUB, Regs.R0, Regs.R1, addressing.Oprnd2Imm8(target.sym.frame_offset)),
                    ])
                else:
                    code.extend([
                        instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.R1, Regs.R1, addressing.Oprnd2Rm(Regs.R0)),
                        instr.ArithmeticLogicOp(op.ArithmeticOpcode.ADD, Regs.R0, Regs.R1, addressing.Oprnd2Imm8(target.sym.frame_offset)),
                    ])

        code.append(PUSH)
        return code

    def to_asm(self) -> List[instr.AssemblyLine]:
        code = self.addr_asm()
        code.append(POP)
        code.append(instr.LoadStoreSingleMode2Op(op.LoadSingleOpcode.LDR, self.elem_size(), Regs.R0, addressing.Mode2ImmediateOffset(Regs.R0, IndexingType.NO_INDEX, None)))
        code.append(PUSH)
        return code

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
