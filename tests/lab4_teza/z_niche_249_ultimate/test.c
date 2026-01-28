int fact(int n) {
    if (n <= 1) return 1;
    return n * fact(n-1);
   
}
 int main(void) {
    int i;
    int sum = 0;
    for(i=0;
    i<5;
    i=i+1) {
    sum = sum + fact(i);
   
}
 return sum;
   
}

