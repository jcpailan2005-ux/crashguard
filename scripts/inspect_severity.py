import os
from pathlib import Path

p = Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv\SeverityScore\Severity Score Dataset with Labels")
print(f"=== Items in {p} ===")
if p.exists():
    for item in p.iterdir():
        print(f"  {item.name}: is_dir={item.is_dir()}, size={item.stat().st_size if item.is_file() else 'dir'}")
