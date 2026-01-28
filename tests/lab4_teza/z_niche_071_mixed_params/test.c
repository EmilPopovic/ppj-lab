int f(int a, char b, int c, char d) {
    return a + (int)b + c + (int)d;
}
int main(void) {
    return f(1, (char)2, 3, (char)4); // 1+2+3+4 = 10
}
