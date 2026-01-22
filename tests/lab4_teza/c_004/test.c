
int A[9];
int C[9];

int get(int arr[], int r, int c) {
    return arr[r * 3 + c];
}

void set(int arr[], int r, int c, int val) {
    arr[r * 3 + c] = val;
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int main(void) {
    int i;
    int j;
    int k;
    int sum;
    int val;
    
    i = 0;
    while (i < 3) {
        j = 0;
        while (j < 3) {
            set(A, i, j, i + j);
            j = j + 1;
        }
        i = i + 1;
    }
    
    i = 0;
    while (i < 3) {
        j = 0;
        while (j < 3) {
            sum = 0;
            k = 0;
            while (k < 3) {
                sum = sum + get(A, i, k) * get(A, k, j);
                k = k + 1;
            }
            set(C, i, j, sum);
            j = j + 1;
        }
        i = i + 1;
    }
    
    sum = 0;
    i = 0;
    while (i < 3) {
        sum = sum + get(C, i, i);
        i = i + 1;
    }
    
    return factorial(sum % 5);
}
