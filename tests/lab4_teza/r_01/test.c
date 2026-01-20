int main(void) {
    int i;
    int sum = 0;
    for (i = 0; i < 10; i = i + 1) {
        if (i < 5) continue;
        sum = sum + i;
    }
    return sum; // 5+6+7+8+9 = 35
}
