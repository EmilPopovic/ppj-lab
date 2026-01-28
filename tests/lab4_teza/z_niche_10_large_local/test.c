int main(void) {
    int a[200];
    a[199] = 42;
    a[0] = 7;
    return a[199] + a[0];
}
