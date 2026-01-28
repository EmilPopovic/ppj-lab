int main(void) {
    int x = 0;
    if ((x = 1)) {
        if ((x = 2)) {
            return x;
        }
    }
    return 0;
}
