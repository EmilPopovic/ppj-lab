int main(void) {
    int x = 1;
    {
        int x = 2;
        {
            int x = 3;
            x = x;
        }
        if (x == 2) return 42;
    }
    return 0;
}
