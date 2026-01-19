#!/bin/bash

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${BOLD}${BLUE}=============================="
echo -e "     Running Lab 4 tests"
echo -e "==============================${RESET}\n"

echo -e "Running with:"
python3.8 --version
echo

pass_count=0
fail_count=0

if [ -n "$1" ]; then
    pattern="tests/lab4_teza/${1}*"
else
    pattern="tests/lab4_teza/*"
fi

found_any=false

# Start total timer (in milliseconds)
total_start=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))

for dict in $pattern; do
    [ -d "$dict" ] || continue
    found_any=true
    test_name=$(basename "$dict")

    echo -e "${BOLD}${YELLOW}→ Testing:${RESET} ${test_name}"

    if [[ ! -f "$dict/test.in" || ! -f "$dict/test.out" ]]; then
        echo -e "${RED}  ⚠ Missing one or more required files in ${dict}${RESET}\n"
        continue
    fi

    # Start generation timer (in milliseconds)
    gen_start=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))

    # Step 1: Run GeneratorKoda.py with .in file on stdin to generate ARM assembly
    python3.8 src/lab4/GeneratorKoda.py <"$dict/test.in" >a.s 2>/dev/null

    # End generation timer
    gen_end=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
    gen_time_ms=$((gen_end - gen_start))

    if [[ ! -f "a.s" ]]; then
        echo -e "${RED}  ⚠ Failed to generate ARM assembly${RESET}\n"
        ((fail_count++))
        continue
    fi

    # Get size of generated file
    asm_size=$(wc -c < "a.s")

    # Start simulation timer (in milliseconds)
    sim_start=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))

    # Step 2: Run the simulator to check R6 register value
    expected_val=$(cat "$dict/test.out" | tr -d ' \n')
    
    result=$(python "$(dirname "$0")/arm_simulator.py" "./src/lab4/a.s" "$expected_val" 2>/dev/null)

    # End simulation timer
    sim_end=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
    sim_time_ms=$((sim_end - sim_start))

    # Step 3: Check result
    if [[ "$result" == "PASS" ]]; then
        echo -e "${GREEN}  ✔ PASS${RESET} (gen: ${gen_time_ms}ms, sim: ${sim_time_ms}ms, ASM: ${asm_size} bytes)\n"
        ((pass_count++))
    else
        echo -e "${RED}  ✘ FAIL${RESET} (gen: ${gen_time_ms}ms, sim: ${sim_time_ms}ms, ASM: ${asm_size} bytes)"
        echo -e "    Expected: ${expected_val}"
        echo
        ((fail_count++))
    fi
done

# End total timer
total_end=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
total_time_ms=$((total_end - total_start))
total_time=$(awk "BEGIN {printf \"%.3f\", $total_time_ms / 1000}")

if [ "$found_any" = false ]; then
    echo -e "${RED}No matching tests found for pattern: ${pattern}${RESET}"
fi

rm -f a.s output.txt

total=$((pass_count + fail_count))
echo -e "${BOLD}${BLUE}==============================${RESET}"
echo -e " ${BOLD}Test Summary:${RESET}"
echo -e "   ${GREEN}✔ Passed:${RESET} $pass_count"
echo -e "   ${RED}✘ Failed:${RESET} $fail_count"
echo -e "   ${BOLD}Total:${RESET} $total"
echo -e "   ${BOLD}Total Time:${RESET} ${total_time}s"
echo -e "${BOLD}${BLUE}==============================${RESET}"
