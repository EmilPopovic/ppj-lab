int a[10] = {1, 2, 3};
int main(void) {
    int sum = 0;
    int i;
    for (i = 0; i < 10; i = i + 1) {
        sum = sum + a[i];
    }
    return sum;
}
