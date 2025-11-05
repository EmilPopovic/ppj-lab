import sys
import hashlib
from enum import Enum
from abc import ABC
from collections import deque
from typing import Generator, Set, List, Optional, Iterator, Dict, Tuple

EPSILON = None
EOF = None

def deterministic_hash(s: str) -> int:
    return int.from_bytes(hashlib.md5(s.encode('utf-8')).digest(), 'big')

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
        return deterministic_hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LRItem):
            return False

        return all({
            self.right_side == other.right_side,
            self.dot_before_idx == other.dot_before_idx,
            self.context == other.context
        })

    def is_complete(self) -> bool:
        return self.dot_before_idx == len(self.right_side.symbols)

class NFAState:
    __last_id = 0

    def __init__(self, lr_item: LRItem) -> None:
        self.id = NFAState.__last_id
        NFAState.__last_id += 1

        self.lr_item = lr_item
        self.moves: Dict[Symbol, Set[NFAState]] = {}

    def __hash__(self) -> int:
        return deterministic_hash(str(self.lr_item))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NFAState):
            return False

        return self.lr_item == other.lr_item

    def immediate_move(self, symbol: Symbol) -> Set['NFAState']:
        return self.moves.get(symbol, set())

    def add_epsilon(self, other: 'NFAState') -> None:
        epsilon = self.moves.get(EPSILON, set())
        epsilon.add(other)
        self.moves.setdefault(EPSILON, epsilon)

    def add_move(self, c: Symbol, other: 'NFAState') -> None:
        next_states = self.moves.get(c, set())
        next_states.add(other)
        self.moves.setdefault(c, next_states)

    @staticmethod
    def epsilon_set(states: Set['NFAState']) -> Set['NFAState']:
        epsilon = set(states)
        stack = list(states)

        while stack:
            state = stack.pop()
            for next_state in state.immediate_move(EPSILON):
                if next_state not in epsilon:
                    epsilon.add(next_state)
                    stack.append(next_state)

        return epsilon

    def epsilon(self) -> Set['NFAState']:
        return NFAState.epsilon_set({self})

    @staticmethod
    def move_set(states: Set['NFAState'], symbol: Symbol) -> Set['NFAState']:
        return set.union(*(state.move(symbol) for state in states)) if states else set()

    def move(self, symbol: Symbol) -> Set['NFAState']:
        return NFAState.epsilon_set(self.immediate_move(symbol))

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
        self.moves: Dict[Symbol, 'DFAState'] = {}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DFAState):
            return False

        return self.lr_items == other.lr_items

    def __hash__(self) -> int:
        return deterministic_hash(str(sorted(list(self.lr_items), key=str)))

    def add_move(self, c: Symbol, other: 'DFAState') -> None:
        self.moves.setdefault(c, other)

    def move(self, symbol: Symbol) -> Optional['DFAState']:
        return self.moves.get(symbol)

class DFA:

    def __init__(self, states: Set[DFAState], start_state: DFAState, alphabet: Set['Terminal | Nonterminal']) -> None:
        self.states = states
        self.start_state = start_state
        self.alphabet = alphabet

class RightSide:
    __last_id = 0

    def __init__(self, *args, left_side: 'Nonterminal', is_epsilon: bool = False, **kwargs) -> None:
        self.id = RightSide.__last_id
        RightSide.__last_id += 1

        self.left_side: Nonterminal = left_side
        self.symbols: List['Terminal | Nonterminal'] = list(*args, **kwargs)
        self.is_epsilon: bool = is_epsilon
        self.is_nullable: Optional[bool] = None
        self.first: Set[Terminal] = set()
        self.states: List[NFAState] = []

    def __hash__(self) -> int:
        return deterministic_hash(str(self.left_side) + ';'.join(str(e) for e in self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RightSide):
            return False

        return self.left_side == other.left_side and self.symbols == other.symbols

    def __iter__(self) -> Iterator['Terminal | Nonterminal']:
        return iter(self.symbols)

    def __getitem__(self, index) -> 'Terminal | Nonterminal':
        return self.symbols[index]

    def __repr__(self) -> str:
        return str(self.symbols)

    def append(self, e: 'Terminal | Nonterminal') -> None:
        self.symbols.append(e)

    @property
    def nonterminal_only(self) -> bool:
        return all(isinstance(e, Nonterminal) for e in self.symbols)

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

        self.first = RightSide.set_first(self.symbols)

class Nonterminal:

    def __init__(self, name: str) -> None:
        self.name = name
        self.right_sides: Set[RightSide] = set()
        self._right_sides_list: Optional[List[RightSide]] = None
        self.is_empty: Optional[bool] = None
        self.in_nt_only_production_of: Optional[Set[Nonterminal]] = None
        self.first: Set[Terminal] = set()
        self.states: Set[NFAState] = set()

    def __hash__(self) -> int:
        return deterministic_hash(self.name)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Nonterminal):
            return False
        return self.name == other.name

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

    @property
    def right_sides_list(self) -> List[RightSide]:
        if self._right_sides_list is None:
            self._right_sides_list = sorted(list(self.right_sides), key=str)

        return self._right_sides_list

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

    def immediate_first(self, other: 'Nonterminal | Terminal') -> bool:
        for rs in self.right_sides:
            if rs.is_epsilon:
                continue

            i = 0
            while i < len(rs.symbols) and isinstance(rs[i], Nonterminal) and rs[i].is_empty: # pyright: ignore[reportAttributeAccessIssue]
                if rs[i] == other:
                    return True
                i += 1

            if i == len(rs.symbols):
                continue
            elif rs[i] == other:
                return True

        return False

def mark_first(table_directly_first: SymbolTable) -> None:
    for row, row_dict in table_directly_first.items():
        for col in row_dict:
            if row == col:
                row_dict[col] = True

            elif isinstance(col, Nonterminal) and row_dict[col]:
                for col2 in table_directly_first[col]:
                    if table_directly_first[col][col2]:
                        row_dict[col2] = True

def print_sym_table(table: SymbolTable) -> None:
    all_symbols = set()
    for row_symbol in table:
        all_symbols.add(row_symbol)
        for col_symbol in table[row_symbol]:
            all_symbols.add(col_symbol)

    nonterminals = sorted(
        [s for s in all_symbols if type(s).__name__ == 'Nonterminal'], 
        key=lambda s: s.name
    )
    terminals = sorted(
        [s for s in all_symbols if type(s).__name__ == 'Terminal'], 
        key=lambda s: s.name
    )

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
    
    def __hash__(self) -> int:
        return deterministic_hash(self.name)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Terminal):
            return False
        return self.name == other.name
    
class SAActionType(str, Enum):
    SHIFT = 'shift'
    REDUCE = 'reduce'
    ACCEPT = 'accept'
    REJECT = 'reject'

class SAAction(ABC):
    type: SAActionType

class SAActionShift(SAAction):
    type = SAActionType.SHIFT

    def __init__(self, state: DFAState) -> None:
        super().__init__()
        self.state = state

class SAActionReduce(SAAction):
    type = SAActionType.REDUCE

    def __init__(self, reduction: RightSide) -> None:
        super().__init__()
        self.reduction = reduction

class SAActionAccept(SAAction):
    type = SAActionType.ACCEPT

    def __init__(self) -> None:
        super().__init__()

class SAActionReject(SAAction):
    type = SAActionType.REJECT

    def __init__(self) -> None:
        super().__init__()

class Token:

    def __init__(self, type: Terminal, line_number: int, source: str) -> None:
        self.type: Terminal = type
        self.line_number: int = line_number
        self.source: str = source

    def __repr__(self) -> str:
        return f'{self.type} {self.line_number} {self.source}'

class AST:

    def __init__(self, root: Nonterminal, parent: 'Optional[AST]' = None) -> None:
        self.root: Nonterminal = root
        self.children: deque[AST | Optional[Token]] = deque()
        self.parent: Optional[AST] = parent

    def __repr__(self) -> str:
        return self.__repr(0).strip()

    def __repr(self, indent: int) -> str:
        indent_str: str = ' ' * indent
        result = f'{indent_str}{self.root}\n'

        for child in self.children:
            if child is None:
                result += f'{indent_str} $\n'
            elif isinstance(child, Token):
                result += f'{indent_str} {child}\n'
            else:
                result += child.__repr(indent + 1)
    
        return result

class SA:

    def __init__(self) -> None:
        self.starting_nonterminal: Optional[Nonterminal] = None
        self.nonterminals: Set[Nonterminal] = set()
        self.terminals: Set[Terminal] = set()
        self.sync_symbols: Set[Terminal] = set()

        self.starting_state: Optional[DFAState] = None

        self.table_action: Dict[DFAState, Dict[Optional[Terminal], SAAction]] = {}
        self.table_new_state: Dict[DFAState, Dict[Nonterminal, Optional[DFAState]]] = {}

    def parse_from_stdin(self) -> AST:
        return self.parse_from_string(sys.stdin.read())
        
    def parse_from_file(self, filename: str) -> AST:
        with open(filename, 'r') as f:
            content = f.read()
        return self.parse_from_string(content)

    def parse_from_string(self, string: str) -> AST:
        lines = string.split('\n')
        tokens = []
        for line in lines:
            if line.strip() == '':
                break

            terminal_name, line_number, *source = line.split()
            tokens.append(
                Token(
                    self.get_terminal(terminal_name),
                    int(line_number),
                    ' '.join(source)
                )
            )

        return self.parse(tokens)
    
    def parse(self, tokens: List[Optional[Token]]) -> AST:
        class StackItem:
            def __init__(self, state: DFAState, symbol: 'Optional[Token] | AST') -> None:
                self.state = state
                self.symbol = symbol

            def __repr__(self) -> str:
                return f'({self.state.id}, {self.symbol if not isinstance(self.symbol, AST) else self.symbol.root})'
        
        assert self.starting_nonterminal is not None
        assert self.starting_state is not None

        stack: List[StackItem] = [
            StackItem(
                self.starting_state,
                None
            )
        ]

        i = 0
        while True:
            token = tokens[i] if i < len(tokens) else None

            current_state = stack[-1].state
            action = self.table_action[current_state][token.type if token is not None else None]

            if action.type == SAActionType.ACCEPT:
                top_of_stack_symbol = stack[-1].symbol
                assert isinstance(top_of_stack_symbol, AST)
                return top_of_stack_symbol

            elif action.type == SAActionType.SHIFT:
                assert isinstance(action, SAActionShift)
                stack.append(StackItem(action.state, token if token is not None else None))
                i += 1

            elif action.type == SAActionType.REDUCE:
                assert isinstance(action, SAActionReduce)

                reduction = action.reduction
                node = AST(reduction.left_side)
                
                if not reduction.is_epsilon:
                    num_to_pop = len(reduction.symbols)

                    for _ in range(num_to_pop):
                        stack_item = stack.pop()
                        node.children.appendleft(stack_item.symbol)
                else:
                    node.children = deque([None])

                new_top_of_stack_state = stack[-1].state

                new_state = self.table_new_state[new_top_of_stack_state][reduction.left_side]
                assert new_state is not None
                stack.append(StackItem(new_state, node))

            elif action.type == SAActionType.REJECT:
                assert token is not None
                log(f'Syntax error on line {token.line_number}')
                log(f'  Unexpected token {token.type} `{token.source}`')

                while len(stack) > 1:
                    current_state = stack[-1].state

                    can_accept_sync = False
                    for sync in self.sync_symbols:
                        action = self.table_action[current_state][sync]
                        if action.type != SAActionType.REJECT:
                            can_accept_sync = True
                            break

                    if can_accept_sync:
                        break

                    stack_item = stack.pop()

                recovered = False

                while i < len(tokens) - 1:
                    token = tokens[i]
                    assert token is not None
                    current_terminal = token.type
                    current_state = stack[-1].state

                    if current_terminal in self.sync_symbols:
                        action = self.table_action[current_state][current_terminal]

                        if action.type != SAActionType.REJECT:
                            recovered = True
                            break

                    i += 1

                if not recovered:
                    log('Fatal error')
                    log('  Unexpected EOF')
                    raise Exception('Unexpected EOF')

    def get_nonterminal(self, name: str) -> Nonterminal:
        nonterms = [n for n in self.nonterminals if n.name == name]
        assert len(nonterms) == 1
        return nonterms[0]

    def get_terminal(self, name: str) -> Terminal:
        terms = [t for t in self.terminals if t.name == name]
        assert len(terms) == 1
        return terms[0]
    
    def compile(self, dfa: DFA) -> None:
        self.starting_state = dfa.start_state
        self._compile_table_action(dfa)
        self._compile_table_new_state(dfa)

    def _make_table_action_keys(self, dfa: DFA) -> None:
        for state in dfa.states:
            self.table_action[state] = {}
            row = self.table_action[state]
            for t in self.terminals | {None}:
                row[t] = SAActionReject()

    def _compile_table_action(self, dfa: DFA) -> None:
        self._make_table_action_keys(dfa)

        for state in dfa.states:
            can_take_actions: List[Tuple[SAAction, Optional[Terminal]]] = []

            for lr_item in state.lr_items:
                if lr_item.is_complete():
                    if lr_item.context == {None} and lr_item.right_side.left_side == self.starting_nonterminal:
                        can_take_actions.append((SAActionAccept(), EOF))
                        continue

                    for t in lr_item.context:
                        can_take_actions.append((SAActionReduce(lr_item.right_side), t))
                else:
                    symbol_at_idx = lr_item.right_side[lr_item.dot_before_idx]
                    next_state = state.move(symbol_at_idx)
                    if isinstance(symbol_at_idx, Terminal) and next_state is not None:
                        can_take_actions.append((SAActionShift(next_state), symbol_at_idx))

            actions_by_terminal: Dict[Optional[Terminal], List[SAAction]] = {}
            for action, terminal in can_take_actions:
                if terminal not in actions_by_terminal:
                    actions_by_terminal[terminal] = []
                actions_by_terminal[terminal].append(action)
            
            for terminal, actions in actions_by_terminal.items():
                accept_action = None
                shift_action = None
                reduce_action = None
                
                for action in actions:
                    if isinstance(action, SAActionAccept):
                        accept_action = action
                    elif isinstance(action, SAActionShift):
                        shift_action = action
                    elif isinstance(action, SAActionReduce):
                        if reduce_action is None or action.reduction.id < reduce_action.reduction.id:
                            reduce_action = action
                
                if accept_action is not None:
                    self.table_action[state][terminal] = accept_action
                elif shift_action is not None:
                    self.table_action[state][terminal] = shift_action
                elif reduce_action is not None:
                    self.table_action[state][terminal] = reduce_action

    def _make_table_new_state_keys(self, dfa: DFA) -> None:
        for state in dfa.states:
            row = self.table_new_state[state] = {}
            for nt in self.nonterminals:
                row[nt] = None

    def _compile_table_new_state(self, dfa: DFA) -> None:
        self._make_table_new_state_keys(dfa)

        for state in dfa.states:
            for nt, new_state in [item for item in state.moves.items() if isinstance(item[0], Nonterminal)]:
                assert isinstance(nt, Nonterminal)
                self.table_new_state[state][nt] = new_state

    def to_bnf(self) -> str:
        return '\n'.join(n.to_bnf() for n in self.nonterminals)
    
    def __repr__(self) -> str:
        if not self.table_action and not self.table_new_state:
            return 'SA(empty tables)'
        
        # Sort states by ID for consistent output
        sorted_states = sorted(self.table_action.keys(), key=lambda s: s.id)
        # Sort terminals, putting None (EOF) at the end
        sorted_terminals = sorted(self.terminals, key=lambda t: t.name) + [None]
        sorted_nonterminals = sorted(self.nonterminals, key=lambda nt: nt.name)
        
        def format_action(action: SAAction) -> str:
            if action.type == SAActionType.SHIFT:
                assert isinstance(action, SAActionShift)
                return f'Shift({action.state.id})'
            elif action.type == SAActionType.REDUCE:
                assert isinstance(action, SAActionReduce)
                rs = action.reduction
                if rs.is_epsilon:
                    right_side_str = '$'
                else:
                    right_side_str = ' '.join(str(s) for s in rs)
                return f'Reduce({rs.left_side.name} -> {right_side_str})'
            elif action.type == SAActionType.ACCEPT:
                return 'Accept'
            else:  # REJECT
                return '-'
        
        def format_new_state(state: Optional[DFAState]) -> str:
            return str(state.id) if state else '-'
        
        # Calculate column widths
        state_col_width = max(len(f'State {s.id}') for s in sorted_states) if sorted_states else 8
        
        # Action table columns
        action_widths = {}
        for t in sorted_terminals:
            t_name = t.name if t else 'EOF'
            max_width = len(t_name)
            for state in sorted_states:
                action = self.table_action[state].get(t, SAActionReject())
                max_width = max(max_width, len(format_action(action)))
            action_widths[t] = max(max_width, 3) + 1
        
        # New state table columns
        newstate_widths = {}
        for nt in sorted_nonterminals:
            max_width = len(nt.name)
            for state in sorted_states:
                new_state = self.table_new_state[state].get(nt)
                max_width = max(max_width, len(format_new_state(new_state)))
            newstate_widths[nt] = max(max_width, 3) + 1
        
        lines = []
        
        # Header row
        header = ' ' * (state_col_width + 1) + ' │'
        for t in sorted_terminals:
            t_name = t.name if t else 'EOF'
            header += f' {t_name:>{action_widths[t]-1}}'
        header += ' ║'
        for nt in sorted_nonterminals:
            header += f' {nt.name:>{newstate_widths[nt]-1}}'
        lines.append(header)
        
        # Separator
        separator = '─' * (state_col_width + 1) + '─┼'
        separator += '─' * sum(action_widths.values())
        separator += '─╫'
        separator += '─' * sum(newstate_widths.values())
        lines.append(separator)
        
        # Data rows
        for state in sorted_states:
            row = f'State {state.id:<{state_col_width-6}}{"*" if state == self.starting_state else " "} │'
            
            # Action table entries
            for t in sorted_terminals:
                action = self.table_action[state].get(t, SAActionReject())
                action_str = format_action(action)
                row += f' {action_str:>{action_widths[t]-1}}'
            
            row += ' ║'
            
            # New state table entries
            for nt in sorted_nonterminals:
                new_state = self.table_new_state[state].get(nt)
                state_str = format_new_state(new_state)
                row += f' {state_str:>{newstate_widths[nt]-1}}'
            
            lines.append(row)
        
        return '\n'.join(lines)

class SAUtils:

    @staticmethod
    def augment_grammar(sa: SA) -> None:
        assert sa.starting_nonterminal is not None
        
        original_start = sa.starting_nonterminal
        
        augmented_name = original_start.name + "'"
        
        existing_names = {nt.name for nt in sa.nonterminals}
        while augmented_name in existing_names:
            augmented_name += "'"
        
        augmented_start = Nonterminal(augmented_name)
        
        right_side = RightSide(left_side=augmented_start)
        right_side.append(original_start)
        
        augmented_start.right_sides.add(right_side)
        
        augmented_start.is_empty = False
        augmented_start.calculate_in_nt_only_production_of(sa.nonterminals | {augmented_start})
        
        augmented_start.first = original_start.first.copy()
        
        right_side.calculate_first()
        
        sa.nonterminals.add(augmented_start)
        sa.starting_nonterminal = augmented_start

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
                table_first[row][col] = row.immediate_first(col)

        assert sa.starting_nonterminal is not None

        mark_first(table_first)

        all_right_sides: Set[RightSide] = set.union(*(nt.right_sides for nt in sa.nonterminals))

        for nt in sa.nonterminals:
            nt.calculate_first(table_first)

        for rs in all_right_sides:
            rs.calculate_first()

        SAUtils.augment_grammar(sa)

        nfa = SAUtils.construct_epislon_nfa(sa.nonterminals, sa.terminals, sa.starting_nonterminal)
        dfa = SAUtils.epsilon_nfa_to_dfa(nfa)

        # draw_automaton(dfa.states)
        
        sa.compile(dfa)

        return sa

    @staticmethod
    def construct_epislon_nfa(nonterminals: Set[Nonterminal], terminals: Set[Terminal], starting_nonterminal: Nonterminal) -> NFA:
        q0 = NFAState(LRItem(RightSide(left_side=starting_nonterminal), 0, set()))

        queue: List[NFAState] = []
        created: Dict[str, NFAState] = {str(q0.lr_item) : q0}

        for rs in starting_nonterminal.right_sides_list:
            new_state = NFAState(
                LRItem(rs, 0, {EOF})
            )

            q0.add_epsilon(new_state)

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

            state.add_move(symbol_at_idx, state2)

            state2_key = str(state2.lr_item)
            if state2_key not in created:
                created[state2_key] = state2
                queue.append(state2)

            if isinstance(symbol_at_idx, Terminal):
                continue

            beta: List[Terminal | Nonterminal] = lr_item.right_side.symbols[lr_item.dot_before_idx+1:]

            context: Set[Optional[Terminal]] = RightSide.set_first(beta) # type: ignore

            beta_is_nullable: bool = not any(s for s in beta if isinstance(s, Terminal) or (isinstance(s, Nonterminal) and not s.is_empty))

            if beta_is_nullable:
                context |= lr_item.context

            for rs in symbol_at_idx.right_sides_list:
                # Create the LRItem first to generate the key
                lr_item_new = LRItem(rs, 0, context)
                key = str(lr_item_new)

                if key in created:
                    found_state = created[key]
                else:
                    # Only create NFAState if it doesn't exist (to avoid incrementing ID counter unnecessarily)
                    new_state = NFAState(lr_item_new)
                    created[key] = new_state
                    found_state = new_state
                    queue.append(found_state)

                state.add_epsilon(found_state)

        return NFA(set(created.values()), q0, nonterminals | terminals)

    @staticmethod
    def epsilon_nfa_to_dfa(epsilon_nfa: NFA) -> DFA:
        start_epsilon_closure: Set[NFAState] = epsilon_nfa.start_state.epsilon() - {epsilon_nfa.start_state}
        
        if not start_epsilon_closure:
            start_state = DFAState(set())
            return DFA({start_state}, start_state, epsilon_nfa.alphabet)
        
        start_state = DFAState({state.lr_item for state in start_epsilon_closure})
        dfa = DFA({start_state}, start_state, epsilon_nfa.alphabet)
        
        queue: List[frozenset[NFAState]] = [frozenset(start_epsilon_closure)]
        state_dict: Dict[frozenset[NFAState], DFAState] = {frozenset(start_epsilon_closure): start_state}
        
        epsilon_cache: Dict[int, Set[NFAState]] = {}
        
        def get_epsilon_closure(state: NFAState) -> Set[NFAState]:
            if state.id not in epsilon_cache:
                epsilon_cache[state.id] = state.epsilon()
            return epsilon_cache[state.id]
        
        while queue:
            current_states: frozenset[NFAState] = queue.pop(0)
            current_dfa_state = state_dict[current_states]
            
            for symbol in epsilon_nfa.alphabet:
                next_states_set: Set[NFAState] = set()
                
                for state in current_states:
                    immediate = state.immediate_move(symbol)
                    for next_state in immediate:
                        next_states_set.update(get_epsilon_closure(next_state))
                
                if not next_states_set:
                    continue
                
                next_states: frozenset[NFAState] = frozenset(next_states_set)
                
                if next_states not in state_dict:
                    dfa_state = DFAState({state.lr_item for state in next_states})
                    state_dict[next_states] = dfa_state
                    dfa.states.add(dfa_state)
                    queue.append(next_states)
                else:
                    dfa_state = state_dict[next_states]
                
                current_dfa_state.add_move(symbol, dfa_state)
        
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
            for symbol, target_state in state.moves.items():
                edge_key = (state.id, target_state.id)
                display_symbol = 'ε' if symbol is None else str(symbol)
                
                if edge_key in transitions_map:
                    transitions_map[edge_key].append(display_symbol)
                else:
                    transitions_map[edge_key] = [display_symbol]
        else:
            # NFA: transitions is Dict[Symbol, Set[NFAState]]
            for symbol, target_states in state.moves.items():
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

    log(sa)

    # ast = sa.parse_from_file(sys.argv[1])

    # out(ast)

if __name__ == '__main__':
    main()
