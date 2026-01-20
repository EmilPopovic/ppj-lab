int main(void) {
    int i; int j; int s=0;
    for(i=0; i<3; i=i+1) {
        for(j=0; j<3; j=j+1) {
            if (i==j) continue;
            s = s + 1;
        }
    }
    return s;
}
