int f(int a, int b, int c, int d, int e, int g) {
    if (a <= 0) return g;
    return f(a - 1, b, c, d, e, g + 1);
}
int main(void) {
    return f(5, 0, 0, 0, 0, 10); // 10 + 5 = 15
}
