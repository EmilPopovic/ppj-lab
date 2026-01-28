int main(void) {
    char a[1024];
    a[1023] = (char)42;
    return a[1023];
}
