int sum(int arr[], int n) {
    if (n == 0) return 0;
    return arr[n-1] + sum(arr, n-1);
}
int main(void) {
    int a[3] = {1, 2, 3};
    return sum(a, 3); // 6
}
