int main(void) {
    int x = 10;
    int count = 0;
    while((x = x - 2) > 0) {
        count = count + 1;
    }
    return count; // 8, 6, 4, 2 -> 4 times
}
