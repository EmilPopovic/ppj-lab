int main(void) {
    int arr[5] = {1, arr[0] + 1, arr[1] + 1, arr[2] + 1, arr[3] + 1};
    return arr[4]; // 1, 2, 3, 4, 5 -> returns 5
}
