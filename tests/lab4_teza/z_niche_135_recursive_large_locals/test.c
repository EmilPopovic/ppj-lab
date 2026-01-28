int f(int n) {
    int a[50];
    if (n <= 0) return 42;
    a[0] = n;
    return f(n - 1);
}
int main(void) {
    return f(10);
}
