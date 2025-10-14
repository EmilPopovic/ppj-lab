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

pass_count=0
fail_count=0

for dict in tests/lab1_teza/*; do
    [ -d "$dict" ] || continue
    test_name=$(basename "$dict")

    echo -e "${BOLD}${YELLOW}→ Testing:${RESET} ${test_name}"

    if [[ ! -f "$dict/test.lan" || ! -f "$dict/test.in" || ! -f "$dict/test.out" ]]; then
        echo -e "${RED}  ⚠ Missing one or more required files in ${dict}${RESET}\n"
        continue
    fi

    python src/lab1/GLA.py <"$dict/test.lan" 2>/dev/null
    python LA.py <"$dict/test.in" >output.txt 2>/dev/null

    if diff -q output.txt "$dict/test.out" >/dev/null; then
        echo -e "${GREEN}  ✔ PASS${RESET}\n"
        ((pass_count++))
    else
        echo -e "${RED}  ✘ FAIL${RESET}"
        diff --color=always output.txt "$dict/test.out" | sed 's/^/    /'
        echo
        ((fail_count++))
    fi
done

rm -f output.txt LA.py

total=$((pass_count + fail_count))
echo -e "${BOLD}${BLUE}==============================${RESET}"
echo -e " ${BOLD}Test Summary:${RESET}"
echo -e "   ${GREEN}✔ Passed:${RESET} $pass_count"
echo -e "   ${RED}✘ Failed:${RESET} $fail_count"
echo -e "   ${BOLD}Total:${RESET} $total"
echo -e "${BOLD}${BLUE}==============================${RESET}"
