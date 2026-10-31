import os
import sys
import time
import json
import csv
from pathlib import Path
from collections import defaultdict, Counter

import cv2
import numpy as np
import torch
from ultralytics import YOLO

os.environ["YOLO_OFFLINE"] = "1"
os.environ["ULTRALYTICS_AUTOINSTALL"] = "0"

WORKSPACE_ROOT = Path(r"C:\Users\Lenovo\Desktop\MyCrushguard")
DATASET_ROOT = WORKSPACE_ROOT / "backend" / "datasets" / "crash_classification"
MODEL_PATH = WORKSPACE_ROOT / "backend" / "models" / "crash_classifier.pt"

print("=== Starting Full Event-Level Audit & Evaluation ===", flush=True)

# 1. Collect all images in crash_classification
all_samples = []
for split in ["train", "val", "test"]:
    for cls in ["accident", "non_accident"]:
        folder = DATASET_ROOT / split / cls
        if folder.exists():
            for p in sorted(folder.glob("*")):
                if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                    all_samples.append({
                        "path": p,
                        "filename": p.name,
                        "current_split": split,
                        "class": cls,
                        "label": 1 if cls == "accident" else 0
                    })

print(f"Loaded {len(all_samples)} total images from {DATASET_ROOT}", flush=True)

# 2. Perceptual hashing & Event Identification
def dhash(image, hash_size=8):
    resized = cv2.resize(image, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    if len(resized.shape) == 3:
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    diff = resized[:, 1:] > resized[:, :-1]
    return sum([bool(val) << i for i, val in enumerate(diff.flatten())])

def hamming_dist(h1, h2):
    return bin(h1 ^ h2).count('1')

print("Extracting event IDs and perceptual hashes...", flush=True)

# For carcrash1: use the known video prefix (e.g. test10, test1, etc.)
# For carcrash2: cluster by background/camera dhash
c2_acc_clusters = [] # [(rep_hash, event_id, [indices])]
c2_non_acc_clusters = []

for idx, s in enumerate(all_samples):
    fn = s["filename"]
    if fn.startswith("carcrash1cctv_"):
        parts = fn[len("carcrash1cctv_"):].split("_")
        s["event_id"] = f"c1_{parts[0]}_{s['class']}"
        s["source"] = "carcrash1cctv"
    elif fn.startswith("carcrash2cctv_"):
        s["source"] = "carcrash2cctv"
        # We will cluster carcrash2 by dhash
    else:
        s["event_id"] = f"misc_{fn.split('_')[0]}"
        s["source"] = "misc"

# Now compute hashes for carcrash2 to build real event clusters
c2_samples = [s for s in all_samples if s["source"] == "carcrash2cctv"]
print(f"Clustering {len(c2_samples)} carcrash2 samples into events...", flush=True)

c2_event_clusters = {
    "accident": [],
    "non_accident": []
}

for idx, s in enumerate(c2_samples):
    if idx % 2000 == 0:
        print(f"  Processed {idx}/{len(c2_samples)} carcrash2 images...", flush=True)
    im = cv2.imread(str(s["path"]))
    if im is None:
        h = 0
    else:
        h = dhash(im)
    s["dhash"] = h
    
    cls = s["class"]
    clusters = c2_event_clusters[cls]
    matched = False
    for c_id, c_rep_hash, member_list in clusters:
        if hamming_dist(c_rep_hash, h) <= 6:
            s["event_id"] = c_id
            member_list.append(s)
            matched = True
            break
    if not matched:
        new_c_id = f"c2_{cls}_ev_{len(clusters)+1:04d}"
        s["event_id"] = new_c_id
        clusters.append((new_c_id, h, [s]))

print(f"Event identification complete!", flush=True)

# 3. Analyze Leakage across Current Splits
event_to_splits = defaultdict(set)
event_to_samples = defaultdict(list)
event_to_class = {}

for s in all_samples:
    eid = s["event_id"]
    event_to_splits[eid].add(s["current_split"])
    event_to_samples[eid].append(s)
    event_to_class[eid] = s["class"]

total_events = len(event_to_splits)
leaking_events = {e: s for e, s in event_to_splits.items() if len(s) > 1}
train_val_leak = {e: s for e, s in event_to_splits.items() if 'train' in s and 'val' in s}
train_test_leak = {e: s for e, s in event_to_splits.items() if 'train' in s and 'test' in s}
val_test_leak = {e: s for e, s in event_to_splits.items() if 'val' in s and 'test' in s}

test_samples = [s for s in all_samples if s["current_split"] == "test"]
test_leaking = [s for s in test_samples if 'train' in event_to_splits[s["event_id"]]]

print(f"\n--- Leakage Audit Summary ---", flush=True)
print(f"Total Events: {total_events}", flush=True)
print(f"Leaking Events: {len(leaking_events)} / {total_events} ({len(leaking_events)/total_events*100:.1f}%)", flush=True)
print(f"  Train <-> Val leak: {len(train_val_leak)} events", flush=True)
print(f"  Train <-> Test leak: {len(train_test_leak)} events", flush=True)
print(f"  Val <-> Test leak: {len(val_test_leak)} events", flush=True)
print(f"Test samples contaminated by Train: {len(test_leaking)} / {len(test_samples)} ({len(test_leaking)/len(test_samples)*100:.1f}%)", flush=True)

# 4. Construct Proposed Event-Level Split Manifest
# Deterministic event split: 70% train, 15% val, 15% test by EVENT ID
import random
rng = random.Random(20260906)

events_by_class = defaultdict(list)
for eid, cls in event_to_class.items():
    events_by_class[cls].append(eid)

event_split_assignment = {}
for cls, e_list in events_by_class.items():
    rng.shuffle(e_list)
    n = len(e_list)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    for i, eid in enumerate(e_list):
        if i < n_train:
            event_split_assignment[eid] = "train"
        elif i < n_train + n_val:
            event_split_assignment[eid] = "val"
        else:
            event_split_assignment[eid] = "test"

# Assign proposed split to all samples
for s in all_samples:
    s["proposed_split"] = event_split_assignment[s["event_id"]]

# 5. Evaluate Current Model on the Proposed Leakage-Free Test Split
print("\nLoading current classifier for evaluation...", flush=True)
model = YOLO(str(MODEL_PATH))

def run_inference(sample_list, desc="eval"):
    y_true = []
    y_scores = []
    y_preds = []
    start_t = time.time()
    
    for idx, s in enumerate(sample_list):
        if idx % 500 == 0:
            print(f"  [{desc}] Progress: {idx}/{len(sample_list)}...", flush=True)
        im = cv2.imread(str(s["path"]))
        if im is None:
            continue
        res = model.predict(im, imgsz=224, verbose=False)
        probs = res[0].probs
        if probs is None:
            score = 0.0
        else:
            score = float(probs.data.detach().cpu().tolist()[0])
        s["accident_score"] = score
        y_true.append(s["label"])
        y_scores.append(score)
        y_preds.append(1 if score >= 0.50 else 0)
        
    duration = time.time() - start_t
    y_true = np.array(y_true)
    y_scores = np.array(y_scores)
    y_preds = np.array(y_preds)
    
    tp = int(np.sum((y_true == 1) & (y_preds == 1)))
    fp = int(np.sum((y_true == 0) & (y_preds == 1)))
    tn = int(np.sum((y_true == 0) & (y_preds == 0)))
    fn = int(np.sum((y_true == 1) & (y_preds == 0)))
    
    acc = (tp + tn) / len(y_true) if len(y_true) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    brier = float(np.mean((y_scores - y_true) ** 2))
    
    # ECE
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    for i in range(len(bins) - 1):
        mask = (y_scores >= bins[i]) & (y_scores < bins[i+1])
        if np.sum(mask) > 0:
            b_acc = np.mean(y_true[mask])
            b_conf = np.mean(y_scores[mask])
            ece += np.sum(mask) / len(y_true) * abs(b_acc - b_conf)
            
    # Threshold sweep
    th_res = {}
    for th in [0.50, 0.60, 0.70, 0.80, 0.90]:
        yp = (y_scores >= th).astype(int)
        c_tp = int(np.sum((y_true == 1) & (yp == 1)))
        c_fp = int(np.sum((y_true == 0) & (yp == 1)))
        c_tn = int(np.sum((y_true == 0) & (yp == 0)))
        c_fn = int(np.sum((y_true == 1) & (yp == 0)))
        p = c_tp / (c_tp + c_fp) if (c_tp + c_fp) else 0.0
        r = c_tp / (c_tp + c_fn) if (c_tp + c_fn) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        th_res[str(th)] = {
            "precision": float(p), "recall": float(r), "f1": float(f),
            "tp": c_tp, "fp": c_fp, "tn": c_tn, "fn": c_fn
        }
        
    return {
        "count": len(y_true),
        "duration_s": duration,
        "latency_ms": duration / len(y_true) * 1000 if len(y_true) else 0.0,
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "specificity": float(spec),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "brier": float(brier),
        "ece": float(ece),
        "thresholds": th_res
    }

# Run on Proposed Leakage-Free Test Split
clean_test_samples = [s for s in all_samples if s["proposed_split"] == "test"]
print(f"\nEvaluating on LEAKAGE-FREE TEST SET ({len(clean_test_samples)} images across {sum(1 for e, sp in event_split_assignment.items() if sp == 'test')} events)...", flush=True)
clean_test_metrics = run_inference(clean_test_samples, desc="Leakage-Free Test")

print("\n--- Leakage-Free Test Set Metrics ---", flush=True)
print(f"Accuracy: {clean_test_metrics['accuracy']*100:.2f}%", flush=True)
print(f"Precision: {clean_test_metrics['precision']*100:.2f}%", flush=True)
print(f"Recall: {clean_test_metrics['recall']*100:.2f}%", flush=True)
print(f"F1: {clean_test_metrics['f1']*100:.2f}%", flush=True)
print(f"Specificity: {clean_test_metrics['specificity']*100:.2f}%", flush=True)
print(f"TP: {clean_test_metrics['tp']}, FP: {clean_test_metrics['fp']}, TN: {clean_test_metrics['tn']}, FN: {clean_test_metrics['fn']}", flush=True)
print(f"Brier score: {clean_test_metrics['brier']:.4f}, ECE: {clean_test_metrics['ece']:.4f}", flush=True)
print(f"Latency: {clean_test_metrics['latency_ms']:.2f} ms/frame", flush=True)

# 6. Event-Level Evaluation Metrics
# For each event in clean test:
# True crash event: detected if max(accident_score) >= threshold (or at least 2 frames >= threshold)
test_events = defaultdict(list)
for s in clean_test_samples:
    test_events[s["event_id"]].append(s)

print(f"\nComputing Event-Level Metrics on {len(test_events)} test events...", flush=True)
ev_true = []
ev_detected = []
ev_scores = []
ev_details = []

for eid, s_list in test_events.items():
    is_crash = 1 if s_list[0]["class"] == "accident" else 0
    scores = [s.get("accident_score", 0.0) for s in s_list]
    max_score = max(scores) if scores else 0.0
    mean_score = sum(scores) / len(scores) if scores else 0.0
    # An event is flagged crash if max_score >= 0.50
    flagged = 1 if max_score >= 0.50 else 0
    ev_true.append(is_crash)
    ev_detected.append(flagged)
    ev_scores.append(max_score)
    ev_details.append({
        "event_id": eid,
        "class": s_list[0]["class"],
        "frame_count": len(s_list),
        "max_score": float(max_score),
        "mean_score": float(mean_score),
        "flagged": bool(flagged)
    })

ev_true = np.array(ev_true)
ev_detected = np.array(ev_detected)
ev_tp = int(np.sum((ev_true == 1) & (ev_detected == 1)))
ev_fp = int(np.sum((ev_true == 0) & (ev_detected == 1)))
ev_tn = int(np.sum((ev_true == 0) & (ev_detected == 0)))
ev_fn = int(np.sum((ev_true == 1) & (ev_detected == 0)))

ev_rec = ev_tp / (ev_tp + ev_fn) if (ev_tp + ev_fn) else 0.0
ev_prec = ev_tp / (ev_tp + ev_fp) if (ev_tp + ev_fp) else 0.0
ev_f1 = 2 * ev_prec * ev_rec / (ev_prec + ev_rec) if (ev_prec + ev_rec) else 0.0
ev_spec = ev_tn / (ev_tn + ev_fp) if (ev_tn + ev_fp) else 0.0

print(f"Event-Level Crash Recall: {ev_rec*100:.2f}% ({ev_tp}/{ev_tp+ev_fn} events)", flush=True)
print(f"Event-Level Crash Precision: {ev_prec*100:.2f}% ({ev_tp}/{ev_tp+ev_fp} events)", flush=True)
print(f"Event-Level Specificity: {ev_spec*100:.2f}% ({ev_tn}/{ev_tn+ev_fp} events)", flush=True)
print(f"Event-Level CM: TP={ev_tp}, FP={ev_fp}, TN={ev_tn}, FN={ev_fn}", flush=True)

# 7. False Negatives and False Positives Categorization
fn_samples = [s for s in clean_test_samples if s["label"] == 1 and s.get("accident_score", 0.0) < 0.50]
fp_samples = [s for s in clean_test_samples if s["label"] == 0 and s.get("accident_score", 0.0) >= 0.50]

print(f"\nFalse Negatives in Clean Test: {len(fn_samples)} frames", flush=True)
print(f"False Positives in Clean Test: {len(fp_samples)} frames", flush=True)

# 8. Save artifacts and reports
OUTPUT_DATA = {
    "audit_timestamp": "2026-09-06T21:00:00Z",
    "total_images": len(all_samples),
    "total_events": total_events,
    "leaking_events": len(leaking_events),
    "test_leaking_samples": len(test_leaking),
    "test_total_samples": len(test_samples),
    "leakage_percentage": len(test_leaking) / len(test_samples) * 100.0,
    "clean_test_metrics": clean_test_metrics,
    "event_level_metrics": {
        "total_test_events": len(test_events),
        "tp": ev_tp, "fp": ev_fp, "tn": ev_tn, "fn": ev_fn,
        "recall": float(ev_rec),
        "precision": float(ev_prec),
        "f1": float(ev_f1),
        "specificity": float(ev_spec)
    },
    "event_details": ev_details,
    "sample_fn": [{
        "filename": s["filename"],
        "event_id": s["event_id"],
        "score": s.get("accident_score", 0.0)
    } for s in fn_samples[:30]],
    "sample_fp": [{
        "filename": s["filename"],
        "event_id": s["event_id"],
        "score": s.get("accident_score", 0.0)
    } for s in fp_samples[:30]]
}

with open(WORKSPACE_ROOT / "scratch_clean_event_audit.json", "w") as f:
    json.dump(OUTPUT_DATA, f, indent=2)

# Save Proposed Manifest
manifest_path = WORKSPACE_ROOT / "dataset_v2_manifest.csv"
with open(manifest_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["filename", "current_split", "proposed_split", "class", "event_id", "source", "accident_score"])
    for s in all_samples:
        writer.writerow([
            s["filename"],
            s["current_split"],
            s["proposed_split"],
            s["class"],
            s["event_id"],
            s["source"],
            f"{s.get('accident_score', 0.0):.4f}" if "accident_score" in s else ""
        ])

print(f"Manifest written to {manifest_path}", flush=True)
print("=== Event-Level Audit Finished Successfully! ===", flush=True)
