int g_val = 10;
int f_chaos(int x) {
    int i;
    for(i=0; i<x; i=i+1) g_val = g_val + 1;
    return g_val;
}
int main(void) {
    if (f_chaos(5) > 10) return f_chaos(5);
    return 0;
}
