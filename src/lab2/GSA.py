import sys
from typing import Generator, Set, List, Optional, Iterator, Dict

SymbolTable = Dict['Nonterminal', Dict['Nonterminal | Terminal', bool]]

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class RightSide:

    def __init__(self, *args, left_side: 'Nonterminal', is_epsilon: bool = False, **kwargs) -> None:
        self.left_side: Nonterminal = left_side
        self._items = list(*args, **kwargs)
        self.is_epsilon: bool = is_epsilon
        self.is_empty: Optional[bool] = None

    def __hash__(self) -> int:
        return hash(str(self.left_side) + ';'.join(str(e) for e in self))
    
    def __iter__(self) -> Iterator['Terminal | Nonterminal']:
        return iter(self._items)
    
    def __getitem__(self, index) -> 'Terminal | Nonterminal':
        return self._items[index]
    
    def __repr__(self) -> str:
        return str(self._items)
    
    def append(self, e: 'Terminal | Nonterminal') -> None:
        self._items.append(e)

    @property
    def nonterminal_only(self) -> bool:
        return all(isinstance(e, Nonterminal) for e in self._items)

class Nonterminal:
    
    def __init__(self, name: str) -> None:
        self.name = name
        self.right_sides: Set[RightSide] = set()
        self.is_empty: Optional[bool] = None
        self.in_nt_only_production_of: Optional[Set[Nonterminal]] = None

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
    
    def calculate_in_nt_only_production_of(self, nonterminals: Set['Nonterminal']) -> None:
        self.in_nt_only_production_of = {
            nt for nt in nonterminals if
            any(
                any(nt_in_p == self for nt_in_p in p) for p in nt.right_sides if p.nonterminal_only
            )
        }
    
    def is_in_production_of(self, other: 'Nonterminal') -> bool:
        assert isinstance(self.in_nt_only_production_of, set)
        return other in self.in_nt_only_production_of
    
    def _mark_empty(self, start: 'Nonterminal') -> bool:
        if self.is_empty is not None:
            return self.is_empty

        for rs in {rs for rs in self.right_sides if rs.nonterminal_only}:
            if rs.is_empty:
                rs.left_side.is_empty = True
                rs.is_empty = True
                return True
            elif rs.is_empty is None:
                return all(nt._mark_empty(start) for nt in rs if isinstance(nt, Nonterminal) and nt is not start)
        
        return False

    def mark_empty(self) -> bool:
        return self._mark_empty(start=self)
    
    def starts_directly_with(self, other: 'Nonterminal | Terminal') -> bool:
        for rs in self.right_sides:
            if rs.is_epsilon:
                continue
            
            i = 0
            while i < len(rs._items) and isinstance(rs[i], Nonterminal) and rs[i].is_empty: # pyright: ignore[reportAttributeAccessIssue]
                if rs[i] == other:
                    return True
                i += 1

            if i == len(rs._items):
                continue
            elif rs[i] == other:
                return True

        return False

def mark_starts_with(table_starts_directly_with: SymbolTable) -> None:
    for row, row_dict in table_starts_directly_with.items():
        for col in row_dict:
            if row == col:
                row_dict[col] = True

            elif isinstance(col, Nonterminal) and row_dict[col]:
                for col2 in table_starts_directly_with[col]:
                    if table_starts_directly_with[col][col2]:
                        row_dict[col2] = True

def print_sym_table(table: SymbolTable) -> None:
    all_symbols = set()
    for row_symbol in table:
        all_symbols.add(row_symbol)
        for col_symbol in table[row_symbol]:
            all_symbols.add(col_symbol)

    nonterminals = sorted([s for s in all_symbols if type(s).__name__ == 'Nonterminal'], 
                         key=lambda s: s.name)
    terminals = sorted([s for s in all_symbols if type(s).__name__ == 'Terminal'], 
                      key=lambda s: s.name)

    columns = nonterminals + terminals

    def display_name(symbol):
        if type(symbol).__name__ == 'Nonterminal':
            return f'<{symbol.name}>'
        return symbol.name

    col_width = max(len(display_name(s)) for s in columns) + 2

    print(' ' * col_width, end='')
    for col in columns:
        print(f'{display_name(col):>{col_width}}', end='')
    print()

    for row in nonterminals + terminals:
        if row in table:
            print(f'{display_name(row):<{col_width}}', end='')
            for col in columns:
                if col in table[row] and table[row][col]:
                    print(f'{"1":>{col_width}}', end='')
                else:
                    print(' ' * col_width, end='')
            print()


    
class Terminal:

    def __init__(self, name: str) -> None:
        self.name: str = name

    def __repr__(self) -> str:
        return self.name

class SA:
    
    def __init__(self) -> None:
        self.starting_nonterminal: Optional[Nonterminal] = None
        self.nonterminals: Set[Nonterminal] = set()
        self.terminals: Set[Terminal] = set()
        self.sync_symbols: Set[Terminal] = set()

    def get_nonterminal(self, name: str) -> Nonterminal:
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
        current_nonterminal: Optional[Nonterminal] = None

        for row in data:
            if row.startswith('%V'):
                _, *nonterminals_list = row.split(' ')
                sa.nonterminals = {Nonterminal(n[1:-1]) for n in nonterminals_list}
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
                assert isinstance(current_nonterminal, Nonterminal)
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

                assert isinstance(current_nonterminal, Nonterminal)
                current_nonterminal.right_sides.add(right_side)

        for nt in sa.nonterminals:
            nt.calculate_in_nt_only_production_of(sa.nonterminals)

        stack: list[Nonterminal] = [n for n in sa.nonterminals if n.is_empty]
        
        while stack:
            curr = stack.pop()
            assert curr.in_nt_only_production_of is not None
            if curr.is_empty == False:  # noqa: E712
                continue

            parents: Set[Nonterminal] = {nt for nt in curr.in_nt_only_production_of if nt.is_empty is None}

            for parent in parents:
                parent.is_empty = parent.mark_empty()
                if parent.is_empty:
                    stack.append(parent)           

        for nt in sa.nonterminals:
            if nt.is_empty is None:
                nt.is_empty = False

        table_starts_directly_with: SymbolTable = {}
        for row in sa.nonterminals:
            table_starts_directly_with[row] = {}
            for col in sa.nonterminals | sa.terminals:
                table_starts_directly_with[row][col] = row.starts_directly_with(col)

        print_sym_table(table_starts_directly_with)

        mark_starts_with(table_starts_directly_with)

        print_sym_table(table_starts_directly_with)

        # table_starts_with: SymbolTable = {}
        # for row in sa.nonterminals:
        #     for col in sa.nonterminals | sa.terminals:
        #         table_starts_with[row][col] = row.starts_with(col, table_starts_directly_with)

        return sa

def main() -> None:
    sa: SA = SAUtils.from_stdin()
    log(sa.to_bnf())

if __name__ == '__main__':
    main()
