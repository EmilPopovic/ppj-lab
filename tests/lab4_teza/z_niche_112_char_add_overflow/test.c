int main(void) {
    char c = (char)250;
    c = (char)(c + 10); // 260 % 256 = 4
    return (int)c;
}
