from typing import Optional, List

class Type:
    def __init__(self, name: str, is_const: bool = False, nested_type: Optional['Type | FuncSignature'] = None) -> None:
        self.name: str = name
        self.is_const: bool = is_const
        self.nested_type: Optional['Type | FuncSignature'] = nested_type

    def implicitly_reduces_to(self, other: 'Type') -> bool:
        if self.name == other.name:
            return True
        elif self.name == 'char':
            return other.name == 'int'
        return False
    
    def explicitly_reduces_to(self, other: 'Type') -> bool:
        if self.name == other.name:
            return True
        elif self.name == 'char':
            return other.name == 'int'
        elif self.name == 'int':
            return other.name == 'char'
        return False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Type):
            return self.name == other.name and self.nested_type == other.nested_type
        return False
    
    def __repr__(self) -> str:
        res = f'{self.name}'
        if isinstance(self.nested_type, Type):
            res += f'[{self.nested_type.name}]'
        return res

class FuncSignature:
    def __init__(self, return_type: Type, arg_types: List[Type]) -> None:
        self.return_type: Type = return_type
        self.arg_types: List[Type] = arg_types

    def callable_with(self, args: List[Type]) -> bool:
        if len(args) != len(self.arg_types):
            return False
        
        for i in range(len(args)):
            if not args[i].implicitly_reduces_to(self.arg_types[i]):
                return False
        return True

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FuncSignature):
            return self.return_type == other.return_type and self.arg_types == other.arg_types
        return False
    
    def __repr__(self) -> str:
        return f'{self.arg_types} -> {self.return_type}'
