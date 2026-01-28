int main(void) {
    int x = 0;
    if (1 || (x = 1)) {
        if (!(0 && (x = 2))) {
            return x; // Should be 0
        }
    }
    return 99;
}
