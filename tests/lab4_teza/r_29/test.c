int main(void) {
    int x = 1;
    {
        int x = 2;
        if (x != 2) return 0;
    }
    return x; // Should be 1
}
