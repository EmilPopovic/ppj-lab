from src.lab1.GLA import Automaton, log

def draw_automaton(automaton: Automaton, filename: str = "automaton"):
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
                display_symbol = 'ε' if symbol is None else symbol
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
