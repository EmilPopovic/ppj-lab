int main(void) {
    char c = (char)255;
    c = (char)(c + 1);
    if (c == 0) return 1;
    return 0;
}
