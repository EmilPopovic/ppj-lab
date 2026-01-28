int main(void) {
    int x = 0;
    int y = 0;
    if ((x = 1) || (y = 1)) {
        return x + y;
    }
    return 0;
}
