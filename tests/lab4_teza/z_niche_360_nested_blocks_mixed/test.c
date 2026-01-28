int main(void) {
    int x = 1;
    {
        int y = 2;
        x = x + y;
        {
            int z = 3;
            x = x + z;
        }
    }
    return x;
}
