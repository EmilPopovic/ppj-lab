import sys
from typing import Iterator, Optional, Tuple, List, Dict

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

def line_depth(s: str) -> int:
    return len(s) - len(s.lstrip())

def get_line(iter: Iterator[str]) -> Tuple[Optional[str], int]:
    try:
        l = next(iter)
        return l.strip(), line_depth(l)
    except StopIteration:
        return None, -1

class Type:
    def __init__(self, name: str, is_const: bool = False, nested_type: Optional['Type | FuncSignature'] = None) -> None:
        self.name: str = name
        self.is_const: bool = is_const
        self.nested_type: Optional[Type | FuncSignature] = nested_type

    def implicitly_reduces_to(self, other: 'Type') -> bool:
        if self.name == other.name:
            return True
        elif self.name == 'char':
            return other.name == 'int'
        return False
    
    def explicitly_reduces_to(self, other: 'Type') -> bool:
        if self.name == other.name:
            return True
        elif self.name == 'char':
            return other.name == 'int'
        elif self.name == 'int':
            return other.name == 'char'
        return False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Type):
            return self.name == other.name and self.nested_type == other.nested_type
        return False
    
    def __repr__(self) -> str:
        res = f'{self.name}'
        if isinstance(self.nested_type, Type):
            res += f'[{self.nested_type.name}]'
        return res

class FuncSignature:
    def __init__(self, return_type: Type, arg_types: List[Type]) -> None:
        self.return_type: Type = return_type
        self.arg_types: List[Type] = arg_types

    def callable_with(self, args: List[Type]) -> bool:
        if len(args) != len(self.arg_types):
            return False
        
        for i in range(len(args)):
            if not args[i].implicitly_reduces_to(self.arg_types[i]):
                return False
        return True

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FuncSignature):
            return self.return_type == other.return_type and self.arg_types == other.arg_types
        return False
    
    def __repr__(self) -> str:
        return f'{self.arg_types} -> {self.return_type}'

class Token:
    def __init__(self, name: str, line_number: int, source: str, symbol: Optional['Symbol'] = None) -> None:
        self.name: str = name
        self.line_number: int = line_number
        self.source: str = source
        self.symbol: Optional[Symbol] = symbol

    @property
    def is_int(self) -> bool:
        try:
            num = int(self.source)
            return num < 2 ** 31 and num >= -(2 ** 31)
        except ValueError:
            return False
        
    @property
    def is_char(self) -> bool:
        try:
            no_quotes = self.source[1:-1]
            if no_quotes.startswith('\\'):
                escape_map = {
                    '\\t': '\t',
                    '\\n': '\n',
                    '\\0': '\0',
                    "\\'": "'",
                    '\\"': '"',
                    '\\\\': '\\'
                }
                char = escape_map.get(no_quotes, no_quotes[1:])
            else:
                char = no_quotes

            ascii_val = ord(char) if len(char) == 1 else -1
            return 0 <= ascii_val < 2 ** 8
        except (TypeError, IndexError):
            return False
        
    @property
    def is_valid_str(self) -> bool:
        without_backslash = self.source.replace('\\\\', '')[1:-1]
        for i, c in enumerate(without_backslash):
            if c == '\\' and (i == len(without_backslash) or without_backslash[i+1] not in ['t', 'n', '0', '\'', '"']):
                return False
        return True 

    @staticmethod
    def from_str(s: str, symbol: Optional['Symbol'] = None) -> 'Token':
        token_type, line_num_str, *source = s.split()
        return Token(token_type, int(line_num_str), ' '.join(source), symbol) 

    def __repr__(self) -> str:
        return f'{self.name}({self.line_number},{self.source})'

class Nonterminal:
    def __init__(self, name: str, scope: 'Scope') -> None:
        self.name: str = name
        self.scope = scope
        self.attributes: Dict[str, object] = {}

    def add_attr(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def get_attr(self, key: str) -> object:
        return self.attributes[key]

    def copy_attr_from(self, src: 'Nonterminal', names: List[str]) -> None:
        for name in names:
            self.add_attr(name, src.get_attr(name))

    def __repr__(self) -> str:
        return f'{self.name} {self.attributes}'
    
class Symbol:
    def __init__(self, name: str, type: Optional[Type], is_l_expr: bool) -> None:
        self.name: str = name
        self.type: Optional[Type] = type
        self.is_l_expr: bool = is_l_expr

    def __repr__(self) -> str:
        if self.type and isinstance(self.type.nested_type, FuncSignature):
            type = self.type.nested_type
        else:
            type = self.type
        return f'[{type}] {self.name}'

class Scope:
    root: Optional['Scope']

    def __init__(self, parent: Optional['Scope'], type: str) -> None:
        self.parent: Optional[Scope] = parent
        self.type: str = type
        self.children: List = []

    def add_child(self, child: 'Symbol | Scope') -> None:
        self.children.append(child)

    def get_symbol(self, name: str) -> Optional[Symbol]:
        with_name = [c for c in self.children if isinstance(c, Symbol) and c.name == name]
        if len(with_name) > 0:
            return with_name[0]
        elif self.parent:
            return self.parent.get_symbol(name)
        return None

    def __repr__(self) -> str:
        return self.__repr_inner(0)[:-1]

    def __repr_inner(self, indent: int) -> str:
        indent_str = ' ' * indent
        result = f'{indent_str}{self.type}\n'

        for child in self.children:
            if child is None:
                result += f'{indent_str} $\n'
            elif isinstance(child, Symbol):
                result += f'{indent_str} {child}\n'
            else:
                result += child.__repr_inner(indent + 1)

        return result

class ParseTree:
    def __init__(self, root: Nonterminal, parent: Optional['ParseTree']) -> None:
        self.root: Nonterminal = root
        self.name: str = self.root.name
        self.scope: Scope = self.root.scope
        self.children: List = []
        self.parent: Optional[ParseTree] = parent

    def add_child(self, child: 'ParseTree | Token') -> None:
        self.children.append(child)

    def validate(self) -> Optional[str]:
        nested_error = self.validate_prijevodna_jedinica()
        if nested_error:
            return nested_error
        
        main = self.scope.get_symbol('main')

        if main is None or main.type != Type('function', nested_type=FuncSignature(return_type=Type('int'), arg_types=[])):
            return 'main'

        ...

    def validate_primarni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)
        symbol = self.scope.get_symbol(first_child.source)

        if first_child.name == 'IDN':
            if symbol is None:
                return self.error_str
            self.root.add_attr('type', symbol.type)
            self.root.add_attr('is_l_expr', symbol.is_l_expr)
            
        elif first_child.name == 'BROJ':
            if not first_child.is_int:
                return self.error_str
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

        elif first_child.name == 'ZNAK':
            if not first_child.is_char:
                return self.error_str
            self.root.add_attr('type', Type('char'))
            self.root.add_attr('is_l_expr', False)

        elif first_child.name == 'NIZ_ZNAKOVA':
            if not first_child.is_valid_str:
                return self.error_str
            self.root.add_attr('type', Type('arr', nested_type=Type('char', is_const=True)))
            self.root.add_attr('is_l_expr', False)

        elif first_child.name == 'L_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            nested_error = second_child.validate_izraz()
            if nested_error:
                return nested_error
            self.root.copy_attr_from(second_child.root, ['type', 'is_l_expr'])

    def validate_postfiks_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<primarni_izraz>':
            nested_error = first_child.validate_primarni_izraz()
            if nested_error:
                return nested_error
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<postfiks_izraz>' and self.children[1].name in ['OP_INC', 'OP_DEC']:
            nested_error = first_child.validate_postfiks_izraz()
            if nested_error:
                return nested_error
            
            if not first_child.root.get_attr('is_l_expr'):
                return self.error_str
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == '<izraz>':
            nested_error = first_child.validate_postfiks_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)
            if first_child_type.name != 'arr':
                return self.error_str
            
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            nested_error = third_child.validate_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)
            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            assert isinstance(first_child_type.nested_type, Type)
            self.root.add_attr('type', first_child_type.nested_type)
            self.root.add_attr('is_l_expr', not first_child_type.nested_type.is_const)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == 'D_ZAGRADA':
            nested_error = first_child.validate_postfiks_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)
            first_child_nested_type = first_child_type.nested_type
            assert isinstance(first_child_nested_type, FuncSignature)
            first_child_return_type = first_child_nested_type.return_type
            first_child_args = first_child_nested_type.arg_types

            if len(first_child_args) > 0:
                return self.error_str
            
            self.root.add_attr('type', first_child_return_type)
            self.root.add_attr('is_l_expr', False)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == '<lista_argumenata>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = first_child.validate_postfiks_izraz() or third_child.validate_lista_argumenata()
            if nested_error:
                return nested_error

            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)
            first_child_nested_type = first_child_type.nested_type
            assert isinstance(first_child_nested_type, FuncSignature)
            first_child_return_type = first_child_nested_type.return_type

            third_child_types = third_child.root.get_attr('types')
            assert isinstance(third_child_types, list)

            if not first_child_nested_type.callable_with(third_child_types):
                return self.error_str
            
            self.root.add_attr('type', first_child_return_type)
            self.root.add_attr('is_l_expr', False)


    def validate_lista_argumenata(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            nested_error = first_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.root.add_attr('types', [first_child_type])
        
        elif first_child.name == '<lista_argumenata>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = first_child.validate_lista_argumenata() or third_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error
            
            first_child_types = first_child.root.get_attr('types')
            assert isinstance(first_child_types, list)

            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            first_child_types.append(third_child_type)
            self.root.add_attr('types', first_child_types)

    def validate_unarni_izraz(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<postfiks_izraz>':
            nested_error = first_child.validate_postfiks_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif isinstance(first_child, Token) and first_child.name in ['OP_INC', 'OP_DEC']:
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            nested_error = second_child.validate_unarni_izraz()
            if nested_error:
                return nested_error
            
            if not second_child.root.get_attr('is_l_expr'):
                return self.error_str
            
            second_child_type = second_child.root.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

        elif isinstance(first_child, ParseTree) and first_child.name == '<unarni_operator>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            nested_error = second_child.validate_cast_izraz()
            if nested_error:
                return nested_error
            
            second_child_type = second_child.root.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_cast_izraz(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<unarni_izraz>':
            nested_error = first_child.validate_unarni_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif isinstance(first_child, Token) and first_child.name == 'L_ZAGRADA':
            second_child = self.children[1]
            fourth_child = self.children[3]
            assert isinstance(second_child, ParseTree)
            assert isinstance(fourth_child, ParseTree)

            nested_error = second_child.validate_ime_tipa() or fourth_child.validate_cast_izraz()
            if nested_error:
                return nested_error
            
            second_child_type = second_child.root.get_attr('type')
            fourth_child_type = fourth_child.root.get_attr('type')
            assert isinstance(second_child_type, Type)
            assert isinstance(fourth_child_type, Type)

            if not fourth_child_type.explicitly_reduces_to(second_child_type):
                return self.error_str
            
            self.root.add_attr('type', second_child_type)
            self.root.add_attr('is_l_expr', False)
    
    def validate_ime_tipa(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<specifikator_tipa>':
            nested_error = first_child.validate_specifikator_tipa()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.root.add_attr('type', first_child_type)

        elif isinstance(first_child, Token) and first_child.name == 'KR_CONST':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            nested_error = second_child.validate_specifikator_tipa()
            if nested_error:
                return nested_error
            
            second_child_type = second_child.root.get_attr('type')
            assert isinstance(second_child_type, Type)

            if second_child_type.name == 'void':
                return self.error_str
            
            self.root.add_attr('type', Type(second_child_type.name, is_const=True, nested_type=second_child_type.nested_type))

    def validate_specifikator_tipa(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name == 'KR_VOID':
            self.root.add_attr('type', Type('void'))
        
        elif first_child.name == 'KR_CHAR':
            self.root.add_attr('type', Type('char'))

        elif first_child.name == 'KR_INT':
            self.root.add_attr('type', Type('int'))

    def validate_multiplikativni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<cast_izraz>':
            nested_error = first_child.validate_cast_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<multiplikativni_izraz>':
            nested_error = first_child.validate_multiplikativni_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_cast_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_aditivni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<multiplikativni_izraz>':
            nested_error = first_child.validate_multiplikativni_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<aditivni_izraz>':
            nested_error = first_child.validate_aditivni_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_multiplikativni_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_odnosni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<aditivni_izraz>':
            nested_error = first_child.validate_aditivni_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<odnosni_izraz>':
            nested_error = first_child.validate_odnosni_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_aditivni_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_jednakosni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<odnosni_izraz>':
            nested_error = first_child.validate_odnosni_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<jednakosni_izraz>':
            nested_error = first_child.validate_jednakosni_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_odnosni_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_bin_i_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<jednakosni_izraz>':
            nested_error = first_child.validate_jednakosni_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<bin_i_izraz>':
            nested_error = first_child.validate_bin_i_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_jednakosni_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_bin_xili_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_i_izraz>':
            nested_error = first_child.validate_bin_i_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<bin_xili_izraz>':
            nested_error = first_child.validate_bin_xili_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_bin_i_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_bin_ili_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_xili_izraz>':
            nested_error = first_child.validate_bin_xili_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<bin_ili_izraz>':
            nested_error = first_child.validate_bin_ili_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_bin_xili_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_log_i_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_ili_izraz>':
            nested_error = first_child.validate_bin_ili_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<log_i_izraz>':
            nested_error = first_child.validate_log_i_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_bin_ili_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_log_ili_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<log_i_izraz>':
            nested_error = first_child.validate_log_i_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<log_ili_izraz>':
            nested_error = first_child.validate_log_ili_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_log_i_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

    def validate_izraz_pridruzivanja(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<log_ili_izraz>':
            nested_error = first_child.validate_log_ili_izraz()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<postfiks_izraz>':
            nested_error = first_child.validate_postfiks_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            if not first_child.root.get_attr('is_l_expr'):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(first_child_type):
                return self.error_str
            
            self.root.add_attr('type', first_child_type)
            self.root.add_attr('is_l_expr', False)

    def validate_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            nested_error = first_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

        elif first_child.name == '<izraz>':
            nested_error = first_child.validate_izraz()
            if nested_error:
                return nested_error

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            nested_error = third_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)
            
            self.root.add_attr('type', third_child_type)
            self.root.add_attr('is_l_expr', False)

    def validate_slozena_naredba(self) -> Optional[str]:
        second_child = self.children[1]
        assert isinstance(second_child, ParseTree)

        if second_child.name == '<lista_naredbi>':
            nested_error = second_child.validate_lista_naredbi()
            if nested_error:
                return nested_error
            
        elif second_child.name == '<lista_deklaracija>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = second_child.validate_lista_deklaracija() or third_child.validate_lista_naredbi()
            if nested_error:
                return nested_error

    def validate_lista_naredbi(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<naredba>':
            nested_error = first_child.validate_naredba()
            if nested_error:
                return nested_error
            
        elif first_child.name == '<lista_naredbi>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            nested_error = first_child.validate_lista_naredbi() or second_child.validate_naredba()
            if nested_error:
                return nested_error
            
    def validate_naredba(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        nested_error = None

        if first_child.name == '<slozena_naredba>':
            nested_error = first_child.validate_slozena_naredba()

        elif first_child.name == '<izraz_naredba>':
            nested_error = first_child.validate_izraz_naredba()

        elif first_child.name == '<naredba_grananja>':
            nested_error = first_child.validate_naredba_grananja()
            
        elif first_child.name == '<naredba_petlje>':
            nested_error = first_child.validate_naredba_petlje()
        
        elif first_child.name == '<naredba_skoka>':
            nested_error = first_child.validate_naredba_skoka()

        return nested_error
    
    def validate_izraz_naredba(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, Token) and first_child.name == 'TOCKAZAREZ':
            self.root.add_attr('type', Type('int'))

        elif isinstance(first_child, ParseTree) and first_child.name == '<izraz>':
            nested_error = first_child.validate_izraz()
            if nested_error:
                return nested_error
            
            first_child_type = first_child.root.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.root.add_attr('type', first_child_type)

    def validate_naredba_grananja(self) -> Optional[str]:
        third_child = self.children[2]
        assert isinstance(third_child, ParseTree)

        nested_error = third_child.validate_izraz()
        if nested_error:
            return nested_error
        
        third_child_type = third_child.root.get_attr('type')
        assert isinstance(third_child_type, Type)

        if not third_child_type.implicitly_reduces_to(Type('int')):
            return self.error_str
        
        fifth_child = self.children[4]
        assert isinstance(fifth_child, ParseTree)

        nested_error = fifth_child.validate_naredba()
        if nested_error:
            return nested_error

        if len(self.children) > 5:
            seventh_child = self.children[6]
            assert isinstance(seventh_child, ParseTree)

            nested_error = seventh_child.validate_naredba()
            if nested_error:
                return nested_error

    def validate_naredba_petlje(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name == 'KR_WHILE':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = third_child.validate_izraz()
            if nested_error:
                return nested_error
            
            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            fifth_child = self.children[4]
            assert isinstance(fifth_child, ParseTree)

            nested_error = fifth_child.validate_naredba()
            if nested_error:
                return nested_error
            
        elif first_child.name == 'KR_FOR':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            fourth_child = self.children[3]
            assert isinstance(fourth_child, ParseTree)

            nested_error = third_child.validate_izraz_naredba() or fourth_child.validate_izraz_naredba()
            if nested_error:
                return nested_error
            
            fourth_child_type = fourth_child.root.get_attr('type')
            assert isinstance(fourth_child_type, Type)

            if not fourth_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            if self.children[4].name == 'D_ZAGRADA':
                sixth_child = self.children[5]
                assert isinstance(sixth_child, ParseTree)

                nested_error = sixth_child.validate_naredba()
                if nested_error:
                    return nested_error

            elif self.children[4].name == '<izraz>':
                fifth_child = self.children[4]
                assert isinstance(fifth_child, ParseTree)

                nested_error = fifth_child.validate_izraz()
                if nested_error:
                    return nested_error
                
                seventh_child = self.children[6]
                assert isinstance(seventh_child, ParseTree)

                nested_error = seventh_child.validate_izraz()
                if nested_error:
                    return nested_error

    def validate_naredba_skoka(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name in ('KR_CONTINUE', 'KR_BREAK'):
            loop: Optional[ParseTree] = self
            while loop and loop.name != '<naredba_petlje>':
                loop = loop.parent

            if loop is None:
                return self.error_str

        elif self.children[1].name == 'TOCKAZAREZ':
            definition: Optional[ParseTree] = self
            while definition and definition.name != '<definicija_funkcije>':
                definition = definition.parent

            if definition is None:
                return self.error_str
            
            definition_idn = definition.children[1]
            assert isinstance(definition_idn, Token)

            log(definition_idn)

            func = self.scope.get_symbol(definition_idn.source)
            assert func is not None
            assert func.type is not None
            assert isinstance(func.type.nested_type, FuncSignature)
            func_signature = func.type.nested_type

            if func_signature.return_type != Type('void'):
                return self.error_str

        elif self.children[1].name == '<izraz>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            nested_error = second_child.validate_izraz()
            if nested_error:
                return nested_error

            definition: Optional[ParseTree] = self
            while definition and definition.name != '<definicija_funkcije>':
                definition = definition.parent

            if definition is None:
                return self.error_str
            
            definition_idn = definition.children[1]
            assert isinstance(definition_idn, Token)

            func = self.scope.get_symbol(definition_idn.source)
            assert func is not None
            assert func.type is not None
            assert isinstance(func.type.nested_type, FuncSignature)
            func_signature = func.type.nested_type

            second_child_type = second_child.root.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(func_signature.return_type):
                return self.error_str

    def validate_prijevodna_jedinica(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<vanjska_deklaracija>':
            nested_error = first_child.validate_vanjska_deklaracija()
            if nested_error:
                return nested_error

        elif first_child.name == '<prijevodna_jedinica>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            nested_error = first_child.validate_prijevodna_jedinica() or second_child.validate_vanjska_deklaracija()
            if nested_error:
                return nested_error

    def validate_vanjska_deklaracija(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        nested_error = None

        if first_child.name == '<definicija_funkcije>':
            nested_error = first_child.validate_definicija_funkcije()

        elif first_child.name == '<deklaracija>':
            nested_error = first_child.validate_deklaracija()

        return nested_error

    def validate_definicija_funkcije(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        nested_error = first_child.validate_ime_tipa()
        if nested_error:
            return nested_error
        
        first_child_type = first_child.root.get_attr('type')
        assert isinstance(first_child_type, Type)

        if first_child_type.is_const:
            return self.error_str
        
        fourth_child = self.children[3]

        second_child = self.children[1]
        assert isinstance(second_child, Token)
        
        assert Scope.root is not None
        root_func = Scope.root.get_symbol(second_child.source)

        sixth_child = self.children[5]
        assert isinstance(sixth_child, ParseTree)
        
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

                Scope.root.add_child(root_func)
            
        elif isinstance(fourth_child, ParseTree) and fourth_child.name == '<lista_parametara>':
            nested_error = fourth_child.validate_lista_parametara()
            if nested_error:
                return nested_error
                        
            decl_types = fourth_child.root.get_attr('types')
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

                Scope.root.add_child(root_func)

                names = fourth_child.root.get_attr('names')
                assert isinstance(names, list)
                for type, name in zip(decl_types, names):
                    self.scope.add_child(Symbol(name, type, is_l_expr=not type.is_const))

        nested_error = sixth_child.validate_slozena_naredba()
        if nested_error:
            return nested_error

    def validate_lista_parametara(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<deklaracija_parametra>':
            nested_error = first_child.validate_deklaracija_parametra()
            if nested_error:
                return nested_error
            
            self.root.add_attr('types', [first_child.root.get_attr('type')])
            self.root.add_attr('names', [first_child.root.get_attr('name')])

        elif first_child.name == '<lista_parametara>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = first_child.validate_lista_parametara() or third_child.validate_deklaracija_parametra()
            if nested_error:
                return nested_error
            
            names = first_child.root.get_attr('names')
            assert isinstance(names, list)
            if third_child.root.get_attr('name') in names:
                return self.error_str
            
            types = first_child.root.get_attr('types')
            assert isinstance(types, list)

            self.root.add_attr('names', names + [third_child.root.get_attr('name')])
            self.root.add_attr('types', types + [third_child.root.get_attr('type')])

    def validate_deklaracija_parametra(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        nested_error = first_child.validate_ime_tipa()
        if nested_error:
            return nested_error

        type = first_child.root.get_attr('type')
        assert isinstance(type, Type)

        if type.name == 'void':
            return self.error_str
        
        second_child = self.children[1]
        assert isinstance(second_child, Token)

        self.root.add_attr('name', second_child.source)

        if len(self.children) == 2:
            self.root.add_attr('type', type)

        else:
            self.root.add_attr('type', Type('arr', nested_type=type))

    def validate_lista_deklaracija(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if len(self.children) == 1:
            nested_error = first_child.validate_deklaracija()
            if nested_error:
                return nested_error
            
        else:
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            
            nested_error = first_child.validate_lista_deklaracija() or second_child.validate_deklaracija()
            if nested_error:
                return nested_error

    def validate_deklaracija(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)
        nested_error = first_child.validate_ime_tipa()
        if nested_error:
            return nested_error

        second_child = self.children[1]
        assert isinstance(second_child, ParseTree)

        second_child.root.add_attr('ntype', first_child.root.get_attr('type'))

        nested_error = second_child.validate_lista_init_deklaratora()
        if nested_error:
            return nested_error

    def validate_lista_init_deklaratora(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        first_child.root.add_attr('ntype', self.root.get_attr('ntype'))

        if first_child.name == '<init_deklarator>':
            nested_error = first_child.validate_init_deklarator()
            if nested_error:
                return nested_error

        elif first_child.name == '<lista_init_deklaratora>':
            nested_error = first_child.validate_lista_init_deklaratora()
            if nested_error:
                return nested_error
            
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            third_child.root.add_attr('ntype', self.root.get_attr('ntype'))

            nested_error = third_child.validate_init_deklarator()
            if nested_error:
                return nested_error

    def validate_init_deklarator(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        first_child.root.add_attr('ntype', self.root.get_attr('ntype'))
        nested_error = first_child.validate_izravni_deklarator()
        if nested_error:
            return nested_error
        
        first_child_type = first_child.root.get_attr('type')
        assert isinstance(first_child_type, Type)

        if len(self.children) == 1:
            if first_child_type.is_const or (
                    first_child_type.name == 'arr'
                    and isinstance(first_child_type.nested_type, Type)
                    and first_child_type.nested_type.is_const
            ):
                return self.error_str

        else:
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = third_child.validate_inicijalizator()
            if nested_error:
                return nested_error
            
            if first_child_type.name == 'arr':
                first_child_elem_count = first_child.root.get_attr('elem_count')
                assert isinstance(first_child_elem_count, int)
                third_child_elem_count = third_child.root.get_attr('elem_count')
                assert isinstance(third_child_elem_count, int)

                log(first_child_elem_count)
                log(third_child_elem_count)

                if third_child_elem_count > first_child_elem_count:
                    return self.error_str
                
                third_child_types = third_child.root.get_attr('types')
                assert isinstance(third_child_types, list)
                assert isinstance(first_child_type.nested_type, Type)

                for t in third_child_types:
                    assert isinstance(t, Type)
                    if not t.implicitly_reduces_to(first_child_type.nested_type):
                        return self.error_str
            
            else:
                third_child_type = third_child.root.get_attr('type')
                assert isinstance(third_child_type, Type)

                if not third_child_type.implicitly_reduces_to(first_child_type):
                    return self.error_str

    def validate_izravni_deklarator(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        root_ntype = self.root.get_attr('ntype')
        assert isinstance(root_ntype, Type)

        if len(self.children) == 1:
            if root_ntype.name == 'void':
                return self.error_str
            
            declared = first_child.source in [c.name for c in self.scope.children if isinstance(c, Symbol)]
            if declared:
                return self.error_str
            
            self.scope.add_child(
                Symbol(
                    name=first_child.source,
                    type=root_ntype,
                    is_l_expr=not root_ntype.is_const
                )
            )

            self.root.add_attr('type', root_ntype)

        elif self.children[2].name == 'BROJ':
            if root_ntype.name == 'void':
                return self.error_str
            
            declared = first_child.source in [c.name for c in self.scope.children if isinstance(c, Symbol)]
            if declared:
                return self.error_str
            
            third_child = self.children[2]
            assert isinstance(third_child, Token)
            third_child_int = int(third_child.source)

            if not (0 < third_child_int <= 1024):
                return self.error_str
            
            self.scope.add_child(
                Symbol(
                    name=first_child.source,
                    type=Type('arr', nested_type=root_ntype),
                    is_l_expr=not root_ntype.is_const
                )
            )

            self.root.add_attr('type', Type('arr', nested_type=root_ntype))
            self.root.add_attr('elem_count', third_child_int)

        elif self.children[2].name == 'KR_VOID':
            declared = [c for c in self.scope.children if isinstance(c, Symbol) and c.name == first_child.name]
            
            new_signature = FuncSignature(
                return_type=root_ntype,
                arg_types=[]
            )

            self.root.add_attr('type', Type('function', nested_type=new_signature))

            if declared:
                declared = declared[0]
                assert isinstance(declared.type, Type)                

                if declared.type != 'function':
                    return self.error_str
                
                declared_signature = declared.type.nested_type
                assert isinstance(declared_signature, FuncSignature)

                if declared_signature != new_signature:
                    return self.error_str
                
            else:
                self.root.scope.add_child(
                    Symbol(
                        name=first_child.source,
                        type=Type('function', nested_type=new_signature),
                        is_l_expr=False
                    )
                )

        elif self.children[2].name == '<lista_parametara>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = third_child.validate_lista_parametara()
            if nested_error:
                return nested_error
            
            declared = [c for c in self.scope.children if isinstance(c, Symbol) and c.name == first_child.name]

            third_child_types = third_child.root.get_attr('types')
            assert isinstance(third_child_types, list)
            
            new_signature = FuncSignature(
                return_type=root_ntype,
                arg_types=third_child_types
            )

            self.root.add_attr('type', Type('function', nested_type=new_signature))

            if declared:
                declared = declared[0]
                assert isinstance(declared.type, Type)                

                if declared.type != 'function':
                    return self.error_str
                
                declared_signature = declared.type.nested_type
                assert isinstance(declared_signature, FuncSignature)

                if declared_signature != new_signature:
                    return self.error_str

            else:
                self.root.scope.add_child(
                    Symbol(
                        name=first_child.source,
                        type=Type('function', nested_type=new_signature),
                        is_l_expr=False
                    )
                )

    def validate_inicijalizator(self) -> Optional[str]:
        first_child = self.children[0]
    
        if isinstance(first_child, ParseTree) and first_child.name == '<izraz_pridruzivanja>':
            nested_child = first_child
            while isinstance(nested_child, ParseTree):
                nested_child = nested_child.children[0]

            nested_error = first_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error

            if nested_child.name == 'NIZ_ZNAKOVA':
                elem_count = len(nested_child.source) - 1
                self.root.add_attr('elem_count', elem_count)
                self.root.add_attr('types', [Type('char')] * elem_count)
            else:
                self.root.add_attr('type', first_child.root.get_attr('type'))


        elif isinstance(first_child, Token) and first_child.name == 'L_VIT_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            nested_error = second_child.validate_lista_izraza_pridruzivanja()
            if nested_error:
                return nested_error
            
            self.root.copy_attr_from(second_child.root, ['elem_count', 'types'])

    def validate_lista_izraza_pridruzivanja(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            nested_error = first_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error
            
            self.root.add_attr('types', [first_child.root.get_attr('type')])
            self.root.add_attr('elem_count', 1)

        elif first_child.name == '<lista_izraza_pridruzivanja>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            nested_error = first_child.validate_lista_izraza_pridruzivanja() or third_child.validate_izraz_pridruzivanja()
            if nested_error:
                return nested_error
            
            first_child_types = first_child.root.get_attr('types')
            assert isinstance(first_child_types, list)
            first_child_elem_count = first_child.root.get_attr('elem_count')
            assert isinstance(first_child_elem_count, int)
            
            self.root.add_attr('types', first_child_types + [third_child.root.get_attr('type')])
            self.root.add_attr('elem_count', first_child_elem_count + 1)

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
    def from_iter(lines: Iterator[str]) -> Tuple['ParseTree', 'Scope']:
        starting_nt, _ = get_line(lines)
        if starting_nt is None:
            raise ValueError('[FATAL] Empty file')
        
        root_scope = Scope(None, 'root')
        Scope.root = root_scope

        return TreeFactory.__from_str_inner(
            curr_root=starting_nt,
            parent=None,
            scope=root_scope, 
            lines=lines,
            depth=0
        )[0], root_scope

    @staticmethod
    def __from_str_inner(curr_root: str, parent: Optional['ParseTree'], scope: Scope, lines: Iterator[str], depth: int) -> Tuple['ParseTree', Optional[str], int]:
        tree = ParseTree(Nonterminal(curr_root, scope), parent)
        do_next = True
        line = curr_root
        inner_depth = depth

        while True:
            if do_next:
                line, inner_depth = get_line(lines)
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
    parse_tree, scope_tree = TreeFactory.from_stdin()
    error = parse_tree.validate()
    log(scope_tree)
    if error:
        out(error)

if __name__ == '__main__':
    main()
