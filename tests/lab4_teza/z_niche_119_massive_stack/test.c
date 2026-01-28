int main(void) {
    int a[100];
    int b[100];
    int i;
    for(i=0; i<100; i=i+1) a[i] = i;
    for(i=0; i<100; i=i+1) b[i] = a[99-i];
    return b[0]; // a[99] = 99
}
