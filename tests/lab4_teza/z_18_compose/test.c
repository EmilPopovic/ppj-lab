int inc(int x) { 
    return x + 1;
}

int dbl(int x) { 
    return x * 2; 
}

int main(void) {
    return dbl(inc(5));
}