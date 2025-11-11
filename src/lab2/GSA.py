import inspect
import os
from collections import OrderedDict
from typing import Generator, Tuple, FrozenSet

# begin preamble
import sys
import time
import zlib
import base64
import pickle
from enum import Enum
from abc import ABC
from collections import deque
from typing import Set, List, Optional, Iterator, Dict

SA_PICKLE_BASE64 = '{{ SA_PICKLE_BASE64 }}'

EPSILON = None
EOF = None

Symbol = Optional['Nonterminal | Terminal']
# end preamble

OUTPUT_FILENAME = 'analizator/SA.py'

def tuple_hash(t: tuple) -> int:
    return hash(t)

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class LRItem:
    __slots__ = ('right_side', 'dot_before_idx', 'context', '_repr_cache', '_hash_cache')

    def __init__(self, right_side: 'RightSide', dot_before_idx: int, context: Set[Optional['Terminal']]) -> None:
        self.right_side = right_side
        self.dot_before_idx = dot_before_idx
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
            ctx_ids = tuple(
                sorted((
                    s.name if s is not None else str(s) for s in self.context
                ))
            )

            self._hash_cache = tuple_hash((self.right_side.id, self.dot_before_idx, ctx_ids))

        return self._hash_cache

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LRItem):
            return False

        return (
            self.right_side == other.right_side and
            self.dot_before_idx == other.dot_before_idx and
            self.context == other.context
        )

    def is_complete(self) -> bool:
        return self.dot_before_idx >= len(self.right_side.symbols)

class NFAState:
    __last_id = 0

    __slots__ = ('id', 'lr_item', 'moves')

    def __init__(self, lr_item: LRItem) -> None:
        self.id = NFAState.__last_id
        NFAState.__last_id += 1

        self.lr_item = lr_item
        self.moves: Dict[Symbol, Set['NFAState']] = {}

    def __hash__(self) -> int:
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
            epsilon_moves = s.moves.get(EPSILON)
            if epsilon_moves:
                for state in epsilon_moves:
                    if state not in closure:
                        closure.add(state)
                        stack.append(state)

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

    __slots__ = ('id', 'lr_items', 'moves', '_hash_cache')

    def __init__(self, lr_items: Set[LRItem]) -> None:
        self.id = DFAState.__last_id
        DFAState.__last_id += 1

        self.lr_items = frozenset(lr_items)
        self.moves: Dict[Symbol, 'DFAState'] = {}
        self._hash_cache: Optional[int] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DFAState):
            return False

        return self.lr_items == other.lr_items

    def __hash__(self) -> int:
        if self._hash_cache is None:
            self._hash_cache = tuple_hash(
                tuple(
                    sorted((hash(lr) for lr in self.lr_items))
                )
            )

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

    __slots__ = ('id', 'left_side', 'symbols', 'is_epsilon', 'is_nullable', 'first', 'states')

    def __init__(
            self,
            left_side: 'Nonterminal',
            symbols: Optional[List['Terminal | Nonterminal']] = None,
            is_epsilon: bool = False
    ) -> None:
        self.id = RightSide.__last_id
        RightSide.__last_id += 1

        self.left_side: Nonterminal = left_side
        self.symbols: List['Terminal | Nonterminal'] = list(symbols) if symbols else []
        self.is_epsilon: bool = is_epsilon
        self.is_nullable: Optional[bool] = None
        self.first: Set['Terminal'] = set()
        self.states: List[NFAState] = []

    def __hash__(self) -> int:
        syms = tuple((s.name if hasattr(s, 'name') else str(s)) for s in self.symbols)
        left_name = self.left_side.name if hasattr(self.left_side, 'name') else str(self.left_side)
        return tuple_hash((left_name, syms))

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
    __last_id = 0
    __slots__ = ('id', 'name', 'right_sides', '_right_sides_list', 'is_empty', 'in_nt_only_production_of', 'first', 'states')

    def __init__(self, name: str) -> None:
        self.id = Nonterminal.__last_id
        Nonterminal.__last_id += 1
        self.name = name
        self.right_sides: Set[RightSide] = set()
        self._right_sides_list: Optional[List[RightSide]] = None
        self.is_empty: Optional[bool] = None
        self.in_nt_only_production_of: Optional[Set['Nonterminal']] = None
        self.first: Set['Terminal'] = set()
        self.states: Set[NFAState] = set()

    def __hash__(self) -> int:
        return tuple_hash((self.name if hasattr(self, 'name') else id(self),))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Nonterminal):
            return False

        return self.name == other.name

    def __repr__(self) -> str:
        return f'<{self.name if hasattr(self, "name") else "Nonterminal"}>'

    def to_bnf(self) -> str:
        result = f'{str(self)}{"*" if self.is_empty else ""} ::= '
        first = True

        for p in sorted(self.right_sides, key=lambda r: repr(r)):
            if not first:
                result += ' | '

            first = False

            if p.is_epsilon:
                result += '""'
            else:
                result += ' '.join([str(e) for e in p])

        return result

    def calculate_in_nt_only_production_of(self, nonterminals: Set['Nonterminal']) -> None:
        self.in_nt_only_production_of = {
            nt for nt in nonterminals
            if any(
                any(
                    nt_in_p == self
                    for nt_in_p in p
                )
                for p in nt.right_sides
                if p.nonterminal_only
            )
        }

    @property
    def right_sides_list(self) -> List[RightSide]:
        if self._right_sides_list is None:
            self._right_sides_list = sorted(list(self.right_sides), key=repr)

        return self._right_sides_list

    def calculate_first(self, table_first: Dict['Nonterminal', Dict['Nonterminal | Terminal', bool]]) -> None:
        self.first = {
            t for t in table_first[self]
            if isinstance(t, Terminal) and table_first[self][t]
        }

    def is_in_production_of(self, other: 'Nonterminal') -> bool:
        assert isinstance(self.in_nt_only_production_of, set)
        return other in self.in_nt_only_production_of

    def _mark_empty(self, start: 'Nonterminal') -> bool:
        if self.is_empty is not None:
            return bool(self.is_empty)

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

            while i < len(rs.symbols):
                symbol = rs[i]
                if not isinstance(symbol, Nonterminal):
                    break
                if not symbol.is_empty:
                    break
                if symbol == other:
                    return True
                i += 1

            if i < len(rs.symbols) and rs[i] == other:
                return True

        return False

def mark_first(table_directly_first: Dict['Nonterminal', Dict['Terminal | Nonterminal', bool]]) -> None:
    changed = True

    while changed:
        changed = False

        for row, row_dict in table_directly_first.items():
            for col, val in list(row_dict.items()):
                if not val:
                    continue

                if not isinstance(col, Nonterminal):
                    continue

                for col2, v2 in table_directly_first[col].items():
                    if v2 and not row_dict.get(col2, False):
                        row_dict[col2] = True
                        changed = True

            if not row_dict.get(row, False):
                row_dict[row] = True
                changed = True

class Terminal:
    __last_id = 0
    __slots__ = ('id', 'name')

    def __init__(self, name: str) -> None:
        self.id = Terminal.__last_id
        Terminal.__last_id += 1
        self.name: str = name

    def __repr__(self) -> str:
        return self.name if hasattr(self, 'name') else 'Terminal'

    def __hash__(self) -> int:
        return tuple_hash((self.name if hasattr(self, 'name') else id(self),))

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
    __slots__ = ('state_id',)

    def __init__(self, state_id: int) -> None:
        super().__init__()
        self.state_id = state_id

class SAActionReduce(SAAction):
    type = SAActionType.REDUCE
    __slots__ = ('reduction',)

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
    __slots__ = ('type', 'line_number', 'source')

    def __init__(self, type: Terminal, line_number: int, source: str) -> None:
        self.type: Terminal = type
        self.line_number: int = line_number
        self.source: str = source

    def __repr__(self) -> str:
        return f'{self.type} {self.line_number} {self.source}'

class AST:
    __slots__ = ('root', 'children', 'parent')

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

        self.starting_state_id: Optional[int] = None

        self.table_action: Dict[int, Dict[Optional[Terminal] | int, SAAction]] = {}
        self.table_new_state: Dict[int, Dict[Nonterminal | int, Optional[int]]] = {}
        
        self._terminal_id_map: Optional[List[Optional[Terminal]]] = None
        self._nonterminal_id_map: Optional[List[Nonterminal]] = None

    def parse_from_stdin(self) -> AST:
        return self.parse_from_string(sys.stdin.read())

    def parse_from_file(self, filename: str) -> AST:
        with open(filename, 'r') as f:
            content = f.read()

        return self.parse_from_string(content)

    def parse_from_string(self, string: str) -> AST:
        start_tokenize = time.time()
        lines = string.split('\n')
        tokens: List[Optional[Token]] = []

        for line in lines:
            parts = line.split(' ', 2)

            if len(parts) == 3:
                terminal_name, line_number, source = parts
            else:
                continue

            tokens.append(Token(self.get_terminal(terminal_name), int(line_number), source))

        end_tokenize = time.time()
        log(f'[Timing] Tokenization: {(end_tokenize - start_tokenize) * 1000:.2f} ms')

        return self.parse(tokens)

    def _is_optimized(self) -> bool:
        """Check if tables are using optimized ID-based storage"""
        return self._terminal_id_map is not None

    def _get_action(self, state_id: int, terminal: Optional[Terminal]) -> SAAction:
        """Get action from table, handling both optimized and non-optimized formats"""
        state_actions = self.table_action.get(state_id, {})
        
        if self._is_optimized():
            terminal_id = terminal.id if terminal is not None else -1
            return state_actions.get(terminal_id, SAActionReject())
        else:
            return state_actions.get(terminal, SAActionReject())

    def _get_new_state(self, state_id: int, nonterminal: Nonterminal) -> Optional[int]:
        """Get new state from table, handling both optimized and non-optimized formats"""
        state_moves = self.table_new_state.get(state_id, {})
        
        if self._is_optimized():
            return state_moves.get(nonterminal.id)
        else:
            return state_moves.get(nonterminal)

    def parse(self, tokens: List[Optional[Token]]) -> AST:
        start_parse = time.time()
        
        class StackItem:
            __slots__ = ('state_id', 'symbol')

            def __init__(self, state_id: int, symbol: 'Optional[Token] | AST') -> None:
                self.state_id = state_id
                self.symbol = symbol

            def __repr__(self) -> str:
                return f'({self.state_id}, {self.symbol if not isinstance(self.symbol, AST) else self.symbol.root})'

        assert self.starting_nonterminal is not None
        assert self.starting_state_id is not None

        stack: List[StackItem] = [StackItem(self.starting_state_id, None)]

        i = 0

        while True:
            token = tokens[i] if i < len(tokens) else None
            current_state = stack[-1].state_id
            action = self._get_action(current_state, token.type if token is not None else None)

            if action.type == SAActionType.ACCEPT:
                top_of_stack_symbol = stack[-1].symbol
                assert isinstance(top_of_stack_symbol, AST)
                end_parse = time.time()
                log(f'[Timing] Parse tokens to AST: {(end_parse - start_parse) * 1000:.2f} ms')
                return top_of_stack_symbol

            elif action.type == SAActionType.SHIFT:
                assert isinstance(action, SAActionShift)
                stack.append(StackItem(action.state_id, token if token is not None else None))
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

                new_top_of_stack_state = stack[-1].state_id
                new_state = self._get_new_state(new_top_of_stack_state, reduction.left_side)

                assert new_state is not None
                stack.append(StackItem(new_state, node))

            elif action.type == SAActionType.REJECT:
                if token is None:
                    log('Fatal error\n  Unexpected EOF')
                    raise Exception('Unexpected EOF')

                log(f'Syntax error on line {token.line_number}')
                log(f'  Unexpected token {token.type} `{token.source}`')

                while len(stack) > 1:
                    current_state = stack[-1].state_id
                    can_accept_sync = False

                    for sync in self.sync_symbols:
                        action_test = self._get_action(current_state, sync)

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
                    current_state = stack[-1].state_id

                    if current_terminal in self.sync_symbols:
                        action_test = self._get_action(current_state, current_terminal)

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

    def to_bnf(self) -> str:
        return '\n'.join(n.to_bnf() for n in sorted(self.nonterminals, key=lambda x: x.name))
    
    @staticmethod
    def from_pickle(b64_pickle: str) -> 'SA':
        compressed = base64.b64decode(b64_pickle.encode('utf-8'))
        pickled = zlib.decompress(compressed)
        sa: SA = pickle.loads(pickled)
        return sa

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
        start_total = time.time()
        
        def read_input() -> Generator[str, None, None]:
            while True:
                try:
                    yield input()
                except EOFError:
                    break

        start_parse_input = time.time()
        sa = SA()
        data = read_input()
        current_nonterminal: Optional[Nonterminal] = None

        for row in data:
            if not row:
                continue

            if row.startswith('%V'):
                _, *nonterminals_list = row.split()
                sa.nonterminals = {Nonterminal(n[1:-1]) for n in nonterminals_list}
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

        end_parse_input = time.time()
        log(f'[Timing] Parse input: {(end_parse_input - start_parse_input) * 1000:.2f} ms')

        start_calculate_properties = time.time()
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

        table_first: Dict[Nonterminal, Dict[Terminal | Nonterminal, bool]] = {}
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

        end_calculate_properties = time.time()
        log(f'[Timing] Calculate grammar properties: {(end_calculate_properties - start_calculate_properties) * 1000:.2f} ms')

        start_augment = time.time()
        SAUtils.augment_grammar(sa)
        end_augment = time.time()
        log(f'[Timing] Augment grammar: {(end_augment - start_augment) * 1000:.2f} ms')

        start_nfa = time.time()
        nfa = SAUtils.construct_epislon_nfa(sa.nonterminals, sa.terminals, sa.starting_nonterminal)
        end_nfa = time.time()
        log(f'[Timing] Construct epsilon-NFA: {(end_nfa - start_nfa) * 1000:.2f} ms')

        start_dfa = time.time()
        dfa = SAUtils.epsilon_nfa_to_dfa(nfa)
        end_dfa = time.time()
        log(f'[Timing] Convert NFA to DFA: {(end_dfa - start_dfa) * 1000:.2f} ms')

        start_compile = time.time()
        SAUtils.compile(sa, dfa)
        end_compile = time.time()
        log(f'[Timing] Compile parsing tables: {(end_compile - start_compile) * 1000:.2f} ms')

        end_total = time.time()
        log(f'[Timing] Total SA construction: {(end_total - start_total) * 1000:.2f} ms')
        
        return sa

    @staticmethod
    def construct_epislon_nfa(nonterminals: Set[Nonterminal], terminals: Set[Terminal], starting_nonterminal: Nonterminal) -> NFA:
        q0 = NFAState(LRItem(RightSide(left_side=starting_nonterminal, symbols=[]), 0, set()))
        created: Dict[Tuple[int, int, Tuple[str, ...]], NFAState] = {}

        queue: deque[NFAState] = deque()

        for rs in starting_nonterminal.right_sides_list:
            item = LRItem(rs, 0, set([EOF]))
            st = NFAState(item)

            q0.add_epsilon(st)

            key = (rs.id, 0, tuple(sorted(s.name if isinstance(s, Terminal) else str(s) for s in item.context)))
            created[key] = st

            queue.append(st)

        while queue:
            state = queue.popleft()
            lr_item = state.lr_item

            if lr_item.is_complete():
                continue

            symbol_at_idx = lr_item.right_side.symbols[lr_item.dot_before_idx]

            new_item = LRItem(lr_item.right_side, lr_item.dot_before_idx + 1, set(lr_item.context))
            state2 = NFAState(new_item)

            state.add_move(symbol_at_idx, state2)

            sorted_context = sorted(s.name if isinstance(s, Terminal)  else str(s) for s in new_item.context)
            key2 = (new_item.right_side.id, new_item.dot_before_idx, tuple(sorted_context))

            if key2 not in created:
                created[key2] = state2
                queue.append(state2)
            else:
                state2 = created[key2]

            if isinstance(symbol_at_idx, Terminal):
                continue

            beta = lr_item.right_side.symbols[lr_item.dot_before_idx+1:]
            beta_first = RightSide.set_first(beta)
            context: Set[Optional[Terminal]] = set(beta_first)

            beta_is_nullable = all(
                isinstance(s, Nonterminal) and s.is_empty
                or isinstance(s, Terminal) and False for s in beta
            ) if beta else True

            if beta_is_nullable:
                context |= set(lr_item.context)

            for rs in symbol_at_idx.right_sides_list:
                new_lr_item = LRItem(rs, 0, context)

                rs_sorted_context = sorted(s.name if isinstance(s, Terminal) else str(s) for s in new_lr_item.context)
                key = (rs.id, 0, tuple(rs_sorted_context))

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
        start_closure = set()

        for s in epsilon_nfa.start_state.immediate_move(EPSILON):
            start_closure.update(s.epsilon())

        if not start_closure:
            start_state = DFAState(set())
            return DFA({start_state}, start_state, epsilon_nfa.alphabet)

        epsilon_cache: Dict[int, FrozenSet[NFAState]] = {}
        for nfa_state in epsilon_nfa.states:
            epsilon_cache[nfa_state.id] = frozenset(nfa_state.epsilon())

        state_symbols: Dict[int, Set[Symbol]] = {}
        state_moves: Dict[Tuple[int, Symbol], FrozenSet[NFAState]] = {}

        for nfa_state in epsilon_nfa.states:
            symbols = set(nfa_state.moves.keys()) - {EPSILON}
            state_symbols[nfa_state.id] = symbols

            for symbol in symbols:
                immediates = nfa_state.moves.get(symbol, set())
                closure: Set[NFAState] = set()

                for immediate in immediates:
                    closure.update(epsilon_cache[immediate.id])
                    
                state_moves[(nfa_state.id, symbol)] = frozenset(closure)

        start_state = DFAState({s.lr_item for s in start_closure})

        dfa_states: Set[DFAState] = {start_state}
        queue: deque[FrozenSet[NFAState]] = deque()
        key_map: Dict[FrozenSet[NFAState], DFAState] = {}

        start_key = frozenset(start_closure)
        key_map[start_key] = start_state
        queue.append(start_key)

        while queue:
            current_key = queue.popleft()
            current_dfa = key_map[current_key]

            symbol_to_states: Dict[Symbol, List[FrozenSet[NFAState]]] = {}
            
            for nfa_state in current_key:
                for symbol in state_symbols.get(nfa_state.id, set()):
                    move_result = state_moves.get((nfa_state.id, symbol))
                    
                    if move_result:
                        symbol_to_states.setdefault(symbol, []).append(move_result)

            for symbol, move_results in symbol_to_states.items():
                next_set: Set[NFAState] = set()
                
                for move_result in move_results:
                    next_set.update(move_result)

                next_key = frozenset(next_set)

                if next_key not in key_map:
                    new_dfa_state = DFAState({s.lr_item for s in next_key})
                    key_map[next_key] = new_dfa_state
                    dfa_states.add(new_dfa_state)
                    queue.append(next_key)

                current_dfa.add_move(symbol, key_map[next_key])

        start_state = key_map[start_key]
        return DFA(dfa_states, start_state, epsilon_nfa.alphabet)
    
    @staticmethod
    def compile(sa: SA, dfa: DFA) -> None:
        sa.starting_state_id = dfa.start_state.id
        SAUtils._compile_table_action(sa, dfa)
        SAUtils._compile_table_new_state(sa, dfa)
        SAUtils._optimize_tables(sa)
        SAUtils._cleanup_for_pickle(sa)

    @staticmethod
    def _cleanup_for_pickle(sa: SA) -> None:
        """Remove data only needed during construction to reduce pickle size"""
        for nt in sa.nonterminals:
            for rs in nt.right_sides:
                rs.states = []
                rs.first = set()
                rs.is_nullable = None
            
            nt.states = set()
            nt.first = set()
            nt.in_nt_only_production_of = None
            nt._right_sides_list = None

    @staticmethod
    def _optimize_tables(sa: SA) -> None:
        """Convert tables to use integer IDs instead of object references"""
        terminal_list = sorted(sa.terminals, key=lambda t: t.id)
        nonterminal_list = sorted(sa.nonterminals, key=lambda nt: nt.id)
        
        sa._terminal_id_map = terminal_list + [None]
        sa._nonterminal_id_map = nonterminal_list
        
        optimized_action: Dict[int, Dict[int | Optional[Terminal], SAAction]] = {}
        for state_id, actions in sa.table_action.items():
            optimized_action[state_id] = {}
            for terminal, action in actions.items():
                if isinstance(terminal, int):
                    terminal_id = terminal
                else:
                    terminal_id = terminal.id if terminal is not None else -1
                optimized_action[state_id][terminal_id] = action
        
        sa.table_action = optimized_action
        
        optimized_new_state: Dict[int, Dict[int | Nonterminal, Optional[int]]] = {}
        for state_id, moves in sa.table_new_state.items():
            optimized_new_state[state_id] = {}
            for nonterminal, new_state in moves.items():
                if isinstance(nonterminal, int):
                    nt_id = nonterminal
                else:
                    nt_id = nonterminal.id
                optimized_new_state[state_id][nt_id] = new_state
        
        sa.table_new_state = optimized_new_state

    @staticmethod
    def _compile_table_action(sa: SA, dfa: DFA) -> None:

        for state in dfa.states:
            can_take_actions: List[Tuple[SAAction, Optional[Terminal]]] = []

            for lr_item in state.lr_items:
                if lr_item.is_complete():
                    if lr_item.context == frozenset({None}) and lr_item.right_side.left_side == sa.starting_nonterminal:
                        can_take_actions.append((SAActionAccept(), None))
                        continue

                    for t in lr_item.context:
                        can_take_actions.append((SAActionReduce(lr_item.right_side), t))
                else:
                    symbol_at_idx = lr_item.right_side.symbols[lr_item.dot_before_idx]
                    next_state = state.move(symbol_at_idx)

                    if isinstance(symbol_at_idx, Terminal) and next_state is not None:
                        can_take_actions.append((SAActionShift(next_state.id), symbol_at_idx))

            actions_by_terminal: Dict[Optional[Terminal], List[SAAction]] = {}

            for action, terminal in can_take_actions:
                actions_by_terminal.setdefault(terminal, []).append(action)

            for terminal, actions in actions_by_terminal.items():
                chosen: Optional[SAAction] = None

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
                    reduces = [a for a in actions if isinstance(a, SAActionReduce)]

                    if reduces:
                        reduces.sort(key=lambda r: r.reduction.id)
                        chosen = reduces[0]

                if chosen is not None:
                    sa.table_action.setdefault(state.id, {})[terminal] = chosen

    @staticmethod
    def _compile_table_new_state(sa: SA, dfa: DFA) -> None:
        for state in dfa.states:
            for symbol, target in state.moves.items():
                if isinstance(symbol, Nonterminal):
                    sa.table_new_state.setdefault(state.id, {})[symbol] = target.id

def make_sa_file(filename: str, sa: SA) -> None:
    pickled = pickle.dumps(sa)
    compressed = zlib.compress(pickled, level=9)
    b64_sa: str = base64.b64encode(compressed).decode('utf-8')

    log(f'[Info] Generated SA size: {len(b64_sa)}')

    all_src = inspect.getsource(sys.modules[__name__])
    before_preamble_end = all_src.split('# end preamble', 1)[0]
    preamble = before_preamble_end.split('# begin preamble', 1)[1]

    src = OrderedDict([
        ('preamble_src', preamble.replace('{{ SA_PICKLE_BASE64 }}', b64_sa)),
        ('tuple_hash_src', inspect.getsource(tuple_hash)),
        ('out_src', inspect.getsource(out)),
        ('log_src', inspect.getsource(log)),
        ('lr_item_src', inspect.getsource(LRItem)),
        ('right_side_src', inspect.getsource(RightSide)),
        ('nfa_state_src', inspect.getsource(NFAState)),
        ('nonterminal_src', inspect.getsource(Nonterminal)),
        ('terminal_src', inspect.getsource(Terminal)),
        ('sa_action_type_src', inspect.getsource(SAActionType)),
        ('sa_action_src', inspect.getsource(SAAction)),
        ('sa_action_reduce_src', inspect.getsource(SAActionReduce)),
        ('sa_action_shift_src', inspect.getsource(SAActionShift)),
        ('sa_action_accept_src', inspect.getsource(SAActionAccept)),
        ('sa_action_reject_src', inspect.getsource(SAActionReject)),
        ('token_src', inspect.getsource(Token)),
        ('ast_src', inspect.getsource(AST)),
        ('sa_src', inspect.getsource(SA)),
        ('sa_main_src', inspect.getsource(sa_main)),
        ('entrypoint_src', 'if __name__ == \'__main__\':\n    sa_main()')
    ])

    src_str = ''    
    for _, class_src in src.items():
        src_str += class_src + '\n'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(src_str)

def sa_main() -> None:
    sa = SA.from_pickle(SA_PICKLE_BASE64)
    ast = sa.parse_from_stdin()
    out(ast)

def main() -> None:
    log(f'[Info] Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')

    sa: SA = SAUtils.from_stdin()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, OUTPUT_FILENAME)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    make_sa_file(output_path, sa)

if __name__ == '__main__':
    main()
