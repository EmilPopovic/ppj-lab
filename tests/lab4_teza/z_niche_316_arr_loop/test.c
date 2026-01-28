int main(void) {
    int a[5];
    int i;
    int sum = 0;
    for (i = 0; i < 5; i = i + 1) a[i] = i * i;
    for (i = 0; i < 5; i = i + 1) sum = sum + a[i];
    return sum;
}
