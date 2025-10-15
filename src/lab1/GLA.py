import inspect
from collections import OrderedDict

# begin preamble
import sys
import json
import pickle
import base64
from typing import Generator, Dict, List, Set, Optional, Tuple

LA_PICKLE_BASE64 = '{{ LA_PICKLE_BASE64 }}'

EPSILON = None

Symbol = Optional[str]
# end preamble

OUTPUT_FILENAME = 'LeksickiAnalizator.py'

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, set):
            return list(o)
        
        if isinstance(o, State):
            result = {
                'id': o.id,
                'is_acceptable': o.is_acceptable,
                'rule_id': o.rule_id,
                'transitions': {}
            }
            
            # Store only state IDs in transitions
            for symbol, states in o.transitions.items():
                result['transitions'][symbol] = [s.id for s in states]
            
            return result
        
        if hasattr(o, '__dict__'):
            return o.__dict__
        
        return super().default(o)

class State:
    """A state of an epsilon NFA"""
    __last_id: int = 0

    def __init__(self, is_acceptable: bool = False) -> None:
        self.id = State.__last_id
        State.__last_id += 1

        self.is_acceptable: bool = is_acceptable
        self.transitions: Dict[Symbol, Set[State]] = {}

        self.rule_id: int = -1

    def immediate_transition(self, symbol: Symbol) -> Set['State']:
        return self.transitions.get(symbol, set())
    
    def add_epsilon(self, other: 'State') -> None:
        epsilon = self.transitions.get(EPSILON, set())
        epsilon.add(other)
        self.transitions.setdefault(EPSILON, epsilon)

    def add_transition(self, c: Symbol, other: 'State') -> None:
        next_states = self.transitions.get(c, set())
        next_states.add(other)
        self.transitions.setdefault(c, next_states)

    @staticmethod
    def epsilon_set(states: Set['State']) -> Set['State']:
        epsilon = set(states)
        stack = list(states)

        while stack:
            state = stack.pop()
            for next_state in state.immediate_transition(EPSILON):
                if next_state not in epsilon:
                    epsilon.add(next_state)
                    stack.append(next_state)

        return epsilon

    def epsilon(self) -> Set['State']:
        return State.epsilon_set({self})

    @staticmethod
    def transition_set(states: Set['State'], symbol: Symbol) -> Set['State']:
        return set.union(*(state.transition(symbol) for state in states)) if states else set()

    def transition(self, symbol: Symbol) -> Set['State']:
        return State.epsilon_set(self.immediate_transition(symbol))

class Automaton:
    """Epsilon NFA with simulation logic"""

    def __init__(self, start_state: State, end_state: State) -> None:
        self.states: Set[State] = {start_state, end_state}

        self.start_state: State = start_state
        self.end_state: State = end_state

        self.current_states: Set[State] = start_state.epsilon()

    def add_state(self, new_state: State) -> None:
        self.states.add(new_state)

    def add_states(self, new_states: Set['State']):
        self.states.update(new_states)

    def simulate(self, inputs: str) -> bool:
        accepts = False
        for c in inputs:
            accepts = self.nextc(c)
        return accepts

    def nextc(self, c: str) -> bool:
        self.current_states = State.transition_set(self.current_states, c)
        return any([state.is_acceptable for state in self.current_states])
    
    def match(self, input: str, start_idx: int = 0) -> Optional[Tuple[int, int]]:        
        self.reset()
        match: Optional[Tuple[int, int]] = None

        i = start_idx
        prev_accepting = False
        accepting = False
        
        while i < len(input):
            c = input[i]
            prev_accepting = accepting
            accepting = self.nextc(c)
            
            if not self.current_states:
                start_idx = i + 1
                self.reset()
                if prev_accepting:
                    break

            if accepting:
                match = (start_idx, i + 1)

            i += 1
            
        return match

    def matches(self, input: str) -> Generator[Tuple[int, int], None, None]:
        i = 0
        while True:
            match = self.match(input, i)
            if match is None:
                break
            _, i = match
            yield match

    def reset(self) -> None:
        """Resets the automaton. Used before starting a new simulation when not in initial state."""
        self.current_states = self.start_state.epsilon()

    def to_json(self) -> str:
        return str(self)

    def __repr__(self) -> str:
        return json.dumps(
            {
                'states': self.states,
                'start_state': self.start_state,
                'end_state': self.end_state,
            },
            indent=2,
            cls=CustomEncoder
        )

class AutomatonFactory:

    @staticmethod
    def from_rule(rule: 'Rule') -> Automaton:
        automaton = AutomatonFactory.from_re(rule.regex)
        automaton.end_state.rule_id = rule.id
        return automaton

    @staticmethod
    def from_re(re: str) -> Automaton:
        automaton = AutomatonFactory.__from_re(re)
        automaton.end_state.is_acceptable = True
        return automaton

    @staticmethod
    def __from_re(re: str) -> Automaton:
        start_state = State()
        end_state = State()
        automaton = Automaton(start_state, end_state)
        
        depth = 0
        before_parenthesis_state = start_state 
        current_state = start_state

        root_parenthesis_str = ''
        is_root_parenthesis_str = False
        backslash_count = 0
        
        for c in re:

            if not (depth == 0 and c == '|' and backslash_count % 2 == 0):

                if c == '(' and backslash_count % 2 == 0:
                    if depth == 0:
                        root_parenthesis_str = ''
                        is_root_parenthesis_str = True
                        before_parenthesis_state = current_state
                    depth += 1

                elif c == ')' and backslash_count % 2 == 0:
                    depth -= 1
                    if depth == 0:
                        is_root_parenthesis_str = False

                        inner_automaton = AutomatonFactory.__from_re(root_parenthesis_str[1:])
                        automaton.add_states(inner_automaton.states)

                        current_state.add_epsilon(inner_automaton.start_state)
                        current_state = inner_automaton.end_state

                elif c == '\\':
                    if backslash_count % 2 == 1 and depth == 0:
                        before_parenthesis_state = current_state
                        new_state = State()
                        current_state.add_transition(c, new_state)
                        automaton.add_state(new_state)
                        current_state = new_state
                    backslash_count += 1
                 
                elif c == '*' and depth == 0 and backslash_count % 2 == 0:
                    before_parenthesis_state.add_epsilon(current_state)
                    current_state.add_epsilon(before_parenthesis_state)
                    before_parenthesis_state = current_state
                
                elif depth == 0:
                    sym: Symbol = c

                    if c == 'n' and backslash_count % 2 == 1:
                        sym = '\n'
                    elif c == 't' and backslash_count % 2 == 1:
                        sym = '\t'
                    elif c == '_' and backslash_count % 2 == 1:
                        sym = ' '
                    elif c == '$' and backslash_count % 2 == 0:
                        sym = None

                    before_parenthesis_state = current_state
                    new_state = State()
                    current_state.add_transition(sym, new_state)
                    automaton.add_state(new_state)
                    current_state = new_state

                if is_root_parenthesis_str:
                    root_parenthesis_str += c

                if c != '\\':
                    backslash_count = 0

            else:
                current_state.add_epsilon(end_state)

                before_parenthesis_state = start_state
                current_state = start_state
                backslash_count = 0

        current_state.add_epsilon(end_state)

        return automaton

class Rule:
    last_id = 0

    def __init__(self) -> None:
        self.id = Rule.last_id
        Rule.last_id += 1

        self.state: str = ''
        self.regex: str = ''
        self.token: Optional[str] = None
        self.increment_line: bool = False
        self.next_state: Optional[str] = None
        self.cutoff: Optional[int] = None
        self.automaton: Optional[Automaton] = None

    def __repr__(self) -> str:
        return json.dumps(self.__dict__, indent=2, cls=CustomEncoder)
    
class Token:

    def __init__(self, type: str, line_number: int, source: str) -> None:
        self.type: str = type
        self.line_number: int = line_number
        self.source: str = source

    def __repr__(self) -> str:
        return f'{self.type} {self.line_number} {self.source}'

class LA:
    """A Lexical Analyzer object, usually created using LAFactory"""

    def __init__(self) -> None:
        self.reg_defs: dict[str, str] = {}
        self.all_states: set[str] = set()
        self.state: str = ''
        self.start_state: str = ''
        self.token_types: List[str] = []
        self.rules: List[Rule] = []
        self.re_automaton: Optional[Automaton] = None

        self.source: str = ''
        self.start_idx: int = 0
        self.last_accepted_idx: int = -1

        self.line_number = 1

    def __token(self) -> Optional[Token]:
        if self.start_idx >= len(self.source):
            raise EOFError()

        if self.re_automaton is None:
            raise ValueError('Lexer Automaton is None')

        applicable_rules = [rule for rule in self.rules if rule.state == self.state]
        applicable_states: Set[State] = set()
        applicable_end_states: Set[State] = set()

        for rule in applicable_rules:
            if rule.automaton:
                applicable_states.update(rule.automaton.states)
                applicable_end_states.add(rule.automaton.end_state)

        last_found_rule_id: int = -1
        self.re_automaton.reset()

        for i, c in enumerate(self.source[self.start_idx:]):
            self.re_automaton.nextc(c)

            if not (self.re_automaton.current_states & applicable_states):
                break

            accepting_states = sorted(
                [state for state in self.re_automaton.current_states & applicable_end_states],
                key=lambda state: state.rule_id
            )

            if accepting_states:
                last_found_rule_id = accepting_states[0].rule_id
                self.last_accepted_idx = self.start_idx + i

        rule = next((r for r in self.rules if r.id == last_found_rule_id), None)

        if rule is None:
            self.last_accepted_idx = self.start_idx
            self.start_idx += 1

            log(f'Error on line {self.line_number}')
            raise ValueError()

        token_type = rule.token
        
        line_number = self.line_number
        if rule.increment_line:
            self.line_number += 1

        if rule.next_state:
            self.state = rule.next_state

        if rule.cutoff is not None:
            source = self.source[self.start_idx : self.start_idx + rule.cutoff]
            self.start_idx += rule.cutoff
            self.last_accepted_idx = self.start_idx - 1
        else:
            source = self.source[self.start_idx:self.last_accepted_idx+1]
            self.start_idx = self.last_accepted_idx + 1

        if token_type is None:
            return None

        return Token(token_type, line_number, source)

    def token(self) -> Optional[Token]:
        while True:
            try:
                token = self.__token()

                if token is not None:
                    return token

            except EOFError as _:
                return None
            except ValueError as _:
                continue

    def tokens(self) -> Generator[Token, None, None]:
        while True:
            token = self.token()
            if token is None:
                break
            yield token

    def __repr__(self) -> str:
        return json.dumps(self.__dict__, indent=2, cls=CustomEncoder)
    
    @staticmethod
    def from_pickle(b64_pickle: str) -> 'LA':
        la: LA = pickle.loads(base64.b64decode(b64_pickle.encode('utf-8')))
        return la

class LAUtils:
    """Factory for creating Lexical Analyzer objects"""

    _letters_re = 'a|b|c|d|e|f|g|h|i|j|k|l|m|n|o|p|q|r|s|t|u|v|w|x|y|z'
    _all_letters_re = f'{_letters_re}|{_letters_re.upper()}'
    _word_re = f'({_all_letters_re})({_all_letters_re})*'
    _macro_re = '{' + _word_re + '}'

    _macros_automaton = None

    @staticmethod
    def compile(la: LA) -> None:
        start_state = State()
        la.re_automaton = Automaton(start_state, State())

        for rule in la.rules:
            rule.automaton = AutomatonFactory.from_rule(rule)
            if rule.automaton:
                start_state.add_epsilon(rule.automaton.start_state)

        la.state = la.start_state

    @classmethod
    def macros_automaton(cls) -> Automaton:
        if cls._macros_automaton is None:
            cls._macros_automaton = AutomatonFactory.from_re(cls._macro_re)
        return cls._macros_automaton

    @staticmethod
    def resolve_macros(regex: str, reg_defs: 'dict[str, str]') -> str:
        """Replaces {macros} in regular expressions"""   
        result = ''
        last_end = 0
        
        for start, end in LAUtils.macros_automaton().matches(regex):
            result += regex[last_end:start]
            last_end = end

            result += f'({reg_defs.get(regex[start+1 : end-1], regex[start:end])})'

        if last_end < len(regex):
            result += regex[last_end:]

        return result

    @staticmethod
    def from_stdin() -> LA:
        """Parses a .lan file redirected to stdin to create an LA (Lexical Analyzer) object"""

        def read_input() -> Generator[str, None, None]:
            while True:
                try:
                    yield input()
                except EOFError:
                    break

        la = LA()
        data = read_input()

        for row in data:
            if row.startswith('{') and len(row) > 1:
                reg_def_name, regex = row[1:].split('} ', 1)
                la.reg_defs[reg_def_name] = LAUtils.resolve_macros(regex, la.reg_defs)

            elif row.startswith('%X'):
                _, *states_list = row.split(' ')
                la.start_state = states_list[0]
                la.all_states = set(states_list)

            elif row.startswith('%L'):
                _, *tokens = row.split(' ')
                tokens = set(tokens)

            elif row.startswith('<'):
                rule = Rule()
                la.rules.append(rule)

                state_name, regex = row[1:].split('>', 1)
                rule.state = state_name
                rule.regex = LAUtils.resolve_macros(regex, la.reg_defs)

                next(data)
                first_arg = next(data)
                rule.token = first_arg if first_arg != '-' else None

                while True:
                    arg = next(data)
                    if arg == '}':
                        break
                    elif arg.startswith('NOVI_REDAK'):
                        rule.increment_line = True
                    elif arg.startswith('VRATI_SE'):
                        rule.cutoff = int(arg.split(' ')[1])
                    elif arg.startswith('UDJI_U_STANJE'):
                        rule.next_state = arg.split(' ')[1]

            else:
                raise Exception('Something broke /(._. )\\')
    
        LAUtils.compile(la)

        return la
    
def make_la_file(filename: str, la: LA) -> None:
    b64_la: str = base64.b64encode(pickle.dumps(la)).decode('utf-8')
    
    all_src = inspect.getsource(sys.modules[__name__])
    before_preamble_end = all_src.split('# end preamble', 1)[0]
    preamble = before_preamble_end.split('# begin preamble', 1)[1]

    src = OrderedDict([
        ('preamble_src', preamble.replace('{{ LA_PICKLE_BASE64 }}', b64_la)),
        ('out_src', inspect.getsource(out)),
        ('log_src', inspect.getsource(log)),
        ('custom_encoder_src', inspect.getsource(CustomEncoder)),
        ('state_src', inspect.getsource(State)),
        ('automaton_src', inspect.getsource(Automaton)),
        ('rule_src', inspect.getsource(Rule)),
        ('token_src', inspect.getsource(Token)),
        ('la_src', inspect.getsource(LA)),
        ('la_main_src', inspect.getsource(la_main)),
        ('entrypoint_src', 'if __name__ == \'__main__\':\n    la_main()')
    ])

    src_str = ''    
    for _, class_src in src.items():
        src_str += class_src + '\n'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(src_str)

def la_main() -> None:
    la = LA.from_pickle(LA_PICKLE_BASE64)

    la.source = sys.stdin.read()

    for t in la.tokens():
        out(t)

def main() -> None:
    la = LAUtils.from_stdin()

    if la.re_automaton:
        make_la_file(OUTPUT_FILENAME, la)
    else:
        raise Exception('LA must be compiled before generating file')
    
if __name__ == '__main__':
    main()
