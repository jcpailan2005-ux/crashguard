from datasets import load_dataset
from pathlib import Path

ds = load_dataset("justjuu/traffic-accident-cctv-object-detection")

out = Path("car_crash_yolo")
for split in ["train", "validation", "test"]:
    (out / "images" / split).mkdir(parents=True, exist_ok=True)
    (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    for i, row in enumerate(ds[split]):
        img = row["image"]
        width, height = img.size

        img_path = out / "images" / split / f"{i:06d}.jpg"
        label_path = out / "labels" / split / f"{i:06d}.txt"

        img.convert("RGB").save(img_path)

        lines = []
        bboxes = row["objects"]["bbox"]
        classes = row["objects"]["category"]

        for bbox, cls_id in zip(bboxes, classes):
            x, y, w, h = bbox
            x_center = (x + w / 2) / width
            y_center = (y + h / 2) / height
            w_norm = w / width
            h_norm = h / height
            lines.append(f"{cls_id} {x_center} {y_center} {w_norm} {h_norm}")

        label_path.write_text("\n".join(lines), encoding="utf-8")

print("Dataset converted to YOLO format.")