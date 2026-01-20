int main(void) {
    int a[5] = {0, 0, 0, 0, 0};
    int i = 2;
    a[i + 1] = 77; // a[3] = 77
    return a[3];
}
