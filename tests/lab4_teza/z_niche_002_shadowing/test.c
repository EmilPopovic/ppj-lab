int x = 1;
int main(void) {
    int x = 2;
    {
        int x = 3;
        {
            int x = 4;
            if (x == 4) {
                int x = 5;
                return x + 10;
            }
        }
        return x;
    }
    return x;
}
