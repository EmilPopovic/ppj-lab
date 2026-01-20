int main(void) {
    int i = 0;
    int j = 0;
    // Condition: i < 5 AND (j < 2 OR i < 100)
    // j<2 false when j>=2. i<100 always true until end.
    // Effectively while i < 5
    while (i < 5 && (j < 2 || i < 100)) {
        i = i + 1;
        j = j + 1;
    }
    return i;
}
