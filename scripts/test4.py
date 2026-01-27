#!/usr/bin/env python3
"""
Cross-platform test runner for Lab 4
Usage: python scripts/test4.py [test_pattern]
"""

import sys
import subprocess
from pathlib import Path
import time
import os
import tempfile

# ANSI color codes
GREEN = "\033[1;32m"
RED = "\033[1;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[1;34m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ARM simulator constants
ARM_CODE_ADDRESS = 0x10000

def get_time_ms():
    """Get current time in milliseconds"""
    return int(time.time() * 1000)

def run_command(cmd, stdin_data=None, capture_output=True):
    """Run a command with optional stdin data"""
    try:
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=capture_output,
            text=True,
            check=False
        )
        return result
    except Exception as e:
        return None

def hook_intr(mu, intno, user_data):
    """Hook for handling interrupts in ARM emulator"""
    if intno == 2:
        mu.emu_stop()

def evaluate_r6(arm_code_path, expected_r6_value):
    """Compile ARM assembly, link it, and run in unicorn emulator.
    
    Returns True if R6 register value matches expected value, False otherwise.
    """
    try:
        import unicorn.arm_const as arm
        from unicorn import UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_INTR
        from unicorn import Uc, UcError
    except ImportError:
        print(f"{RED}ERROR: unicorn package not installed{RESET}", file=sys.stderr)
        return False
    
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
            print(f"{RED}COMPILE_ERROR: {e.stderr}{RESET}", file=sys.stderr)
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
    except UcError as e:
        print(f"{RED}UNICORN_ERROR: {e}{RESET}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"{RED}RUNTIME_ERROR: {e}{RESET}", file=sys.stderr)
        return False

    # Read R6 register value
    r6_value = mu.reg_read(arm.UC_ARM_REG_R6)

    # Convert to signed 32-bit integer
    if r6_value & 0x80000000:
        r6_signed = r6_value - 0x100000000
    else:
        r6_signed = r6_value

    return r6_signed == expected_r6_value, r6_signed

def main():
    print(f"{BOLD}{BLUE}==============================")
    print(f"     Running Lab 4 tests")
    print(f"=============================={RESET}\n")
    
    # Show Python version
    print("Running with:")
    result = run_command(["python3.8", "--version"])
    if result and result.returncode == 0:
        print(result.stdout.strip())
    print()
    
    # Parse command line argument for test pattern
    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Find test directories
    tests_dir = Path("tests/lab4_teza")
    if pattern:
        test_dirs = sorted(tests_dir.glob(f"{pattern}*"))
    else:
        test_dirs = sorted(tests_dir.glob("*"))
    
    test_dirs = [d for d in test_dirs if d.is_dir()]
    
    pass_count = 0
    fail_count = 0
    found_any = False
    
    # Start total timer
    total_start = get_time_ms()
    
    for test_dir in test_dirs:
        found_any = True
        test_name = test_dir.name
        
        print(f"{BOLD}{YELLOW}→ Testing:{RESET} {test_name}")
        
        # Check required files
        test_in = test_dir / "test.in"
        test_out = test_dir / "test.out"
        
        if not test_in.exists() or not test_out.exists():
            print(f"{RED}  ⚠ Missing one or more required files in {test_dir}{RESET}\n")
            continue
        
        # Step 1: Run GeneratorKoda.py with .in file on stdin to generate ARM assembly
        # Note: GeneratorKoda.py writes output to src/lab4/a.s directly
        with open(test_in, 'r') as f:
            in_content = f.read()
        
        # Start generation timer
        gen_start = get_time_ms()
        
        # GeneratorKoda.py writes to src/lab4/a.s automatically
        asm_path = Path("src/lab4/a.s")
        if asm_path.exists():
            asm_path.unlink()
        
        result = run_command(["python3.8", "src/lab4/GeneratorKoda.py"], stdin_data=in_content)
        
        gen_end = get_time_ms()
        gen_time_ms = gen_end - gen_start
        
        if result is None or result.returncode != 0:
            print(f"{RED}  ⚠ Generator failed with return code {result.returncode if result else 'unknown'}{RESET}")
            if result and result.stderr:
                print(f"    Error: {result.stderr.splitlines()[-1]}")
            fail_count += 1
            continue
        
        if not asm_path.exists():
            print(f"{RED}  ⚠ Failed to generate ARM assembly{RESET}\n")
            fail_count += 1
            continue
        
        # Step 2: Run the simulator to check R6 register value
        with open(test_out, 'r') as f:
            expected_val_str = f.read().strip()
        
        try:
            expected_val = int(expected_val_str)
        except ValueError:
            print(f"{RED}  ⚠ Invalid expected value: {expected_val_str}{RESET}\n")
            fail_count += 1
            continue
        
        # Start simulation timer
        sim_start = get_time_ms()
        
        # Evaluate using integrated ARM simulator
        sim_res = evaluate_r6(str(asm_path), expected_val)
        
        sim_end = get_time_ms()
        sim_time_ms = sim_end - sim_start

        if not sim_res:
            print(f"{RED}  ✘ FAIL{RESET} Could not run test")
            print(f"    Expected: {expected_val}")
            print()
            continue
        passed, actual_val = sim_res
        
        # Step 3: Check result
        if passed:
            print(f"{GREEN}  ✔ PASS{RESET} (gen: {gen_time_ms}ms, sim: {sim_time_ms}ms)\n")
            pass_count += 1
        else:
            print(f"{RED}  ✘ FAIL{RESET} (gen: {gen_time_ms}ms, sim: {sim_time_ms}ms)")
            print(f"    Expected: {expected_val}, Got: {actual_val}")
            print()
            fail_count += 1
    
    # End total timer
    total_end = get_time_ms()
    total_time_ms = total_end - total_start
    total_time = total_time_ms / 1000.0
    
    if not found_any:
        print(f"{RED}No matching tests found for pattern: {pattern or 'tests/lab4_teza/*'}{RESET}")
    
    # Clean up files
    if Path("a.s").exists():
        Path("a.s").unlink()
    if Path("output.txt").exists():
        Path("output.txt").unlink()
    
    # Print summary
    total = pass_count + fail_count
    print(f"{BOLD}{BLUE}=============================={RESET}")
    print(f" {BOLD}Test Summary:{RESET}")
    print(f"   {GREEN}✔ Passed:{RESET} {pass_count}")
    print(f"   {RED}✘ Failed:{RESET} {fail_count}")
    print(f"   {BOLD}Total:{RESET} {total}")
    print(f"   {BOLD}Total Time:{RESET} {total_time:.3f}s")
    print(f"{BOLD}{BLUE}=============================={RESET}")
    
    # Exit with appropriate code
    sys.exit(0 if fail_count == 0 else 1)

if __name__ == "__main__":
    main()
