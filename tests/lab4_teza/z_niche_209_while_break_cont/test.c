int main(void) {
    int sum = 0;
    int i = 0;
    while (i < 10) {
    i = i + 1;
    if (i % 2 == 0) continue;
    if (i > 7) break;
    sum = sum + i;
   
}
 return sum;
   
}

