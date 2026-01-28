int main(void) {
    int sum = 0;
    int i = 0;
    for (; i < 10; ) {
        i = i + 1;
        if (i < 5) continue;
        sum = sum + i;
        if (sum > 20) break;
    }
    return sum;
}
