import re
import sys
import json
from typing import Generator, Dict, List, Set, Optional, Match

ANALYZER = """

"""

class CustomEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, set):
            return list(o)
        if hasattr(o, '__dict__'):
            return o.__dict__
        return super().default(o)

class State:
    """A state of an epsilon NFA"""

    def __init__(self, name: str, is_acceptable: bool) -> None:
        self.name: str = name
        self.is_acceptable: bool = is_acceptable
        self.transitions: Dict[str, Set[State]] = {}

    def immediate_transition(self, symbol: str) -> Set['State']:
        return self.transitions.get(symbol, set())

    @staticmethod
    def epsilon_set(states: Set['State']) -> Set['State']:
        epsilon = set(states)
        stack = list(states)

        while stack:
            state = stack.pop()
            for next_state in state.immediate_transition('$'):
                if next_state not in epsilon:
                    epsilon.add(next_state)
                    stack.append(next_state)

        return epsilon

    def epsilon(self) -> Set['State']:
        return State.epsilon_set({self})

    @staticmethod
    def transition_set(states: Set['State'], symbol: str) -> Set['State']:
        return set.union(*(state.transition(symbol) for state in states)) if states else set()

    def transition(self, symbol: str) -> Set['State']:
        return State.epsilon_set(self.immediate_transition(symbol))

    def __lt__(self, other):
        return self.name < other.name

class Automaton:
    """Epsilon NFA with simulation logic"""

    def __init__(self, states: Set[State], initial_state: State) -> None:
        self.states: Set[State] = states
        self.initial_state: State = initial_state
        self.current_states: Set[State] = initial_state.epsilon()

    def simulate(self, inputs: List[str]) -> None:
        """
        Simulates the working of the epsilon NFA on a single whole input string (list of symbols)
        
        Each symbol can itself be a string.

        Outputs a list of current states after every step.
        """
        out(self.current_states_string(), end='')
        for symbol in inputs:
            out('|', end='')
            self.current_states = State.transition_set(self.current_states, symbol)
            out(self.current_states_string(), end='')
        out()

    def current_states_string(self):
        """Returns a comma-separated list of current states as a string, '#' if none."""
        return ','.join(state.name for state in sorted(self.current_states)) if self.current_states else '#'

    def reset(self) -> None:
        """Resets the automaton. Used before starting a new simulation when not in initial state."""
        self.current_states = self.initial_state.epsilon()

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

def resolve_macros(regex: str, reg_defs: 'dict[str, str]') -> str:
    """Replaces {macros} in regular expressions"""
    def replacer(match: Match[str]) -> str:
        key = match.group(1)
        return f'({reg_defs.get(key, match.group(0))})'
    
    result = re.sub(r'\{(\w+)\}', replacer, regex)
    return result

class Rule:

    def __init__(self) -> None:
        self.state: str = ''
        self.regex: str = ''
        self.token: Optional[str] = None
        self.increment_line: bool = False
        self.next_state: Optional[str] = None
        self.cutoff: int = 0

    def __repr__(self) -> str:
        return json.dumps(self.__dict__, indent=2, cls=CustomEncoder)

class LA:
    """A Lexical Analyzer object, usually created using LAFactory"""

    def __init__(self) -> None:
        self.reg_defs: dict[str, str] = {}
        self.states: set[str] = set()
        self.start_state: str = ''
        self.tokens: list[str] = []
        self.rules: list[Rule] = []

    def to_file(self, filename: str) -> None: ...

    def __repr__(self) -> str:
        return json.dumps(self.__dict__, indent=2, cls=CustomEncoder)

class LAFactory:
    """Factory for creating Lexical Analyzer objects"""

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
            log(f'ROW: {row}')

            if row.startswith('{') and len(row) > 1:
                reg_def_name, regex = row[1:].split('} ', 1)
                la.reg_defs[reg_def_name] = resolve_macros(regex, la.reg_defs)

            elif row.startswith('%X'):
                _, *states_list = row.split(' ')
                la.start_state = states_list[0]
                la.states = set(states_list)

            elif row.startswith('%L'):
                _, *tokens = row.split(' ')
                tokens = set(tokens)

            elif row.startswith('<'):
                rule = Rule()
                la.rules.append(rule)

                state_name, regex = row[1:].split('>', 1)
                rule.state = state_name
                rule.regex = resolve_macros(regex, la.reg_defs)

                next(data)
                first_arg = next(data)
                log(f'FIRST ARG: {first_arg}')
                rule.token = first_arg if first_arg != '-' else None

                while True:
                    arg = next(data)
                    log(f'ARG: {arg}')
                    if arg == '}':
                        break
                    elif arg.startswith('NOVI_REDAK'):
                        rule.increment_line = True
                    elif arg.startswith('VRATI_SE'):
                        rule.cutoff = int(arg.split(' ')[1])
                    elif arg.startswith('UDJI_U_STANJE'):
                        rule.next_state = arg.split(' ')[1]

            else:
                log('/(._. )\\')
    
        return la

def main() -> None:
    la = LAFactory.from_stdin()

    log(la)

    la.to_file('LA.py')
    
if __name__ == '__main__':
    main()
