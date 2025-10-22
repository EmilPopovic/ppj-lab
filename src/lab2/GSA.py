import sys
from typing import Generator, Set, List, Optional

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class RightSide:

    def __init__(self, *args, left_side: 'Nontermial', is_epsilon: bool = False, **kwargs) -> None:
        self.left_side: Nontermial = left_side
        self._items = list(*args, **kwargs)
        self.is_epsilon: bool = is_epsilon
        self.is_empty: Optional[bool] = None

    def __hash__(self) -> int:
        return hash(str(self.left_side) + ';'.join(str(e) for e in self))
    
    def __iter__(self):
        return iter(self._items)
    
    def __getitem__(self, index) -> 'Terminal | Nontermial':
        return self._items[index]
    
    def __repr__(self) -> str:
        return str(self._items)
    
    def append(self, e: 'Terminal | Nontermial') -> None:
        self._items.append(e)

    @property
    def nonterminal_only(self) -> bool:
        return all(isinstance(e, Nontermial) for e in self._items)

class Nontermial:
    
    def __init__(self, name: str) -> None:
        self.name = name
        self.right_sides: Set[RightSide] = set()
        self.is_empty: Optional[bool] = None
        self.in_nt_only_production_of: Optional[Set[Nontermial]] = None

    def __hash__(self) -> int:
        return hash(self.name)
    
    def __repr__(self) -> str:
        return f'<{self.name}>'

    def to_bnf(self) -> str:
        out = f'{str(self)}{"*" if self.is_empty else ""} ::= '
        for p in self.right_sides:
            if p.is_epsilon:
                out += '""'
            else:
                out += ' '.join([str(e) for e in p])
            out += ' | '
        out = out.strip(' |')
        return out
    
    def calculate_in_nt_only_production_of(self, nonterminals: Set['Nontermial']) -> None:
        self.in_nt_only_production_of = {
            nt for nt in nonterminals if
            any(
                any(nt_in_p == self for nt_in_p in p) for p in nt.right_sides if p.nonterminal_only
            )
        }
    
    def is_in_production_of(self, other: 'Nontermial') -> bool:
        assert isinstance(self.in_nt_only_production_of, set)
        return other in self.in_nt_only_production_of
    
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
    
def mark_empty(nonterminal: Nontermial) -> bool:
    if nonterminal.is_empty is not None:
        return nonterminal.is_empty
    
    log(f'Provjeravam {nonterminal}')
    if nonterminal.is_empty:
        log(f'{nonterminal} je trivijalan slučaj')
        return True
    
    right_sides: Set[RightSide] = {rs for rs in nonterminal.right_sides if rs.nonterminal_only}
    log(f'Desne strane: {right_sides}')
    
    for rs in right_sides:
        if rs.is_empty:
            rs.left_side.is_empty = True
            rs.is_empty = True
            return True
        elif rs.is_empty is None:
            return all(mark_empty(nt) for nt in rs)
        else:
            continue

    return False

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
                assert isinstance(current_nonterminal, Nontermial)
                elem_strs: List[str] = row.strip(' ').split(' ')
                right_side: RightSide = RightSide(left_side=current_nonterminal)

                for e in elem_strs:
                    if e == '$':
                        right_side.is_epsilon = True
                        right_side.is_empty = True
                        current_nonterminal.is_empty = True
                        break
                    elif e.startswith('<'):
                        right_side.append(sa.get_nonterminal(e[1:-1]))
                    else:
                        right_side.append(sa.get_terminal(e))

                assert isinstance(current_nonterminal, Nontermial)
                current_nonterminal.right_sides.add(right_side)

        for nt in sa.nonterminals:
            nt.calculate_in_nt_only_production_of(sa.nonterminals)

        stack: list[Nontermial] = [n for n in sa.nonterminals if n.is_empty]
        log(f'Trivijalni: {stack}')
        
        while stack:
            curr = stack.pop()
            assert curr.in_nt_only_production_of is not None
            if curr.is_empty == False:  # noqa: E712
                continue

            log(f'{curr} je prazan, gledam roditelje')
            parents: Set[Nontermial] = {nt for nt in curr.in_nt_only_production_of if nt.is_empty is None}
            log(f'Roditelji od {str(curr)}: {parents}')

            for parent in parents:
                parent.is_empty = mark_empty(parent)
                if parent.is_empty:
                    log(f'Roditelj {parent} od {curr} je prazan')
                    stack.append(parent)           

        for nt in sa.nonterminals:
            if nt.is_empty is None:
                nt.is_empty = False

        return sa

def main() -> None:
    sa: SA = SAUtils.from_stdin()
    log(sa.to_bnf())

if __name__ == '__main__':
    main()
