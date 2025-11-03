from os import stat
import sys
from typing import Generator, Set, List, Optional, Iterator, Dict

EPSILON = None

SymbolTable = Dict['Nonterminal', Dict['Nonterminal | Terminal', bool]]
Symbol = Optional['Nonterminal | Terminal']

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)


class LRItem:

    def __init__(self, right_side: 'RightSide', dot_before_idx: int) -> None:
        self.right_side = right_side
        self.dot_before_idx = dot_before_idx

    def __repr__(self) -> str:
        result: str = str(self.right_side.left_side) + ' →'

        for i, s in enumerate(self.right_side):
            if i == self.dot_before_idx:
                result += ' •'

            result += f' {str(s)}'

        if self.is_complete():
            result += '•'

        return result


    def is_complete(self) -> bool:
        return self.dot_before_idx == len(self.right_side._symbols)

class NFAState:
    __last_id = 0

    def __init__(self, lr_item: LRItem) -> None:
        self.id = NFAState.__last_id
        NFAState.__last_id += 1

        self.lr_item = lr_item
        self.transitions: Dict[Symbol, Set[NFAState]] = {}

    def immediate_transition(self, symbol: Symbol) -> Set['NFAState']:
        return self.transitions.get(symbol, set())

    def add_epsilon(self, other: 'NFAState') -> None:
        epsilon = self.transitions.get(EPSILON, set())
        epsilon.add(other)
        self.transitions.setdefault(EPSILON, epsilon)

    def add_transition(self, c: Symbol, other: 'NFAState') -> None:
        next_states = self.transitions.get(c, set())
        next_states.add(other)
        self.transitions.setdefault(c, next_states)

    @staticmethod
    def epsilon_set(states: Set['NFAState']) -> Set['NFAState']:
        epsilon = set(states)
        stack = list(states)

        while stack:
            state = stack.pop()
            for next_state in state.immediate_transition(EPSILON):
                if next_state not in epsilon:
                    epsilon.add(next_state)
                    stack.append(next_state)

        return epsilon

    def epsilon(self) -> Set['NFAState']:
        return NFAState.epsilon_set({self})

    @staticmethod
    def transition_set(states: Set['NFAState'], token: Symbol) -> Set['NFAState']:
        return set.union(*(state.transition(token) for state in states)) if states else set()

    def transition(self, token: Symbol) -> Set['NFAState']:
        return NFAState.epsilon_set(self.immediate_transition(token))


class RightSide:

    def __init__(self, *args, left_side: 'Nonterminal', is_epsilon: bool = False, **kwargs) -> None:
        self.left_side: Nonterminal = left_side
        self._symbols = list(*args, **kwargs)
        self.is_epsilon: bool = is_epsilon
        self.is_empty: Optional[bool] = None
        self.starts_with: Set[Terminal] = set()
        self.states: List[NFAState] = []

    def __hash__(self) -> int:
        return hash(str(self.left_side) + ';'.join(str(e) for e in self))

    def __iter__(self) -> Iterator['Terminal | Nonterminal']:
        return iter(self._symbols)

    def __getitem__(self, index) -> 'Terminal | Nonterminal':
        return self._symbols[index]

    def __repr__(self) -> str:
        return str(self._symbols)

    def append(self, e: 'Terminal | Nonterminal') -> None:
        self._symbols.append(e)

    def compile_states(self) -> None:
        next_state: Optional[NFAState] = None

        for idx in range(len(self._symbols), -1, -1):
            state = NFAState(LRItem(self, idx))
            self.states.append(state)

            if next_state is not None:
                state.add_transition(self._symbols[idx], next_state)

            next_state = state

    @property
    def nonterminal_only(self) -> bool:
        return all(isinstance(e, Nonterminal) for e in self._symbols)

    def calculate_starts_with(self) -> None:
        if self.is_epsilon:
            return

        for s in self:
            if isinstance(s, Terminal):
                self.starts_with.add(s)
                return
            elif isinstance(s, Nonterminal):
                self.starts_with.update(s.starts_with)

                if not s.is_empty:
                    return

class Nonterminal:

    def __init__(self, name: str) -> None:
        self.name = name
        self.right_sides: Set[RightSide] = set()
        self.is_empty: Optional[bool] = None
        self.in_nt_only_production_of: Optional[Set[Nonterminal]] = None
        self.starts_with: Set[Terminal] = set()
        self.states: Set[NFAState] = set()

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

    def cache_states(self, all_right_sides: Set[RightSide]) -> None:
        self.states = {rs.states[-1] for rs in all_right_sides if rs.left_side == self}

    def calculate_starts_with(self, table_starts_with: SymbolTable) -> None:
        self.starts_with = {t for t in table_starts_with[self] if isinstance(t, Terminal) and table_starts_with[self][t]}

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
            while i < len(rs._symbols) and isinstance(rs[i], Nonterminal) and rs[i].is_empty: # pyright: ignore[reportAttributeAccessIssue]
                if rs[i] == other:
                    return True
                i += 1

            if i == len(rs._symbols):
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

    log(' ' * col_width, end='')
    for col in columns:
        log(f'{display_name(col):>{col_width}}', end='')
    log()

    for row in nonterminals + terminals:
        if row in table:
            log(f'{display_name(row):<{col_width}}', end='')
            for col in columns:
                if col in table[row] and table[row][col]:
                    log(f'{"1":>{col_width}}', end='')
                else:
                    log(' ' * col_width, end='')
            log()


    
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

        table_starts_with: SymbolTable = {}
        for row in sa.nonterminals:
            table_starts_with[row] = {}
            for col in sa.nonterminals | sa.terminals:
                table_starts_with[row][col] = row.starts_directly_with(col)

        mark_starts_with(table_starts_with)

        epsilon_nfa_states: Set[NFAState] = set()

        all_right_sides: Set[RightSide] = set.union(*(nt.right_sides for nt in sa.nonterminals))

        for nt in sa.nonterminals:
            nt.calculate_starts_with(table_starts_with)

        for rs in all_right_sides:
            rs.calculate_starts_with()
            rs.compile_states()
            epsilon_nfa_states.update(rs.states)

        for nt in sa.nonterminals:
            nt.cache_states(all_right_sides)

        for state in epsilon_nfa_states:
            if state.lr_item.is_complete():
                continue

            symbol = state.lr_item.right_side[state.lr_item.dot_before_idx]

            print(symbol)

            if isinstance(symbol, Nonterminal):
                print(symbol.states)
                for destination_state in symbol.states:
                    state.add_epsilon(destination_state)

        return sa

def main() -> None:
    sa: SA = SAUtils.from_stdin()
    log(sa.to_bnf())

if __name__ == '__main__':
    main()
