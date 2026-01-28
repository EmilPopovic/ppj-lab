int a[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
int main(void) {
    int i = 2;
    return a[a[i] * 2 + 1];
}
