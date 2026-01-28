int main(void) {
    int a = -2147483647;
    int b = 1;
    a = a - 1; // INT_MIN
    return a / b; // INT_MIN
}
