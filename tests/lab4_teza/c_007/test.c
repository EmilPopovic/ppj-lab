
int is_prime[50];

int main(void) {
    int i;
    int j;
    int sum;
    
    i = 0;
    while (i < 50) {
        is_prime[i] = 0;
        i = i + 1;
    }
    
    is_prime[0] = 1;
    is_prime[1] = 1;
    
    i = 2;
    while (i * i < 50) {
        if (is_prime[i] == 0) {
            j = i * i;
            while (j < 50) {
                is_prime[j] = 1;
                j = j + i;
            }
        }
        i = i + 1;
    }
    
    sum = 0;
    i = 0;
    while (i < 50) {
        if (is_prime[i] == 0) {
            sum = sum + i;
        }
        i = i + 1;
    }
    return sum;
}
