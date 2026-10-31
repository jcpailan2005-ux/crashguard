import os
import sys
from pathlib import Path

print("=== 1. Checking dataset/ subdirectories ===", flush=True)
dataset_p = Path("dataset")
if dataset_p.exists():
    for p in dataset_p.iterdir():
        if p.is_dir():
            count = 0
            img_count = 0
            for root, dirs, files in os.walk(p):
                count += len(files)
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                        img_count += 1
            print(f"  dataset/{p.name}: {count} total files, {img_count} images", flush=True)
else:
    print("  dataset/ directory does not exist", flush=True)

print("\n=== 2. Checking Downloads sources ===", flush=True)
for d in [r"C:\Users\Lenovo\Downloads\carcrash1cctv", r"C:\Users\Lenovo\Downloads\carcrash2cctv"]:
    path = Path(d)
    print(f"  {d}: exists={path.exists()}", flush=True)
    if path.exists():
        count = 0
        img_count = 0
        for root, dirs, files in os.walk(path):
            count += len(files)
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                    img_count += 1
        print(f"    {count} files, {img_count} images", flush=True)

print("\n=== 3. Checking backend/datasets/crash_classification ===", flush=True)
cc_path = Path("backend/datasets/crash_classification")
if cc_path.exists():
    for split in ["train", "val", "test"]:
        sp = cc_path / split
        if sp.exists():
            for cls in ["accident", "non_accident"]:
                cp = sp / cls
                if cp.exists():
                    imgs = [f for f in os.listdir(cp) if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]
                    print(f"    {split}/{cls}: {len(imgs)} files", flush=True)

print("\n=== 4. Checking other image/video folders ===", flush=True)
for folder_name in ["public/samples", "uploads", "backend/uploads", "backend/outputs"]:
    f_path = Path(folder_name)
    if f_path.exists():
        count = 0
        imgs = 0
        vids = 0
        for root, dirs, files in os.walk(f_path):
            count += len(files)
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                    imgs += 1
                elif ext in [".mp4", ".avi", ".mkv", ".mov"]:
                    vids += 1
        print(f"  {folder_name}: {count} files ({imgs} images, {vids} videos)", flush=True)

print("\n=== 5. Checking Models with Ultralytics ===", flush=True)
from ultralytics import YOLO
for m in ["backend/best.pt", "backend/models/crash_classifier.pt", "yolov8n.pt", "yolov8n-cls.pt"]:
    p = Path(m)
    if p.exists():
        model = YOLO(str(p))
        task = getattr(model, "task", None)
        names = getattr(model, "names", None)
        print(f"  {m}:", flush=True)
        print(f"    task: {task}", flush=True)
        print(f"    names: {names}", flush=True)
        print(f"    size_bytes: {p.stat().st_size}", flush=True)

print("\nDone discovery!", flush=True)
