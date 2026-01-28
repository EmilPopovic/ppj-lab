int main(void) {
    int i;
    int j;
    int count = 0;
    for (i = 0; i < 3; i = i + 1) {
        for (j = 0; j < 3; j = j + 1) {
            count = count + 1;
        }
    }
    return count;
}
