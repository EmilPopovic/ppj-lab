int main(void) {
    // 1 || 0 -> 1
    // 1 && 0 -> 0
    // If || higher: (1||0) && 0 = 0
    // If && higher: 1 || (0&&0) = 1
    if (1 || 0 && 0) return 1;
    return 0;
}
