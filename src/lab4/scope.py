from typing import Optional, List, Tuple

from type import Type, FuncSignature

class Symbol:
    def __init__(self, name: str, type: Optional[Type], is_l_expr: bool) -> None:
        self.name: str = name
        self.type: Optional[Type] = type
        self.is_l_expr: bool = is_l_expr
        self.const_val: 'Optional[int | str]' = None
        self.frame_offset: int = 0
        self.parent: Optional[Scope] = None

    def __repr__(self) -> str:
        if self.type and isinstance(self.type.nested_type, FuncSignature):
            type = self.type.nested_type
        else:
            type = self.type
        return f'[{type}] {self.name}'

class Scope:
    root_scope: 'Scope' = None  # type: ignore

    def __init__(self, parent: Optional['Scope'], type: str) -> None:
        self.parent: Optional[Scope] = parent
        self.type: str = type
        self.children: List = []

    def add_child(self, child: 'Symbol | Scope') -> None:
        self.children.append(child)
        child.parent = self

    def get_symbol(self, name: str, levels_removed: int = 0) -> Tuple[Optional[Symbol], int, bool]:
        with_name = [c for c in self.children if isinstance(c, Symbol) and c.name == name]
        if len(with_name) > 0:
            return with_name[0], levels_removed, self == Scope.root_scope
        elif self.parent:
            return self.parent.get_symbol(name, levels_removed + 1)
        return None, 0, False

    def __repr__(self) -> str:
        return self.__repr_inner(0)[:-1]

    def __repr_inner(self, indent: int) -> str:
        indent_str = ' ' * indent
        result = f'{indent_str}{self.type}\n'

        for child in self.children:
            if child is None:
                result += f'{indent_str} $\n'
            elif isinstance(child, Symbol):
                result += f'{indent_str} {child}\n'
            else:
                result += child.__repr_inner(indent + 1)

        return result

Scope.root_scope = Scope(None, 'root')
