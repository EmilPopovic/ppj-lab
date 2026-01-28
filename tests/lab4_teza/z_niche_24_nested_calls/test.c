int f(int x) { return x + 1; }
int g(int x) { return x * 2; }
int main(void) {
    return f(g(f(g(1))));
}
