int main(void) {
    int i;
    for(i=0; i<10; i=i+1) {
        {
            if (i == 5) return i;
        }
    }
    return 0;
}
