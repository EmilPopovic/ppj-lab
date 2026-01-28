int a[3] = {1, 2, 0};
int main(void) {
    return a[a[a[1]]]; // a[a[2]] = a[0] = 1
}
