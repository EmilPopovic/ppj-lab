int main(void) {
    int a=1, b=0;
    if (a || (b = 1)) return b;
    return -1;
}
