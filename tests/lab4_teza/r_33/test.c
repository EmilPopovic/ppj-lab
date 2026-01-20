int f(int x) { return x + x; }
int main(void) {
    // f(1) = 2
    // f(2) = 4
    return f(f(1));
}
