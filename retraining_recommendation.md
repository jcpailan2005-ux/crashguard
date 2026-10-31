# Retraining Decision & Roadmap

## 1. Final Retraining Decision
**Selected Decision**: **`RETRAINING RECOMMENDED`**

*(Neither "NO RETRAINING NEEDED YET" nor "RETRAINING REQUIRED")*

---

## 2. Scientific Justification

### Why NOT "NO RETRAINING NEEDED YET":
1. **Severe Dataset Contamination (99.18% Test Leakage)**:
   - Random frame-level shuffling allowed adjacent frames from the same 10–30 FPS video clips to pollute Train, Validation, and Test sets. Over 75.3% of video events span multiple splits. The previously reported test accuracy (96.14%) is scientifically invalid as a measure of generalization.
2. **Hard Negative Deficiencies (False Positive Risk)**:
   - In our clean event evaluation, the model produced false alarms on 5 out of 43 negative events (11.6% event false alarm rate). Scenarios like bumper-to-bumper congestion, diagonal curbside parking, and large vehicle perspective overlaps scored as high as 0.85–0.96 crash probability.
3. **Severe Underrepresentation of Post-Impact Aftermath**:
   - Over 86% of crash images represent the immediate, dynamic moment of collision (smoke, flying debris, rapid tilt). Upright, stationary post-impact damaged vehicles are rare (<14%), leaving the system vulnerable when CCTV streams monitor the road seconds or minutes after impact.
4. **CCTV Domain Shift**:
   - 92.8% of images are 320×240 heavily compressed web video clips. Physical CrashGuard deployment uses wide-angle 720p/1080p RTSP IP cameras with distinct distortion and lighting profiles.

### Why NOT "RETRAINING REQUIRED":
1. **Current Classifier Is Competent on Unseen Events**:
   - Evaluated against a strictly leakage-free test partition of 90 independent events (1,754 images), the current model achieved **97.87% Event-Level Crash Recall** (46 of 47 crash scenes detected) and **96.29% frame accuracy**. The model is not broken.
2. **Known Crash Scene Failure Was NOT a Classifier Error**:
   - The recent false negative in the demo video scored **0.9577 (95.8% crash probability)** under the current classifier. The event was dropped downstream by the temporal verifier and motion persistence gates, NOT the visual classifier. Immediate retraining would not resolve this failure.
3. **No Retraining on Contaminated Data**:
   - Retraining immediately without curating the dataset and fixing splits would merely produce another contaminated model with the same failure modes.

---

## 3. Mandatory Dataset Fixes Required Before Retraining
Before initiating any retraining run, the following five prerequisites must be completed:

```
[Prerequisite 1: Event-Level Splitting]
       │  Adopt dataset_v2_manifest.csv ensuring 100% video event isolation.
       ▼
[Prerequisite 2: Frame Deduplication]
       │  Subsample consecutive video bursts (pHash <= 4) to 1-2 keyframes per second.
       ▼
[Prerequisite 3: Hard Negative Enrichment]
       │  Add 30-50 diverse events of heavy traffic jams, curbside parking, and towing.
       ▼
[Prerequisite 4: Post-Impact Aftermath Augmentation]
       │  Add stationary crumpled vehicles, bumper contact, and barrier scrapes.
       ▼
[Prerequisite 5: Freeze Leakage-Free Test Set]
       │  Permanently lock test set (test_v2) for final unbiased evaluation only.
```

---

## 4. Proposed Classifier Retraining Plan

### Model Architecture & Hyperparameters
- **Base Architecture**: Ultralytics YOLOv8n-cls (Nano classification backbone)
  - *Rationale*: 2.96 MB size and 35 ms CPU inference latency on Intel Core i5-12450H provides the required 28+ FPS real-time throughput.
- **Input Resolution**: 224 × 224 × 3
- **Batch Size**: 64
- **Epochs**: 25 (with Early Stopping patience = 7 epochs on Validation Loss)
- **Optimizer**: AdamW (`lr0 = 1e-3`, `lrf = 0.01`, weight decay = `1e-4`, cosine annealing)
- **Loss Function**: Binary CrossEntropy with Label Smoothing (`0.05`)

### CCTV Domain Augmentation Strategy
To bridge the domain gap between training data and physical RTSP streams, apply realistic CCTV transformations:
- Random Motion Blur (`blur_limit = 5`)
- JPEG Compression Simulation (`quality = 40 to 80`)
- Random Brightness & Contrast (`limit = 0.2`)
- Mild Perspective Distortion (`scale = 0.05`)
- Lens Flare / Glare Simulation
- *Strict Rule*: No unrealistic geometric transformations (no vertical flips). All augmented variations of an image must strictly stay within the same event split.

---

## 5. Model Evaluation & Deployment Comparison Plan
When the candidate model is trained, it must be evaluated under a dual-track deployment protocol:

1. **Frozen Test Set Benchmark**:
   - Compare `CURRENT_MODEL` (`backend/models/crash_classifier.pt`) against `CANDIDATE_MODEL` across:
     - Event Crash Recall (Target: ≥ 98%)
     - Hard Negative False Alarm Rate (Target: < 5%)
     - Aftermath Crash Recall (Target: ≥ 95%)
     - CPU Inference Latency (Target: ≤ 40 ms)
2. **Shadow Deployment Mode**:
   - Run both models in parallel on active RTSP camera feeds. Log discrepancies to `backend/outputs/shadow_eval.jsonl` for 48 hours without changing dispatcher alarm behavior until candidate superiority is proven.
