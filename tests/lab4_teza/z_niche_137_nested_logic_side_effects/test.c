int main(void) {
    int x = 0;
    if ((x = 1) || (x = 2)) {
        if (!((x = 0) && (x = 3))) {
            return x; // 0
        }
    }
    return 99;
}
