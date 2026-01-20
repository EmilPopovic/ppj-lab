int main(void) {
    int i;
    int sum = 0;
    for (i = 0; i < 5; i = i + 1) {
        int i = 10;
        sum = sum + i;
    }
    return sum; // 5 * 10 = 50
}
