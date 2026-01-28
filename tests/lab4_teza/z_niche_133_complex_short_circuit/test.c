int main(void) {
    int x = 0;
    int y = 0;
    if ((x = 1) && (y = 2) && (x = 3)) {
        return x + y; // 3 + 2 = 5
    }
    return 0;
}
