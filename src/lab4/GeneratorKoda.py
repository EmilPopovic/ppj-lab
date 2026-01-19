import os
import time
import sys
from typing import List, Any

from util import log
from type import Type
from opcodes import *
from cond import Cond
from addressing import mode2
from addressing import mode3
from addressing import mode4
from addressing import oprnd2
from size import WordOrByte, HalfOrByte
from semantic_analyzer import TreeFactory
import instructions as instr
import ast_nodes as ast
from regs import Regs

OUTPUT_FILENAME = 'a.s'

class CodeGenerator:
    runtime = [
        instr.AssemblerDirective('.text'),
        instr.AssemblerDirective('.global _start'),
        instr.Label('_start'),
        instr.LoadStoreSingleMode2Op(LoadSingleOpcode.LDR, WordOrByte.WORD, Regs.SP, mode2.Mode2Immediate(0x20000)),
        instr.BranchOp(BranchOpcode.BL, 'f_main', Cond.ALWAYS),
        instr.MoveOp(MoveOpcode.MOV, Regs.R6, oprnd2.Oprnd2Rm(Regs.R0)),
        instr.SoftwareInterruptOp(0),
    ]

    def __init__(self, code: List[instr.AssemblyLine]) -> None:
        self.code = code

    def to_file(self, filepath: str) -> None:
        with open(filepath, 'w') as f:
            for instr in self.code:
                f.write(f'{instr}\n')
    
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
    def _compare_values(op: str, left: Any, right: Any) -> ast.Const:
        if op == 'EQ':
            return ast.Const(1 if left == right else 0)
        elif op == 'NEQ':
            return ast.Const(1 if left != right else 0)
        elif op == 'LT':
            return ast.Const(1 if left < right else 0)
        elif op == 'GT':
            return ast.Const(1 if left > right else 0)
        elif op == 'LE':
            return ast.Const(1 if left <= right else 0)
        else:  # op == 'GE'
            return ast.Const(1 if left >= right else 0)
    
    @staticmethod
    def fold_const(expr: ast.Expr) -> ast.Expr:
        if isinstance(expr, ast.Const) or isinstance(expr, ast.ConstStr) or isinstance(expr, ast.CharConst):
            return expr
        
        elif isinstance(expr, ast.Var):
            if expr.sym.type is None or not expr.sym.type.is_const:
                return expr
            elif expr.sym.const_val is not None:
                if expr.sym.type.name == 'int':
                    assert isinstance(expr.sym.const_val, int)
                    return ast.Const(expr.sym.const_val)
                elif expr.sym.type.name == 'char':
                    assert isinstance(expr.sym.const_val, int)
                    return ast.CharConst(expr.sym.const_val)
                elif expr.sym.type.name == 'arr':
                    assert isinstance(expr.sym.const_val, str)
                    return ast.ConstStr(expr.sym.const_val)
            
        elif isinstance(expr, ast.BinOp):
            left_expr = CodeGenerator.fold_const(expr.left)
            if left_expr is None:
                return expr
            right_expr = CodeGenerator.fold_const(expr.right)
            if right_expr is None:
                return expr
            
            left_val = None
            right_val = None
            is_char_op = False

            if isinstance(left_expr, ast.Const):
                left_val = left_expr.value
            elif isinstance(left_expr, ast.CharConst):
                left_val = left_expr.value if left_expr.value else 0
                is_char_op = True

            if isinstance(right_expr, ast.Const):
                right_val = right_expr.value
            elif isinstance(right_expr, ast.CharConst):
                right_val = right_expr.value if right_expr.value else 0
                is_char_op = is_char_op and isinstance(right_expr, ast.CharConst)

            if isinstance(left_expr, ast.ConstStr) and isinstance(right_expr, ast.ConstStr):
                return CodeGenerator._compare_values(expr.op, left_expr.value, right_expr.value)
            
            if left_val is None or right_val is None:
                return expr
            
            wrap = CodeGenerator.to_int32 if is_char_op else CodeGenerator.to_int32

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
                return CodeGenerator._compare_values(expr.op, left_val, right_val)
            
            elif expr.op == 'LOG_AND':
                return ast.Const(1 if left_val and right_val else 0)
            elif expr.op == 'LOG_OR':
                return ast.Const(1 if left_val or right_val else 0)
            
            else:
                return expr
            
            if is_char_op:
                return ast.CharConst(result)
            else:
                return ast.Const(result)
            
        elif isinstance(expr, ast.UnaryOp):
            operand_expr = CodeGenerator.fold_const(expr.operand)
            if operand_expr is None:
                return expr
            
            if isinstance(operand_expr, ast.Const):
                val = operand_expr.value
                is_char = False
                wrap = CodeGenerator.to_int32
            elif isinstance(operand_expr, ast.CharConst):
                val = operand_expr.value if operand_expr.value else 0
                is_char = True
                wrap = CodeGenerator.to_int8
            else:
                return expr
            
            if expr.op == 'NEG':
                result = wrap(-val)
            elif expr.op == 'BITNOT':
                result = wrap(~val)
            elif expr.op == 'LOGNOT':
                return ast.Const(1 if not val else 0)
            else:
                return expr
            
            if is_char:
                return ast.CharConst(result)
            else:
                return ast.Const(result)
        
        return expr
    
    @staticmethod
    def fold_global_var(var: ast.VarDecl) -> List[instr.AssemblyLine]:
        code: List[instr.AssemblyLine] = [instr.Label(f'g_{var.sym.name}')]
        if var.init:
            if isinstance(var.init, ast.Expr):
                val = CodeGenerator.fold_const(var.init)
                
                if isinstance(val, ast.Const):
                    code.append(instr.AssemblerDirective(f'.word {val.value}'))
                    var.sym.const_val = val.value
                elif isinstance(val, ast.CharConst):
                    code.append(instr.AssemblerDirective(f'.byte {val.value}'))
                    var.sym.const_val = val.value
                elif isinstance(val, ast.ConstStr):
                    code.append(instr.AssemblerDirective(f'.string "{val.value}"'))
                    var.sym.const_val = val.value
                else:
                    assert False

                if var.vtype.name == 'arr':
                    assert isinstance(val, ast.ConstStr)
                    code.append(instr.AssemblerDirective(f'.space {var.bytes - len(val.value) - 1}'))

            else:
                for elem_init in var.init:
                    val = CodeGenerator.fold_const(elem_init)
                    
                    if isinstance(val, ast.Const):
                        code.append(instr.AssemblerDirective(f'.word {val.value}'))
                    elif isinstance(val, ast.CharConst):
                        code.append(instr.AssemblerDirective(f'.byte {val.value}'))
                    elif isinstance(val, ast.ConstStr):
                        code.append(instr.AssemblerDirective(f'.string "{val.value}"'))
                    else:
                        assert False

                assert isinstance(var.vtype.nested_type, Type)
                code.append(instr.AssemblerDirective(f'.space {var.bytes - len(var.init) * Type.sizeof(var.vtype.nested_type)}'))

        else:
            code.append(instr.AssemblerDirective(f'.size {var.bytes}'))

        return code
    
    @staticmethod
    def globals_asm(program: ast.Program) -> List[instr.AssemblyLine]:
        code = []
        for glob in program.globals:
            code.extend(CodeGenerator.fold_global_var(glob))
        return code
    
    @staticmethod
    def enter(f: ast.FuncDef) -> List[instr.AssemblyLine]:
        f_sym = f.sym
        code: List[instr.AssemblyLine] = [instr.Label(f'f_{f_sym.name}')]
        code.append(instr.LoadStoreMultipleOp(LoadStoreBlockOpcode.STM, Regs.SP, mode4.Mode4.DECREMENT_BEFORE, [Regs.FP, Regs.LR], True))
        code.append(instr.MoveOp(MoveOpcode.MOV, Regs.FP, oprnd2.Oprnd2Rm(Regs.SP)))
        code.append(instr.Comment(f'Entered {f_sym.name}'))
        return code
    
    @staticmethod
    def leave(f: ast.FuncDef) -> List[instr.AssemblyLine]:
        f_sym = f.sym
        code: List[instr.AssemblyLine] = [instr.Comment(f'Leaving {f_sym.name}')]
        code.append(instr.MoveOp(MoveOpcode.MOV, Regs.SP, oprnd2.Oprnd2Rm(Regs.FP)))
        code.append(instr.LoadStoreMultipleOp(LoadStoreBlockOpcode.LDM, Regs.SP, mode4.Mode4.INCREMENT_AFTER, [Regs.FP, Regs.LR], True))
        code.append(instr.MoveOp(MoveOpcode.MOV, Regs.PC, oprnd2.Oprnd2Rm(Regs.LR)))
        return code

    @staticmethod
    def from_ast(program: ast.Program) -> 'CodeGenerator':
        code = CodeGenerator.runtime

        for func in program.functions:
            code.extend(CodeGenerator.enter(func))
            body_instrs = func.body.to_asm()
            for line in body_instrs:
                code.append(line)
            code.extend(CodeGenerator.leave(func))

        code.extend(CodeGenerator.globals_asm(program))

        return CodeGenerator(code)

def main() -> None:
    log(f'[Info]   Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')
    log(f'[Info]   Starting semantic analysis...')
    
    start_parse_input = time.time()
    parse_tree, _ = TreeFactory.from_stdin()
    end_parse_input = time.time()
    log(f'[Timing] Parse input: {(end_parse_input - start_parse_input) * 1000:.2f} ms')

    start_validation = time.time()
    error, ast = parse_tree.generate_ast()
    end_validation = time.time()
    log(f'[Timing] Validate semantic rules: {(end_validation - start_validation) * 1000:.2f} ms')

    if error:
        log(f'[Error]  Finished with error: {error}')
        return
    
    assert ast is not None

    log(f'[Info]   Found no semantic errors')
    log(f'[Info]   Starting code generation...')

    ast.log()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, OUTPUT_FILENAME)

    CodeGenerator.from_ast(ast).to_file(output_path)

if __name__ == '__main__':
    main()
