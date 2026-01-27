from abc import ABC
from enum import Enum
from typing import Optional

from indexing import IndexingType
from shift import ShiftType

def reg_to_str(reg: int) -> str:
    if reg == 11:
        return 'fp'
    elif reg == 13:
        return 'sp'
    elif reg == 14:
        return 'lr'
    elif reg == 15:
        return 'pc'
    elif reg > 15:
        return f'v{reg}'
    else:
        return f'r{reg}'

# Mode2 classes

class Mode2(ABC):
    pass

class Mode2Immediate(Mode2):
    def __init__(
            self,
            imm: int
    ) -> None:
        self.imm: int = imm

    def __repr__(self) -> str:
        return f'={hex(self.imm)}'

class Mode2RegisterOffset(Mode2):
    def __init__(
            self,
            rn: int,
            indexing: IndexingType,
            rm: Optional[int] = None,
            negate_rm: bool = False
    ) -> None:
        self.rn: int = rn
        self.rm: Optional[int] = rm
        self.indexing: IndexingType = indexing
        self.negate_rm: bool = negate_rm

    def __repr__(self) -> str:
        if self.rm is None:
            return f'[{reg_to_str(self.rn)}]'

        rm_sign_str = "-" if self.negate_rm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[{reg_to_str(self.rn)}, {rm_sign_str}{reg_to_str(self.rm)}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[{reg_to_str(self.rn)}], {rm_sign_str}{reg_to_str(self.rm)}'

class Mode2ImmediateOffset(Mode2):
    def __init__(
            self,
            rn: int,
            indexing: IndexingType,
            imm_12: Optional[int],
            negate_imm: bool = False
    ) -> None:
        self.rn: int = rn
        self.imm_12: Optional[int] = imm_12
        self.indexing: IndexingType = indexing
        self.negate_imm: bool = negate_imm

    def __repr__(self) -> str:
        if self.imm_12 is None:
            return f'[{reg_to_str(self.rn)}]'

        imm_sign_str = "-" if self.negate_imm and self.imm_12 != 0 else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[{reg_to_str(self.rn)}, #{imm_sign_str}{self.imm_12}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[{reg_to_str(self.rn)}], #{imm_sign_str}{self.imm_12}'

class Mode2ScaledOffset(Mode2):
    def __init__(
            self,
            rn: int,
            rm: int,
            indexing: IndexingType,
            shift: ShiftType,
            imm_5: Optional[int],
            negate_rm: bool = False
    ) -> None:
        self.rn: int = rn
        self.rm: int = rm
        self.indexing: IndexingType = indexing
        self.shift: ShiftType = shift
        self.imm_5: Optional[int] = imm_5
        self.negate_rm: bool = negate_rm

    def __repr__(self) -> str:
        if self.imm_5 is None:
            return f'[{reg_to_str(self.rn)}]'

        rm_sign_str = "-" if self.negate_rm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[{reg_to_str(self.rn)}, {rm_sign_str}{reg_to_str(self.rm)}, {self.shift.value} #{self.imm_5}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[{reg_to_str(self.rn)}], {rm_sign_str}{reg_to_str(self.rm)}, {self.shift.value} #{self.imm_5}'

class Mode2Label(Mode2):
    def __init__(self, label: str) -> None:
        self.label: str = label

    def __repr__(self) -> str:
        return self.label

class Mode2LabelAddr(Mode2):
    def __init__(self, label: str) -> None:
        self.label: str = label

    def __repr__(self) -> str:
        return f'={self.label}'

# Mode3 classes

class Mode3(ABC):
    pass

class Mode3Immediate(Mode3):
    def __init__(
            self,
            imm: int
    ) -> None:
        self.imm: int = imm

    def __repr__(self) -> str:
        return f'={hex(self.imm)}'

class Mode3RegiserOffset(Mode3):
    def __init__(
            self,
            rn: int,
            indexing: IndexingType,
            rm: Optional[int] = None,
            negate_rm: bool = False
    ) -> None:
        self.rn: int = rn
        self.rm: Optional[int] = rm
        self.indexing: IndexingType = indexing
        self.negate_rm: bool = negate_rm

    def __repr__(self) -> str:
        if self.rm is None:
            return f'[{reg_to_str(self.rn)}]'

        rm_sign_str = "-" if self.negate_rm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[{reg_to_str(self.rn)}, {rm_sign_str}{reg_to_str(self.rm)}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[{reg_to_str(self.rn)}], {rm_sign_str}{reg_to_str(self.rm)}'

class Mode3ImmediateOffset(Mode3):
    def __init__(
            self,
            rn: int,
            indexing: IndexingType,
            imm_8: Optional[int],
            negate_imm: bool = False
    ) -> None:
        self.rn: int = rn
        self.imm_8: Optional[int] = imm_8
        self.indexing: IndexingType = indexing
        self.negate_imm: bool = negate_imm

    def __repr__(self) -> str:
        if self.imm_8 is None:
            return f'[{reg_to_str(self.rn)}]'

        imm_sign_str = "-" if self.negate_imm and self.imm_12 != 0 else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[{reg_to_str(self.rn)}, #{imm_sign_str}{self.imm_8}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[{reg_to_str(self.rn)}], #{imm_sign_str}{self.imm_8}'

class Mode3Label(Mode3):
    def __init__(self, label: str) -> None:
        self.label: str = label

    def __repr__(self) -> str:
        return self.label

# Mode4 enum

class Mode4(Enum):
    INCREMENT_AFTER = 'ia'
    INCREMENT_BEFORE = 'ib'
    DECREMENT_AFTER = 'da'
    DECREMENT_BEFORE = 'db'

# Oprnd2 classes

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
