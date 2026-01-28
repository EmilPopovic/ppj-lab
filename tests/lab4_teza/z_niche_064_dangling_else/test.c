int main(void) {
    if (1) if (0) return 1; else return 2; // dangling else belongs to closest if
    return 0;
}
