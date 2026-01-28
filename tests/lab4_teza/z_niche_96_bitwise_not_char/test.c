int main(void) {
    char c = (char)0;
    return (int)(char)(~c); // ~0 = -1 (int), (char)-1 = 255
}
