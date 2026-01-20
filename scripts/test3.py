#!/usr/bin/env python3
"""
Cross-platform test runner for Lab 3
Usage: python scripts/test3.py [test_pattern]
"""

import sys
import subprocess
from pathlib import Path
import time
import difflib

# ANSI color codes
GREEN = "\033[1;32m"
RED = "\033[1;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[1;34m"
BOLD = "\033[1m"
RESET = "\033[0m"

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

def compare_files(file1, file2):
    """Compare two files, return True if identical"""
    try:
        with open(file1, 'r', encoding='utf-8', errors='replace') as f1:
            content1 = f1.read()
        with open(file2, 'r', encoding='utf-8', errors='replace') as f2:
            content2 = f2.read()
        return content1 == content2
    except Exception:
        return False

def show_diff(actual_file, expected_file):
    """Show colorized diff between two files"""
    try:
        with open(actual_file, 'r', encoding='utf-8', errors='replace') as f:
            actual_lines = f.readlines()
        with open(expected_file, 'r', encoding='utf-8', errors='replace') as f:
            expected_lines = f.readlines()
        
        diff = difflib.unified_diff(expected_lines, actual_lines, 
                                    fromfile='expected', tofile='actual', lineterm='')
        
        for line in diff:
            if line.startswith('+'):
                print(f"    {GREEN}{line}{RESET}")
            elif line.startswith('-'):
                print(f"    {RED}{line}{RESET}")
            elif line.startswith('@'):
                print(f"    {BLUE}{line}{RESET}")
            else:
                print(f"    {line}")
    except Exception as e:
        print(f"    Could not show diff: {e}")

def main():
    print(f"{BOLD}{BLUE}==============================")
    print(f"     Running Lab 3 tests")
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
    tests_dir = Path("tests/lab3_teza")
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
        
        # Run SemantickiAnalizator.py with .in file on stdin
        with open(test_in, 'r') as f:
            in_content = f.read()
        
        # Start analysis timer
        analysis_start = get_time_ms()
        
        output_file = Path("output.txt")
        result = run_command(["python3.8", "src/lab3/SemantickiAnalizator.py"], stdin_data=in_content)
        
        analysis_end = get_time_ms()
        analysis_time_ms = analysis_end - analysis_start
        
        if result:
            with open(output_file, 'w') as f:
                f.write(result.stdout)
        
        # Compare stdout with .out file
        if compare_files(output_file, test_out):
            print(f"{GREEN}  ✔ PASS{RESET} ({analysis_time_ms}ms)\n")
            pass_count += 1
        else:
            print(f"{RED}  ✘ FAIL{RESET} ({analysis_time_ms}ms)")
            show_diff(output_file, test_out)
            print()
            fail_count += 1
    
    # End total timer
    total_end = get_time_ms()
    total_time_ms = total_end - total_start
    total_time = total_time_ms / 1000.0
    
    if not found_any:
        print(f"{RED}No matching tests found for pattern: {pattern or 'tests/lab3_teza/*'}{RESET}")
    
    # Clean up output file
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
