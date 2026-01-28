int foo(int x) {
    int a[10];
    if (x > 10) return 1;
    if (x < 0) return -1;
    return 0;
}
int main(void) {
    return foo(5) + foo(15) + foo(-5);
}
