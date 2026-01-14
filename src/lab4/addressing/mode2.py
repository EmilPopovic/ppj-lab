from abc import ABC
from typing import Optional

from indexing import IndexingType
from shift import ShiftType

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

class Mode2RegiserOffset(Mode2):
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
            return f'[r{self.rn}]'
        
        rm_sign_str = "-" if self.negate_rm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[r{self.rn}, {rm_sign_str}r{self.rm}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[r{self.rn}], {rm_sign_str}r{self.rm}'

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
            return f'[r{self.rn}]'
        
        imm_sign_str = "-" if self.negate_imm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[r{self.rn}, #{imm_sign_str}{self.imm_12}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[r{self.rn}], #{imm_sign_str}{self.imm_12}'

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
            return f'[r{self.rn}]'
        
        rm_sign_str = "-" if self.negate_rm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[r{self.rn}, {rm_sign_str}r{self.rm}, {self.shift} #{self.imm_5}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[r{self.rn}], {rm_sign_str}r{self.rm}, {self.shift} #{self.imm_5}'
    
class Mode2Label(Mode2):
    def __init__(self, label: str) -> None:
        self.label: str = label

    def __repr__(self) -> str:
        return self.label
