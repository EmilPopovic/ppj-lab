from abc import ABC
from typing import Optional

from indexing import IndexingType
from addressing.util import reg_to_str

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
        
        imm_sign_str = "-" if self.negate_imm else ""
        if self.indexing in [IndexingType.NO_INDEX, IndexingType.PREINDEX]:
            return f'[{reg_to_str(self.rn)}, #{imm_sign_str}{self.imm_8}]{"!" if self.indexing == IndexingType.PREINDEX else ""}'
        else:
            return f'[{reg_to_str(self.rn)}], #{imm_sign_str}{self.imm_8}'
    
class Mode3Label(Mode3):
    def __init__(self, label: str) -> None:
        self.label: str = label

    def __repr__(self) -> str:
        return self.label