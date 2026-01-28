int x = 0;
void g(void) { x = 42; }
void f(void) { g(); }
int main(void) {
    f();
    return x;
}
