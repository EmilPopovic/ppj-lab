int x = 10;
int f(int n, int m) {
    int i, res = 0;
    for (i = 0; i < n; i = i + 1) {
        if (i % 2 == 0) res = res + m;
        else res = res - 1;
    }
    return res;
}
int main(void) {
    int val = f(5, x); // i=0: +10, i=1: -1, i=2: +10, i=3: -1, i=4: +10 => 28
    return val + (1 || (x = 100)) + (!0) * 2; // 28 + 1 + 2 = 31
}
