int x_gs = 10;
int main(void) {
    int x_gs = 20;
    {
        int x_gs = 30;
        x_gs = x_gs;
    }
    return x_gs;
}
