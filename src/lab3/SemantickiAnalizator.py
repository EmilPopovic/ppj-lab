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

class Token:
    def __init__(self, name: str, line_number: int, source: str, symbol: 'Symbol | None' = None) -> None:
        self.name: str = name
        self.line_number: int = line_number
        self.source: str = source
        self.symbol: Symbol | None = symbol

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

    def __repr__(self) -> str:
        return self.name
    
class Symbol:
    def __init__(self, name: str, type: str | None) -> None:
        self.name: str = name
        self.type: str | None = type

class Scope:
    def __init__(self, parent: 'Scope | None', type: str) -> None:
        self.parent: Scope | None = parent
        self.type: str = type
        self.children: list[Symbol | Scope] = []

    def add_child(self, child: 'Symbol | Scope') -> None:
        self.children.append(child)

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
        if first_child.name == 'IDN':
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
