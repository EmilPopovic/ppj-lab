int rsum(int n) {
    if (n <= 0) return 0;
    return n + rsum(n-1);
}
int main(void) { return rsum(5); }
