int main(void) {
    int a[2] = {10, 20};
    int b[2] = {0, 1};
    int i = 0;
    return (a[b[i+1]])++; // a[b[1]]++ = a[1]++ = 20, returns 20
}
