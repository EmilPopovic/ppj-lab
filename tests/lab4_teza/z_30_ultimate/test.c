int helper(int a, int b, int c, int d, int e) {
    int x1=a*2, x2=b*3, x3=c*4, x4=d*5, x5=e*6;
    int x6=a+b, x7=c+d, x8=e+a, x9=b+c, x10=d+e;
    int x11=a-b, x12=c-d, x13=e-a, x14=b-c, x15=d-e;
    return x1+x2+x3+x4+x5+x6+x7+x8+x9+x10-x11-x12-x13-x14-x15;
}

int main(void) {
    int a0=0, a1=1, a2=2, a3=3, a4=4, a5=5, a6=6, a7=7, a8=8, a9=9;
    int b0=10, b1=11, b2=12, b3=13, b4=14, b5=15, b6=16, b7=17, b8=18, b9=19;
    int c0=20, c1=21, c2=22, c3=23, c4=24, c5=25, c6=26, c7=27, c8=28, c9=29;
    int arr[30];
    int i = 0;
    int sum = 0;

    while (i < 30) {
        arr[i] = i * i;
        i = i + 1;
    }

    sum = sum + helper(a0, a1, a2, a3, a4);
    sum = sum + helper(a5, a6, a7, a8, a9);
    sum = sum + helper(b0, b1, b2, b3, b4);
    sum = sum + helper(b5, b6, b7, b8, b9);
    sum = sum + helper(c0, c1, c2, c3, c4);
    i = 0;
    while (i < 30) {
        sum = sum + arr[i];
        i = i + 1;
    }
    {
        int local1 = sum + 1;
        int local2 = sum + 2;
        int local3 = sum + 3;
        {
            int nested1 = local1 * 2;
            int nested2 = local2 * 3;
            int nested3 = local3 * 4;
            sum = sum + nested1 + nested2 + nested3;
        }
        sum = sum + local1 + local2 + local3;
    }
    return sum;
}
