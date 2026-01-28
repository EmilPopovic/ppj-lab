int main(void) {
    char c = (char)0;
    c = (char)((int)c - 1);
    return (int)c; // Should be 255 if 8-bit unsigned char range
}
