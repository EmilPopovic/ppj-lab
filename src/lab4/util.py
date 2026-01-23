import sys

def out(*args, **kwargs) -> None:
    print(*args, file=sys.stdout, **kwargs)

def log(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)
