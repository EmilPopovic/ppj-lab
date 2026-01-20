int g[5] = {1, 2, 3, 4, 5};
int main(void) {
    int i;
    int sum = 0;
    for(i=0; i<5; i=i+1) {
        sum = sum + g[i];
    }
    return sum; // 15
}
