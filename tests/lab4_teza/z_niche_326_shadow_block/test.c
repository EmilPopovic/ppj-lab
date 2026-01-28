int main(void) {
    int x = 1;
    {
        int x = 2;
        {
            int x = 3;
            if (x != 3) return 0;
        }
        if (x != 2) return 0;
    }
    return x;
}
