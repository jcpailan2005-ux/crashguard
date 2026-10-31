import cv2
from pathlib import Path

acc_dir = Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv\Accident\Accident")
for i in range(1, 15):
    p = acc_dir / f"{i}.jpg"
    if p.exists():
        im = cv2.imread(str(p))
        if im is not None:
            print(f"Frame {i}: shape={im.shape}, mean_rgb={[round(c, 1) for c in cv2.mean(im)[:3]]}")
