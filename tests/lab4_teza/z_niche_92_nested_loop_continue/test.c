int main(void) {
    int i, j, sum = 0;
    for (i = 0; i < 3; i = i + 1) {
        for (j = 0; j < 3; j = j + 1) {
            if (j == 1) continue;
            sum = sum + 1;
        }
    }
    return sum; // (2 per inner loop) * 3 = 6
}
