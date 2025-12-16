#!/bin/bash

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${BOLD}${BLUE}=============================="
echo -e "     Running Lab 3 tests"
echo -e "==============================${RESET}\n"

echo -e "Running with:"
python3.8 --version
echo

pass_count=0
fail_count=0

if [ -n "$1" ]; then
    pattern="tests/lab3_teza/${1}*"
else
    pattern="tests/lab3_teza/*"
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

    # Start analysis timer (in milliseconds)
    analysis_start=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
    
    # Run SemantickiAnalizator.py with .in file on stdin
    python3.8 src/lab3/SemantickiAnalizator.py <"$dict/test.in" >output.txt 2>/dev/null

    # End analysis timer
    analysis_end=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
    analysis_time_ms=$((analysis_end - analysis_start))

    # Compare stdout with .out file
    if diff -q output.txt "$dict/test.out" >/dev/null; then
        echo -e "${GREEN}  ✔ PASS${RESET} (${analysis_time_ms}ms)\n"
        ((pass_count++))
    else
        echo -e "${RED}  ✘ FAIL${RESET} (${analysis_time_ms}ms)"
        diff --color=always output.txt "$dict/test.out" | sed 's/^/    /'
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

rm -f output.txt

total=$((pass_count + fail_count))
echo -e "${BOLD}${BLUE}==============================${RESET}"
echo -e " ${BOLD}Test Summary:${RESET}"
echo -e "   ${GREEN}✔ Passed:${RESET} $pass_count"
echo -e "   ${RED}✘ Failed:${RESET} $fail_count"
echo -e "   ${BOLD}Total:${RESET} $total"
echo -e "   ${BOLD}Total Time:${RESET} ${total_time}s"
echo -e "${BOLD}${BLUE}==============================${RESET}"
