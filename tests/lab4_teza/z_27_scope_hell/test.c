int main(void) {
  int x = 1;
  int sum = x;
  {
    int x = 2;
    sum = sum + x;
    {
      int x = 3;
      sum = sum + x;
      {
        int x = 4;
        sum = sum + x;
        {
          int x = 5;
          sum = sum + x;
          {
            int x = 6;
            sum = sum + x;
            {
              int x = 7;
              sum = sum + x;
              {
                int x = 8;
                sum = sum + x;
                {
                  int x = 9;
                  sum = sum + x;
                  {
                    int x = 10;
                    sum = sum + x;
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  return sum;
}
