from pathlib import Path
from calibrate_altumPT import run

root_dir = Path("/mnt/d/dancejod/dp_data/20250622")
dir_list = [dir for dir in root_dir.glob("*SET/images") if dir.is_dir()]

for dir_path in dir_list:
    run(dir_path)