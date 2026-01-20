int g = 0;
void f(void) { if (1) { g=1; return; } g=2; }
int main(void) { f(); return g; }
