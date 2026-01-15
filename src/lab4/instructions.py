from typing import List

from opcodes import *
from cond import Cond
from size import WordOrByte, HalfOrByte
from addressing.oprnd2 import *
from addressing.mode2 import *
from addressing.mode3 import *
from addressing.mode4 import *

def reg_to_str(reg: int) -> str:
    if reg == 11:
        return 'fp'
    elif reg == 13:
        return 'sp'
    elif reg == 14:
        return 'lr'
    elif reg == 15:
        return 'pc'
    else:
        return f'r{reg}'

class AssemblyLine:
    pass

class Comment(AssemblyLine):
    def __init__(self, s: str) -> None:
        self.s = s
    
    def __repr__(self) -> str:
        return f'    // {self.s}'

class AssemblerDirective(AssemblyLine):
    def __init__(self, name: str) -> None:
        if not name.startswith('.'):
            self.name = f'.{name}'
        else:
            self.name = name

    def __repr__(self) -> str:
        return f'    {self.name}'

class Label(AssemblyLine):
    __last = -1

    def __init__(self, name: Optional[str] = None) -> None:
        if name is None:
            name = self.__new_name()
        self.name = name

    @staticmethod
    def __new_name() -> str:
        Label.__last += 1
        return f'l{Label.__last}'

    def __repr__(self) -> str:
        return f'{self.name}:'

class Instruction(AssemblyLine):
    pass

class ArithmeticLogicOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}{"s" if self.save_flags else ""}'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}, {reg_to_str(self.rn)}, {self.oprnd2}'
    
class TestOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}'
        return f'    {opcode_str:<8} {reg_to_str(self.rn)}, {self.oprnd2}'
    
class MoveOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}, {self.oprnd2}'
    
class NopOp(Instruction):
    def __init__(self) -> None:
        self.opcode: NopOpcode = NopOpcode.NOP
    
    def __repr__(self) -> str:
        opcode_str = f'{self.opcode.value}'
        return f'    {opcode_str:<8}'
    
class MultiplyOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}{"s" if self.save_flags else ""}'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}, {reg_to_str(self.rm)}, {reg_to_str(self.rs)}'

class MultiplyAccumulateOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}{"s" if self.save_flags else ""}'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}, {reg_to_str(self.rm)}, {reg_to_str(self.rs)}, {reg_to_str(self.rn)}'

class BranchOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}'
        return f'    {opcode_str:<8} {self.label}'
    
class SoftwareInterruptOp(Instruction):
    def __init__(self, irq_num: int) -> None:
        self.opcode: ControlOpcode = ControlOpcode.SWI
        self.irq_num: int = irq_num

    def __repr__(self) -> str:
        return f'    {self.opcode.value:<8} {self.irq_num}'

class LoadStoreSingleMode2Op(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}{self.size.value}'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}, {self.mode2}'

class LoadStoreHalfMode3UnsignedOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}h'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}, {self.mode3}'

class LoadSingleMode3SignedOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}s{self.size.value}'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}, {self.mode3}'

class LoadStoreMultipleOp(Instruction):
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
        opcode_str = f'{self.opcode.value}{self.cond.value}{self.mode4.value}'
        reglist_str = f'{{ {", ".join(reg_to_str(reg) for reg in self.reglist)} }}'
        return f'    {opcode_str:<8} {reg_to_str(self.rd)}{"!" if self.save_rd else ""}, {reglist_str}'
