import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict

def dhash(image, hash_size=8):
    resized = cv2.resize(image, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    if len(resized.shape) == 3:
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    diff = resized[:, 1:] > resized[:, :-1]
    return sum([bool(val) << i for i, val in enumerate(diff.flatten())])

def hamming_dist(h1, h2):
    return bin(h1 ^ h2).count('1')

acc_dir = Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv\Accident\Accident")
hashes = []
for i in range(1, 1001):
    p = acc_dir / f"{i}.jpg"
    if p.exists():
        im = cv2.imread(str(p))
        if im is not None:
            hashes.append((i, dhash(im)))

print(f"Computed dHash for {len(hashes)} images.")
# Group by hash similarity (hamming distance <= 4)
clusters = []
for idx, h in hashes:
    matched = False
    for cluster in clusters:
        # compare to cluster representative
        if hamming_dist(cluster[0][1], h) <= 6:
            cluster.append((idx, h))
            matched = True
            break
    if not matched:
        clusters.append([(idx, h)])

print(f"Total clusters (independent scenes) in first 1000 images: {len(clusters)}")
cluster_sizes = sorted([len(c) for c in clusters], reverse=True)
print(f"Top 10 cluster sizes: {cluster_sizes[:10]}")
print(f"Clusters with >1 image: {sum(1 for c in clusters if len(c) > 1)}")
