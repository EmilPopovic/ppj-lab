int x = 1;
    int f(void) {
    int x = 2;
    return x;
   
}
 int main(void) {
    return x + f();
   
}

