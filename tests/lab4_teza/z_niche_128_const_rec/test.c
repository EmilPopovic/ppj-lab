int f(int n) {
    if (n == 0) return 42;
    return f(0);
}
int main(void) {
    return f(5);
}
