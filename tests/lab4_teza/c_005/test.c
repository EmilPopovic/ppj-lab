
int arr[10];

void swap(int i, int j) {
    int temp;
    temp = arr[i];
    arr[i] = arr[j];
    arr[j] = temp;
}

int partition(int low, int high) {
    int pivot;
    int i;
    int j;
    pivot = arr[high];
    i = low - 1;
    j = low;
    while (j < high) {
        if (arr[j] < pivot) {
            i = i + 1;
            swap(i, j);
        }
        j = j + 1;
    }
    swap(i + 1, high);
    return i + 1;
}

void quickSort(int low, int high) {
    int pi;
    if (low < high) {
        pi = partition(low, high);
        quickSort(low, pi - 1);
        quickSort(pi + 1, high);
    }
}

int main(void) {
    int sum;
    int i;
    
    i = 0;
    while (i < 10) {
        arr[i] = 10 - i;
        i = i + 1;
    }
    
    quickSort(0, 9);
    
    sum = 0;
    i = 0;
    while (i < 5) {
        sum = sum + arr[i];
        i = i + 1;
    }
    return sum;
}
