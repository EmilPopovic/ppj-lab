int g = 0;

void inc(void) {
    g = g + 1;
}

int main(void) {
    inc();
    inc();
    return g;
}