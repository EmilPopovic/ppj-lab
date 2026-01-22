
int a;
int b;

int f(int a) {
    int b;
    b = a + 1;
    {
        int a;
        a = 10;
        b = b + a;
    }
    return b;
}

int main(void) {
    a = 5;
    b = 3;
    return f(a) + b;
}
