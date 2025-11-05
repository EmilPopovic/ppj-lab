#!/usr/bin/env python3
import sys
from enum import Enum
from abc import ABC
from collections import deque
from typing import Generator, Set, List, Optional, Iterator, Dict, Tuple, FrozenSet

# Sentinels
EPSILON = object()   # distinct epsilon sentinel
EOF = None           # keep None for EOF in parse tables (parser expects None)

# Small deterministic hash helper (fast): we use built-in hashing of tuples for speed.
def tuple_hash(t: tuple) -> int:
    return hash(t)

Symbol = Optional['Nonterminal | Terminal']  # Terminal or Nonterminal or None

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class LRItem:
    __slots__ = ("right_side", "dot_before_idx", "context", "_repr_cache", "_hash_cache")

    def __init__(self, right_side: 'RightSide', dot_before_idx: int, context: Set[Optional['Terminal']]) -> None:
        self.right_side = right_side
        self.dot_before_idx = dot_before_idx
        # store context as frozenset for immutability and fast comparisons
        self.context = frozenset(context)
        self._repr_cache: Optional[str] = None
        self._hash_cache: Optional[int] = None

    def __repr__(self) -> str:
        if self._repr_cache is not None:
            return self._repr_cache

        parts = [f'{self.right_side.left_side} →']
        for i, s in enumerate(self.right_side.symbols):
            if i == self.dot_before_idx:
                parts.append('•')
            parts.append(str(s))
        if self.is_complete():
            parts.append('•')

        ctx = ','.join(sorted((str(s) for s in self.context), key=str))
        self._repr_cache = ' '.join(parts) + f' , {{{ctx}}}'
        return self._repr_cache

    def __hash__(self) -> int:
        if self._hash_cache is None:
            # small, fast tuple-based hash using immutable ids
            ctx_ids = tuple(sorted((s.name if hasattr(s, 'name') else str(s) for s in self.context)))
            self._hash_cache = tuple_hash((self.right_side.id, self.dot_before_idx, ctx_ids))
        return self._hash_cache

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LRItem):
            return False
        return (self.right_side == other.right_side and
                self.dot_before_idx == other.dot_before_idx and
                self.context == other.context)

    def is_complete(self) -> bool:
        return self.dot_before_idx >= len(self.right_side.symbols)

class NFAState:
    __last_id = 0

    __slots__ = ("id", "lr_item", "moves")

    def __init__(self, lr_item: LRItem) -> None:
        self.id = NFAState.__last_id
        NFAState.__last_id += 1

        self.lr_item = lr_item
        # moves: symbol -> set of NFAState
        self.moves: Dict[Symbol, Set['NFAState']] = {}

    def __hash__(self) -> int:
        # depend on lr_item hash for identity
        return hash((self.lr_item.__hash__(), self.id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NFAState):
            return False
        return self.lr_item == other.lr_item

    def immediate_move(self, symbol: Symbol) -> Set['NFAState']:
        return self.moves.get(symbol, set())

    def add_epsilon(self, other: 'NFAState') -> None:
        self.moves.setdefault(EPSILON, set()).add(other)

    def add_move(self, c: Symbol, other: 'NFAState') -> None:
        self.moves.setdefault(c, set()).add(other)

    @staticmethod
    def epsilon_set(states: Set['NFAState']) -> Set['NFAState']:
        closure = set(states)
        stack = list(states)
        while stack:
            s = stack.pop()
            for nxt in s.immediate_move(EPSILON):
                if nxt not in closure:
                    closure.add(nxt)
                    stack.append(nxt)
        return closure

    def epsilon(self) -> Set['NFAState']:
        return NFAState.epsilon_set({self})

    @staticmethod
    def move_set(states: Set['NFAState'], symbol: Symbol) -> Set['NFAState']:
        result: Set['NFAState'] = set()
        for s in states:
            for t in s.immediate_move(symbol):
                result.update(t.epsilon())
        return result

    def move(self, symbol: Symbol) -> Set['NFAState']:
        return NFAState.move_set({self}, symbol)

class NFA:
    def __init__(self, states: Set[NFAState], start_state: NFAState, alphabet: Set['Terminal | Nonterminal']) -> None:
        self.states = states
        self.start_state = start_state
        self.alphabet = alphabet

class DFAState:
    __last_id = 0

    __slots__ = ("id", "lr_items", "moves", "_hash_cache")

    def __init__(self, lr_items: Set[LRItem]) -> None:
        self.id = DFAState.__last_id
        DFAState.__last_id += 1

        # store lr_items as frozenset for hashing/comparisons
        self.lr_items = frozenset(lr_items)
        self.moves: Dict[Symbol, 'DFAState'] = {}
        self._hash_cache: Optional[int] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DFAState):
            return False
        return self.lr_items == other.lr_items

    def __hash__(self) -> int:
        if self._hash_cache is None:
            # compute hash of the frozenset of LRItem hashes
            self._hash_cache = tuple_hash(tuple(sorted((hash(it) for it in self.lr_items))))
        return self._hash_cache

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

    __slots__ = ("id", "left_side", "symbols", "is_epsilon", "is_nullable", "first", "states")

    def __init__(self, left_side: 'Nonterminal', symbols: Optional[List['Terminal | Nonterminal']] = None, is_epsilon: bool = False) -> None:
        self.id = RightSide.__last_id
        RightSide.__last_id += 1

        self.left_side: Nonterminal = left_side
        self.symbols: List['Terminal | Nonterminal'] = list(symbols) if symbols else []
        self.is_epsilon: bool = is_epsilon
        self.is_nullable: Optional[bool] = None
        self.first: Set['Terminal'] = set()
        self.states: List[NFAState] = []

    def __hash__(self) -> int:
        # hash based on left-side id and symbols' names
        syms = tuple((s.name if hasattr(s, 'name') else str(s)) for s in self.symbols)
        return tuple_hash((self.left_side.name, syms))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RightSide):
            return False
        return (self.left_side == other.left_side) and (self.symbols == other.symbols)

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
    __slots__ = ("name", "right_sides", "_right_sides_list", "is_empty", "in_nt_only_production_of", "first", "states")

    def __init__(self, name: str) -> None:
        self.name = name
        self.right_sides: Set[RightSide] = set()
        self._right_sides_list: Optional[List[RightSide]] = None
        self.is_empty: Optional[bool] = None
        self.in_nt_only_production_of: Optional[Set['Nonterminal']] = None
        self.first: Set['Terminal'] = set()
        self.states: Set[NFAState] = set()

    def __hash__(self) -> int:
        return tuple_hash((self.name,))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Nonterminal):
            return False
        return self.name == other.name

    def __repr__(self) -> str:
        return f'<{self.name}>'

    def to_bnf(self) -> str:
        out_s = f'{str(self)}{"*" if self.is_empty else ""} ::= '
        first = True
        for p in sorted(self.right_sides, key=lambda r: repr(r)):
            if not first:
                out_s += ' | '
            first = False
            if p.is_epsilon:
                out_s += '""'
            else:
                out_s += ' '.join([str(e) for e in p])
        return out_s

    def calculate_in_nt_only_production_of(self, nonterminals: Set['Nonterminal']) -> None:
        self.in_nt_only_production_of = {
            nt for nt in nonterminals if
            any(any(nt_in_p == self for nt_in_p in p) for p in nt.right_sides if p.nonterminal_only)
        }

    @property
    def right_sides_list(self) -> List[RightSide]:
        if self._right_sides_list is None:
            self._right_sides_list = sorted(list(self.right_sides), key=lambda r: repr(r))
        return self._right_sides_list

    def calculate_first(self, table_first: Dict['Nonterminal', Dict['Nonterminal | Terminal', bool]]) -> None:
        self.first = {t for t in table_first[self] if isinstance(t, Terminal) and table_first[self][t]}

    def is_in_production_of(self, other: 'Nonterminal') -> bool:
        assert isinstance(self.in_nt_only_production_of, set)
        return other in self.in_nt_only_production_of

    def _mark_empty(self, start: 'Nonterminal') -> bool:
        if self.is_empty is not None:
            return bool(self.is_empty)
        # Conservative: if any nonterminal-only right side is nullable, this is empty
        for rs in (rs for rs in self.right_sides if rs.nonterminal_only):
            if rs.is_nullable:
                self.is_empty = True
                return True
            elif rs.is_nullable is None:
                if all((nt._mark_empty(start) for nt in rs.symbols if isinstance(nt, Nonterminal) and nt is not start)):
                    self.is_empty = True
                    return True
        return False

    def mark_empty(self) -> bool:
        return self._mark_empty(start=self)

    def immediate_first(self, other: 'Nonterminal | Terminal') -> bool:
        for rs in self.right_sides:
            if rs.is_epsilon:
                continue
            i = 0
            while i < len(rs.symbols) and isinstance(rs[i], Nonterminal) and rs[i].is_empty:
                if rs[i] == other:
                    return True
                i += 1
            if i < len(rs.symbols) and rs[i] == other:
                return True
        return False

def mark_first(table_directly_first: Dict[Nonterminal, Dict[Symbol, bool]]) -> None:
    # simple transitive closure on the boolean table (Floyd-Warshall-like for boolean reachability)
    changed = True
    while changed:
        changed = False
        for row, row_dict in table_directly_first.items():
            for col, val in list(row_dict.items()):
                if val:
                    # if col is nonterminal, copy its row
                    if isinstance(col, Nonterminal):
                        for col2, v2 in table_directly_first[col].items():
                            if v2 and not row_dict.get(col2, False):
                                row_dict[col2] = True
                                changed = True
            # a symbol derives itself
            if not row_dict.get(row, False):
                row_dict[row] = True
                changed = True

def print_sym_table(table: Dict[Nonterminal, Dict[Symbol, bool]]) -> None:
    all_symbols = set()
    for row_symbol in table:
        all_symbols.add(row_symbol)
        for col_symbol in table[row_symbol]:
            all_symbols.add(col_symbol)

    nonterminals = sorted([s for s in all_symbols if type(s).__name__ == 'Nonterminal'], key=lambda s: s.name)
    terminals = sorted([s for s in all_symbols if type(s).__name__ == 'Terminal'], key=lambda s: s.name)
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
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name: str = name

    def __repr__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return tuple_hash((self.name,))

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
    __slots__ = ("state",)

    def __init__(self, state: DFAState) -> None:
        super().__init__()
        self.state = state

class SAActionReduce(SAAction):
    type = SAActionType.REDUCE
    __slots__ = ("reduction",)

    def __init__(self, reduction: RightSide) -> None:
        super().__init__()
        self.reduction = reduction

class SAActionAccept(SAAction):
    type = SAActionType.ACCEPT
    __slots__ = ()
    def __init__(self) -> None:
        super().__init__()

class SAActionReject(SAAction):
    type = SAActionType.REJECT
    __slots__ = ()
    def __init__(self) -> None:
        super().__init__()

class Token:
    __slots__ = ("type", "line_number", "source")
    def __init__(self, type: Terminal, line_number: int, source: str) -> None:
        self.type: Terminal = type
        self.line_number: int = line_number
        self.source: str = source

    def __repr__(self) -> str:
        return f'{self.type} {self.line_number} {self.source}'

class AST:
    __slots__ = ("root", "children", "parent")
    def __init__(self, root: Nonterminal, parent: 'Optional[AST]' = None) -> None:
        self.root: Nonterminal = root
        self.children: deque[AST | Optional[Token]] = deque()
        self.parent: Optional[AST] = parent

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
        tokens: List[Optional[Token]] = []
        for line in lines:
            parts = line.split(' ', 2)
            if len(parts) == 3:
                terminal_name, line_number, source = parts
            else:
                continue

            tokens.append(Token(self.get_terminal(terminal_name), int(line_number), source))
        return self.parse(tokens)

    def parse(self, tokens: List[Optional[Token]]) -> AST:
        class StackItem:
            __slots__ = ("state", "symbol")
            def __init__(self, state: DFAState, symbol: 'Optional[Token] | AST') -> None:
                self.state = state
                self.symbol = symbol
            def __repr__(self) -> str:
                return f'({self.state.id}, {self.symbol if not isinstance(self.symbol, AST) else self.symbol.root})'

        assert self.starting_nonterminal is not None
        assert self.starting_state is not None

        stack: List[StackItem] = [StackItem(self.starting_state, None)]
        i = 0
        while True:
            token = tokens[i] if i < len(tokens) else None
            current_state = stack[-1].state
            action = self.table_action[current_state].get(token.type if token is not None else None, SAActionReject())

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
                # error recovery path (kept much as original but made robust)
                if token is None:
                    log('Fatal error\n  Unexpected EOF')
                    raise Exception('Unexpected EOF')
                log(f'Syntax error on line {token.line_number}')
                log(f'  Unexpected token {token.type} `{token.source}`')

                # pop until sync possible
                while len(stack) > 1:
                    current_state = stack[-1].state
                    can_accept_sync = False
                    for sync in self.sync_symbols:
                        action_test = self.table_action[current_state].get(sync, SAActionReject())
                        if action_test.type != SAActionType.REJECT:
                            can_accept_sync = True
                            break
                    if can_accept_sync:
                        break
                    stack.pop()

                recovered = False
                while i < len(tokens):
                    token = tokens[i]
                    if token is None:
                        break
                    current_terminal = token.type
                    current_state = stack[-1].state
                    if current_terminal in self.sync_symbols:
                        action_test = self.table_action[current_state].get(current_terminal, SAActionReject())
                        if action_test.type != SAActionType.REJECT:
                            recovered = True
                            break
                    i += 1
                if not recovered:
                    log('Fatal error\n  Unexpected EOF')
                    raise Exception('Unexpected EOF')

    def get_nonterminal(self, name: str) -> Nonterminal:
        matches = [n for n in self.nonterminals if n.name == name]
        assert len(matches) == 1, f'Nonterminal not found: {name}'
        return matches[0]

    def get_terminal(self, name: str) -> Terminal:
        matches = [t for t in self.terminals if t.name == name]
        assert len(matches) == 1, f'Terminal not found: {name}'
        return matches[0]

    def compile(self, dfa: DFA) -> None:
        self.starting_state = dfa.start_state
        self._compile_table_action(dfa)
        self._compile_table_new_state(dfa)

    def _make_table_action_keys(self, dfa: DFA) -> None:
        for state in dfa.states:
            row: Dict[Optional[Terminal], SAAction] = {}
            for t in (self.terminals | {None}):
                row[t] = SAActionReject()
            self.table_action[state] = row

    def _compile_table_action(self, dfa: DFA) -> None:
        self._make_table_action_keys(dfa)
        for state in dfa.states:
            can_take_actions: List[Tuple[SAAction, Optional[Terminal]]] = []

            for lr_item in state.lr_items:
                if lr_item.is_complete():
                    # Accept
                    if lr_item.context == frozenset({None}) and lr_item.right_side.left_side == self.starting_nonterminal:
                        can_take_actions.append((SAActionAccept(), None))
                        continue
                    for t in lr_item.context:
                        can_take_actions.append((SAActionReduce(lr_item.right_side), t))
                else:
                    symbol_at_idx = lr_item.right_side.symbols[lr_item.dot_before_idx]
                    next_state = state.move(symbol_at_idx)
                    if isinstance(symbol_at_idx, Terminal) and next_state is not None:
                        can_take_actions.append((SAActionShift(next_state), symbol_at_idx))

            actions_by_terminal: Dict[Optional[Terminal], List[SAAction]] = {}
            for action, terminal in can_take_actions:
                actions_by_terminal.setdefault(terminal, []).append(action)

            for terminal, actions in actions_by_terminal.items():
                # prefer accept > shift > reduce (and choose smallest-reduction id on conflict)
                chosen: Optional[SAAction] = None
                # check accept
                for a in actions:
                    if isinstance(a, SAActionAccept):
                        chosen = a
                        break
                if chosen is None:
                    for a in actions:
                        if isinstance(a, SAActionShift):
                            chosen = a
                            break
                if chosen is None:
                    # pick reduce with smallest id (deterministic)
                    reduces = [a for a in actions if isinstance(a, SAActionReduce)]
                    if reduces:
                        reduces.sort(key=lambda r: r.reduction.id)
                        chosen = reduces[0]
                if chosen is not None:
                    self.table_action[state][terminal] = chosen

    def _make_table_new_state_keys(self, dfa: DFA) -> None:
        for state in dfa.states:
            row: Dict[Nonterminal, Optional[DFAState]] = {}
            for nt in self.nonterminals:
                row[nt] = None
            self.table_new_state[state] = row

    def _compile_table_new_state(self, dfa: DFA) -> None:
        self._make_table_new_state_keys(dfa)
        for state in dfa.states:
            for symbol, target in state.moves.items():
                if isinstance(symbol, Nonterminal):
                    self.table_new_state[state][symbol] = target

    def to_bnf(self) -> str:
        return '\n'.join(n.to_bnf() for n in sorted(self.nonterminals, key=lambda x: x.name))

    def __repr__(self) -> str:
        if not self.table_action and not self.table_new_state:
            return 'SA(empty tables)'
        sorted_states = sorted(self.table_action.keys(), key=lambda s: s.id)
        sorted_terminals = sorted(self.terminals, key=lambda t: t.name) + [None]
        sorted_nonterminals = sorted(self.nonterminals, key=lambda nt: nt.name)

        def format_action(action: SAAction) -> str:
            if action.type == SAActionType.SHIFT:
                return f'Shift({action.state.id})'
            elif action.type == SAActionType.REDUCE:
                rs = action.reduction
                right_side_str = '$' if rs.is_epsilon else ' '.join(str(s) for s in rs.symbols)
                return f'Reduce({rs.left_side.name} -> {right_side_str})'
            elif action.type == SAActionType.ACCEPT:
                return 'Accept'
            else:
                return '-'

        def format_new_state(state: Optional[DFAState]) -> str:
            return str(state.id) if state else '-'

        # widths
        state_col_width = max([len(f'State {s.id}') for s in sorted_states] + [8])
        action_widths = {}
        for t in sorted_terminals:
            t_name = (t.name if t else 'EOF')
            max_width = len(t_name)
            for state in sorted_states:
                action = self.table_action[state].get(t, SAActionReject())
                max_width = max(max_width, len(format_action(action)))
            action_widths[t] = max_width + 1

        newstate_widths = {}
        for nt in sorted_nonterminals:
            max_width = len(nt.name)
            for state in sorted_states:
                new_state = self.table_new_state[state].get(nt)
                max_width = max(max_width, len(format_new_state(new_state)))
            newstate_widths[nt] = max_width + 1

        lines = []
        header = ' ' * (state_col_width + 1) + ' │'
        for t in sorted_terminals:
            t_name = (t.name if t else 'EOF')
            header += f' {t_name:>{action_widths[t]-1}}'
        header += ' ║'
        for nt in sorted_nonterminals:
            header += f' {nt.name:>{newstate_widths[nt]-1}}'
        lines.append(header)

        separator = '─' * (state_col_width + 1) + '─┼'
        separator += '─' * (sum(action_widths.values()))
        separator += '─╫'
        separator += '─' * (sum(newstate_widths.values()))
        lines.append(separator)

        for state in sorted_states:
            row = f'State {state.id:<{state_col_width-6}}{"*" if state == self.starting_state else " "} │'
            for t in sorted_terminals:
                action = self.table_action[state].get(t, SAActionReject())
                action_str = format_action(action)
                row += f' {action_str:>{action_widths[t]-1}}'
            row += ' ║'
            for nt in sorted_nonterminals:
                new_state = self.table_new_state[state].get(nt)
                row += f' {format_new_state(new_state):>{newstate_widths[nt]-1}}'
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
        # create production: Augmented -> original_start
        rhs = RightSide(left_side=augmented_start, symbols=[original_start])
        augmented_start.right_sides.add(rhs)
        augmented_start.is_empty = False
        augmented_start.calculate_in_nt_only_production_of(sa.nonterminals | {augmented_start})
        augmented_start.first = original_start.first.copy()
        rhs.calculate_first()
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
            if not row:
                continue
            if row.startswith('%V'):
                _, *nonterminals_list = row.split()
                sa.nonterminals = {Nonterminal(n[1:-1]) for n in nonterminals_list}
                # first listed is starting nonterminal
                sa.starting_nonterminal = sa.get_nonterminal(nonterminals_list[0][1:-1])
            elif row.startswith('%T'):
                _, *terminals_list = row.split()
                sa.terminals = {Terminal(t) for t in terminals_list}
            elif row.startswith('%Syn'):
                _, *sync_list = row.split()
                sa.sync_symbols = {t for t in sa.terminals if t.name in sync_list}
            elif row.startswith('<'):
                current_nonterminal = sa.get_nonterminal(row[1:-1])
            elif row.startswith(' '):
                assert current_nonterminal is not None
                elem_strs = row.split()
                rs = RightSide(left_side=current_nonterminal)
                for e in elem_strs:
                    if e == '$':
                        rs.is_epsilon = True
                        rs.is_nullable = True
                        current_nonterminal.is_empty = True
                        break
                    elif e.startswith('<'):
                        rs.append(sa.get_nonterminal(e[1:-1]))
                    else:
                        rs.append(sa.get_terminal(e))
                current_nonterminal.right_sides.add(rs)

        # compute in_nt_only_production_of links
        for nt in sa.nonterminals:
            nt.calculate_in_nt_only_production_of(sa.nonterminals)

        # propagate emptiness
        stack = [n for n in sa.nonterminals if n.is_empty]
        while stack:
            curr = stack.pop()
            assert curr.in_nt_only_production_of is not None
            parents = {nt for nt in curr.in_nt_only_production_of if nt.is_empty is None}
            for parent in parents:
                parent.is_empty = parent.mark_empty()
                if parent.is_empty:
                    stack.append(parent)

        for nt in sa.nonterminals:
            if nt.is_empty is None:
                nt.is_empty = False

        # build direct-first table
        table_first: Dict[Nonterminal, Dict[Symbol, bool]] = {}
        for row in sa.nonterminals:
            table_first[row] = {}
            for col in sa.nonterminals | sa.terminals:
                table_first[row][col] = row.immediate_first(col)

        assert sa.starting_nonterminal is not None

        mark_first(table_first)

        all_right_sides: Set[RightSide] = set()
        for nt in sa.nonterminals:
            nt.calculate_first(table_first)
            all_right_sides.update(nt.right_sides)

        for rs in all_right_sides:
            rs.calculate_first()

        SAUtils.augment_grammar(sa)

        nfa = SAUtils.construct_epislon_nfa(sa.nonterminals, sa.terminals, sa.starting_nonterminal)
        dfa = SAUtils.epsilon_nfa_to_dfa(nfa)

        sa.compile(dfa)
        return sa

    @staticmethod
    def construct_epislon_nfa(nonterminals: Set[Nonterminal], terminals: Set[Terminal], starting_nonterminal: Nonterminal) -> NFA:
        # q0: start
        q0 = NFAState(LRItem(RightSide(left_side=starting_nonterminal, symbols=[]), 0, set()))
        created: Dict[Tuple[int, int, Tuple[str, ...]], NFAState] = {}
        queue: deque[NFAState] = deque()

        # For each production of starting_nonterminal, add epsilon transition from q0
        for rs in starting_nonterminal.right_sides_list:
            item = LRItem(rs, 0, frozenset({EOF}))
            st = NFAState(item)
            q0.add_epsilon(st)
            key = (rs.id, 0, tuple(sorted(s.name if hasattr(s, 'name') else str(s) for s in item.context)))
            created[key] = st
            queue.append(st)

        # BFS build
        while queue:
            state = queue.popleft()
            lr_item = state.lr_item
            if lr_item.is_complete():
                continue
            symbol_at_idx = lr_item.right_side.symbols[lr_item.dot_before_idx]

            # move over symbol
            new_item = LRItem(lr_item.right_side, lr_item.dot_before_idx + 1, set(lr_item.context))
            state2 = NFAState(new_item)
            state.add_move(symbol_at_idx, state2)
            key2 = (new_item.right_side.id, new_item.dot_before_idx, tuple(sorted(s.name if hasattr(s, 'name') else str(s) for s in new_item.context)))
            if key2 not in created:
                created[key2] = state2
                queue.append(state2)
            else:
                state2 = created[key2]

            # if symbol is terminal, we don't expand epsilon from it
            if isinstance(symbol_at_idx, Terminal):
                continue

            # compute beta = symbols after the symbol_at_idx
            beta = lr_item.right_side.symbols[lr_item.dot_before_idx+1:]
            beta_first = RightSide.set_first(beta)
            context = set(beta_first)
            # if beta nullable, include current context
            beta_is_nullable = all((isinstance(s, Nonterminal) and s.is_empty) or isinstance(s, Terminal) and False for s in beta) if beta else True
            if beta_is_nullable:
                context |= set(lr_item.context)

            # for each production of the nonterminal symbol_at_idx, add epsilon edges
            for rs in symbol_at_idx.right_sides_list:
                new_lr_item = LRItem(rs, 0, context)
                key = (rs.id, 0, tuple(sorted(s.name if hasattr(s, 'name') else str(s) for s in new_lr_item.context)))
                if key in created:
                    found_state = created[key]
                else:
                    found_state = NFAState(new_lr_item)
                    created[key] = found_state
                    queue.append(found_state)
                state.add_epsilon(found_state)

        return NFA(set(created.values()) | {q0}, q0, nonterminals | terminals)

    @staticmethod
    def epsilon_nfa_to_dfa(epsilon_nfa: NFA) -> DFA:
        # initial epsilon-closure from start state's immediate epsilon moves (excluding q0 itself)
        start_closure = set()
        for s in epsilon_nfa.start_state.immediate_move(EPSILON):
            start_closure.update(s.epsilon())
        # if closure empty, create single empty DFA state
        if not start_closure:
            start_state = DFAState(set())
            return DFA({start_state}, start_state, epsilon_nfa.alphabet)

        start_state = DFAState({s.lr_item for s in start_closure})
        dfa_states: Set[DFAState] = {start_state}
        queue: deque[FrozenSet[NFAState]] = deque()
        key_map: Dict[FrozenSet[NFAState], DFAState] = {}

        start_key = frozenset(start_closure)
        key_map[start_key] = start_state
        queue.append(start_key)

        # cache epsilon closures
        epsilon_cache: Dict[int, Set[NFAState]] = {}
        def epsilon_of(state: NFAState) -> Set[NFAState]:
            if state.id not in epsilon_cache:
                epsilon_cache[state.id] = state.epsilon()
            return epsilon_cache[state.id]

        while queue:
            current_key = queue.popleft()
            current_dfa = key_map[current_key]
            # for each symbol in alphabet, compute move
            for symbol in epsilon_nfa.alphabet:
                # collect immediate moves for each NFA state in current_key
                next_set: Set[NFAState] = set()
                for nfa_state in current_key:
                    for immediate in nfa_state.immediate_move(symbol):
                        next_set.update(epsilon_of(immediate))
                if not next_set:
                    continue
                next_key = frozenset(next_set)
                if next_key not in key_map:
                    new_dfa_state = DFAState({s.lr_item for s in next_key})
                    key_map[next_key] = new_dfa_state
                    dfa_states.add(new_dfa_state)
                    queue.append(next_key)
                current_dfa.add_move(symbol, key_map[next_key])

        # return dfa
        start_state = key_map[start_key]
        return DFA(dfa_states, start_state, epsilon_nfa.alphabet)


def main() -> None:
    sa: SA = SAUtils.from_stdin()
    # log(sa)
    if len(sys.argv) < 2:
        log("No input file provided to parse. Exiting.")
        return
    ast = sa.parse_from_file(sys.argv[1])
    out(ast)

if __name__ == '__main__':
    main()
