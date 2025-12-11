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
    def __init__(self, name: str, is_const: bool = False, nested_type: 'Type | None' = None) -> None:
        self.name: str = name
        self.is_const: bool = is_const
        self.nested_type: Type | None = nested_type

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
        return f'{self.name} {self.line_number} {self.source}'

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
                return f'<primarni_izraz> ::= IDN({first_child.line_number},{first_child.source})'
            self.root.copy_attr_from(symbol, ['type', 'is_l_expr'])
            
        elif first_child.name == 'BROJ':
            if not first_child.is_int:
                return f'<primarni_izraz> ::= BROJ({first_child.line_number},{first_child.source})'
            self.root.add_attr('type', Type('int'))
            self.root.add_attr('is_l_expr', False)

        elif first_child.name == 'ZNAK':
            if not first_child.is_char:
                return f'<primarni_izraz> ::= ZNAK({first_child.line_number},{first_child.source})'
            self.root.add_attr('type', Type('char'))
            self.root.add_attr('is_l_expr', False)

        elif first_child == 'NIZ_ZNAKOVA':
            if not first_child.is_valid_str:
                return f'<primarni_izraz> ::= NIZ_ZNAKOVA({first_child.line_number},{first_child.source})'
            self.root.add_attr('type', Type('arr', nested_type=Type('char', is_const=True)))

        elif first_child == 'L_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            nested_error = second_child.validate_izraz()
            if nested_error:
                return nested_error
            self.root.copy_attr_from(second_child.root, ['type', 'is_l_expr'])

    def validate_izraz(self) -> str | None:
        ... 
            
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
