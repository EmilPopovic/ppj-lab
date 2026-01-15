import os
import time
import sys
from typing import Iterator, Optional, Tuple, List, Dict

from util import log, out
from instructions import *
from opcodes import *
from size import WordOrByte, HalfOrByte
from type import Type, FuncSignature
from scope import Symbol, Scope
from token_class import Token
from nonterminal import Nonterminal
import ast_nodes

OUTPUT_FILENAME = 'a.s'

class ParseTree:
    def __init__(self, root: Nonterminal, parent: Optional['ParseTree']) -> None:
        self.root: Nonterminal = root
        self.children: List = []
        self.parent: Optional[ParseTree] = parent

    @property
    def name(self) -> str:
        return self.root.name
    
    @property
    def scope(self) -> Scope:
        return self.root.scope

    def add_attr(self, key: str, value: object) -> None:
        self.root.add_attr(key, value)

    def get_attr(self, key: str) -> object:
        return self.root.get_attr(key)

    def copy_attr_from(self, src: 'ParseTree', names: List[str]) -> None:
        self.root.copy_attr_from(src.root, names)

    def add_child(self, child: 'ParseTree | Token') -> None:
        self.children.append(child)

    def generate_ast(self) -> Tuple[Optional[str], Optional[ast_nodes.Program]]:
        program = ast_nodes.Program([], [])
        if e := self.validate_prijevodna_jedinica(program): return e, None
        
        main = self.scope.get_symbol('main')

        if main is None or main.type != Type('function', nested_type=FuncSignature(return_type=Type('int'), arg_types=[])):
            return 'main', None
        
        stack = [c for c in self.scope.children if isinstance(c, Scope)]

        while stack:
            c: Scope = stack.pop()
            
            for sym in [s for s in c.children if isinstance(s, Symbol) and s.type and s.type.name == 'function']:
                f = self.scope.get_symbol(sym.name)
                if f is None:
                    return 'funkcija', None
                
                assert isinstance(sym, Symbol)
                assert isinstance(sym.type, Type)
                sym_signature = sym.type.nested_type

                assert isinstance(f, Symbol)
                assert isinstance(f.type, Type)
                f_signature = f.type.nested_type

                if sym_signature != f_signature:
                    return 'funkcija', None

            stack.extend([d for d in c.children if isinstance(d, Scope)])

        return None, program

    def validate_primarni_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)
        symbol = self.scope.get_symbol(first_child.source)

        if first_child.name == 'IDN':
            if symbol is None:
                return self.error_str, None
            self.add_attr('type', symbol.type)
            self.add_attr('is_l_expr', symbol.is_l_expr)
            return None, ast_nodes.Var(symbol)
            
        elif first_child.name == 'BROJ':
            if not first_child.is_int:
                return self.error_str, None
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)
            return None, ast_nodes.Const(int(first_child.source))

        elif first_child.name == 'ZNAK':
            if not first_child.is_char:
                return self.error_str, None
            self.add_attr('type', Type('char'))
            self.add_attr('is_l_expr', False)
            return None, ast_nodes.CharConst(first_child.to_int)

        elif first_child.name == 'NIZ_ZNAKOVA':
            if not first_child.is_valid_str:
                return self.error_str, None
            self.add_attr('type', Type('arr', nested_type=Type('char', is_const=True)))
            self.add_attr('is_l_expr', False)
            return None, ast_nodes.ConstStr(first_child.source[1:-1])

        elif first_child.name == 'L_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            e, expr = second_child.validate_izraz()
            if e:
                return e, None
            self.copy_attr_from(second_child, ['type', 'is_l_expr'])
            return None, expr
        
        return None, None

    def validate_postfiks_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<primarni_izraz>':
            e, expr = first_child.validate_primarni_izraz()
            if e:
                return e, None
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, expr

        elif first_child.name == '<postfiks_izraz>' and self.children[1].name in ['OP_INC', 'OP_DEC']:
            e, expr = first_child.validate_postfiks_izraz()
            if e:
                return e, None
            assert expr is not None
            
            if not first_child.get_attr('is_l_expr'):
                return self.error_str, None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            return None, ast_nodes.UnaryOp('POSTFIX_INC' if self.children[1].name == 'OP_INC' else 'POSTFIX_DEC', expr)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == '<izraz>':
            e, array_expr = first_child.validate_postfiks_izraz()
            if e:
                return e, None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            if first_child_type.name != 'arr':
                return self.error_str, None
            
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            e, index_expr = third_child.validate_izraz()
            if e:
                return e, None
            
            assert array_expr is not None
            assert index_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)
            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            assert isinstance(first_child_type.nested_type, Type)
            self.add_attr('type', first_child_type.nested_type)
            self.add_attr('is_l_expr', not first_child_type.nested_type.is_const)
            
            return None, ast_nodes.ArrayAccess(array_expr, index_expr)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == 'D_ZAGRADA':
            e, func_expr = first_child.validate_postfiks_izraz()
            if e:
                return e, None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            first_child_nested_type = first_child_type.nested_type
            assert isinstance(first_child_nested_type, FuncSignature)
            first_child_return_type = first_child_nested_type.return_type
            first_child_args = first_child_nested_type.arg_types

            if len(first_child_args) > 0:
                return self.error_str, None
            
            self.add_attr('type', first_child_return_type)
            self.add_attr('is_l_expr', False)
            
            assert isinstance(func_expr, ast_nodes.Var)
            return None, ast_nodes.Call(func_expr.sym.name, [])

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == '<lista_argumenata>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            e, func_expr = first_child.validate_postfiks_izraz()
            if e:
                return e, None
            
            param_exprs: List[ast_nodes.Expr] = []
            if e := third_child.validate_lista_argumenata(param_exprs):
                return e, None

            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            first_child_nested_type = first_child_type.nested_type
            assert isinstance(first_child_nested_type, FuncSignature)
            first_child_return_type = first_child_nested_type.return_type

            third_child_types = third_child.get_attr('types')
            assert isinstance(third_child_types, list)

            if not first_child_nested_type.callable_with(third_child_types):
                return self.error_str, None
            
            self.add_attr('type', first_child_return_type)
            self.add_attr('is_l_expr', False)
            
            assert isinstance(func_expr, ast_nodes.Var)
            return None, ast_nodes.Call(func_expr.sym.name, param_exprs)
        
        return None, None


    def validate_lista_argumenata(self, exprs: List[ast_nodes.Expr]) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            e, expr = first_child.validate_izraz_pridruzivanja()
            if e:
                return e
            if expr:
                exprs.append(expr)
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.add_attr('types', [first_child_type])
        
        elif first_child.name == '<lista_argumenata>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := first_child.validate_lista_argumenata(exprs):
                return e
            
            e, expr = third_child.validate_izraz_pridruzivanja()
            if e:
                return e
            if expr:
                exprs.append(expr)
            
            first_child_types = first_child.get_attr('types')
            assert isinstance(first_child_types, list)

            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            first_child_types.append(third_child_type)
            self.add_attr('types', first_child_types)

    def validate_unarni_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<postfiks_izraz>':
            e, nested_expr = first_child.validate_postfiks_izraz()
            if e:
                return e, None
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif isinstance(first_child, Token) and first_child.name in ['OP_INC', 'OP_DEC']:
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            e, operand_expr = second_child.validate_unarni_izraz()
            if e:
                return e, None
            assert operand_expr is not None
            
            if not second_child.get_attr('is_l_expr'):
                return self.error_str, None
            
            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)
            
            op = 'PREFIX_INC' if first_child.name == 'OP_INC' else 'PREFIX_DEC'
            return None, ast_nodes.UnaryOp(op, operand_expr)

        elif isinstance(first_child, ParseTree) and first_child.name == '<unarni_operator>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            e, operand_expr = second_child.validate_cast_izraz()
            if e:
                return e, None
            assert operand_expr is not None
            
            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)
            
            # Get operator from unarni_operator child
            unarni_op_token = first_child.children[0]
            assert isinstance(unarni_op_token, Token)
            if unarni_op_token.name == 'MINUS':
                op = 'NEG'
            elif unarni_op_token.name == 'OP_TILDA':
                op = 'BITNOT'
            else:  # OP_NEG
                op = 'LOGNOT'
            
            return None, ast_nodes.UnaryOp(op, operand_expr)
        
        return None, None

    def validate_cast_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<unarni_izraz>':
            e, nested_expr = first_child.validate_unarni_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif isinstance(first_child, Token) and first_child.name == 'L_ZAGRADA':
            second_child = self.children[1]
            fourth_child = self.children[3]
            assert isinstance(second_child, ParseTree)
            assert isinstance(fourth_child, ParseTree)

            if e := second_child.validate_ime_tipa():
                return e, None
            
            e, cast_expr = fourth_child.validate_cast_izraz()
            if e:
                return e, None
            
            second_child_type = second_child.get_attr('type')
            fourth_child_type = fourth_child.get_attr('type')
            assert isinstance(second_child_type, Type)
            assert isinstance(fourth_child_type, Type)

            if not fourth_child_type.explicitly_reduces_to(second_child_type):
                return self.error_str, None
            
            self.add_attr('type', second_child_type)
            self.add_attr('is_l_expr', False)
            
            # Cast expression - for now just return the expression
            # A proper implementation might wrap it in a Cast node
            return None, cast_expr
        
        return None, None
    
    def validate_ime_tipa(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<specifikator_tipa>':
            if e := first_child.validate_specifikator_tipa(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.add_attr('type', first_child_type)

        elif isinstance(first_child, Token) and first_child.name == 'KR_CONST':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := second_child.validate_specifikator_tipa(): return e
            
            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if second_child_type.name == 'void':
                return self.error_str
            
            self.add_attr('type', Type(second_child_type.name, is_const=True, nested_type=second_child_type.nested_type))

    def validate_specifikator_tipa(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name == 'KR_VOID':
            self.add_attr('type', Type('void'))
        
        elif first_child.name == 'KR_CHAR':
            self.add_attr('type', Type('char'))

        elif first_child.name == 'KR_INT':
            self.add_attr('type', Type('int'))

    def validate_multiplikativni_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<cast_izraz>':
            e, nested_expr = first_child.validate_cast_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<multiplikativni_izraz>':
            e, left_expr = first_child.validate_multiplikativni_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_cast_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            second_child = self.children[1]
            assert isinstance(second_child, Token)
            if second_child.name == 'OP_PUTA':
                op = 'MUL'
            elif second_child.name == 'OP_DIJELI':
                op = 'DIV'
            else:  # OP_MOD
                op = 'MOD'
            
            mul_op = ast_nodes.BinOp(op, left_expr, right_expr)
            return None, mul_op

        return None, None

    def validate_aditivni_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<multiplikativni_izraz>':
            e, nested_expr = first_child.validate_multiplikativni_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<aditivni_izraz>':
            e, left_expr = first_child.validate_aditivni_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_multiplikativni_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            second_child = self.children[1]
            assert isinstance(second_child, Token)
            if second_child.name == 'PLUS':
                op = 'ADD'
            else:  # MINUS
                op = 'SUB'
            
            add_op = ast_nodes.BinOp(op, left_expr, right_expr)
            return None, add_op

        return None, None

    def validate_odnosni_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<aditivni_izraz>':
            e, nested_expr = first_child.validate_aditivni_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<odnosni_izraz>':
            e, left_expr = first_child.validate_odnosni_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_aditivni_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            second_child = self.children[1]
            assert isinstance(second_child, Token)
            if second_child.name == 'OP_LT':
                op = 'LT'
            elif second_child.name == 'OP_GT':
                op = 'GT'
            elif second_child.name == 'OP_LTE':
                op = 'LTE'
            else:  # OP_GTE
                op = 'GTE'
            
            rel_op = ast_nodes.BinOp(op, left_expr, right_expr)
            return None, rel_op

        return None, None

    def validate_jednakosni_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<odnosni_izraz>':
            e, nested_expr = first_child.validate_odnosni_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<jednakosni_izraz>':
            e, left_expr = first_child.validate_jednakosni_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_odnosni_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            second_child = self.children[1]
            assert isinstance(second_child, Token)
            if second_child.name == 'OP_EQ':
                op = 'EQ'
            else:  # OP_NEQ
                op = 'NEQ'
            
            eq_op = ast_nodes.BinOp(op, left_expr, right_expr)
            return None, eq_op

        return None, None

    def validate_bin_i_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<jednakosni_izraz>':
            e, nested_expr = first_child.validate_jednakosni_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<bin_i_izraz>':
            e, left_expr = first_child.validate_bin_i_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_jednakosni_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            bit_and_op = ast_nodes.BinOp('AND', left_expr, right_expr)
            return None, bit_and_op

        return None, None

    def validate_bin_xili_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_i_izraz>':
            e, nested_expr = first_child.validate_bin_i_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<bin_xili_izraz>':
            e, left_expr = first_child.validate_bin_xili_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_bin_i_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            bit_xor_op = ast_nodes.BinOp('XOR', left_expr, right_expr)
            return None, bit_xor_op

        return None, None

    def validate_bin_ili_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_xili_izraz>':
            e, nested_expr = first_child.validate_bin_xili_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<bin_ili_izraz>':
            e, left_expr = first_child.validate_bin_ili_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_bin_xili_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            bit_or_op = ast_nodes.BinOp('OR', left_expr, right_expr)
            return None, bit_or_op

        return None, None

    def validate_log_i_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_ili_izraz>':
            e, nested_expr = first_child.validate_bin_ili_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<log_i_izraz>':
            e, left_expr = first_child.validate_log_i_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_bin_ili_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            log_and_op = ast_nodes.BinOp('LOG_AND', left_expr, right_expr)
            return None, log_and_op

        return None, None

    def validate_log_ili_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<log_i_izraz>':
            e, nested_expr = first_child.validate_log_i_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<log_ili_izraz>':
            e, left_expr = first_child.validate_log_ili_izraz()
            if e:
                return e, None
            assert left_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_log_i_izraz()
            if e:
                return e, None
            assert right_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

            log_or_op = ast_nodes.BinOp('LOG_OR', left_expr, right_expr)
            return None, log_or_op

        return None, None

    def validate_izraz_pridruzivanja(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<log_ili_izraz>':
            e, nested_expr = first_child.validate_log_ili_izraz()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<postfiks_izraz>':
            e, target_expr = first_child.validate_postfiks_izraz()
            if e:
                return e, None
            assert target_expr is not None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            if not first_child.get_attr('is_l_expr'):
                return self.error_str, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, value_expr = third_child.validate_izraz_pridruzivanja()
            if e:
                return e, None
            assert value_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(first_child_type):
                return self.error_str, None
            
            self.add_attr('type', first_child_type)
            self.add_attr('is_l_expr', False)

            assign_expr = ast_nodes.BinOp('ASSIGN', target_expr, value_expr)
            return None, assign_expr

        return None, None

    def validate_izraz(self) -> Tuple[Optional[str], Optional[ast_nodes.Expr]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            e, nested_expr = first_child.validate_izraz_pridruzivanja()
            if e:
                return e, None
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])
            return None, nested_expr

        elif first_child.name == '<izraz>':
            e, left_expr = first_child.validate_izraz()
            if e:
                return e, None

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            e, right_expr = third_child.validate_izraz_pridruzivanja()
            if e:
                return e, None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)
            
            self.add_attr('type', third_child_type)
            self.add_attr('is_l_expr', False)
            
            # For comma operator, return the right expression
            return None, right_expr
        
        return None, None

    def validate_slozena_naredba(self) -> Tuple[Optional[str], Optional[ast_nodes.Block]]:
        second_child = self.children[1]
        assert isinstance(second_child, ParseTree)

        block = ast_nodes.Block([], [])

        if second_child.name == '<lista_naredbi>':
            if e := second_child.validate_lista_naredbi(block): return e, None
            
        elif second_child.name == '<lista_deklaracija>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            if e := (second_child.validate_lista_deklaracija(block) or third_child.validate_lista_naredbi(block)): return e, None
        
        return None, block

    def validate_lista_naredbi(self, block: ast_nodes.Block) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<naredba>':
            if e := first_child.validate_naredba(block)[0]: return e
            
        elif first_child.name == '<lista_naredbi>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := (first_child.validate_lista_naredbi(block) or second_child.validate_naredba(block)[0]): return e
            
    def validate_naredba(self, block: Optional[ast_nodes.Block]) -> Tuple[Optional[str], Optional[ast_nodes.Stmt]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        e = None

        if first_child.name == '<slozena_naredba>':
            e, stmt = first_child.validate_slozena_naredba()
            if e:
                return e, None
            if block is None:
                return None, stmt

        elif first_child.name == '<izraz_naredba>':
            e, stmt = first_child.validate_izraz_naredba()

        elif first_child.name == '<naredba_grananja>':
            e, stmt = first_child.validate_naredba_grananja()
            
        elif first_child.name == '<naredba_petlje>':
            e, stmt = first_child.validate_naredba_petlje()
        
        else:  # <naredba_skoka>
            e, stmt = first_child.validate_naredba_skoka()
        
        if e:
            return e, None

        if block is None:
            block = ast_nodes.Block([], [])
        if stmt is not None:
            block.stmts.append(stmt)

        return None, stmt
    
    def validate_izraz_naredba(self) -> Tuple[Optional[str], Optional[ast_nodes.ExprStmt]]:
        first_child = self.children[0]

        if isinstance(first_child, Token) and first_child.name == 'TOCKAZAREZ':
            self.add_attr('type', Type('int'))
            return None, None

        elif isinstance(first_child, ParseTree) and first_child.name == '<izraz>':
            e, expr = first_child.validate_izraz()
            if e:
                return e, None
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.add_attr('type', first_child_type)

            assert expr is not None
            return None, ast_nodes.ExprStmt(expr)
        
        return None, None

    def validate_naredba_grananja(self) -> Tuple[Optional[str], Optional[ast_nodes.If]]:
        third_child = self.children[2]
        assert isinstance(third_child, ParseTree)

        e, cond_expr = third_child.validate_izraz()
        if e:
            return e, None
        assert cond_expr is not None
        
        third_child_type = third_child.get_attr('type')
        assert isinstance(third_child_type, Type)

        if not third_child_type.implicitly_reduces_to(Type('int')):
            return self.error_str, None
        
        fifth_child = self.children[4]
        assert isinstance(fifth_child, ParseTree)

        e, if_block = fifth_child.validate_naredba(None)
        if e:
            return e, None
        
        assert if_block is not None

        if_stmt = ast_nodes.If(cond_expr, if_block, None)

        if len(self.children) > 5:
            seventh_child = self.children[6]
            assert isinstance(seventh_child, ParseTree)

            else_block = ast_nodes.Block([], [])

            e, else_block = seventh_child.validate_naredba(None)
            if e:
                return e, None
            
            assert else_block is not None

            if_stmt.else_branch = else_block

        return None, if_stmt

    def validate_naredba_petlje(self) -> Tuple[Optional[str], Optional[ast_nodes.While]]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name == 'KR_WHILE':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            e, cond_expr = third_child.validate_izraz()
            if e:
                return e, None
            assert cond_expr is not None
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            fifth_child = self.children[4]
            assert isinstance(fifth_child, ParseTree)

            e, while_block = fifth_child.validate_naredba(None)
            if e:
                return e, None
            assert while_block
            
            return None, ast_nodes.While(None, cond_expr, while_block)
            
        elif first_child.name == 'KR_FOR':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            fourth_child = self.children[3]
            assert isinstance(fourth_child, ParseTree)

            e, decl_stmt = third_child.validate_izraz_naredba()
            if e:
                return e, None
            
            e, cond_stmt = fourth_child.validate_izraz_naredba()
            if e:
                return e, None

            fourth_child_type = fourth_child.get_attr('type')
            assert isinstance(fourth_child_type, Type)

            if not fourth_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str, None
            
            after_iter_expr = None

            if self.children[4].name == 'D_ZAGRADA':
                sixth_child = self.children[5]
                assert isinstance(sixth_child, ParseTree)
                e, for_block =  sixth_child.validate_naredba(None)
                if e:
                    return e, None

            else: # fifth_child.name == '<izraz>':
                fifth_child = self.children[4]
                assert isinstance(fifth_child, ParseTree)

                e, after_iter_expr = fifth_child.validate_izraz()
                if e:
                    return e, None
                
                seventh_child = self.children[6]
                assert isinstance(seventh_child, ParseTree)

                e, for_block = seventh_child.validate_naredba(None)
                if e:
                    return e, None
            
            assert isinstance(for_block, ast_nodes.Block)
            if after_iter_expr:
                for_block.stmts.append(ast_nodes.ExprStmt(after_iter_expr))
            return None, ast_nodes.While(decl_stmt, None if cond_stmt is None else cond_stmt.expr, for_block)

        return None, None

    def validate_naredba_skoka(self) -> Tuple[Optional[str], Optional[ast_nodes.CtrlFlowStmt]]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name in ('KR_CONTINUE', 'KR_BREAK'):
            loop: Optional[ParseTree] = self
            while loop and loop.name != '<naredba_petlje>':
                loop = loop.parent

            if loop is None:
                return self.error_str, None
            
            if first_child.name == 'KR_CONTINUE':
                return None, ast_nodes.Continue()
            else:  # KR_BREAK
                return None, ast_nodes.Break()

        elif self.children[1].name == 'TOCKAZAREZ':
            definition: Optional[ParseTree] = self
            while definition and definition.name != '<definicija_funkcije>':
                definition = definition.parent

            if definition is None:
                return self.error_str, None
            
            definition_idn = definition.children[1]
            assert isinstance(definition_idn, Token)

            func = self.scope.get_symbol(definition_idn.source)
            assert func is not None
            assert func.type is not None
            assert isinstance(func.type.nested_type, FuncSignature)
            func_signature = func.type.nested_type

            if func_signature.return_type != Type('void'):
                return self.error_str, None
            
            return None, ast_nodes.Return(None)

        elif self.children[1].name == '<izraz>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            e, return_expr = second_child.validate_izraz()
            if e:
                return e, None

            definition: Optional[ParseTree] = self
            while definition and definition.name != '<definicija_funkcije>':
                definition = definition.parent

            if definition is None:
                return self.error_str, None
            
            definition_idn = definition.children[1]
            assert isinstance(definition_idn, Token)

            func = self.scope.get_symbol(definition_idn.source)
            assert func is not None
            assert func.type is not None
            assert isinstance(func.type.nested_type, FuncSignature)
            func_signature = func.type.nested_type

            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(func_signature.return_type):
                return self.error_str, None
            
            return None, ast_nodes.Return(return_expr)
        
        return None, None

    def validate_prijevodna_jedinica(self, program: ast_nodes.Program) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<vanjska_deklaracija>':
            if e := first_child.validate_vanjska_deklaracija(program): return e

        elif first_child.name == '<prijevodna_jedinica>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            if e := (first_child.validate_prijevodna_jedinica(program) or second_child.validate_vanjska_deklaracija(program)): return e

    def validate_vanjska_deklaracija(self, program: ast_nodes.Program) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        e = None

        if first_child.name == '<definicija_funkcije>':
            e = first_child.validate_definicija_funkcije(program)

        elif first_child.name == '<deklaracija>':
            e, var_decls = first_child.validate_deklaracija()
            program.globals.extend(var_decls)

        return e

    def validate_definicija_funkcije(self, program: ast_nodes.Program) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if e := first_child.validate_ime_tipa(): return e
        
        first_child_type = first_child.get_attr('type')
        assert isinstance(first_child_type, Type)

        if first_child_type.is_const:
            return self.error_str
        
        fourth_child = self.children[3]

        second_child = self.children[1]
        assert isinstance(second_child, Token)

        root_func = Scope.root_scope.get_symbol(second_child.source)

        sixth_child = self.children[5]
        assert isinstance(sixth_child, ParseTree)

        func_def = None
        
        if isinstance(fourth_child, Token) and fourth_child.name == 'KR_VOID':
            if root_func:
                assert root_func.type is not None
                func = root_func.type.nested_type
                assert isinstance(func, FuncSignature)

                if root_func.type != first_child_type or func.arg_types != []:
                    return self.error_str

            else:
                root_func = Symbol(
                    name=second_child.source,
                    type=Type(
                        'function',
                        nested_type=FuncSignature(
                            return_type=first_child_type,
                            arg_types=[]
                        )
                    ),
                    is_l_expr=False
                )

                Scope.root_scope.add_child(root_func)
                
                func_def = ast_nodes.FuncDef(root_func.name, first_child_type, [], ast_nodes.Block([], []))
                program.functions.append(func_def)
            
        elif isinstance(fourth_child, ParseTree) and fourth_child.name == '<lista_parametara>':
            if e := fourth_child.validate_lista_parametara(): return e
                        
            decl_types = fourth_child.get_attr('types')
            assert isinstance(decl_types, list)

            if root_func:
                assert root_func.type is not None
                func = root_func.type.nested_type
                assert isinstance(func, FuncSignature)

                if decl_types != func.arg_types:
                    return self.error_str
                
            else:
                root_func = Symbol(
                    name=second_child.source,
                    type=Type(
                        'function',
                        nested_type=FuncSignature(
                            return_type=first_child_type,
                            arg_types=decl_types
                        )
                    ),
                    is_l_expr=False
                )

            Scope.root_scope.add_child(root_func)

            names = fourth_child.get_attr('names')
            var_decls = []

            assert isinstance(names, list)
            for type, name in zip(decl_types, names):
                symbol = Symbol(name, type, is_l_expr=not type.is_const)
                self.scope.add_child(symbol)
                var_decls.append(ast_nodes.VarDecl(symbol, type, Type.sizeof(type), None))

            func_def = ast_nodes.FuncDef(root_func.name, first_child_type, var_decls, ast_nodes.Block([], []))
            program.functions.append(func_def)

        e, func_body = sixth_child.validate_slozena_naredba()
        if e:
            return e
        assert func_body is not None
        assert func_def is not None
        func_def.body = func_body

    def validate_lista_parametara(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<deklaracija_parametra>':
            if e := first_child.validate_deklaracija_parametra(): return e            
            self.add_attr('types', [first_child.get_attr('type')])
            self.add_attr('names', [first_child.get_attr('name')])

        elif first_child.name == '<lista_parametara>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := (first_child.validate_lista_parametara() or third_child.validate_deklaracija_parametra()): return e
            
            names = first_child.get_attr('names')
            assert isinstance(names, list)
            if third_child.get_attr('name') in names:
                return self.error_str
            
            types = first_child.get_attr('types')
            assert isinstance(types, list)

            self.add_attr('names', names + [third_child.get_attr('name')])
            self.add_attr('types', types + [third_child.get_attr('type')])

    def validate_deklaracija_parametra(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if e := first_child.validate_ime_tipa(): return e

        type = first_child.get_attr('type')
        assert isinstance(type, Type)

        if type.name == 'void':
            return self.error_str
        
        second_child = self.children[1]
        assert isinstance(second_child, Token)

        self.add_attr('name', second_child.source)

        if len(self.children) == 2:
            self.add_attr('type', type)

        else:
            self.add_attr('type', Type('arr', nested_type=type))

    def validate_lista_deklaracija(self, block: ast_nodes.Block) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if len(self.children) == 1:
            e, var_decls = first_child.validate_deklaracija()
            if e:
                return e
            block.var_decls.extend(var_decls)
            
        else:
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            if e := first_child.validate_lista_deklaracija(block): return e

            e, var_decls = second_child.validate_deklaracija()
            if e:
                return e
            block.var_decls.extend(var_decls)

    def validate_deklaracija(self) -> Tuple[Optional[str], List[ast_nodes.VarDecl]]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)
        if e := first_child.validate_ime_tipa(): return e, []

        second_child = self.children[1]
        assert isinstance(second_child, ParseTree)

        second_child.add_attr('ntype', first_child.get_attr('type'))

        var_decls = []
        if e := second_child.validate_lista_init_deklaratora(var_decls): return e, []
        
        return None, var_decls

    def validate_lista_init_deklaratora(self, var_decls: List[ast_nodes.VarDecl]) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        first_child.add_attr('ntype', self.get_attr('ntype'))

        if first_child.name == '<init_deklarator>':
            if e := first_child.validate_init_deklarator(var_decls): return e

        elif first_child.name == '<lista_init_deklaratora>':
            if e := first_child.validate_lista_init_deklaratora(var_decls): return e
            
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            third_child.add_attr('ntype', self.get_attr('ntype'))

            if e := third_child.validate_init_deklarator(var_decls): return e

    def validate_init_deklarator(self, var_decls: List[ast_nodes.VarDecl]) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        first_child.add_attr('ntype', self.get_attr('ntype'))
        e, var_decl = first_child.validate_izravni_deklarator()
        if e:
            return e
        
        first_child_type = first_child.get_attr('type')
        assert isinstance(first_child_type, Type)

        if len(self.children) == 1:
            if first_child_type.is_const or (
                    first_child_type.name == 'arr'
                    and isinstance(first_child_type.nested_type, Type)
                    and first_child_type.nested_type.is_const
            ):
                return self.error_str
            if var_decl is not None:
                var_decls.append(var_decl)

        else:
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            e, init_expr = third_child.validate_inicijalizator()
            if e:
                return e
            assert init_expr is not None
            
            if first_child_type.name == 'arr':
                first_child_elem_count = first_child.get_attr('elem_count')
                assert isinstance(first_child_elem_count, int)
                third_child_elem_count = third_child.get_attr('elem_count')
                assert isinstance(third_child_elem_count, int)

                if third_child_elem_count > first_child_elem_count:
                    return self.error_str
                
                third_child_types = third_child.get_attr('types')
                assert isinstance(third_child_types, list)
                assert isinstance(first_child_type.nested_type, Type)

                for t in third_child_types:
                    assert isinstance(t, Type)
                    if not t.implicitly_reduces_to(first_child_type.nested_type):
                        return self.error_str
            
            else:
                third_child_type = third_child.get_attr('type')
                assert isinstance(third_child_type, Type)

                if not third_child_type.implicitly_reduces_to(first_child_type):
                    return self.error_str

            if var_decl is not None:
                var_decl.init = init_expr
                var_decls.append(var_decl)

    def validate_izravni_deklarator(self) -> Tuple[Optional[str], Optional[ast_nodes.VarDecl]]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        root_ntype = self.get_attr('ntype')
        assert isinstance(root_ntype, Type)

        if len(self.children) == 1:
            if root_ntype.name == 'void':
                return self.error_str, None
            
            declared = first_child.source in [c.name for c in self.scope.children if isinstance(c, Symbol)]
            if declared:
                return self.error_str, None
            
            symbol = Symbol(
                name=first_child.source,
                type=root_ntype,
                is_l_expr=not root_ntype.is_const
            )
            self.scope.add_child(symbol)

            self.add_attr('type', root_ntype)

            assert symbol.type is not None
            decl = ast_nodes.VarDecl(symbol, symbol.type, Type.sizeof(root_ntype), None)
            return None, decl

        elif self.children[2].name == 'BROJ':
            if root_ntype.name == 'void':
                return self.error_str, None
            
            declared = first_child.source in [c.name for c in self.scope.children if isinstance(c, Symbol)]
            if declared:
                return self.error_str, None
            
            third_child = self.children[2]
            assert isinstance(third_child, Token)
            third_child_int = int(third_child.source)

            if not (0 < third_child_int <= 1024):
                return self.error_str, None
            
            symbol = Symbol(
                name=first_child.source,
                type=Type('arr', nested_type=root_ntype),
                is_l_expr=not root_ntype.is_const
            )
            self.scope.add_child(symbol)

            self.add_attr('type', Type('arr', nested_type=root_ntype))
            self.add_attr('elem_count', third_child_int)

            size = third_child_int * Type.sizeof(root_ntype)

            assert symbol.type is not None
            decl = ast_nodes.VarDecl(symbol, symbol.type, size, None)
            return None, decl

        elif self.children[2].name == 'KR_VOID':
            declared = [c for c in self.scope.children if isinstance(c, Symbol) and c.name == first_child.source]
            
            new_signature = FuncSignature(
                return_type=root_ntype,
                arg_types=[]
            )

            self.add_attr('type', Type('function', nested_type=new_signature))

            if declared:
                declared = declared[0]
                assert isinstance(declared.type, Type)                

                if declared.type.name != 'function':
                    return self.error_str, None
                
                declared_signature = declared.type.nested_type
                assert isinstance(declared_signature, FuncSignature)

                if declared_signature != new_signature:
                    return self.error_str, None
                
            else:
                self.scope.add_child(
                    Symbol(
                        name=first_child.source,
                        type=Type('function', nested_type=new_signature),
                        is_l_expr=False
                    )
                )
        
            return None, None

        elif self.children[2].name == '<lista_parametara>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := third_child.validate_lista_parametara(): return e, None
            
            declared = [c for c in self.scope.children if isinstance(c, Symbol) and c.name == first_child.source]

            third_child_types = third_child.get_attr('types')
            assert isinstance(third_child_types, list)
            
            new_signature = FuncSignature(
                return_type=root_ntype,
                arg_types=third_child_types
            )

            self.add_attr('type', Type('function', nested_type=new_signature))

            if declared:
                declared = declared[0]
                assert isinstance(declared.type, Type)                

                if declared.type.name != 'function':
                    return self.error_str, None
                
                declared_signature = declared.type.nested_type
                assert isinstance(declared_signature, FuncSignature)

                if declared_signature != new_signature:
                    return self.error_str, None

            else:
                self.scope.add_child(
                    Symbol(
                        name=first_child.source,
                        type=Type('function', nested_type=new_signature),
                        is_l_expr=False
                    )
                )

            return None, None
        
        return None, None

    def validate_inicijalizator(self) -> Tuple[Optional[str], 'Optional[ast_nodes.Expr] | List[ast_nodes.Expr]']:
        first_child = self.children[0]
    
        if isinstance(first_child, ParseTree) and first_child.name == '<izraz_pridruzivanja>':
            nested_child = first_child
            while isinstance(nested_child, ParseTree):
                nested_child = nested_child.children[0]

            e, init_expr = first_child.validate_izraz_pridruzivanja()
            if e:
                return e, None

            if nested_child.name == 'NIZ_ZNAKOVA':
                escape_map = {
                    r'\t': '\t',
                    r'\n': '\n',
                    r'\0': '\0',
                    r"\'": "'",
                    r'\"': '"',
                    r'\\': '\\',
                }

                escaped_str = nested_child.source
                for esc, real in escape_map.items():
                    escaped_str = escaped_str.replace(esc, real)

                elem_count = len(escaped_str) - 1

                self.add_attr('elem_count', elem_count)
                self.add_attr('types', [Type('char')] * elem_count)
            else:
                self.add_attr('type', first_child.get_attr('type'))
            
            return None, init_expr

        elif isinstance(first_child, Token) and first_child.name == 'L_VIT_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            expr_list: List[ast_nodes.Expr] = []
            if e := second_child.validate_lista_izraza_pridruzivanja(expr_list):
                return e, None
            
            self.copy_attr_from(second_child, ['elem_count', 'types'])
            return None, expr_list
        
        return None, None

    def validate_lista_izraza_pridruzivanja(self, expr_list: List[ast_nodes.Expr]) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            e, expr = first_child.validate_izraz_pridruzivanja()
            if e:
                return e
            self.add_attr('types', [first_child.get_attr('type')])
            self.add_attr('elem_count', 1)
            if expr is not None:
                expr_list.append(expr)

        elif first_child.name == '<lista_izraza_pridruzivanja>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := first_child.validate_lista_izraza_pridruzivanja(expr_list):
                return e
            
            e, expr = third_child.validate_izraz_pridruzivanja()
            if e:
                return e
            if expr is not None:
                expr_list.append(expr)
            
            first_child_types = first_child.get_attr('types')
            assert isinstance(first_child_types, list)
            first_child_elem_count = first_child.get_attr('elem_count')
            assert isinstance(first_child_elem_count, int)
            
            self.add_attr('types', first_child_types + [third_child.get_attr('type')])
            self.add_attr('elem_count', first_child_elem_count + 1)

    @property
    def error_str(self) -> str:
        res = f'{self.name} ::='
        for child in self.children:
            res += f' {child.name}' if isinstance(child, ParseTree) else f' {child}'
        return res
    
    def __repr__(self) -> str:
        return self.__repr_inner(0)[:-1]

    def __repr_inner(self, indent: int) -> str:
        indent_str = ' ' * indent
        result = f'{indent_str}{self.root}\n'

        for child in self.children:
            if child is None:
                result += f'{indent_str} $\n'
            elif isinstance(child, Token):
                result += f'{indent_str} {child}\n'
            else:
                result += child.__repr_inner(indent + 1)

        return result
            
class TreeFactory:
    @staticmethod
    def from_stdin() -> Tuple['ParseTree', 'Scope']:
        return TreeFactory.from_iter(iter(sys.stdin))
    
    @staticmethod
    def get_line(iter: Iterator[str]) -> Tuple[Optional[str], int]:
        def line_depth(s: str) -> int:
            return len(s) - len(s.lstrip())

        try:
            l = next(iter)
            return l.strip(), line_depth(l)
        except StopIteration:
            return None, -1

    @staticmethod
    def from_iter(lines: Iterator[str]) -> Tuple['ParseTree', 'Scope']:
        starting_nt, _ = TreeFactory.get_line(lines)
        if starting_nt is None:
            raise ValueError('[FATAL] Empty file')
        
        return TreeFactory.__from_str_inner(
            curr_root=starting_nt,
            parent=None,
            scope=Scope.root_scope, 
            lines=lines,
            depth=0
        )[0], Scope.root_scope

    @staticmethod
    def __from_str_inner(curr_root: str, parent: Optional['ParseTree'], scope: Scope, lines: Iterator[str], depth: int) -> Tuple['ParseTree', Optional[str], int]:
        tree = ParseTree(Nonterminal(curr_root, scope), parent)
        do_next = True
        line = curr_root
        inner_depth = depth

        while True:
            if do_next:
                line, inner_depth = TreeFactory.get_line(lines)
            do_next = True

            if inner_depth <= depth or line is None:
                return tree, line, inner_depth

            if line.startswith('<'):
                if line in (
                    '<slozena_naredba>',
                    '<definicija_funkcije>',
                    '<naredba_petlje>',
                    '<naredba_grananja>',
                ) and tree.root.name != '<definicija_funkcije>':
                    new_scope = Scope(scope, line)
                    scope.add_child(new_scope)
                else:
                    new_scope = scope

                subtree, line, inner_depth = TreeFactory.__from_str_inner(
                    curr_root=line,
                    parent=tree,
                    scope=new_scope,
                    lines=lines,
                    depth=depth+1
                )

                tree.add_child(subtree)
                do_next = False

            else:
                tree.add_child(Token.from_str(line))

def main() -> None:
    log(f'[Info]   Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')
    log(f'[Info]   Starting semantic analysis...')
    
    start_parse_input = time.time()
    parse_tree, _ = TreeFactory.from_stdin()
    end_parse_input = time.time()
    log(f'[Timing] Parse input: {(end_parse_input - start_parse_input) * 1000:.2f} ms')

    start_validation = time.time()
    error, _ = parse_tree.generate_ast()
    end_validation = time.time()
    log(f'[Timing] Validate semantic rules: {(end_validation - start_validation) * 1000:.2f} ms')

    if error:
        log(f'[Error]  Finished with error: {error}')
    else:
        log(f'[Info]   Finished without errors')

if __name__ == '__main__':
    main()
