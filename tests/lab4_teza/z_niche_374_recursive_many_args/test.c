int f_many(int a, int b, int c, int d, int n) {
    if (n <= 0) return a+b+c+d;
    return f_many(a+1, b+1, c+1, d+1, n-1);
}
int main(void) { return f_many(0,0,0,0,5); }
