import re
import sys
import json
from typing import Generator, Dict, List, Set, Optional, Match

ANALYZER = """

"""

EPSILON = '$'

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, set):
            return list(o)
        
        if isinstance(o, State):
            result = {
                "id": o.id,
                "is_acceptable": o.is_acceptable,
                "transitions": {}
            }
            
            # Store only state IDs in transitions
            for symbol, states in o.transitions.items():
                result["transitions"][symbol] = [s.id for s in states]
            
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
        self.transitions: Dict[str, Set[State]] = {}

    def immediate_transition(self, symbol: str) -> Set['State']:
        return self.transitions.get(symbol, set())
    
    def add_epsilon(self, other: 'State') -> None:
        epsilon = self.transitions.get(EPSILON, set())
        epsilon.add(other)
        self.transitions.setdefault(EPSILON, epsilon)

    def add_transition(self, c: str, other: 'State') -> None:
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
    def transition_set(states: Set['State'], symbol: str) -> Set['State']:
        return set.union(*(state.transition(symbol) for state in states)) if states else set()

    def transition(self, symbol: str) -> Set['State']:
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

    def reset(self) -> None:
        """Resets the automaton. Used before starting a new simulation when not in initial state."""
        self.current_states = self.start_state.epsilon()

    def __repr__(self) -> str:
        return json.dumps(self.states, indent=2, cls=CustomEncoder)

class AutomatonFactory:

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

        left_re = ''
        root_parenthesis_str = ''
        is_root_parenthesis_str = False
        backslash_count = 0
        
        for c in re:
            log(f'c: {c}, bc: {backslash_count}, d: {depth}')

            if not (depth == 0 and c == '|' and backslash_count % 2 == 0):
                log('+')
                left_re += c

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

                        log(f'parenthesis regex: {root_parenthesis_str[1:]}')
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
                    sym = c

                    if c == 'n' and backslash_count % 2 == 1:
                        sym = '\n'
                    elif c == 't' and backslash_count % 2 == 1:
                        sym = '\t'
                    elif c == '_' and backslash_count % 2 == 1:
                        sym = ' '

                    before_parenthesis_state = current_state
                    new_state = State()
                    current_state.add_transition(sym, new_state)
                    automaton.add_state(new_state)
                    current_state = new_state

                if is_root_parenthesis_str:
                    root_parenthesis_str += c
                    log(f'rps: {root_parenthesis_str}')

                if c != '\\':
                    backslash_count = 0

            else:
                current_state.add_epsilon(end_state)

                log(f'root regex: {left_re}')
                left_re = ''

                before_parenthesis_state = start_state
                current_state = start_state
                backslash_count = 0

        current_state.add_epsilon(end_state)

        return automaton

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

def draw_automaton_graphviz(automaton: Automaton, filename: str = "automaton"):
    """Draw automaton using Graphviz for publication-quality output"""
    try:
        from graphviz import Digraph
    except ImportError:
        print("Install graphviz: pip install graphviz")
        return
    
    dot = Digraph(comment='Automaton')
    dot.attr(rankdir='LR')  # Left to right layout
    
    # Add invisible start node for the start arrow
    dot.node('', shape='none', width='0')
    
    # Add all states
    for state in automaton.states:
        if state.is_acceptable:
            dot.node(str(state.id), shape='doublecircle')
        else:
            dot.node(str(state.id), shape='circle')
    
    # Add start arrow
    dot.edge('', str(automaton.start_state.id))
    
    # Group transitions between same states
    transitions_map = {}
    for state in automaton.states:
        for symbol, target_states in state.transitions.items():
            for target in target_states:
                edge_key = (state.id, target.id)
                # Display epsilon as ε
                display_symbol = 'ε' if symbol == '$' else symbol
                display_symbol = display_symbol.replace('\\', '\\\\').replace('"', '\\"').replace('\n', 'NL').replace('\t', 'TAB').replace(' ', 'SPACE')
                if edge_key in transitions_map:
                    transitions_map[edge_key].append(display_symbol)
                else:
                    transitions_map[edge_key] = [display_symbol]
    
    # Add edges with combined labels
    for (from_id, to_id), symbols in transitions_map.items():
        label = ', '.join(sorted(symbols))
        dot.edge(str(from_id), str(to_id), label=label)
    
    # Render the graph
    dot.render(filename, view=True, format='png', cleanup=True)
    log(f"Saved to {filename}.png")
    
    return dot
    
if __name__ == '__main__':
    # main()

    # regex = '((x|y)*a*|c(ef)*)|b|k'
    regex = r'(\)a|\_)\|\(|x*|y*'
    # regex = r'\||a'

    log(regex)

    automaton = AutomatonFactory.from_re(regex)

    draw_automaton_graphviz(automaton, 'a')

    # tests = [
    #     'b',
    #     'k',
    #     'bk',
    #     'cefef',
    #     'cefe',
    #     'xy',
    #     'xyya',
    #     'xca',
    # ]

    # for s in tests:
    #     log(f'{s} -> {automaton.simulate(s)}')
    #     automaton.reset()
