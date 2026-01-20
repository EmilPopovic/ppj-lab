int main(void) {
    int i = 0;
    int j = 0;
    int sum = 0;
    while (i < 5) {
        j = 0;
        while (j < 5) {
            if (j == 3) break;
            sum = sum + 1;
            j = j + 1;
        }
        i = i + 1;
    }
    return sum; // 5 * 3 = 15
}
