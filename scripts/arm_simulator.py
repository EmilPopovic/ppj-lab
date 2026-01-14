#!/usr/bin/env python3.8

import os
import subprocess
import tempfile
import sys

try:
    import unicorn.arm_const as arm
    from unicorn import UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_INTR
    from unicorn.unicorn import Uc
except ImportError:
    print("ERROR: unicorn package not installed", file=sys.stderr)
    sys.exit(1)

ARM_CODE_ADDRESS = 0x10000


def hook_intr(mu, intno, user_data):
    if intno == 0:
        mu.emu_stop()


def evaluate_r6(arm_code_path, expected_r6_value):
    """Compile ARM assembly, link it, and run in unicorn emulator.
    
    Returns True if R6 register value matches expected value, False otherwise.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        asm_file = os.path.join(tmpdir, "code.s")
        obj_file = os.path.join(tmpdir, "code.o")
        elf_file = os.path.join(tmpdir, "code.elf")
        bin_file = os.path.join(tmpdir, "code.bin")

        # Copy assembly file to temp directory
        with open(arm_code_path, "r") as src, open(asm_file, "w") as dst:
            dst.write(src.read())

        # Compile, link, and convert to binary
        try:
            subprocess.run(
                ["arm-none-eabi-as", asm_file, "-o", obj_file],
                capture_output=True, check=True, text=True
            )

            subprocess.run([
                "arm-none-eabi-ld",
                "-Ttext", hex(ARM_CODE_ADDRESS),
                obj_file, "-o", elf_file
            ], capture_output=True, check=True, text=True)

            subprocess.run(
                ["arm-none-eabi-objcopy", "-O", "binary", elf_file, bin_file],
                capture_output=True, check=True, text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"COMPILE_ERROR: {e.stderr}", file=sys.stderr)
            return False

        with open(bin_file, "rb") as f:
            code = f.read()

    # Initialize unicorn emulator
    mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    mu.hook_add(UC_HOOK_INTR, hook_intr)
    mu.mem_map(0x0000, 0x30000)
    mu.mem_write(ARM_CODE_ADDRESS, code)
    mu.reg_write(arm.UC_ARM_REG_SP, 0x20000)

    # Run emulation
    try:
        mu.emu_start(ARM_CODE_ADDRESS, 0)
    except Exception as e:
        pass

    # Read R6 register value
    r6_value = mu.reg_read(arm.UC_ARM_REG_R6)

    # Convert to signed 32-bit integer
    if r6_value & 0x80000000:
        r6_signed = r6_value - 0x100000000
    else:
        r6_signed = r6_value

    return r6_signed == expected_r6_value


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: arm_simulator.py <asm_file> <expected_value>", file=sys.stderr)
        sys.exit(1)

    asm_file = sys.argv[1]
    expected_value = int(sys.argv[2])

    if evaluate_r6(asm_file, expected_value):
        print("PASS")
        sys.exit(0)
    else:
        print("FAIL")
        sys.exit(1)
