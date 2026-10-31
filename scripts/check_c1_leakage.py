import os
from pathlib import Path
from collections import defaultdict

c1_root = Path(r"C:\Users\Lenovo\Downloads\carcrash1cctv\data")
if c1_root.exists():
    video_to_splits = defaultdict(set)
    for split in ["train", "val", "test"]:
        for cls in ["Accident", "Non Accident"]:
            folder = c1_root / split / cls
            if folder.exists():
                for f in folder.glob("*.jpg"):
                    stem = f.stem
                    # e.g. test10_33 -> test10
                    prefix = stem.split("_")[0] if "_" in stem else stem
                    video_to_splits[prefix].add(split)
    
    leaks = {k: v for k, v in video_to_splits.items() if len(v) > 1}
    print(f"carcrash1 total prefixes: {len(video_to_splits)}")
    print(f"carcrash1 leaking prefixes across its own train/val/test: {len(leaks)}")
    for k, v in list(leaks.items())[:10]:
        print(f"  {k}: {v}")
