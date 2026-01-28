int main(void) {
    int a[3]; int b[3]; int c[3];
    c[0] = 1; b[1] = 2; a[2] = 42;
    return a[b[c[0]]];
}
