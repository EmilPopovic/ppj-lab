
int main(void) {
    int hash;
    int i;
    hash = 0;
    
    for (i = 0; i < 20; i = i + 1) {
        if (i % 2 == 0) {
            hash = (hash << 1) ^ i;
        } else {
            hash = (hash >> 1) | i;
        }
    }
    
    return hash & 255;
}
