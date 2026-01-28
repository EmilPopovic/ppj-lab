int f(int a, int b, int c, int d) {
    if (a <= 0) return d;
    return f(a - 1, b, c, d + 1);
}
int main(void) {
    return f(10, 0, 0, 100); // 110
}
