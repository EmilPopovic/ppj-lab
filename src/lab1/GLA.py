import re
import sys
from typing import Generator, Dict, List, Set, Optional, Match

ANALYZER = """

"""

class State:
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
    def __init__(self, states: Set[State], initial_state: State) -> None:
        self.states: Set[State] = states
        self.initial_state: State = initial_state
        self.current_states: Set[State] = initial_state.epsilon()

    def simulate(self, inputs: List[str]) -> None:
        out(self.current_states_string(), end='')
        for symbol in inputs:
            out('|', end='')
            self.current_states = State.transition_set(self.current_states, symbol)
            out(self.current_states_string(), end='')
        out()

    def current_states_string(self):
        return ','.join(state.name for state in sorted(self.current_states)) if self.current_states else '#'

    def reset(self) -> None:
        self.current_states = self.initial_state.epsilon()

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

class Rule:
    state: str = ''
    regex: str = ''
    token: Optional[str] = None
    increment_line: bool = False
    next_state: Optional[str] = None
    cutoff: int = 0

    def __repr__(self) -> str:
        return f'state: {self.state} | regex: {self.regex} | token: {self.token} {"| inc" if self.increment_line else ""} | next state: {self.next_state} | cutoff: {self.cutoff}'

def resolve_macros(regex: str, reg_defs: 'dict[str, str]') -> str:
    def replacer(match: Match[str]) -> str:
        key = match.group(1)
        return f'({reg_defs.get(key, match.group(0))})'
    
    result = re.sub(r'\{(\w+)\}', replacer, regex)
    return result

def main() -> None:
    def read_input() -> Generator[str, None, None]:
        while True:
            try:
                yield input()
            except EOFError:
                break

    reg_defs: dict[str, str] = {}

    states = []
    start_state = ''
    tokens = []
    rules: list[Rule] = []

    data = read_input()

    for row in data:
        log(f'ROW: {row}')

        if row.startswith('{') and len(row) > 1:
            reg_def_name, regex = row[1:].split('} ', 1)
            reg_defs[reg_def_name] = resolve_macros(regex, reg_defs)

        elif row.startswith('%X'):
            _, *states = row.split(' ')
            start_state = states[0]
            states = set(states)

        elif row.startswith('%L'):
            _, *tokens = row.split(' ')
            tokens = set(tokens)

        elif row.startswith('<'):
            rule = Rule()
            rules.append(rule)

            state_name, regex = row[1:].split('>', 1)
            rule.state = state_name
            rule.regex = resolve_macros(regex, reg_defs)

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

    log('----- REGULAR DEFINITIONS -----')
    log(reg_defs)
    log('----- STATES -----')
    log(states)
    log('----- TOKENS -----')
    log(tokens)
    log('----- RULES -----')
    log(rules)
    
if __name__ == '__main__':
    main()
