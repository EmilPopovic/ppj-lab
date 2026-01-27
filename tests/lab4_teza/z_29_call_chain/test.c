int f20(int x) { return x + 20; }
int f19(int x) { return f20(x) + 19; }
int f18(int x) { return f19(x) + 18; }
int f17(int x) { return f18(x) + 17; }
int f16(int x) { return f17(x) + 16; }
int f15(int x) { return f16(x) + 15; }
int f14(int x) { return f15(x) + 14; }
int f13(int x) { return f14(x) + 13; }
int f12(int x) { return f13(x) + 12; }
int f11(int x) { return f12(x) + 11; }
int f10(int x) { return f11(x) + 10; }
int f9(int x) { return f10(x) + 9; }
int f8(int x) { return f9(x) + 8; }
int f7(int x) { return f8(x) + 7; }
int f6(int x) { return f7(x) + 6; }
int f5(int x) { return f6(x) + 5; }
int f4(int x) { return f5(x) + 4; }
int f3(int x) { return f4(x) + 3; }
int f2(int x) { return f3(x) + 2; }
int f1(int x) { return f2(x) + 1; }

int main(void) {
    return f1(0);
}
