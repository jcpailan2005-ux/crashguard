import os
from pathlib import Path

for name, root in [("carcrash1", Path(r"C:\Users\Lenovo\Downloads\carcrash1cctv")), ("carcrash2", Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv"))]:
    print(f"=== {name} sample filenames ===")
    if root.exists():
        samples = []
        for r, d, files in os.walk(root):
            for f in files:
                if f.endswith((".jpg", ".png")):
                    samples.append(os.path.join(r, f))
                    if len(samples) >= 15:
                        break
            if len(samples) >= 15:
                break
        for s in samples:
            print(" ", s)
