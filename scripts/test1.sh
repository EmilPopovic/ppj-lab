#!/bin/bash

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${BOLD}${BLUE}=============================="
echo -e "     Running Lab 1 tests"
echo -e "==============================${RESET}\n"

echo -e "Running with:"
python3.8 --version
echo

pass_count=0
fail_count=0

if [ -n "$1" ]; then
    pattern="tests/lab1_teza/${1}*"
else
    pattern="tests/lab1_teza/*"
fi

found_any=false

# Create analizator directory if it doesn't exist
mkdir -p src/lab1/analizator

# Start total timer (in milliseconds)
total_start=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))

for dict in $pattern; do
    [ -d "$dict" ] || continue
    found_any=true
    test_name=$(basename "$dict")

    echo -e "${BOLD}${YELLOW}→ Testing:${RESET} ${test_name}"

    if [[ ! -f "$dict/test.lan" || ! -f "$dict/test.in" || ! -f "$dict/test.out" ]]; then
        echo -e "${RED}  ⚠ Missing one or more required files in ${dict}${RESET}\n"
        continue
    fi

    # Start generation timer (in milliseconds)
    gen_start=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))

    # Step 1: Run GLA.py with .lan file on stdin to generate LA.py
    python3.8 src/lab1/GLA.py <"$dict/test.lan" 2>/dev/null

    # End generation timer
    gen_end=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
    gen_time_ms=$((gen_end - gen_start))

    if [[ ! -f "src/lab1/analizator/LA.py" ]]; then
        echo -e "${RED}  ⚠ Failed to generate LA.py${RESET}\n"
        ((fail_count++))
        continue
    fi

    # Get size of generated file
    la_size=$(wc -c < "src/lab1/analizator/LA.py")
    
    # Start lexing timer (in milliseconds)
    lex_start=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
    
    # Step 2: Run the generated LA.py with .in file on stdin
    python3.8 src/lab1/analizator/LA.py <"$dict/test.in" >output.txt 2>/dev/null

    # End lexing timer
    lex_end=$(( $(date +%s) * 1000 + 10#$(date +%N) / 1000000 ))
    lex_time_ms=$((lex_end - lex_start))

    # Step 3: Compare stdout with .out file
    if diff -q output.txt "$dict/test.out" >/dev/null; then
        echo -e "${GREEN}  ✔ PASS${RESET} (gen: ${gen_time_ms}ms, lex: ${lex_time_ms}ms, LA.py: ${la_size} bytes)\n"
        ((pass_count++))
    else
        echo -e "${RED}  ✘ FAIL${RESET} (gen: ${gen_time_ms}ms, lex: ${lex_time_ms}ms, LA.py: ${la_size} bytes)"
        diff --color=always output.txt "$dict/test.out" | sed 's/^/    /'
        echo
        ((fail_count++))
    fi

    # Clean up generated analizator directory for next test
    rm -rf src/lab1/analizator
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

