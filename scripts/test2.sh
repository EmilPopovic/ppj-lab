#!/bin/bash

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${BOLD}${BLUE}=============================="
echo -e "     Running Lab 2 tests"
echo -e "==============================${RESET}\n"

echo -e "Running with:"
python3.8 --version
echo

pass_count=0
fail_count=0

if [ -n "$1" ]; then
    pattern="tests/lab2_teza/${1}_*"
else
    pattern="tests/lab2_teza/*"
fi

found_any=false

for dict in $pattern; do
    [ -d "$dict" ] || continue
    found_any=true
    test_name=$(basename "$dict")

    echo -e "${BOLD}${YELLOW}→ Testing:${RESET} ${test_name}"

    if [[ ! -f "$dict/test.san" || ! -f "$dict/test.in" || ! -f "$dict/test.out" ]]; then
        echo -e "${RED}  ⚠ Missing one or more required files in ${dict}${RESET}\n"
        continue
    fi

    # Step 1: Run GSA.py with .san file on stdin to generate SA.py
    python3.8 src/lab2/GSA.py <"$dict/test.san" 2>/dev/null

    if [[ ! -f "src/lab2/analizator/SA.py" ]]; then
        echo -e "${RED}  ⚠ Failed to generate SA.py${RESET}\n"
        ((fail_count++))
        continue
    fi

    # Step 2: Run the generated SA.py with .in file on stdin
    python3.8 src/lab2/analizator/SA.py <"$dict/test.in" >output.txt 2>/dev/null

    # Step 3: Compare stdout with .out file
    if diff -q output.txt "$dict/test.out" >/dev/null; then
        echo -e "${GREEN}  ✔ PASS${RESET}\n"
        ((pass_count++))
    else
        echo -e "${RED}  ✘ FAIL${RESET}"
        diff -y --color=always output.txt "$dict/test.out" | sed 's/^/    /'
        echo
        ((fail_count++))
    fi

    # Clean up generated SA.py for next test
    rm -f src/lab2/analizator/SA.py
done

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
echo -e "${BOLD}${BLUE}==============================${RESET}"
