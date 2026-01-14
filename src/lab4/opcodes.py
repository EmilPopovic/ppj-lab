from enum import Enum

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
