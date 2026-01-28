int main(void) {
    int a = 7, b = 3, c = 1, d = 4;
    // 7 & 3 | 1 ^ 4 -> (7 & 3) | (1 ^ 4) -> 3 | 5 = 7
    return a & b | c ^ d;
}
