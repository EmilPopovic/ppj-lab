int main(void) {
    int arr1[50];
    int arr2[50];
    int arr3[50];
    int i = 0;
    int sum;

    while (i < 50) {
        arr1[i] = i;
        arr2[i] = i * 2;
        arr3[i] = i * 3;
        i = i + 1;
    }

    sum = 0;
    i = 0;

    while (i < 50) {
        sum = sum + arr1[i] + arr2[i] + arr3[i];
        i = i + 1;
    }

    return sum;
}
