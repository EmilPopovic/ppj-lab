int main(void) {
    int a[256]; // 1024 bytes (0x400 - OK)
    int b = 1;  // 1028 bytes (0x404 - NOT OK for imm8)
    b = 42;
    return b;
}
