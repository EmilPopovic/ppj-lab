import sys
from typing import Iterator

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
    __slots__ = ('type', 'line_number', 'source')

    def __init__(self, type: str, line_number: int, source: str) -> None:
        self.type: str = type
        self.line_number: int = line_number
        self.source: str = source

    @staticmethod
    def from_str(s: str) -> 'Token':
        token_type, line_num_str, *source = s.split()
        return Token(token_type, int(line_num_str), ' '.join(source)) 

    def __repr__(self) -> str:
        return f'{self.type} {self.line_number} {self.source}'

class Nonterminal:
    def __init__(self, name: str) -> None:
        self.name: str = name.strip('<>')
        self.attributes: dict[str, object] = {}

    def __repr__(self) -> str:
        return f'<{self.name}>'

class ParseTree:
    __slots__ = ('root', 'children', 'parent')

    def __init__(self, root: Nonterminal, parent: 'ParseTree | None') -> None:
        self.root: Nonterminal = root
        self.children: list[ParseTree | Token | None] = []
        self.parent: ParseTree | None = parent

    def add_child(self, child: 'ParseTree | Token | None') -> None:
        self.children.append(child)

    @staticmethod
    def from_stdin() -> 'ParseTree':
        return ParseTree.from_iter(iter(sys.stdin))

    @staticmethod
    def from_iter(lines: Iterator[str]) -> 'ParseTree':
        starting_nt, _ = get_line(lines)
        if starting_nt is None:
            raise ValueError('[FATAL] Empty file')
        return ParseTree.__from_str_inner(starting_nt, None, lines, depth=0)[0]
    
    @staticmethod
    def __from_str_inner(curr_root: str, parent: 'ParseTree | None', lines: Iterator[str], depth: int) -> 'tuple[ParseTree, str | None, int]':
        tree = ParseTree(Nonterminal(curr_root), parent)
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
                subtree, line, inner_depth = ParseTree.__from_str_inner(line, tree, lines, depth+1)
                tree.add_child(subtree)
                do_next = False
            elif line.startswith('$'):
                tree.add_child(None)
            else:
                tree.add_child(Token.from_str(line))
    
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

def main() -> None:
    tree = ParseTree.from_stdin()

    log(tree)

if __name__ == '__main__':
    main()
