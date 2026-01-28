int main(void) {
    int i, j = 0, k = 0;
    for (i = 0; i < 5; i = i + 1) {
        j = j + 1;
        k = k + 1;
    }
    return i + j + k;
}
