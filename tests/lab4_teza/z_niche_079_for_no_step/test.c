int main(void) {
    int i;
    int sum = 0;
    for (i = 0; i < 5; ) {
        sum = sum + i;
        i = i + 1;
    }
    return sum;
}
