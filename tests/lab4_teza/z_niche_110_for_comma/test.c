int main(void) {
    int i, j, sum = 0;
    for(i = 0, j = 10; i < j; i = i + 1, j = j - 1) {
        sum = sum + 1;
    }
    return sum; // 0<10, 1<9, 2<8, 3<7, 4<6 (5 times)
}
