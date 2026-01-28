int count = 5;
int main(void) {
    if (count == 0) return 100;
    count = count - 1;
    return main() + 1;
}
