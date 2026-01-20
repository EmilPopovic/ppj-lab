from abc import ABC

from shift import ShiftType
from addressing.util import reg_to_str

def is_valid_arm_immediate(val: int) -> bool:
    if val < 0 or val > 0xFFFFFFFF:
        return False

    for k in range(0, 32, 2):
        rotated_val = ((val << k) | (val >> (32 - k))) & 0xFFFFFFFF

        if rotated_val <= 0xFF:
            return True

    return False

class Oprnd2(ABC):
    pass

class Oprnd2Rm(Oprnd2):
    def __init__(self, rm: int) -> None:
        self.rm: int = rm

    def __repr__(self) -> str:
        return f'{reg_to_str(self.rm)}'

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
        return f'{reg_to_str(self.rm)}, {self.shift.value} #{self.imm_5}'

class Oprnd2ShiftRs(Oprnd2):
    def __init__(self, rm: int, shift: ShiftType, rs: int) -> None:
        self.rm: int = rm
        self.shift: ShiftType = shift
        self.rs: int = rs

    def __repr__(self) -> str:
        return f'{reg_to_str(self.rm)}, {self.shift.value} {reg_to_str(self.rs)}'

class Oprnd2ShiftRRX(Oprnd2):
    def __init__(self, rm: int) -> None:
        self.rm = rm
    
    def __repr__(self) -> str:
        return f'{reg_to_str(self.rm)}, rrx'
