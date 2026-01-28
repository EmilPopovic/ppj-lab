int main(void) {
    char a[500];
    a[99] = 'x';
    a[499] = 'y';
    return a[99] + a[499]; // 120 + 121 = 241
}
