int g = 0;
int f(void) { g=1; return 1; }
int main(void) {
    int x = 0;
    if (x && f()) { ; }
    return g;
}
