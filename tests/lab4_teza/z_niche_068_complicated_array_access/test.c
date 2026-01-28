int main(void) {
    int a[3] = {0, 1, 2};
    int b[3] = {2, 1, 0};
    int c[3] = {1, 2, 0};
    return a[b[c[0]]]; // a[b[2]] = a[0] = 0
}
