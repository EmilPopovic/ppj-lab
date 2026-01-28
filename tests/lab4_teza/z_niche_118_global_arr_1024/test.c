int a[1024];
int main(void) {
    a[1023] = 123;
    return a[1023];
}
