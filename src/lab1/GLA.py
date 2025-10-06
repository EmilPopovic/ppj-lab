import sys

def out(*args, **kwargs) -> None:
    """Use this function for program output"""
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    """Use this function for logging and errors not needed in program output"""
    print(*args, file=sys.stderr, **kwargs)

def main() -> None:
    rows = [line.strip() for line in sys.stdin]
    for row in rows:
        log(row)

    ...

if __name__ == '__main__':
    main()
