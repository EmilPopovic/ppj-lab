import os
import time
import sys

from util import log, out
from instructions import *
from opcodes import *
from size import WordOrByte, HalfOrByte
from semantic_analyzer import TreeFactory

OUTPUT_FILENAME = 'a.s'

class CodeGenerator:
    @staticmethod
    def to_file(filepath: str) -> None:

        start = [
            LoadStoreSingleMode2Op(LoadSingleOpcode.LDR, WordOrByte.WORD, 7, Mode2Immediate(0x20000)),
            BranchOp(BranchOpcode.BL, 'f_main', Cond.ALWAYS),
            SoftwareInterruptOp(0),
        ]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('    .text\n')
            f.write('    .global _start\n')
            f.write('_start:\n')

            for inst in start:
                f.write(f'{inst}\n')

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
        return

    log(f'[Info]   Found no semantic errors')
    log(f'[Info]   Starting code generation...')

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, OUTPUT_FILENAME)

    CodeGenerator.to_file(output_path)

if __name__ == '__main__':
    main()
