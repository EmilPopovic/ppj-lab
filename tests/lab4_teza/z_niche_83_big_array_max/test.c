int a[1024];
int main(void) {
    a[0] = 1;
    a[1023] = 42;
    return a[0] + a[1023];
}
