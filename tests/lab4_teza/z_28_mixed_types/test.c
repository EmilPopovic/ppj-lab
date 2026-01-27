int main(void) {
    int i1 = 100, i2 = 200, i3 = 300;
    char c1 = 10, c2 = 20, c3 = 30;
    int arr[20];
    char carr[20];
    int idx = 0;

    while (idx < 20) {
        arr[idx] = idx * 10;
        carr[idx] = (char)(idx + 65);
        idx = idx + 1;
    }

    int sum = i1 + i2 + i3;
    sum = sum + (int)c1 + (int)c2 + (int)c3;
    idx = 0;

    while (idx < 20) {
        sum = sum + arr[idx];
        sum = sum + (int)carr[idx];
        idx = idx + 1;
    }

    return sum;
}
