int main(void) {
    int i = 0;
    int sum = 0;
    for (i=0; i<6; i++) {
        if (i == 3) continue;
        sum = sum + i;
    }
    return sum;
}