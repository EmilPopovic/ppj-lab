int main(void) {
    int i, sum = 0;
    for(i=0; i<3; i=i+1) {
        for(i=0; i<2; i=i+1) {
            sum = sum + 1;
        }
        // after inner loop i is 2. Outer loop increments i to 3. Loop ends.
    }
    return sum;
}
