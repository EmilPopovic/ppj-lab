int main(void) {
    int x = 10;
    int y = 0;
    while (x > 0 && y < 5) {
        x = x - 1;
        y = y + 1;
    }
    return x + y; // Runs 5 times. x=5, y=5. sum=10
}
