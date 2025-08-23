from pathlib import Path
from calibrate_altumPT import run

root_dir = Path("/mnt/d/dancejod/dp_data/20250622")
dir_list = [dir for dir in root_dir.glob("*SET/raw") if dir.is_dir()]

for dir_path in dir_list:
    print(f"Now working on folder {dir_path}")
    run(dir_path)