import os
from pathlib import Path

c2_root = Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv")
print("=== carcrash2 top-level contents ===")
for p in c2_root.iterdir():
    print(f"  {p.name}: is_dir={p.is_dir()}")
    if p.is_dir():
        subdirs = [s.name for s in p.iterdir() if s.is_dir()]
        subfiles = [s.name for s in p.iterdir() if s.is_file()]
        print(f"    subdirs: {subdirs[:5]}, files: {len(subfiles)}")

for sub in ["Accident", "NonAccident", "SeverityScore"]:
    folder = c2_root / sub
    if folder.exists():
        for child in folder.iterdir():
            if child.is_dir():
                fcount = len(list(child.glob("*")))
                print(f"  {sub}/{child.name}: {fcount} items")
