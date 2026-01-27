import os
import subprocess
import glob

def main():
    test_base_dir = 'tests/lab4_teza'
    z_dirs = glob.glob(os.path.join(test_base_dir, 'z_*'))
    
    la_path = 'src/lab1/analizator/LA.py'
    sa_path = 'src/lab2/analizator/SA.py'
    
    for dir_path in sorted(z_dirs):
        test_c = os.path.join(dir_path, 'test.c')
        test_in = os.path.join(dir_path, 'test.in')
        
        if os.path.exists(test_c):
            print(f"Processing {dir_path}...")
            # python src/lab1/analizator/LA.py < tests/lab4_teza/z_21_extreme_locals/test.c | python src/lab2/analizator/SA.py | tee tests/lab4_teza/z_21_extreme_locals/test.in
            
            try:
                # We use shell=True to easily handle redirection and pipes as in the user's request
                cmd = f"python {la_path} < {test_c} | python {sa_path} | tee {test_in}"
                subprocess.run(cmd, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error processing {dir_path}: {e}")
        else:
            print(f"Skipping {dir_path}, test.c not found.")

if __name__ == "__main__":
    main()
