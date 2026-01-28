int h(int x) { return x + 1; }
int g(int x) { return h(x) * 2; }
int f(int x) { return g(x) - 3; }
int main(void) { return f(5); }
