int g = 10;
int f(int a, int b) {
    int i, res = 0;
    for(i=0; i<a; i=i+1) {
        if (i % 2 == 0) res = res + b;
        else res = res - g;
    }
    return res;
}
int main(void) {
    int x[2] = {5, 10};
    return f(x[0], x[1]); // f(5, 10) -> i=0:+10, i=1:-10, i=2:+10, i=3:-10, i=4:+10 => 10
}
