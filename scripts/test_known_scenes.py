import os
from pathlib import Path
from ultralytics import YOLO

os.environ["YOLO_OFFLINE"] = "1"
os.environ["ULTRALYTICS_AUTOINSTALL"] = "0"

model_path = Path("backend/models/crash_classifier.pt")
print(f"Loading model: {model_path}")
model = YOLO(str(model_path))

print("\n=== Testing public/samples ===")
for p in sorted(Path("public/samples").glob("*")):
    if p.suffix.lower() in [".jpg", ".png", ".webp"]:
        res = model.predict(str(p), imgsz=224, verbose=False)
        probs = res[0].probs
        p_vals = probs.data.detach().cpu().tolist()
        print(f"  {p.name}: accident={p_vals[0]:.4f}, non_accident={p_vals[1]:.4f}, top1={model.names[int(probs.top1)]}")

print("\n=== Testing crash images in uploads / backend/uploads ===")
for folder in ["backend/uploads", "uploads"]:
    count = 0
    for p in Path(folder).glob("*crash*.*"):
        if p.suffix.lower() in [".jpg", ".png", ".webp"]:
            res = model.predict(str(p), imgsz=224, verbose=False)
            probs = res[0].probs
            p_vals = probs.data.detach().cpu().tolist()
            print(f"  {folder}/{p.name}: accident={p_vals[0]:.4f}, non_accident={p_vals[1]:.4f}, top1={model.names[int(probs.top1)]}")
            count += 1
            if count >= 10:
                break
