int main(void) {
    int x = 0;
    if (1)
        if (0) x = 1;
        else x = 2; // Should exeucte this
    return x;
}
