int x = 10;
int f(int n) {
    if (n <= 0) return x;
    {
        int x = n;
        return f(n - 1) + x;
    }
}
int main(void) {
    return f(3); // f(3) = f(2) + 3 = (f(1) + 2) + 3 = ((f(0) + 1) + 2) + 3 = ((10 + 1) + 2) + 3 = 16
}
