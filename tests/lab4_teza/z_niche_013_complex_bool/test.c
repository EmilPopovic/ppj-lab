int main(void) {
    int a = 1, b = 0, c = 1, d = 0;
    if (!(a && b) && (c || d)) {
        return 42;
    }
    return 0;
}
