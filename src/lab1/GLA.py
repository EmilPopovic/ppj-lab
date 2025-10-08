import sys
from typing import Generator, Dict, List, Set

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
    def __init__(self, states: Set[State], alphabet: Set[str], initial_state: State) -> None:
        self.states: Set[State] = states
        self.alphabet: Set[str] = alphabet
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

# def main() -> None:
#     def read_input() -> Generator[str, None, None]:
#         while True:
#             try:
#                 yield input()
#             except EOFError:
#                 break

#     data = read_input()

#     input_strings = [s.split(',') for s in next(data).split('|')]
#     state_names = next(data).split(',')
#     alphabet = set(next(data).split(','))
#     acceptable_state_names = set(next(data).split(','))
#     initial_state = next(data)

#     states = {State(name, name in acceptable_state_names) for name in state_names}
#     states_dict = {state.name: state for state in states}
#     initial_state = states_dict[initial_state]

#     for line in data:
#         key_part, value = line.split('->')
#         state, symbol = key_part.split(',')
#         from_state = states_dict[state]
#         to_states = {states_dict[to_state] for to_state in value.split(',')} if value != '#' else set()
#         from_state.transitions[symbol] = to_states

#     automaton = Automaton(states, alphabet, initial_state)
#     for s in input_strings:
#         automaton.simulate(s)
#         automaton.reset()

def main() -> None:
    rows = [line.strip() for line in sys.stdin]
    for row in rows:
        log(row)

    ...

if __name__ == '__main__':
    main()
