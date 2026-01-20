int main(void) {
    int a = 5;
    int b = 10;
    int c = 15;
    if (a < b && b < c || a > c) {
        return 1;
    }
    return 0;
}
