int x = 0;
void f(int n) {
    if (n > 5) return;
    x = 10;
}
int main(void) {
    f(10);
    f(2);
    return x;
}
