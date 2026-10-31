import cv2
import numpy as np
from pathlib import Path

acc_dir = Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv\Accident\Accident")
if acc_dir.exists():
    print("Testing shot boundary detection on carcrash2 Accident frames 1..300...")
    prev_hist = None
    cuts = []
    clip_lengths = []
    current_len = 0

    for i in range(1, 301):
        p = acc_dir / f"{i}.jpg"
        if not p.exists():
            continue
        img = cv2.imread(str(p))
        if img is None:
            continue
        # HSV histogram
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        
        if prev_hist is not None:
            # Bhattacharyya distance (0 = identical, 1 = completely different)
            dist = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
            if dist > 0.45: # scene cut
                cuts.append((i, dist))
                clip_lengths.append(current_len)
                current_len = 1
            else:
                current_len += 1
        else:
            current_len = 1
        prev_hist = hist
    clip_lengths.append(current_len)

    print(f"Found {len(cuts)} scene cuts in 300 frames:")
    for cut_frame, dist in cuts[:15]:
        print(f"  Frame {cut_frame}: dist = {dist:.4f}")
    print(f"Clip lengths: {clip_lengths[:15]}")
