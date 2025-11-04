import sys
from typing import Generator, Set, List, Optional, Iterator, Dict

EPSILON = None
EOF = None

SymbolTable = Dict['Nonterminal', Dict['Nonterminal | Terminal', bool]]
Symbol = Optional['Nonterminal | Terminal']

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class LRItem:

    def __init__(self, right_side: 'RightSide', dot_before_idx: int, context: Set[Optional['Terminal']]) -> None:
        self.right_side = right_side
        self.dot_before_idx = dot_before_idx
        self.context: Set[Optional['Terminal']] = context
        self._repr: Optional[str] = None

    def __repr__(self) -> str:
        if self._repr is not None:
            return self._repr

        result: str = str(self.right_side.left_side) + ' →'

        for i, s in enumerate(self.right_side):
            if i == self.dot_before_idx:
                result += ' •'
            result += f' {str(s)}'

        if self.is_complete():
            result += '•'

        result += ', {'

        sorted_context = sorted(self.context, key=lambda s: str(s) if s is not None else '')
        for s in sorted_context:
            result += f' {str(s)}'

        result += '}'
        
        self._repr = result
        return result

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LRItem):
            return False

        return all({
            self.right_side == other.right_side,
            self.dot_before_idx == other.dot_before_idx,
            self.context == other.context
        })

    def is_complete(self) -> bool:
        return self.dot_before_idx == len(self.right_side._symbols)

class NFAState:
    __last_id = 0

    def __init__(self, lr_item: LRItem) -> None:
        self.id = NFAState.__last_id
        NFAState.__last_id += 1

        self.lr_item = lr_item
        self.transitions: Dict[Symbol, Set[NFAState]] = {}

    def __hash__(self) -> int:
        return hash(self.lr_item)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NFAState):
            return False

        return self.lr_item == other.lr_item

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
    def transition_set(states: Set['NFAState'], symbol: Symbol) -> Set['NFAState']:
        return set.union(*(state.transition(symbol) for state in states)) if states else set()

    def transition(self, symbol: Symbol) -> Set['NFAState']:
        return NFAState.epsilon_set(self.immediate_transition(symbol))

class NFA:

    def __init__(self, states: Set[NFAState], start_state: NFAState, alphabet: Set['Terminal | Nonterminal']) -> None:
        self.states = states
        self.start_state = start_state
        self.alphabet = alphabet

class DFAState:
    __last_id = 0

    def __init__(self, lr_items: Set[LRItem]) -> None:
        self.id = DFAState.__last_id
        DFAState.__last_id += 1

        self.lr_items = lr_items
        self.transitions: Dict[Symbol, 'DFAState'] = {}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, 'DFAState'):
            return False

        return self.lr_items == other.lr_items

    def __hash__(self) -> int:
        return hash(frozenset(self.lr_items))

    def add_transition(self, c: Symbol, other: 'DFAState') -> None:
        self.transitions.setdefault(c, other)

    def transition(self, symbol: Symbol) -> Optional['DFAState']:
        return self.transitions.get(symbol)

class DFA:

    def __init__(self, states: Set[DFAState], start_state: DFAState, alphabet: Set['Terminal | Nonterminal']) -> None:
        self.states = states
        self.start_state = start_state
        self.alphabet = alphabet

class RightSide:

    def __init__(self, *args, left_side: 'Nonterminal', is_epsilon: bool = False, **kwargs) -> None:
        self.left_side: Nonterminal = left_side
        self._symbols: List['Terminal | Nonterminal'] = list(*args, **kwargs)
        self.is_epsilon: bool = is_epsilon
        self.is_nullable: Optional[bool] = None
        self.first: Set[Terminal] = set()
        self.states: List[NFAState] = []

    def __hash__(self) -> int:
        return hash(str(self.left_side) + ';'.join(str(e) for e in self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RightSide):
            return False

        return self.left_side == other.left_side and self._symbols == other._symbols

    def __iter__(self) -> Iterator['Terminal | Nonterminal']:
        return iter(self._symbols)

    def __getitem__(self, index) -> 'Terminal | Nonterminal':
        return self._symbols[index]

    def __repr__(self) -> str:
        return str(self._symbols)

    def append(self, e: 'Terminal | Nonterminal') -> None:
        self._symbols.append(e)

    # def compile_states(self) -> None:
    #     next_state: Optional[NFAState] = None
    #
    #     for idx in range(len(self._symbols), -1, -1):
    #         state = NFAState(LRItem(self, idx))
    #         self.states.append(state)
    #
    #         if next_state is not None:
    #             state.add_transition(self._symbols[idx], next_state)
    #
    #         next_state = state

    @property
    def nonterminal_only(self) -> bool:
        return all(isinstance(e, Nonterminal) for e in self._symbols)

    @staticmethod
    def set_first(symbols: List['Terminal | Nonterminal']) -> Set['Terminal']:
        first: Set['Terminal'] = set()

        for s in symbols:
            if isinstance(s, Terminal):
                first.add(s)

                break
            elif isinstance(s, Nonterminal):
                first.update(s.first)

                if not s.is_empty:
                    break

        return first

    def calculate_first(self) -> None:
        if self.is_epsilon:
            return

        self.first = RightSide.set_first(self._symbols)

class Nonterminal:

    def __init__(self, name: str) -> None:
        self.name = name
        self.right_sides: Set[RightSide] = set()
        self.is_empty: Optional[bool] = None
        self.in_nt_only_production_of: Optional[Set[Nonterminal]] = None
        self.first: Set[Terminal] = set()
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

    def calculate_first(self, table_first: SymbolTable) -> None:
        self.first = {t for t in table_first[self] if isinstance(t, Terminal) and table_first[self][t]}

    def is_in_production_of(self, other: 'Nonterminal') -> bool:
        assert isinstance(self.in_nt_only_production_of, set)
        return other in self.in_nt_only_production_of

    def _mark_empty(self, start: 'Nonterminal') -> bool:
        if self.is_empty is not None:
            return self.is_empty

        for rs in {rs for rs in self.right_sides if rs.nonterminal_only}:
            if rs.is_nullable:
                rs.left_side.is_empty = True
                rs.is_nullable = True
                return True
            elif rs.is_nullable is None:
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

def mark_first(table_starts_directly_with: SymbolTable) -> None:
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
                        right_side.is_nullable = True
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
            if curr.is_empty == False:
                continue

            parents: Set[Nonterminal] = {nt for nt in curr.in_nt_only_production_of if nt.is_empty is None}

            for parent in parents:
                parent.is_empty = parent.mark_empty()
                if parent.is_empty:
                    stack.append(parent)

        for nt in sa.nonterminals:
            if nt.is_empty is None:
                nt.is_empty = False

        table_first: SymbolTable = {}
        for row in sa.nonterminals:
            table_first[row] = {}
            for col in sa.nonterminals | sa.terminals:
                table_first[row][col] = row.starts_directly_with(col)

        assert sa.starting_nonterminal is not None

        mark_first(table_first)

        all_right_sides: Set[RightSide] = set.union(*(nt.right_sides for nt in sa.nonterminals))

        for nt in sa.nonterminals:
            nt.calculate_first(table_first)

        for rs in all_right_sides:
            rs.calculate_first()
            # rs.compile_states()
            # epsilon_nfa_states.update(rs.states)

        # for nt in sa.nonterminals:
        #     nt.cache_states(all_right_sides)

        nfa: NFA  = SAUtils.construct_epislon_nfa(sa.nonterminals, sa.terminals, sa.starting_nonterminal)

        # epsilon_nfa_states: Set[NFAState] = set()
        #
        # for state in epsilon_nfa_states:
        #     if state.lr_item.is_complete():
        #         continue
        #
        #     symbol = state.lr_item.right_side[state.lr_item.dot_before_idx]
        #
        #     if isinstance(symbol, Nonterminal):
        #         for destination_state in symbol.states:
        #             state.add_epsilon(destination_state)
        #
        # start_state = NFAState(LRItem(RightSide(left_side=sa.starting_nonterminal), 0))
        #
        # for s in {rs.states[-1] for rs in sa.starting_nonterminal.right_sides}:
        #     start_state.add_epsilon(s)
        #
        # epsilon_nfa_states.add(start_state)

        # epislon_nfa = NFA(epsilon_nfa_states, start_state, sa.nonterminals | sa.terminals)
        #
        # start_lr_items: Set[LRItem] = {
        #     state.lr_item
        #     for state in epislon_nfa.states
        #     if state is not epislon_nfa.start_state
        #         and state.lr_item.right_side.left_side == sa.starting_nonterminal
        #         and state.lr_item.dot_before_idx == 0
        # }
        #
        # for lr_item in start_lr_items:
        #     lr_item.context = {EOF}
        #
        # log(start_lr_items)
        #
        # dfa: DFA = SAUtils.epsilon_nfa_to_dfa(epislon_nfa)
        #
        # log(len(dfa.states))

        # draw_automaton(nfa.states)
        log(len(nfa.states))

        return sa

    @staticmethod
    def construct_epislon_nfa(nonterminals: Set[Nonterminal], terminals: Set[Terminal], starting_nonterminal: Nonterminal) -> NFA:
        start_state = NFAState(LRItem(RightSide(left_side=starting_nonterminal), 0, set()))

        queue: List[NFAState] = []
        created: Dict[str, NFAState] = {str(start_state.lr_item) : start_state}

        for rs in starting_nonterminal.right_sides:
            new_state = NFAState(
                LRItem(rs, 0, {EOF})
            )

            start_state.add_epsilon(new_state)

            created[str(new_state.lr_item)] = new_state
            queue.append(new_state)

        while queue:
            state: NFAState = queue.pop(0)
            lr_item = state.lr_item

            if lr_item.is_complete():
                continue

            symbol_at_idx = lr_item.right_side[lr_item.dot_before_idx]

            state2 = NFAState(
                LRItem(
                    lr_item.right_side,
                    lr_item.dot_before_idx + 1,
                    lr_item.context
                )
            )

            state.add_transition(symbol_at_idx, state2)

            state2_key = str(state2.lr_item)
            if state2_key not in created:
                created[state2_key] = state2
                queue.append(state2)

            if isinstance(symbol_at_idx, Terminal):
                continue

            beta: List[Terminal | Nonterminal] = lr_item.right_side._symbols[lr_item.dot_before_idx+1:]

            context: Set[Optional[Terminal]] = {s for s in RightSide.set_first(beta)}

            beta_is_nullable: bool = not any(s for s in beta if isinstance(s, Terminal) or (isinstance(s, Nonterminal) and not s.is_empty))

            if beta_is_nullable:
                context |= lr_item.context

            for rs in symbol_at_idx.right_sides:
                new_state = NFAState(LRItem(rs, 0, context))

                key = str(new_state.lr_item)

                if key in created:
                    found_state = created[key]
                else:
                    created[key] = new_state
                    found_state = new_state
                    queue.append(found_state)

                state.add_epsilon(found_state)

        return NFA(set(created.values()), start_state, nonterminals | terminals)

    @staticmethod
    def epsilon_nfa_to_dfa(epsilon_nfa: NFA) -> DFA:
        nfa_states: Dict[int, NFAState] = {}

        for state in epsilon_nfa.states:
            new_state = NFAState(state.lr_item)
            nfa_states[state.id] = new_state

        for state in epsilon_nfa.states:
            new_state = nfa_states[state.id]

            for symbol in epsilon_nfa.alphabet:
                for next_state in NFAState.transition_set(state.epsilon(), symbol):
                    new_state.add_transition(symbol, nfa_states[next_state.id])

        nfa = NFA(set(nfa_states.values()), nfa_states[epsilon_nfa.start_state.id], epsilon_nfa.alphabet)

        epsilon_nfa_real_start_states: Set[NFAState] = epsilon_nfa.start_state.epsilon() - {epsilon_nfa.start_state}
        nfa_real_start_states: Set[NFAState] = {nfa_states[state.id] for state in epsilon_nfa_real_start_states} 

        start_state = DFAState({state.lr_item for state in nfa_real_start_states})
        dfa = DFA({start_state}, start_state, nfa.alphabet)

        queue: List[frozenset[NFAState]] = [frozenset(nfa_real_start_states)]
        discovered_states: Set[DFAState] = {start_state}

        state_dict: Dict[frozenset[NFAState], DFAState] = {frozenset(nfa_real_start_states) : start_state}

        while queue:
            current_states: frozenset[NFAState] = queue.pop(0)
            currect_dfa_state = state_dict[current_states]

            for symbol in dfa.alphabet:
                next_states: frozenset[NFAState] = frozenset(NFAState.transition_set(set(current_states), symbol))

                state_dict.setdefault(next_states, DFAState({next_state.lr_item for next_state in next_states}))
                dfa_state = state_dict[next_states]

                if dfa_state not in discovered_states:
                    discovered_states.add(dfa_state)
                    queue.append(frozenset(next_states))

                currect_dfa_state.add_transition(symbol, dfa_state)

        dfa.states.update(discovered_states)

        return dfa

def draw_automaton(states: Set['NFAState | DFAState'], filename: str = "automaton"):
    """Draw automaton using Graphviz for publication-quality output.
    Works with both NFA and DFA states."""
    try:
        from graphviz import Digraph
    except ImportError:
        print("Install graphviz: pip install graphviz")
        return
    
    def escape_label(text: str) -> str:
        """Escape special characters for Graphviz DOT format"""
        return text.replace('\\', '\\\\').replace('"', '\\"').replace('<', '\\<').replace('>', '\\>')
    
    # Detect state type from first state
    if not states:
        log("No states to draw")
        return
    
    first_state = next(iter(states))
    is_dfa = isinstance(first_state, DFAState)
    
    dot = Digraph(comment='Automaton')
    dot.attr(rankdir='LR')  # Left to right layout
    
    # Add invisible start node for the start arrow
    dot.node('', shape='none', width='0')
    
    # Add all states with properly escaped labels
    for state in states:
        if is_dfa:
            # DFA states contain multiple LR items
            label_parts = [escape_label(str(item)) for item in state.lr_items]
            label = '\\n'.join(label_parts) if label_parts else f'State {state.id}'
        else:
            # NFA states contain a single LR item
            label = escape_label(str(state.lr_item))
        
        dot.node(str(state.id), label=label, shape='circle')
    
    # Group transitions between same states
    transitions_map = {}
    
    for state in states:
        if is_dfa:
            # DFA: transitions is Dict[Symbol, DFAState]
            for symbol, target_state in state.transitions.items():
                edge_key = (state.id, target_state.id)
                display_symbol = 'ε' if symbol is None else str(symbol)
                
                if edge_key in transitions_map:
                    transitions_map[edge_key].append(display_symbol)
                else:
                    transitions_map[edge_key] = [display_symbol]
        else:
            # NFA: transitions is Dict[Symbol, Set[NFAState]]
            for symbol, target_states in state.transitions.items():
                for target in target_states:
                    edge_key = (state.id, target.id)
                    display_symbol = 'ε' if symbol is None else str(symbol)
                    
                    if edge_key in transitions_map:
                        transitions_map[edge_key].append(display_symbol)
                    else:
                        transitions_map[edge_key] = [display_symbol]
    
    # Add edges with combined labels (properly escaped)
    for (from_id, to_id), symbols in transitions_map.items():
        label = ', '.join(sorted(symbols, key=str))
        label = escape_label(label)
        dot.edge(str(from_id), str(to_id), label=label)
    
    # Render the graph
    dot.render(filename, view=True, format='png', cleanup=True)
    log(f"Saved to {filename}.png")
    
    return dot

def main() -> None:
    sa: SA = SAUtils.from_stdin()
    # log(sa.to_bnf())

if __name__ == '__main__':
    main()
