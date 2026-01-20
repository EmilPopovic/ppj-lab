void inc(int arr[]) {
    arr[0] = arr[0] + 1;
}
int main(void) {
    int a[1] = {10};
    inc(a);
    return a[0]; // 11
}
