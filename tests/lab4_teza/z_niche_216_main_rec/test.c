int count_rec = 0;
int main(void) {
    count_rec = count_rec + 1;
    if (count_rec < 5) {
        main();
    }
    return count_rec;
}
