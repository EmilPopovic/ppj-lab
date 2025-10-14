#!/bin/bash

echo "Running Lab 1 tests"

for dict in tests/lab1_teza/*; do
    [ -d "$dict" ] || continue

    echo "Testing directory: $dict"

    if [[ ! -f "$dict/test.lan" || ! -f "$dict/test.in" || ! -f "$dict/test.out" ]]; then
        echo "Missing one or more required files in $dict"
        continue
    fi

    python src/lab1/GLA.py <"$dict/test.lan" 2>/dev/null

    python LA.py <"$dict/test.in" >output.txt 2>/dev/null

    if diff -q output.txt "$dict/test.out" >/dev/null; then
        echo "PASS"
    else
        echo "FAIL"
        echo "Differences:"
        diff output.txt "$dict/test.out"
    fi

    echo
done

# Cleanup temporary file
rm -f output.txt
rm -f LA.py
