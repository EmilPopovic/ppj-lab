int x = 10;
int f(void) {
    int x = 20;
    {
        int x = 30;
        return x;
    }
}
int main(void) {
    return f() + x; // 30 + 10 = 40
}
