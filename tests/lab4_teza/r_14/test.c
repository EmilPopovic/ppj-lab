int main(void) {
    int idx[3] = {2, 0, 1};
    int val[3] = {10, 20, 30};
    return val[idx[0]] + val[idx[1]] + val[idx[2]]; // 30+10+20 = 60
}
