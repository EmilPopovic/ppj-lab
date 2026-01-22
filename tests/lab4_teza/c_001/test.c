
int sum_args(int a, int b, int c, int d, int e, int f) {
    if (a == 0) return 0;
    return a + b + c + d + e + f + sum_args(a - 1, b, c, d, e, f);
}

int main(void) {
    int res;
    res = sum_args(5, 1, 1, 1, 1, 1); 
    return res;
}
