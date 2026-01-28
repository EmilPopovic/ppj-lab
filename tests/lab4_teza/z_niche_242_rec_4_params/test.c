int sum(int n, int a, int b, int c) {
    if (n == 0) return a+b+c;
    return sum(n-1, a+1, b+1, c+1);
   
}
 int main(void) {
    return sum(3, 0, 0, 0);
   
}

