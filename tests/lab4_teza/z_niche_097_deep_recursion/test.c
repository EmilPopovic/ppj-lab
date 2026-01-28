int f(int n) {
    if (n <= 0) return 42;
    return f(n - 1);
}
int main(void) {
    return f(50);
}
