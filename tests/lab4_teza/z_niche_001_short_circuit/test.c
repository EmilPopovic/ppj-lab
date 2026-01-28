int main(void) {
    int a = 0;
    int b = 0;
    if ((a = 1) || (b = 2)) {
        return b;
    }
    return 99;
}
