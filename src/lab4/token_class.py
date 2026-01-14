from typing import Optional

from scope import Symbol

class Token:
    def __init__(self, name: str, line_number: int, source: str, symbol: Optional['Symbol'] = None) -> None:
        self.name: str = name
        self.line_number: int = line_number
        self.source: str = source
        self.symbol: Optional[Symbol] = symbol

    @property
    def is_int(self) -> bool:
        try:
            num = int(self.source)
            return num < 2 ** 31 and num >= -(2 ** 31)
        except ValueError:
            return False
        
    @property
    def is_char(self) -> bool:
        try:
            no_quotes = self.source[1:-1]
            if no_quotes.startswith('\\'):
                escape_map = {
                    '\\t': '\t',
                    '\\n': '\n',
                    '\\0': '\0',
                    "\\'": "'",
                    '\\"': '"',
                    '\\\\': '\\'
                }
                char = escape_map.get(no_quotes, no_quotes[1:])
            else:
                char = no_quotes

            ascii_val = ord(char) if len(char) == 1 else -1
            return 0 <= ascii_val < 2 ** 8
        except (TypeError, IndexError):
            return False
    
    @property
    def to_int(self) -> int:
        no_quotes = self.source[1:-1]
        if no_quotes.startswith('\\'):
            escape_map = {
                '\\t': '\t',
                '\\n': '\n',
                '\\0': '\0',
                "\\'": "'",
                '\\"': '"',
                '\\\\': '\\'
            }
            char = escape_map.get(no_quotes, no_quotes[1:])
        else:
            char = no_quotes

        ascii_val = ord(char) if len(char) == 1 else -1
        return ascii_val
        
    @property
    def is_valid_str(self) -> bool:
        without_backslash = self.source.replace('\\\\', '')[1:-1]
        for i, c in enumerate(without_backslash):
            if c == '\\' and (i == len(without_backslash) or without_backslash[i+1] not in ['t', 'n', '0', '\'', '"']):
                return False
        return True 

    @staticmethod
    def from_str(s: str, symbol: Optional['Symbol'] = None) -> 'Token':
        token_type, line_num_str, *source = s.split()
        return Token(token_type, int(line_num_str), ' '.join(source), symbol) 

    def __repr__(self) -> str:
        return f'{self.name}({self.line_number},{self.source})'
