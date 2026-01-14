from abc import ABC

from shift import ShiftType

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
