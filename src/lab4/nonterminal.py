from typing import Dict, List

from scope import Scope

class Nonterminal:
    def __init__(self, name: str, scope: 'Scope') -> None:
        self.name: str = name
        self.scope = scope
        self.attributes: Dict[str, object] = {}

    def add_attr(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def get_attr(self, key: str) -> object:
        return self.attributes[key]

    def copy_attr_from(self, src: 'Nonterminal', names: List[str]) -> None:
        for name in names:
            self.add_attr(name, src.get_attr(name))

    def __repr__(self) -> str:
        return f'{self.name} {self.attributes}'
