import sys
from typing import Generator, Set, List, Optional

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class Production:

    def __init__(self, *args, is_epsilon: bool = False, **kwargs) -> None:
        self._items = list(*args, **kwargs)
        self.is_epsilon = is_epsilon

    def __hash__(self) -> int:
        return hash(';'.join(str(e) for e in self._items))
    
    def __iter__(self):
        return iter(self._items)
    
    def __getitem__(self, index) -> 'Terminal | Nontermial':
        return self._items[index]
    
    def append(self, e: 'Terminal | Nontermial') -> None:
        self._items.append(e)

class Nontermial:
    
    def __init__(self, name: str) -> None:
        self.name = name
        self.productions: Set[Production] = set()

    def __hash__(self) -> int:
        return hash(self.name)
    
    def __repr__(self) -> str:
        return f'<{self.name}>'

    def to_bnf(self) -> str:
        out = f'{str(self)} ::= '
        for p in self.productions:
            if p is None:
                out += '""'
            else:
                out += ' '.join([str(e) for e in p])
            out += ' | '
        out = out.strip(' |')
        return out
    
class Terminal:

    def __init__(self, name: str) -> None:
        self.name: str = name

    def __repr__(self) -> str:
        return self.name

class SA:
    
    def __init__(self) -> None:
        self.starting_nonterminal: Optional[Nontermial] = None
        self.nonterminals: Set[Nontermial] = set()
        self.terminals: Set[Terminal] = set()
        self.sync_symbols: Set[Terminal] = set()

    def get_nonterminal(self, name: str) -> Nontermial:
        nonterms = [n for n in self.nonterminals if n.name == name]
        assert len(nonterms) == 1
        return nonterms[0]

    def get_terminal(self, name: str) -> Terminal:
        terms = [t for t in self.terminals if t.name == name]
        assert len(terms) == 1
        return terms[0]
    
    def to_bnf(self) -> str:
        return '\n'.join(n.to_bnf() for n in self.nonterminals)

class SAUtils:

    @staticmethod
    def from_stdin() -> SA:
        def read_input() -> Generator[str, None, None]:
            while True:
                try:
                    yield input()
                except EOFError:
                    break

        sa = SA()
        data = read_input()
        current_nonterminal: Optional[Nontermial] = None

        for row in data:
            if row.startswith('%V'):
                _, *nonterminals_list = row.split(' ')
                sa.nonterminals = {Nontermial(n[1:-1]) for n in nonterminals_list}
                sa.starting_nonterminal = sa.get_nonterminal(nonterminals_list[0][1:-1])

            elif row.startswith('%T'):
                _, *terminals_list = row.split(' ')
                sa.terminals = {Terminal(t) for t in terminals_list}

            elif row.startswith('%Syn'):
                _, *sync_list = row.split(' ')
                sa.sync_symbols = {t for t in sa.terminals if t.name in sync_list}

            elif row.startswith('<'):
                current_nonterminal = sa.get_nonterminal(row[1:-1])

            elif row.startswith(' '):
                elem_strs: List[str] = row.strip(' ').split(' ')
                production: Production = Production()

                for e in elem_strs:
                    if e == '$':
                        production.is_epsilon = True
                        break
                    elif e.startswith('<'):
                        production.append(sa.get_nonterminal(e[1:-1]))
                    else:
                        production.append(sa.get_terminal(e))

                assert isinstance(current_nonterminal, Nontermial)
                current_nonterminal.productions.add(production)

        return sa

def main() -> None:
    sa: SA = SAUtils.from_stdin()
    print(sa.to_bnf())

if __name__ == '__main__':
    main()
