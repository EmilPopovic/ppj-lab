import sys
from typing import Iterator, Callable

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

def line_depth(s: str) -> int:
    return len(s) - len(s.lstrip())

def get_line(iter: Iterator[str]) -> tuple[str | None, int]:
    try:
        l = next(iter)
        return l.strip(), line_depth(l)
    except StopIteration:
        return None, -1

class Type:
    def __init__(self, name: str, is_const: bool = False, nested_type: 'Type | FuncSignature | None' = None) -> None:
        self.name: str = name
        self.is_const: bool = is_const
        self.nested_type: Type | FuncSignature | None = nested_type

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
        if isinstance(other, 'Type'):
            return self.name == other.name and self.nested_type == other.nested_type
        return False

class FuncSignature:
    def __init__(self, return_type: Type, arg_types: list[Type]) -> None:
        self.return_type: Type = return_type
        self.arg_types: list[Type] = arg_types

    def callable_with(self, args: list[Type]) -> bool:
        if len(args) != len(self.arg_types):
            return False
        
        for i in range(len(args)):
            if not args[i].implicitly_reduces_to(self.arg_types[i]):
                return False
        return True

    def __eq__(self, other: object) -> bool:
        if isinstance(other, 'FuncSignature'):
            return self.return_type == other.return_type and self.arg_types == other.arg_types
        return False

class Token:
    def __init__(self, name: str, line_number: int, source: str, symbol: 'Symbol | None' = None) -> None:
        self.name: str = name
        self.line_number: int = line_number
        self.source: str = source
        self.symbol: Symbol | None = symbol

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
            if self.source.startswith('\\'):
                escape_map = {
                    '\\t': '\t',
                    '\\n': '\n',
                    '\\0': '\0',
                    "\\'": "'",
                    '\\"': '"',
                    '\\\\': '\\'
                }
                char = escape_map.get(self.source, self.source[1:])
            else:
                char = self.source
            
            ascii_val = ord(char) if len(char) == 1 else -1
            return 0 <= ascii_val < 2 ** 8
        except (TypeError, IndexError):
            return False
        
    @property
    def is_valid_str(self) -> bool:
        without_backslash = self.source.replace('\\\\', '')[1:-2]
        for i, c in enumerate(without_backslash):
            if c == '\\' and (i == len(without_backslash) or without_backslash[i+1] not in ['t', 'n', '0', '\'', '"']):
                return False
        return True 

    @staticmethod
    def from_str(s: str, symbol: 'Symbol | None' = None) -> 'Token':
        token_type, line_num_str, *source = s.split()
        return Token(token_type, int(line_num_str), ' '.join(source), symbol) 

    def __repr__(self) -> str:
        return f'{self.name}({self.line_number},{self.source})'

class Nonterminal:
    def __init__(self, name: str, scope: 'Scope') -> None:
        self.name: str = name
        self.scope = scope
        self.attributes: dict[str, object] = {}

    def add_attr(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def get_attr(self, key: str) -> object:
        return self.attributes[key]

    def copy_attr_from(self, src: Nonterminal | Symbol, names: list[str]) -> None:
        for name in names:
            self.add_attr(name, src.get_attr(name))

    def __repr__(self) -> str:
        return self.name
    
class Symbol:
    def __init__(self, name: str, type: Type | None) -> None:
        self.name: str = name
        self.type: Type | None = type
        self.attributes: dict[str, object] = {}

    def add_attr(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def get_attr(self, key: str) -> object:
        return self.attributes[key]

class Scope:
    def __init__(self, parent: 'Scope | None', type: str) -> None:
        self.parent: Scope | None = parent
        self.type: str = type
        self.children: list[Symbol | Scope] = []

    def add_child(self, child: 'Symbol | Scope') -> None:
        self.children.append(child)

    def get_symbol(self, name: str) -> Symbol | None:        
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
    def __init__(self, root: Nonterminal, parent: 'ParseTree | None') -> None:
        self.root: Nonterminal = root
        self.name: str = self.root.name
        self.scope: Scope = self.root.scope
        self.children: list[ParseTree | Token] = []
        self.parent: ParseTree | None = parent

    def add_child(self, child: 'ParseTree | Token') -> None:
        self.children.append(child)

    @property
    def validators(self) -> dict[str, Callable[[], str | None]]:
        return {
            'prijevodna_jedinica': self.validate_prijevodna_jedinica,
        }

    def validate(self) -> str | None:
        for child in self.children:
            if not isinstance(child, ParseTree):
                continue
            
            error = self.validators.get(child.name, child.validate)()
            if error:
                return error
        
        if self.parent:
            self.parent.root.attributes.update(self.root.attributes)
    
    def validate_prijevodna_jedinica(self) -> str | None:
        ...
    
    def validate_primarni_izraz(self) -> str | None:
        first_child = self.children[0]
        assert isinstance(first_child, Token)
        symbol = self.scope.get_symbol(first_child.source)

        if first_child.name == 'IDN':
            if symbol is None:
                return self.error_str
            self.root.copy_attr_from(symbol, ['type', 'is_l_expr'])
            
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

        elif first_child == 'NIZ_ZNAKOVA':
            if not first_child.is_valid_str:
                return self.error_str
            self.root.add_attr('type', Type('arr', nested_type=Type('char', is_const=True)))

        elif first_child == 'L_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            nested_error = second_child.validate_izraz()
            if nested_error:
                return nested_error
            self.root.copy_attr_from(second_child.root, ['type', 'is_l_expr'])

    def validate_postfiks_izraz(self) -> str | None:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<primarni_izraz>':
            nested_error = first_child.validate_primarni_izraz()
            if nested_error:
                return nested_error
            self.root.copy_attr_from(first_child.root, ['type', 'is_l_expr'])

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
            if third_child_type not in [Type('int'), Type('Char'), Type('int', is_const=True), Type('Char', is_const=True)]:
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

        elif first_child.name == '<postfiks_izraz>' and self.children[1] in ['OP_INC', 'OP_DEC']:
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

    def validate_lista_argumenata(self) -> str | None:
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

            nested_error = first_child.validate_lista_argumenata() or third_child.validate_izraz()
            if nested_error:
                return nested_error
            
            first_child_types = first_child.root.get_attr('types')
            assert isinstance(first_child_types, list)

            third_child_type = third_child.root.get_attr('type')
            assert isinstance(third_child_type, Type)

            first_child_types.append(third_child_type)

    def validate_unarni_izraz(self) -> str | None:
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

    def validate_cast_izraz(self) -> str | None:
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
            fourth_child_type = second_child.root.get_attr('type')
            assert isinstance(second_child_type, Type)
            assert isinstance(fourth_child_type, Type)

            if not fourth_child_type.explicitly_reduces_to(second_child_type):
                return self.error_str
            
            self.root.add_attr('type', second_child_type)
            self.root.add_attr('is_l_expr', False)
    
    def validate_ime_tipa(self) -> str | None:
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

    def validate_specifikator_tipa(self) -> str | None:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name == 'KR_VOID':
            self.root.add_attr('type', Type('void'))
        
        elif first_child.name == 'KR_CHAR':
            self.root.add_attr('type', Type('char'))

        elif first_child.name == 'KR_INT':
            self.root.add_attr('type', Type('int'))

    def validate_multiplikativni_izraz(self) -> str | None:
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

    def validate_aditivni_izraz(self) -> str | None:
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

    def validate_odnosni_izraz(self) -> str | None:
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

    def validate_izraz_pridruzivanja(self) -> str | None:
        ...

    def validate_izraz(self) -> str | None:
        ... 

    @property
    def error_str(self) -> str:
        res = f'{self.name} ::='
        for child in self.children:
            res += f' {child}'
        return res
            
class TreeFactory:
    @staticmethod
    def from_stdin() -> 'tuple[ParseTree, Scope]':
        return TreeFactory.from_iter(iter(sys.stdin))

    @staticmethod
    def from_iter(lines: Iterator[str]) -> 'tuple[ParseTree, Scope]':
        starting_nt, _ = get_line(lines)
        if starting_nt is None:
            raise ValueError('[FATAL] Empty file')
        
        root_scope = Scope(None, 'root')

        return TreeFactory.__from_str_inner(
            curr_root=starting_nt,
            parent=None,
            scope=root_scope, 
            lines=lines,
            depth=0
        )[0], root_scope

    @staticmethod
    def __from_str_inner(curr_root: str, parent: 'ParseTree | None', scope: Scope, lines: Iterator[str], depth: int) -> 'tuple[ParseTree, str | None, int]':
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
                ):
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
    # parse_tree.validate()
    print(scope_tree)

if __name__ == '__main__':
    main()
