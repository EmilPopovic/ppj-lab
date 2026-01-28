int main(void) {
    int x = 5;
    int sum = 0;
    while ((x = x - 1)) {
        sum = sum + 1;
    }
    return sum; // Should be 4 (reaches 0)
}
