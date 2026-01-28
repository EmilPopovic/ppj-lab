int main(void) {
    int x = 1;
    {
        int x = 2;
        {
            int x = 3;
            x = x;
        }
        x = x + 1;
    }
    return x;
}
