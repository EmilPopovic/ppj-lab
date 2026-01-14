import os
import time
import sys
from typing import Iterator, Optional, Tuple, List, Dict
from enum import Enum
from abc import ABC

OUTPUT_FILENAME = 'a.s'
ASM_PREAMBLE = \
"""    .text
    .global _start
_start:
    ldr sp, =0x20000
    bl f_main
    bx lr
    swi 0
"""

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

def line_depth(s: str) -> int:
    return len(s) - len(s.lstrip())

def get_line(iter: Iterator[str]) -> Tuple[Optional[str], int]:
    try:
        l = next(iter)
        return l.strip(), line_depth(l)
    except StopIteration:
        return None, -1

class ArithmeticOpcode(Enum):
    ADD = 'add'
    ADC = 'adc'
    SUB = 'sub'
    SBC = 'sbc'
    RSB = 'rsb'
    RSC = 'rsc'

class LogicOpcode(Enum):
    AND = 'and'
    ORR = 'orr'
    EOR = 'eor'
    BIC = 'bic'

class TestOpcode(Enum):
    CMP = 'cmp'
    CMN = 'cmn'
    TST = 'tst'
    TEQ = 'teq'

class MoveOpcode(Enum):
    MOV = 'mov'
    MVN = 'mvn'

class NopOpcode(Enum):
    NOP = 'nop'

class MultiplyOpcode(Enum):
    MUL = 'mul'

class MultiplyAccumulateOpcode(Enum):
    MLA = 'mla'

class StatusOpcode(Enum):
    MRS = 'mrs'
    MSR = 'msr'

class BranchOpcode(Enum):
    B = 'b'
    BL = 'bl'

class ControlOpcode(Enum):
    SWI = 'swi'

class LoadSingleOpcode(Enum):
    LDR = 'ldr'

class StoreSingleOpcode(Enum):
    STR = 'str'

class LoadStoreBlockOpcode(Enum):
    LDM = 'ldm'
    STM = 'stm'

class Cond(Enum):
    EQUAL = 'eq'
    NOT_EQUAL = 'ne'
    NEGATIVE = 'mi'
    POSITIVE = 'pl'
    OVERFLOW_SET = 'vs'
    OVERFLOW_CLEAR = 'vc'
    CARRY_SET = 'cs'
    UNSIGNED_HIGHER_OR_SAME = 'hs'
    CARRY_CLEAR = 'cc'
    UNSIGNED_LOWER = 'lo'
    UNSIGNED_HIGHER = 'hi'
    UNSIGNED_LOWER_OR_SAME = 'ls'
    SIGNED_GREATER_OR_EQUAL = 'ge'
    SIGNED_LESS_THAN = 'lt'
    SIGNED_GREATER_THAN = 'gt'
    SIGNED_LESS_OR_EQUAL = 'le'
    ALWAYS = ''

class WordOrByte(Enum):
    WORD = ''
    BYTE = 'b'

class HalfOrByte(Enum):
    HALF = 'h'
    BYTE = 'b'

class IndexingType(Enum):
    NO_INDEX = 0
    PREINDEX = 1
    POSTINDEX = 2

class ShiftType(Enum):
    LSL = 'lsl'
    LSR = 'lsr'
    ASR = 'asr'
    ROR = 'ror'

class Oprnd2(ABC):
    pass

class Oprnd2Rm(Oprnd2):
    def __init__(self, rm: int) -> None:
        self.rm: int = rm

    def __repr__(self) -> str:
        return f'r{self.rm}'

class Oprnd2Imm8(Oprnd2):
    def __init__(self, imm_8r: int) -> None:
        self.imm_8r: int = imm_8r
    
    def __repr__(self) -> str:
        return f'#{self.imm_8r}'

class Oprnd2ShiftImm5(Oprnd2):
    def __init__(self, rm: int, shift: ShiftType, imm_5: int) -> None:
        self.rm: int = rm
        self.shift: ShiftType = shift
        self.imm_5: int = imm_5

    def __repr__(self) -> str:
        return f'r{self.rm}, {self.shift} #{self.imm_5}'

class Oprnd2ShiftRs(Oprnd2):
    def __init__(self, rm: int, shift: ShiftType, rs: int) -> None:
        self.rm: int = rm
        self.shift: ShiftType = shift
        self.rs: int = rs

    def __repr__(self) -> str:
        return f'r{self.rm}, {self.shift} r{self.rs}'

class Oprnd2ShiftRRX(Oprnd2):
    def __init__(self, rm: int) -> None:
        self.rm = rm
    
    def __repr__(self) -> str:
        return f'r{self.rm}, rrx'

class Mode2(ABC):
    pass

class Mode3(ABC):
    pass

class Mode3RegiserOffset(Mode3):
    def __init__(
            self,
            rn: int,
            save_rn: bool,
            indexing: IndexingType,
            rm: Optional[int] = None,
            negate_rm: bool = False
    ) -> None:
        self.rn: int = rn
        self.rm: Optional[int] = rm
        self.save_rn: bool = save_rn
        self.indexing: IndexingType = indexing
        self.negate_rm: bool = negate_rm

    def __repr__(self) -> str:
        if self.rm is None:
            return f'[r{self.rn}]'
        
        rm_sign_str = "-" if self.negate_rm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[r{self.rn}, {rm_sign_str}r{self.rm}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[r{self.rn}], {rm_sign_str}r{self.rm}'

class Mode3ImmediateOffset(Mode3):
    def __init__(
            self,
            rn: int,
            save_rn: bool,
            indexing: IndexingType,
            imm_8: Optional[int],
            negate_imm: bool = False
    ) -> None:
        self.rn: int = rn
        self.imm_8: Optional[int] = imm_8
        self.save_rn: bool = save_rn
        self.indexing: IndexingType = indexing
        self.negate_imm: bool = negate_imm

    def __repr__(self) -> str:
        if self.imm_8 is None:
            return f'[r{self.rn}]'
        
        imm_sign_str = "-" if self.negate_imm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[r{self.rn}, #{imm_sign_str}{self.imm_8}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[r{self.rn}], #{imm_sign_str}{self.imm_8}'
    
class Mode3Label(Mode3):
    def __init__(self, label: str) -> None:
        self.label: str = label

    def __repr__(self) -> str:
        return self.label

class Mode4(Enum):
    INCREMENT_AFTER = 'ia'
    INCREMENT_BEFORE = 'ib'
    DECREMENT_AFTER = 'da'
    DECREMENT_BEFORE = 'db'

class ArithmeticLogicOp:
    def __init__(
            self,
            opcode: 'ArithmeticOpcode | LogicOpcode',
            rd: int,
            rn: int,
            oprnd2: Oprnd2,
            cond: Cond = Cond.ALWAYS,
            save_flags: bool = False
    ) -> None:
        self.opcode: 'ArithmeticOpcode | LogicOpcode' = opcode
        self.rd: int = rd
        self.rn: int = rn
        self.oprnd2: Oprnd2 = oprnd2
        self.cond: Cond = cond
        self.save_flags: bool = save_flags

    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}{"s" if self.save_flags else ""}'
        rd_str = f'r{self.rd}'
        rn_str = f'r{self.rn}'
        return f'    {opcode_str:<8} {rd_str:>3}, {rn_str:>3}, {self.oprnd2}'
    
class TestOp:
    def __init__(
            self,
            opcode: TestOpcode,
            rn: int,
            oprnd2: Oprnd2,
            cond: Cond = Cond.ALWAYS
    ) -> None:
        self.opcode: TestOpcode = opcode
        self.rn: int = rn
        self.oprnd2: Oprnd2 = oprnd2
        self.cond: Cond = cond

    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}'
        rn_str = f'r{self.rn}'
        return f'    {opcode_str:<8} {rn_str:>3}, {self.oprnd2}'
    
class MoveOp:
    def __init__(
            self,
            opcode: MoveOpcode,
            rd: int,
            oprnd2: Oprnd2,
            cond: Cond = Cond.ALWAYS
    ) -> None:
        self.opcode: MoveOpcode = opcode
        self.rd: int = rd
        self.oprnd2: Oprnd2 = oprnd2
        self.cond: Cond = cond

    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}'
        rd_str = f'r{self.rd}'
        return f'    {opcode_str:<8} {rd_str:>3}, {self.oprnd2}'
    
class NopOp:
    def __init__(self) -> None:
        self.opcode: NopOpcode = NopOpcode.NOP
    
    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}'
        return f'    {opcode_str:<8}'
    
class MultiplyOp:
    def __init__(
            self,
            rd: int,
            rm: int,
            rs: int,
            cond: Cond = Cond.ALWAYS,
            save_flags: bool = False
    ) -> None:
        self.opcode: MultiplyOpcode = MultiplyOpcode.MUL
        self.rd: int = rd
        self.rm: int = rm
        self.rs: int = rs
        self.cond: Cond = cond
        self.save_flags: bool = save_flags

    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}{"s" if self.save_flags else ""}'
        rd_str = f'r{self.rd}'
        rm_str = f'r{self.rm}'
        rs_str = f'r{self.rs}'
        return f'    {opcode_str:<8} {rd_str:>3}, {rm_str:>3}, {rs_str:>3}'

class MultiplyAccumulateOp:
    def __init__(
            self,
            rd: int,
            rm: int,
            rs: int,
            rn: int,
            cond: Cond = Cond.ALWAYS,
            save_flags: bool = False
    ) -> None:
        self.opcode: MultiplyAccumulateOpcode = MultiplyAccumulateOpcode.MLA
        self.rd: int = rd
        self.rm: int = rm
        self.rs: int = rs
        self.rn: int = rn
        self.cond: Cond = cond
        self.save_flags: bool = save_flags

    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}{"s" if self.save_flags else ""}'
        rd_str = f'r{self.rd}'
        rm_str = f'r{self.rm}'
        rs_str = f'r{self.rs}'
        rn_str = f'r{self.rn}'
        return f'    {opcode_str:<8} {rd_str:>3}, {rm_str:>3}, {rs_str:>3}, {rn_str:>3}'

class BranchOp:
    def __init__(
            self,
            opcode: BranchOpcode,
            label: str,
            cond: Cond
    ) -> None:
        self.opcode: BranchOpcode = opcode
        self.label: str = label
        self.cond: Cond = cond
    
    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}'
        return f'    {opcode_str:<8} {self.label}'
    
class SoftwareInterruptOp:
    def __init__(self, irq_num: int) -> None:
        self.opcode: ControlOpcode = ControlOpcode.SWI
        self.irq_num: int = irq_num

    def __repr__(self) -> str:
        return f'    {self.opcode:<8} {self.irq_num}'
    
class LoadStoreSingleMode2Op:
    def __init__(
            self,
            opcode: 'LoadSingleOpcode | StoreSingleOpcode',
            size: WordOrByte,
            rd: int,
            mode2: Mode2,
            cond: Cond = Cond.ALWAYS
    ) -> None:
        self.opcode: 'LoadSingleOpcode | StoreSingleOpcode' = opcode
        self.size: WordOrByte = size
        self.rd: int = rd
        self.mode2: Mode2 = mode2
        self.cond: Cond = cond
    
    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}{self.size}'
        rd_str = f'r{self.rd}'
        return f'    {opcode_str:<8} {rd_str:>3}, {self.mode2}'

class LoadStoreHalfMode3UnsignedOp:
    def __init__(
            self,
            opcode: 'LoadSingleOpcode | StoreSingleOpcode',
            rd: int,
            mode3: Mode3,
            cond: Cond = Cond.ALWAYS
    ) -> None:
        self.opcode: 'LoadSingleOpcode | StoreSingleOpcode' = opcode
        self.rd: int = rd
        self.mode3: Mode3 = mode3
        self.cond: Cond = cond

    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}h'
        rd_str = f'r{self.rd}'
        return f'    {opcode_str:<8} {rd_str:>3}, {self.mode3}'
    
class LoadSingleMode3SignedOp:
    def __init__(
            self,
            size: HalfOrByte,
            rd: int,
            mode3: Mode3,
            cond: Cond = Cond.ALWAYS
    ) -> None:
        self.opcode: LoadSingleOpcode = LoadSingleOpcode.LDR
        self.size: HalfOrByte = size
        self.rd: int = rd
        self.mode3: Mode3 = mode3
        self.cond: Cond = cond

    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}s{self.size}'
        rd_str = f'r{self.rd}'
        return f'    {opcode_str:<8} {rd_str:>3}, {self.mode3}'

class LoadStoreMultipleOp:
    def __init__(
            self,
            opcode: LoadStoreBlockOpcode,
            rd: int,
            mode4: Mode4,
            reglist: List[int],
            save_rd: bool,
            cond: Cond = Cond.ALWAYS
    ) -> None:
        self.opcode: LoadStoreBlockOpcode = opcode
        self.rd: int = rd
        self.mode4: Mode4 = mode4
        self.reglist: List[int] = reglist
        self.save_rd: bool = save_rd
        self.cond: Cond = cond
    
    def __repr__(self) -> str:
        opcode_str = f'{self.opcode}{self.cond}{self.mode4}'
        rd_str = f'r{self.rd}'
        reglist_str = f'{{ {", ".join(str(reg) for reg in self.reglist)} }}'
        return f'    {opcode_str} {rd_str:>3}{"!" if self.save_rd else ""}, {reglist_str}'

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

class Token:
    def __init__(self, name: str, line_number: int, source: str, symbol: Optional['Symbol'] = None) -> None:
        self.name: str = name
        self.line_number: int = line_number
        self.source: str = source
        self.symbol: Optional[Symbol] = symbol

    @property
    def is_int(self) -> bool:
        try:
            num = int(self.source)
            return num < 2 ** 31 and num >= -(2 ** 31)
        except ValueError:
            return False
        
    @property
    def is_char(self) -> bool:
        try:
            no_quotes = self.source[1:-1]
            if no_quotes.startswith('\\'):
                escape_map = {
                    '\\t': '\t',
                    '\\n': '\n',
                    '\\0': '\0',
                    "\\'": "'",
                    '\\"': '"',
                    '\\\\': '\\'
                }
                char = escape_map.get(no_quotes, no_quotes[1:])
            else:
                char = no_quotes

            ascii_val = ord(char) if len(char) == 1 else -1
            return 0 <= ascii_val < 2 ** 8
        except (TypeError, IndexError):
            return False
        
    @property
    def is_valid_str(self) -> bool:
        without_backslash = self.source.replace('\\\\', '')[1:-1]
        for i, c in enumerate(without_backslash):
            if c == '\\' and (i == len(without_backslash) or without_backslash[i+1] not in ['t', 'n', '0', '\'', '"']):
                return False
        return True 

    @staticmethod
    def from_str(s: str, symbol: Optional['Symbol'] = None) -> 'Token':
        token_type, line_num_str, *source = s.split()
        return Token(token_type, int(line_num_str), ' '.join(source), symbol) 

    def __repr__(self) -> str:
        return f'{self.name}({self.line_number},{self.source})'

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
    
class Symbol:
    def __init__(self, name: str, type: Optional[Type], is_l_expr: bool) -> None:
        self.name: str = name
        self.type: Optional[Type] = type
        self.is_l_expr: bool = is_l_expr

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

    def get_symbol(self, name: str) -> Optional[Symbol]:
        with_name = [c for c in self.children if isinstance(c, Symbol) and c.name == name]
        if len(with_name) > 0:
            return with_name[0]
        elif self.parent:
            return self.parent.get_symbol(name)
        return None

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

class ParseTree:
    def __init__(self, root: Nonterminal, parent: Optional['ParseTree']) -> None:
        self.root: Nonterminal = root
        self.children: List = []
        self.parent: Optional[ParseTree] = parent

    @property
    def name(self) -> str:
        return self.root.name
    
    @property
    def scope(self) -> Scope:
        return self.root.scope

    def add_attr(self, key: str, value: object) -> None:
        self.root.add_attr(key, value)

    def get_attr(self, key: str) -> object:
        return self.root.get_attr(key)

    def copy_attr_from(self, src: 'ParseTree', names: List[str]) -> None:
        self.root.copy_attr_from(src.root, names)

    def add_child(self, child: 'ParseTree | Token') -> None:
        self.children.append(child)

    def validate(self) -> Optional[str]:
        if e := self.validate_prijevodna_jedinica(): return e
        
        main = self.scope.get_symbol('main')

        if main is None or main.type != Type('function', nested_type=FuncSignature(return_type=Type('int'), arg_types=[])):
            return 'main'
        
        stack = [c for c in self.scope.children if isinstance(c, Scope)]

        while stack:
            c: Scope = stack.pop()
            
            for sym in [s for s in c.children if isinstance(s, Symbol) and s.type and s.type.name == 'function']:
                f = self.scope.get_symbol(sym.name)
                if f is None:
                    return 'funkcija'
                
                assert isinstance(sym, Symbol)
                assert isinstance(sym.type, Type)
                sym_signature = sym.type.nested_type

                assert isinstance(f, Symbol)
                assert isinstance(f.type, Type)
                f_signature = f.type.nested_type

                if sym_signature != f_signature:
                    return 'funkcija'

            stack.extend([d for d in c.children if isinstance(d, Scope)])

    def validate_primarni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)
        symbol = self.scope.get_symbol(first_child.source)

        if first_child.name == 'IDN':
            if symbol is None:
                return self.error_str
            self.add_attr('type', symbol.type)
            self.add_attr('is_l_expr', symbol.is_l_expr)
            
        elif first_child.name == 'BROJ':
            if not first_child.is_int:
                return self.error_str
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

        elif first_child.name == 'ZNAK':
            if not first_child.is_char:
                return self.error_str
            self.add_attr('type', Type('char'))
            self.add_attr('is_l_expr', False)

        elif first_child.name == 'NIZ_ZNAKOVA':
            if not first_child.is_valid_str:
                return self.error_str
            self.add_attr('type', Type('arr', nested_type=Type('char', is_const=True)))
            self.add_attr('is_l_expr', False)

        elif first_child.name == 'L_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            if e := second_child.validate_izraz(): return e
            self.copy_attr_from(second_child, ['type', 'is_l_expr'])

    def validate_postfiks_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<primarni_izraz>':
            if e := first_child.validate_primarni_izraz(): return e
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<postfiks_izraz>' and self.children[1].name in ['OP_INC', 'OP_DEC']:
            if e := first_child.validate_postfiks_izraz(): return e
            
            if not first_child.get_attr('is_l_expr'):
                return self.error_str
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == '<izraz>':
            if e := first_child.validate_postfiks_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            if first_child_type.name != 'arr':
                return self.error_str
            
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            if e := third_child.validate_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)
            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            assert isinstance(first_child_type.nested_type, Type)
            self.add_attr('type', first_child_type.nested_type)
            self.add_attr('is_l_expr', not first_child_type.nested_type.is_const)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == 'D_ZAGRADA':
            if e := first_child.validate_postfiks_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            first_child_nested_type = first_child_type.nested_type
            assert isinstance(first_child_nested_type, FuncSignature)
            first_child_return_type = first_child_nested_type.return_type
            first_child_args = first_child_nested_type.arg_types

            if len(first_child_args) > 0:
                return self.error_str
            
            self.add_attr('type', first_child_return_type)
            self.add_attr('is_l_expr', False)

        elif first_child.name == '<postfiks_izraz>' and self.children[2].name == '<lista_argumenata>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := (first_child.validate_postfiks_izraz() or third_child.validate_lista_argumenata()): return e

            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            first_child_nested_type = first_child_type.nested_type
            assert isinstance(first_child_nested_type, FuncSignature)
            first_child_return_type = first_child_nested_type.return_type

            third_child_types = third_child.get_attr('types')
            assert isinstance(third_child_types, list)

            if not first_child_nested_type.callable_with(third_child_types):
                return self.error_str
            
            self.add_attr('type', first_child_return_type)
            self.add_attr('is_l_expr', False)


    def validate_lista_argumenata(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            if e := first_child.validate_izraz_pridruzivanja(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.add_attr('types', [first_child_type])
        
        elif first_child.name == '<lista_argumenata>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := (first_child.validate_lista_argumenata() or third_child.validate_izraz_pridruzivanja()): return e
            
            first_child_types = first_child.get_attr('types')
            assert isinstance(first_child_types, list)

            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            first_child_types.append(third_child_type)
            self.add_attr('types', first_child_types)

    def validate_unarni_izraz(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<postfiks_izraz>':
            if e := first_child.validate_postfiks_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif isinstance(first_child, Token) and first_child.name in ['OP_INC', 'OP_DEC']:
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := second_child.validate_unarni_izraz(): return e
            
            if not second_child.get_attr('is_l_expr'):
                return self.error_str
            
            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

        elif isinstance(first_child, ParseTree) and first_child.name == '<unarni_operator>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := second_child.validate_cast_izraz(): return e
            
            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_cast_izraz(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<unarni_izraz>':
            if e := first_child.validate_unarni_izraz(): return e
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif isinstance(first_child, Token) and first_child.name == 'L_ZAGRADA':
            second_child = self.children[1]
            fourth_child = self.children[3]
            assert isinstance(second_child, ParseTree)
            assert isinstance(fourth_child, ParseTree)

            if e := (second_child.validate_ime_tipa() or fourth_child.validate_cast_izraz()): return e
            
            second_child_type = second_child.get_attr('type')
            fourth_child_type = fourth_child.get_attr('type')
            assert isinstance(second_child_type, Type)
            assert isinstance(fourth_child_type, Type)

            if not fourth_child_type.explicitly_reduces_to(second_child_type):
                return self.error_str
            
            self.add_attr('type', second_child_type)
            self.add_attr('is_l_expr', False)
    
    def validate_ime_tipa(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, ParseTree) and first_child.name == '<specifikator_tipa>':
            if e := first_child.validate_specifikator_tipa(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.add_attr('type', first_child_type)

        elif isinstance(first_child, Token) and first_child.name == 'KR_CONST':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := second_child.validate_specifikator_tipa(): return e
            
            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if second_child_type.name == 'void':
                return self.error_str
            
            self.add_attr('type', Type(second_child_type.name, is_const=True, nested_type=second_child_type.nested_type))

    def validate_specifikator_tipa(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name == 'KR_VOID':
            self.add_attr('type', Type('void'))
        
        elif first_child.name == 'KR_CHAR':
            self.add_attr('type', Type('char'))

        elif first_child.name == 'KR_INT':
            self.add_attr('type', Type('int'))

    def validate_multiplikativni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<cast_izraz>':
            if e := first_child.validate_cast_izraz(): return e
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<multiplikativni_izraz>':
            if e := first_child.validate_multiplikativni_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_cast_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_aditivni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<multiplikativni_izraz>':
            if e := first_child.validate_multiplikativni_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<aditivni_izraz>':
            if e := first_child.validate_aditivni_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_multiplikativni_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_odnosni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<aditivni_izraz>':
            if e := first_child.validate_aditivni_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<odnosni_izraz>':
            if e := first_child.validate_odnosni_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_aditivni_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_jednakosni_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<odnosni_izraz>':
            if e := first_child.validate_odnosni_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<jednakosni_izraz>':
            if e := first_child.validate_jednakosni_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_odnosni_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_bin_i_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<jednakosni_izraz>':
            if e := first_child.validate_jednakosni_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<bin_i_izraz>':
            if e := first_child.validate_bin_i_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_jednakosni_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_bin_xili_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_i_izraz>':
            if e := first_child.validate_bin_i_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<bin_xili_izraz>':
            if e := first_child.validate_bin_xili_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_bin_i_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_bin_ili_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_xili_izraz>':
            if e := first_child.validate_bin_xili_izraz(): return e
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<bin_ili_izraz>':
            if e := first_child.validate_bin_ili_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_bin_xili_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_log_i_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<bin_ili_izraz>':
            if e := first_child.validate_bin_ili_izraz(): return e
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<log_i_izraz>':
            if e := first_child.validate_log_i_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_bin_ili_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_log_ili_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<log_i_izraz>':
            if e := first_child.validate_log_i_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<log_ili_izraz>':
            if e := first_child.validate_log_ili_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)

            if not first_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_log_i_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            self.add_attr('type', Type('int'))
            self.add_attr('is_l_expr', False)

    def validate_izraz_pridruzivanja(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<log_ili_izraz>':
            if e := first_child.validate_log_ili_izraz(): return e            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<postfiks_izraz>':
            if e := first_child.validate_postfiks_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            if not first_child.get_attr('is_l_expr'):
                return self.error_str

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_izraz_pridruzivanja(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(first_child_type):
                return self.error_str
            
            self.add_attr('type', first_child_type)
            self.add_attr('is_l_expr', False)

    def validate_izraz(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            if e := first_child.validate_izraz_pridruzivanja(): return e
            
            self.copy_attr_from(first_child, ['type', 'is_l_expr'])

        elif first_child.name == '<izraz>':
            if e := first_child.validate_izraz(): return e

            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            
            if e := third_child.validate_izraz_pridruzivanja(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)
            
            self.add_attr('type', third_child_type)
            self.add_attr('is_l_expr', False)

    def validate_slozena_naredba(self) -> Optional[str]:
        second_child = self.children[1]
        assert isinstance(second_child, ParseTree)

        if second_child.name == '<lista_naredbi>':
            if e := second_child.validate_lista_naredbi(): return e
            
        elif second_child.name == '<lista_deklaracija>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            if e := (second_child.validate_lista_deklaracija() or third_child.validate_lista_naredbi()): return e

    def validate_lista_naredbi(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<naredba>':
            if e := first_child.validate_naredba(): return e
            
        elif first_child.name == '<lista_naredbi>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := (first_child.validate_lista_naredbi() or second_child.validate_naredba()): return e
            
    def validate_naredba(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        e = None

        if first_child.name == '<slozena_naredba>':
            e = first_child.validate_slozena_naredba()

        elif first_child.name == '<izraz_naredba>':
            e = first_child.validate_izraz_naredba()

        elif first_child.name == '<naredba_grananja>':
            e = first_child.validate_naredba_grananja()
            
        elif first_child.name == '<naredba_petlje>':
            e = first_child.validate_naredba_petlje()
        
        elif first_child.name == '<naredba_skoka>':
            e = first_child.validate_naredba_skoka()

        return e
    
    def validate_izraz_naredba(self) -> Optional[str]:
        first_child = self.children[0]

        if isinstance(first_child, Token) and first_child.name == 'TOCKAZAREZ':
            self.add_attr('type', Type('int'))

        elif isinstance(first_child, ParseTree) and first_child.name == '<izraz>':
            if e := first_child.validate_izraz(): return e
            
            first_child_type = first_child.get_attr('type')
            assert isinstance(first_child_type, Type)
            
            self.add_attr('type', first_child_type)

    def validate_naredba_grananja(self) -> Optional[str]:
        third_child = self.children[2]
        assert isinstance(third_child, ParseTree)

        if e := third_child.validate_izraz(): return e
        
        third_child_type = third_child.get_attr('type')
        assert isinstance(third_child_type, Type)

        if not third_child_type.implicitly_reduces_to(Type('int')):
            return self.error_str
        
        fifth_child = self.children[4]
        assert isinstance(fifth_child, ParseTree)

        if e := fifth_child.validate_naredba(): return e

        if len(self.children) > 5:
            seventh_child = self.children[6]
            assert isinstance(seventh_child, ParseTree)
            if e := seventh_child.validate_naredba(): return e

    def validate_naredba_petlje(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name == 'KR_WHILE':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := third_child.validate_izraz(): return e
            
            third_child_type = third_child.get_attr('type')
            assert isinstance(third_child_type, Type)

            if not third_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str
            
            fifth_child = self.children[4]
            assert isinstance(fifth_child, ParseTree)

            if e := fifth_child.validate_naredba(): return e
            
        elif first_child.name == 'KR_FOR':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)
            fourth_child = self.children[3]
            assert isinstance(fourth_child, ParseTree)

            if e := (third_child.validate_izraz_naredba() or fourth_child.validate_izraz_naredba()): return e
            
            fourth_child_type = fourth_child.get_attr('type')
            assert isinstance(fourth_child_type, Type)

            if not fourth_child_type.implicitly_reduces_to(Type('int')):
                return self.error_str

            if self.children[4].name == 'D_ZAGRADA':
                sixth_child = self.children[5]
                assert isinstance(sixth_child, ParseTree)
                if e := sixth_child.validate_naredba(): return e

            elif self.children[4].name == '<izraz>':
                fifth_child = self.children[4]
                assert isinstance(fifth_child, ParseTree)

                if e := fifth_child.validate_izraz(): return e
                
                seventh_child = self.children[6]
                assert isinstance(seventh_child, ParseTree)

                if e := seventh_child.validate_naredba(): return e

    def validate_naredba_skoka(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        if first_child.name in ('KR_CONTINUE', 'KR_BREAK'):
            loop: Optional[ParseTree] = self
            while loop and loop.name != '<naredba_petlje>':
                loop = loop.parent

            if loop is None:
                return self.error_str

        elif self.children[1].name == 'TOCKAZAREZ':
            definition: Optional[ParseTree] = self
            while definition and definition.name != '<definicija_funkcije>':
                definition = definition.parent

            if definition is None:
                return self.error_str
            
            definition_idn = definition.children[1]
            assert isinstance(definition_idn, Token)

            func = self.scope.get_symbol(definition_idn.source)
            assert func is not None
            assert func.type is not None
            assert isinstance(func.type.nested_type, FuncSignature)
            func_signature = func.type.nested_type

            if func_signature.return_type != Type('void'):
                return self.error_str

        elif self.children[1].name == '<izraz>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := second_child.validate_izraz(): return e

            definition: Optional[ParseTree] = self
            while definition and definition.name != '<definicija_funkcije>':
                definition = definition.parent

            if definition is None:
                return self.error_str
            
            definition_idn = definition.children[1]
            assert isinstance(definition_idn, Token)

            func = self.scope.get_symbol(definition_idn.source)
            assert func is not None
            assert func.type is not None
            assert isinstance(func.type.nested_type, FuncSignature)
            func_signature = func.type.nested_type

            second_child_type = second_child.get_attr('type')
            assert isinstance(second_child_type, Type)

            if not second_child_type.implicitly_reduces_to(func_signature.return_type):
                return self.error_str

    def validate_prijevodna_jedinica(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<vanjska_deklaracija>':
            if e := first_child.validate_vanjska_deklaracija(): return e

        elif first_child.name == '<prijevodna_jedinica>':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            if e := (first_child.validate_prijevodna_jedinica() or second_child.validate_vanjska_deklaracija()): return e

    def validate_vanjska_deklaracija(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        e = None

        if first_child.name == '<definicija_funkcije>':
            e = first_child.validate_definicija_funkcije()

        elif first_child.name == '<deklaracija>':
            e = first_child.validate_deklaracija()

        return e

    def validate_definicija_funkcije(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if e := first_child.validate_ime_tipa(): return e
        
        first_child_type = first_child.get_attr('type')
        assert isinstance(first_child_type, Type)

        if first_child_type.is_const:
            return self.error_str
        
        fourth_child = self.children[3]

        second_child = self.children[1]
        assert isinstance(second_child, Token)

        root_func = Scope.root_scope.get_symbol(second_child.source)

        sixth_child = self.children[5]
        assert isinstance(sixth_child, ParseTree)
        
        if isinstance(fourth_child, Token) and fourth_child.name == 'KR_VOID':
            if root_func:
                assert root_func.type is not None
                func = root_func.type.nested_type
                assert isinstance(func, FuncSignature)

                if root_func.type != first_child_type or func.arg_types != []:
                    return self.error_str

            else:
                root_func = Symbol(
                    name=second_child.source,
                    type=Type(
                        'function',
                        nested_type=FuncSignature(
                            return_type=first_child_type,
                            arg_types=[]
                        )
                    ),
                    is_l_expr=False
                )

                Scope.root_scope.add_child(root_func)
            
        elif isinstance(fourth_child, ParseTree) and fourth_child.name == '<lista_parametara>':
            if e := fourth_child.validate_lista_parametara(): return e
                        
            decl_types = fourth_child.get_attr('types')
            assert isinstance(decl_types, list)

            if root_func:
                assert root_func.type is not None
                func = root_func.type.nested_type
                assert isinstance(func, FuncSignature)

                if decl_types != func.arg_types:
                    return self.error_str
                
            else:
                root_func = Symbol(
                    name=second_child.source,
                    type=Type(
                        'function',
                        nested_type=FuncSignature(
                            return_type=first_child_type,
                            arg_types=decl_types
                        )
                    ),
                    is_l_expr=False
                )

            Scope.root_scope.add_child(root_func)

            names = fourth_child.get_attr('names')
            assert isinstance(names, list)
            for type, name in zip(decl_types, names):
                self.scope.add_child(Symbol(name, type, is_l_expr=not type.is_const))

        if e := sixth_child.validate_slozena_naredba(): return e

    def validate_lista_parametara(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<deklaracija_parametra>':
            if e := first_child.validate_deklaracija_parametra(): return e            
            self.add_attr('types', [first_child.get_attr('type')])
            self.add_attr('names', [first_child.get_attr('name')])

        elif first_child.name == '<lista_parametara>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := (first_child.validate_lista_parametara() or third_child.validate_deklaracija_parametra()): return e
            
            names = first_child.get_attr('names')
            assert isinstance(names, list)
            if third_child.get_attr('name') in names:
                return self.error_str
            
            types = first_child.get_attr('types')
            assert isinstance(types, list)

            self.add_attr('names', names + [third_child.get_attr('name')])
            self.add_attr('types', types + [third_child.get_attr('type')])

    def validate_deklaracija_parametra(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if e := first_child.validate_ime_tipa(): return e

        type = first_child.get_attr('type')
        assert isinstance(type, Type)

        if type.name == 'void':
            return self.error_str
        
        second_child = self.children[1]
        assert isinstance(second_child, Token)

        self.add_attr('name', second_child.source)

        if len(self.children) == 2:
            self.add_attr('type', type)

        else:
            self.add_attr('type', Type('arr', nested_type=type))

    def validate_lista_deklaracija(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if len(self.children) == 1:
            if e := first_child.validate_deklaracija(): return e
            
        else:
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)
            if e := (first_child.validate_lista_deklaracija() or second_child.validate_deklaracija()): return e

    def validate_deklaracija(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)
        if e := first_child.validate_ime_tipa(): return e

        second_child = self.children[1]
        assert isinstance(second_child, ParseTree)

        second_child.add_attr('ntype', first_child.get_attr('type'))

        if e := second_child.validate_lista_init_deklaratora(): return e

    def validate_lista_init_deklaratora(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        first_child.add_attr('ntype', self.get_attr('ntype'))

        if first_child.name == '<init_deklarator>':
            if e := first_child.validate_init_deklarator(): return e

        elif first_child.name == '<lista_init_deklaratora>':
            if e := first_child.validate_lista_init_deklaratora(): return e
            
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            third_child.add_attr('ntype', self.get_attr('ntype'))

            if e := third_child.validate_init_deklarator(): return e

    def validate_init_deklarator(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        first_child.add_attr('ntype', self.get_attr('ntype'))
        if e := first_child.validate_izravni_deklarator(): return e
        
        first_child_type = first_child.get_attr('type')
        assert isinstance(first_child_type, Type)

        if len(self.children) == 1:
            if first_child_type.is_const or (
                    first_child_type.name == 'arr'
                    and isinstance(first_child_type.nested_type, Type)
                    and first_child_type.nested_type.is_const
            ):
                return self.error_str

        else:
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := third_child.validate_inicijalizator(): return e
            
            if first_child_type.name == 'arr':
                first_child_elem_count = first_child.get_attr('elem_count')
                assert isinstance(first_child_elem_count, int)
                third_child_elem_count = third_child.get_attr('elem_count')
                assert isinstance(third_child_elem_count, int)

                if third_child_elem_count > first_child_elem_count:
                    return self.error_str
                
                third_child_types = third_child.get_attr('types')
                assert isinstance(third_child_types, list)
                assert isinstance(first_child_type.nested_type, Type)

                for t in third_child_types:
                    assert isinstance(t, Type)
                    if not t.implicitly_reduces_to(first_child_type.nested_type):
                        return self.error_str
            
            else:
                third_child_type = third_child.get_attr('type')
                assert isinstance(third_child_type, Type)

                if not third_child_type.implicitly_reduces_to(first_child_type):
                    return self.error_str

    def validate_izravni_deklarator(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, Token)

        root_ntype = self.get_attr('ntype')
        assert isinstance(root_ntype, Type)

        if len(self.children) == 1:
            if root_ntype.name == 'void':
                return self.error_str
            
            declared = first_child.source in [c.name for c in self.scope.children if isinstance(c, Symbol)]
            if declared:
                return self.error_str
            
            self.scope.add_child(
                Symbol(
                    name=first_child.source,
                    type=root_ntype,
                    is_l_expr=not root_ntype.is_const
                )
            )

            self.add_attr('type', root_ntype)

        elif self.children[2].name == 'BROJ':
            if root_ntype.name == 'void':
                return self.error_str
            
            declared = first_child.source in [c.name for c in self.scope.children if isinstance(c, Symbol)]
            if declared:
                return self.error_str
            
            third_child = self.children[2]
            assert isinstance(third_child, Token)
            third_child_int = int(third_child.source)

            if not (0 < third_child_int <= 1024):
                return self.error_str
            
            self.scope.add_child(
                Symbol(
                    name=first_child.source,
                    type=Type('arr', nested_type=root_ntype),
                    is_l_expr=not root_ntype.is_const
                )
            )

            self.add_attr('type', Type('arr', nested_type=root_ntype))
            self.add_attr('elem_count', third_child_int)

        elif self.children[2].name == 'KR_VOID':
            declared = [c for c in self.scope.children if isinstance(c, Symbol) and c.name == first_child.source]
            
            new_signature = FuncSignature(
                return_type=root_ntype,
                arg_types=[]
            )

            self.add_attr('type', Type('function', nested_type=new_signature))

            if declared:
                declared = declared[0]
                assert isinstance(declared.type, Type)                

                if declared.type.name != 'function':
                    return self.error_str
                
                declared_signature = declared.type.nested_type
                assert isinstance(declared_signature, FuncSignature)

                if declared_signature != new_signature:
                    return self.error_str
                
            else:
                self.scope.add_child(
                    Symbol(
                        name=first_child.source,
                        type=Type('function', nested_type=new_signature),
                        is_l_expr=False
                    )
                )

        elif self.children[2].name == '<lista_parametara>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := third_child.validate_lista_parametara(): return e
            
            declared = [c for c in self.scope.children if isinstance(c, Symbol) and c.name == first_child.source]

            third_child_types = third_child.get_attr('types')
            assert isinstance(third_child_types, list)
            
            new_signature = FuncSignature(
                return_type=root_ntype,
                arg_types=third_child_types
            )

            self.add_attr('type', Type('function', nested_type=new_signature))

            if declared:
                declared = declared[0]
                assert isinstance(declared.type, Type)                

                if declared.type.name != 'function':
                    return self.error_str
                
                declared_signature = declared.type.nested_type
                assert isinstance(declared_signature, FuncSignature)

                if declared_signature != new_signature:
                    return self.error_str

            else:
                self.scope.add_child(
                    Symbol(
                        name=first_child.source,
                        type=Type('function', nested_type=new_signature),
                        is_l_expr=False
                    )
                )

    def validate_inicijalizator(self) -> Optional[str]:
        first_child = self.children[0]
    
        if isinstance(first_child, ParseTree) and first_child.name == '<izraz_pridruzivanja>':
            nested_child = first_child
            while isinstance(nested_child, ParseTree):
                nested_child = nested_child.children[0]

            if e := first_child.validate_izraz_pridruzivanja(): return e

            if nested_child.name == 'NIZ_ZNAKOVA':
                escape_map = {
                    r'\t': '\t',
                    r'\n': '\n',
                    r'\0': '\0',
                    r"\'": "'",
                    r'\"': '"',
                    r'\\': '\\',
                }

                escaped_str = nested_child.source
                for esc, real in escape_map.items():
                    escaped_str = escaped_str.replace(esc, real)

                elem_count = len(escaped_str) - 1

                self.add_attr('elem_count', elem_count)
                self.add_attr('types', [Type('char')] * elem_count)
            else:
                self.add_attr('type', first_child.get_attr('type'))

        elif isinstance(first_child, Token) and first_child.name == 'L_VIT_ZAGRADA':
            second_child = self.children[1]
            assert isinstance(second_child, ParseTree)

            if e := second_child.validate_lista_izraza_pridruzivanja(): return e
            
            self.copy_attr_from(second_child, ['elem_count', 'types'])

    def validate_lista_izraza_pridruzivanja(self) -> Optional[str]:
        first_child = self.children[0]
        assert isinstance(first_child, ParseTree)

        if first_child.name == '<izraz_pridruzivanja>':
            if e := first_child.validate_izraz_pridruzivanja(): return e            
            self.add_attr('types', [first_child.get_attr('type')])
            self.add_attr('elem_count', 1)

        elif first_child.name == '<lista_izraza_pridruzivanja>':
            third_child = self.children[2]
            assert isinstance(third_child, ParseTree)

            if e := (first_child.validate_lista_izraza_pridruzivanja() or third_child.validate_izraz_pridruzivanja()): return e
            
            first_child_types = first_child.get_attr('types')
            assert isinstance(first_child_types, list)
            first_child_elem_count = first_child.get_attr('elem_count')
            assert isinstance(first_child_elem_count, int)
            
            self.add_attr('types', first_child_types + [third_child.get_attr('type')])
            self.add_attr('elem_count', first_child_elem_count + 1)

    @property
    def error_str(self) -> str:
        res = f'{self.name} ::='
        for child in self.children:
            res += f' {child.name}' if isinstance(child, ParseTree) else f' {child}'
        return res
    
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
            
class TreeFactory:
    @staticmethod
    def from_stdin() -> Tuple['ParseTree', 'Scope']:
        return TreeFactory.from_iter(iter(sys.stdin))

    @staticmethod
    def from_iter(lines: Iterator[str]) -> Tuple['ParseTree', 'Scope']:
        starting_nt, _ = get_line(lines)
        if starting_nt is None:
            raise ValueError('[FATAL] Empty file')
        
        return TreeFactory.__from_str_inner(
            curr_root=starting_nt,
            parent=None,
            scope=Scope.root_scope, 
            lines=lines,
            depth=0
        )[0], Scope.root_scope

    @staticmethod
    def __from_str_inner(curr_root: str, parent: Optional['ParseTree'], scope: Scope, lines: Iterator[str], depth: int) -> Tuple['ParseTree', Optional[str], int]:
        tree = ParseTree(Nonterminal(curr_root, scope), parent)
        do_next = True
        line = curr_root
        inner_depth = depth

        while True:
            if do_next:
                line, inner_depth = get_line(lines)
            do_next = True

            if inner_depth <= depth or line is None:
                return tree, line, inner_depth

            if line.startswith('<'):
                if line in (
                    '<slozena_naredba>',
                    '<definicija_funkcije>',
                    '<naredba_petlje>',
                    '<naredba_grananja>',
                ) and tree.root.name != '<definicija_funkcije>':
                    new_scope = Scope(scope, line)
                    scope.add_child(new_scope)
                else:
                    new_scope = scope

                subtree, line, inner_depth = TreeFactory.__from_str_inner(
                    curr_root=line,
                    parent=tree,
                    scope=new_scope,
                    lines=lines,
                    depth=depth+1
                )

                tree.add_child(subtree)
                do_next = False

            else:
                tree.add_child(Token.from_str(line))

class CodeGenerator:
    @staticmethod
    def to_file(filepath: str) -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(ASM_PREAMBLE)

def main() -> None:
    log(f'[Info]   Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')
    log(f'[Info]   Starting semantic analysis...')
    
    start_parse_input = time.time()
    parse_tree, _ = TreeFactory.from_stdin()
    end_parse_input = time.time()
    log(f'[Timing] Parse input: {(end_parse_input - start_parse_input) * 1000:.2f} ms')

    start_validation = time.time()
    error = parse_tree.validate()
    end_validation = time.time()
    log(f'[Timing] Validate semantic rules: {(end_validation - start_validation) * 1000:.2f} ms')

    if error:
        log(f'[Error]  Finished with error: {error}')
    else:
        log(f'[Info]   Finished without errors')
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, OUTPUT_FILENAME)

        CodeGenerator.to_file(output_path)

if __name__ == '__main__':
    main()
