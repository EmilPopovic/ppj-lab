int sum_arr(int a[], int n) {
    int i;
    int s = 0;
    for (i = 0; i < n; i = i + 1) s = s + a[i];
    return s;
}
int main(void) {
    int b[3];
    b[0]=1; b[1]=2; b[2]=3;
    return sum_arr(b, 3);
}
