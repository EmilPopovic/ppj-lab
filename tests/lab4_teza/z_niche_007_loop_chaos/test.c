int main(void) {
    int i, j, count = 0;
    for (i = 0; i < 5; i = i + 1) {
        for (j = 0; j < 5; j = j + 1) {
            if (i == j) continue;
            if (i + j > 6) break;
            count = count + 1;
        }
    }
    return count;
}
