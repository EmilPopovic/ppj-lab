int main(void) {
    char c = '\0';
    if (c) return 1;
    c = 'a';
    if (c) return 2;
    return 0;
}
