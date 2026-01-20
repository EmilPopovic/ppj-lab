int main(void) {
    int i = 0; int s = 0;
    while(i < 10) {
        i = i + 1;
        if (i % 2 == 0) continue;
        if (i > 7) break;
        s = s + i;
    }
    return s;
}
