import os
import time
import sys
from typing import List, Optional

from util import log, out
from type import Type, FuncSignature
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

OUTPUT_FILENAME = 'a.s'
RUNTIME = [
    instr.AssemblerDirective('.text'),
    instr.AssemblerDirective('.global _start'),
    instr.Label('_start'),
    instr.LoadStoreSingleMode2Op(LoadSingleOpcode.LDR, WordOrByte.WORD, 7, mode2.Mode2Immediate(0x20000)),
    instr.BranchOp(BranchOpcode.BL, 'f_main', Cond.ALWAYS),
    instr.MoveOp(MoveOpcode.MOV, 6, oprnd2.Oprnd2Rm(0)),
    instr.SoftwareInterruptOp(0),
]

class CodeGenerator:
    def __init__(self, code: List[instr.AssemblyLine]) -> None:
        self.code = code

    def to_file(self, filepath: str) -> None:
        with open(filepath, 'w') as f:
            for instr in self.code:
                f.write(f'{instr}\n')
    
    @staticmethod
    def fold_const(expr: ast.Expr) -> Optional[ast.ConstExpr]:
        def clamp_char(v: int):
            return v & 0xff
        
        def clamp_int(v: int):
            return v & 0xffffffff

        if isinstance(expr, ast.Const) or isinstance(expr, ast.ConstStr) or isinstance(expr, ast.CharConst):
            return expr
        
        elif isinstance(expr, ast.Var):
            if expr.sym.type is None or not expr.sym.type.is_const:
                return None
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
                return None
            right_expr = CodeGenerator.fold_const(expr.right)
            if right_expr is None:
                return None
            
            # Both operands are Const (int)
            if isinstance(left_expr, ast.Const) and isinstance(right_expr, ast.Const):
                left_val = left_expr.value
                right_val = right_expr.value
                
                # Arithmetic operations
                if expr.op == 'ADD':
                    return ast.Const(clamp_int(left_val + right_val))
                elif expr.op == 'SUB':
                    return ast.Const(clamp_int(left_val - right_val))
                elif expr.op == 'MUL':
                    return ast.Const(clamp_int(left_val * right_val))
                elif expr.op == 'DIV':
                    if right_val == 0:
                        return None
                    return ast.Const(left_val // right_val)
                elif expr.op == 'MOD':
                    if right_val == 0:
                        return None
                    return ast.Const(left_val % right_val)
                
                # Bitwise operations
                elif expr.op == 'AND':
                    return ast.Const(left_val & right_val)
                elif expr.op == 'OR':
                    return ast.Const(left_val | right_val)
                elif expr.op == 'XOR':
                    return ast.Const(left_val ^ right_val)
                
                # Comparison operations
                elif expr.op == 'EQ':
                    return ast.Const(1 if left_val == right_val else 0)
                elif expr.op == 'NEQ':
                    return ast.Const(1 if left_val != right_val else 0)
                elif expr.op == 'LT':
                    return ast.Const(1 if left_val < right_val else 0)
                elif expr.op == 'GT':
                    return ast.Const(1 if left_val > right_val else 0)
                elif expr.op == 'LE':
                    return ast.Const(1 if left_val <= right_val else 0)
                elif expr.op == 'GE':
                    return ast.Const(1 if left_val >= right_val else 0)
                
                # Logical operations
                elif expr.op == 'LOG_AND':
                    return ast.Const(1 if left_val and right_val else 0)
                elif expr.op == 'LOG_OR':
                    return ast.Const(1 if left_val or right_val else 0)
                
            # Both operands are CharConst
            elif isinstance(left_expr, ast.CharConst) and isinstance(right_expr, ast.CharConst):
                left_val = left_expr.value if left_expr.value else 0
                right_val = right_expr.value if right_expr.value else 0

                # Arithmetic operations
                if expr.op == 'ADD':
                    return ast.CharConst(clamp_char(left_val + right_val))
                elif expr.op == 'SUB':
                    return ast.CharConst(clamp_char(left_val - right_val))
                elif expr.op == 'MUL':
                    return ast.CharConst(clamp_char(left_val * right_val))
                elif expr.op == 'DIV':
                    if right_val == 0:
                        return None
                    return ast.CharConst(left_val // right_val)
                elif expr.op == 'MOD':
                    if right_val == 0:
                        return None
                    return ast.CharConst(left_val % right_val)
                
                # Bitwise operations
                elif expr.op == 'AND':
                    return ast.CharConst(clamp_char(left_val & right_val))
                elif expr.op == 'OR':
                    return ast.CharConst(clamp_char(left_val | right_val))
                elif expr.op == 'XOR':
                    return ast.CharConst(clamp_char(left_val ^ right_val))
                
                # Comparison operations
                if expr.op == 'EQ':
                    return ast.Const(1 if left_val == right_val else 0)
                elif expr.op == 'NEQ':
                    return ast.Const(1 if left_val != right_val else 0)
                elif expr.op == 'LT':
                    return ast.Const(1 if left_val < right_val else 0)
                elif expr.op == 'GT':
                    return ast.Const(1 if left_val > right_val else 0)
                elif expr.op == 'LE':
                    return ast.Const(1 if left_val <= right_val else 0)
                elif expr.op == 'GE':
                    return ast.Const(1 if left_val >= right_val else 0)
            
            # Both operands are ConstStr
            elif isinstance(left_expr, ast.ConstStr) and isinstance(right_expr, ast.ConstStr):
                left_val = left_expr.value
                right_val = right_expr.value
                
                # Comparison operations
                if expr.op == 'EQ':
                    return ast.Const(1 if left_val == right_val else 0)
                elif expr.op == 'NEQ':
                    return ast.Const(1 if left_val != right_val else 0)
                elif expr.op == 'LT':
                    return ast.Const(1 if left_val < right_val else 0)
                elif expr.op == 'GT':
                    return ast.Const(1 if left_val > right_val else 0)
                elif expr.op == 'LE':
                    return ast.Const(1 if left_val <= right_val else 0)
                elif expr.op == 'GE':
                    return ast.Const(1 if left_val >= right_val else 0)
            
            # Mixed Const and CharConst
            elif isinstance(left_expr, ast.Const) and isinstance(right_expr, ast.CharConst):
                left_val = left_expr.value
                right_val = right_expr.value if right_expr.value else 0
                
                # Comparison operations
                if expr.op == 'EQ':
                    return ast.Const(1 if left_val == right_val else 0)
                elif expr.op == 'NEQ':
                    return ast.Const(1 if left_val != right_val else 0)
                elif expr.op == 'LT':
                    return ast.Const(1 if left_val < right_val else 0)
                elif expr.op == 'GT':
                    return ast.Const(1 if left_val > right_val else 0)
                elif expr.op == 'LE':
                    return ast.Const(1 if left_val <= right_val else 0)
                elif expr.op == 'GE':
                    return ast.Const(1 if left_val >= right_val else 0)
            
            elif isinstance(left_expr, ast.CharConst) and isinstance(right_expr, ast.Const):
                left_val = left_expr.value if left_expr.value else 0
                right_val = right_expr.value
                
                # Comparison operations
                if expr.op == 'EQ':
                    return ast.Const(1 if left_val == right_val else 0)
                elif expr.op == 'NEQ':
                    return ast.Const(1 if left_val != right_val else 0)
                elif expr.op == 'LT':
                    return ast.Const(1 if left_val < right_val else 0)
                elif expr.op == 'GT':
                    return ast.Const(1 if left_val > right_val else 0)
                elif expr.op == 'LE':
                    return ast.Const(1 if left_val <= right_val else 0)
                elif expr.op == 'GE':
                    return ast.Const(1 if left_val >= right_val else 0)
            
        elif isinstance(expr, ast.UnaryOp):
            operand = CodeGenerator.fold_const(expr.operand)
            if operand is None:
                return None
            
            if expr.op == 'NEG':
                if isinstance(expr.operand, ast.Const):
                    return ast.Const(clamp_int(-expr.operand.value))
                elif isinstance(expr.operand, ast.CharConst):
                    return ast.CharConst(clamp_char(-expr.operand.value))
            elif expr.op == 'BITNOT':
                if isinstance(expr.operand, ast.Const):
                    return ast.Const(expr.operand.value ^ 0xffffffff)
                elif isinstance(expr.operand, ast.CharConst):
                    return ast.CharConst(expr.operand.value ^ 0xff)
            elif expr.op == 'LOGNOT':
                if isinstance(expr.operand, ast.Const) or isinstance(expr.operand, ast.CharConst):
                    return ast.Const(expr.operand.value != 0)

    @staticmethod
    def from_ast(program: ast.Program) -> 'CodeGenerator':
        code = RUNTIME

        for func in program.functions:
            f_sym = func.sym
            code.append(instr.Label(f'f_{f_sym.name}'))
            code.append(instr.LoadStoreMultipleOp(LoadStoreBlockOpcode.STM, 13, mode4.Mode4.DECREMENT_BEFORE, [11, 14], True))
            code.append(instr.MoveOp(MoveOpcode.MOV, 11, oprnd2.Oprnd2Rm(13)))
            code.append(instr.Comment(f'Entered {f_sym.name}'))
            
            body_instrs = func.body.to_asm()
            for line in body_instrs:
                code.append(line)

            code.append(instr.Comment(f'Leaving {f_sym.name}'))
            code.append(instr.MoveOp(MoveOpcode.MOV, 13, oprnd2.Oprnd2Rm(11)))
            code.append(instr.LoadStoreMultipleOp(LoadStoreBlockOpcode.LDM, 13, mode4.Mode4.INCREMENT_AFTER, [11, 14], True))
            code.append(instr.MoveOp(MoveOpcode.MOV, 15, oprnd2.Oprnd2Rm(14)))

        for glob in program.globals:
            code.append(instr.Label(f'g_{glob.sym.name}'))
            if glob.init:
                if isinstance(glob.init, ast.Expr):
                    val = CodeGenerator.fold_const(glob.init)
                    assert val is not None
                    
                    if isinstance(val, ast.Const):
                        code.append(instr.AssemblerDirective(f'.word {val.value}'))
                        glob.sym.const_val = val.value
                    elif isinstance(val, ast.CharConst):
                        code.append(instr.AssemblerDirective(f'.byte {val.value}'))
                        glob.sym.const_val = val.value
                    elif isinstance(val, ast.ConstStr):  # ConstStr
                        code.append(instr.AssemblerDirective(f'.string "{val.value}"'))
                        glob.sym.const_val = val.value

                    if glob.vtype.name == 'arr':
                        assert isinstance(val, ast.ConstStr)
                        code.append(instr.AssemblerDirective(f'.space {glob.bytes - len(val.value) - 1}'))

                else:
                    for elem_init in glob.init:
                        val = CodeGenerator.fold_const(elem_init)
                        
                        if isinstance(val, ast.Const):
                            code.append(instr.AssemblerDirective(f'.word {val.value}'))
                        elif isinstance(val, ast.CharConst):
                            code.append(instr.AssemblerDirective(f'.byte {val.value}'))
                        elif isinstance(val, ast.ConstStr):  # ConstStr
                            code.append(instr.AssemblerDirective(f'.string "{val.value}"'))

                    assert isinstance(glob.vtype.nested_type, Type)
                    code.append(instr.AssemblerDirective(f'.space {glob.bytes - len(glob.init) * Type.sizeof(glob.vtype.nested_type)}'))

            else:
                code.append(instr.AssemblerDirective(f'.size {glob.bytes}'))

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
