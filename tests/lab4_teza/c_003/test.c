
int A[9];
int B[9];
int C[9];

void set(int arr[], int r, int c, int val) {
    arr[r * 3 + c] = val;
}

int get(int arr[], int r, int c) {
    return arr[r * 3 + c];
}

void multiply(void) {
    int i;
    int j;
    int k;
    int sum;
    
    i = 0;
    while (i < 3) {
        j = 0;
        while (j < 3) {
            sum = 0;
            k = 0;
            while (k < 3) {
                sum = sum + get(A, i, k) * get(B, k, j);
                k = k + 1;
            }
            set(C, i, j, sum);
            j = j + 1;
        }
        i = i + 1;
    }
}

int main(void) {
    int i;
    int j;
    int val;
    
    i = 0;
    while (i < 9) {
        A[i] = i;
        B[i] = 8 - i;
        i = i + 1;
    }
    
    multiply();
    
    val = 0;
    i = 0;
    while (i < 9) {
        val = val + C[i];
        i = i + 1;
    }
    
    return val; 
}
