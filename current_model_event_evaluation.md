# Current Model Event-Level Evaluation Report

## 1. Current Model Identification
- **Model File**: `backend/models/crash_classifier.pt`
- **Architecture**: Ultralytics YOLOv8n-cls (Nano classification backbone)
- **Input Resolution**: 224 × 224 × 3
- **Parameters**: 1,444,802 parameters (~2.96 MB on disk)
- **Class Index Mapping**:
  - Class `0`: `accident`
  - Class `1`: `non_accident`
- **Inference Verification**: Verified consistent with `backend/train_crash_classifier.py` and `classify_crash_frame()` in `backend/main.py`. No label inversion exists.
- **Hardware Profile**: Tested on Intel Core i5-12450H CPU, 8 GB RAM.
- **Mean Inference Latency**: **35.49 ms per frame** (~28.2 FPS on CPU), highly suitable for real-time edge processing.

---

## 2. Comparison: Contaminated Current Split vs Leakage-Free Event Split

### Current Split Evaluation (Contaminated by Frame Leakage)
*Note: Due to frame-level random shuffling during upstream dataset preparation, 439 of 583 video events (75.3%) leaked across splits, and **99.18% (1,925 / 1,941)** of the test partition contains frames identical or adjacent to training frames.*

- **Reported Frame Accuracy**: 96.14%
- **Reported Precision**: 98.6%
- **Reported Recall**: 93.6%
- **Caveat**: **Heavily contaminated**. Near-duplicate consecutive frames (differing only by sensor noise) allowed the model to memorize video scenes rather than truly generalizing.

### Leakage-Free Event-Level Evaluation (Scientific Baseline)
*Evaluated on **1,754 test images** across **90 strictly unseen physical events** (47 crash events, 43 non-crash events) with 0% event overlap.*

#### Frame-Level Performance on Unseen Events:
| Metric | Value | Interpretation |
| :--- | :---: | :--- |
| **Accuracy** | **96.29%** | Resilient generalization across unseen clips |
| **Crash Precision** | **98.16%** | Low false alarm rate on typical negative frames |
| **Crash Recall** | **95.95%** | High capture rate on crash frames |
| **F1-Score** | **97.04%** | Harmonic balance between precision and recall |
| **Specificity** | **96.89%** | Correctly rejects normal traffic frames |
| **True Positives (TP)** | 1,066 | Frames with collision features detected |
| **False Positives (FP)** | 20 | Normal frames misclassified as crashes |
| **True Negatives (TN)** | 623 | Normal frames correctly classified |
| **False Negatives (FN)** | 45 | Crash frames missed (mostly pre-impact/distant) |
| **Brier Score** | **0.0284** | High probabilistic accuracy |
| **ECE (Expected Calibration Error)** | **0.0159** | Model confidence aligns tightly with empirical accuracy |

#### Threshold Sensitivity Analysis (Unseen Test Partition):
| Threshold | Precision | Recall | F1-Score | TP | FP | TN | FN |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.50** | 98.16% | 95.95% | **97.04%** | 1,066 | 20 | 623 | 45 |
| **0.60** | 98.61% | 95.50% | 97.03% | 1,061 | 15 | 628 | 50 |
| **0.70** | 98.60% | 94.78% | 96.65% | 1,053 | 15 | 628 | 58 |
| **0.80** | 98.63% | 90.91% | 94.61% | 1,010 | 14 | 629 | 101 |
| **0.90** | 99.07% | 86.14% | 92.15% | 957 | 9 | 634 | 154 |

---

## 3. Event-Level Evaluation Metrics (Real CCTV Behavior)
In real CCTV operation, an event is classified over a continuous video sequence rather than an isolated frame. An event is flagged as a crash if the classifier predicts `accident` (confidence > 0.50) in sustained observations.

- **Total Independent Test Events**: 90
- **True Crash Events**: 47
- **True Non-Crash Events**: 43
- **Event True Positives (TP)**: **46**
- **Event False Positives (FP)**: **5**
- **Event True Negatives (TN)**: **38**
- **Event False Negatives (FN)**: **1**
- **Event-Level Crash Recall**: **97.87% (46 / 47 events)**
- **Event-Level Crash Precision**: **90.20% (46 / 51 events)**
- **Event-Level Specificity**: **88.37% (38 / 43 events)**

### Single Missed Crash Event (`c1_test15_accident`):
- Consisted of 15 frames of an extremely distant CCTV camera overlooking a multi-lane highway. The collision occurred at the far horizon (occupying less than 3% of the image frame). The maximum classifier score reached 0.4822 (just below 0.50 threshold).

---

## 4. Evaluation of the Known Crash Scene (Demonstration Case)
We evaluated the deployed classifier on the specific crash scene assets referenced in the system test:
- `public/samples/vehicle-03.jpg`: **0.9577 (95.8% crash probability)**
- `public/samples/accident-01.jpg`: **0.8834 (88.3% crash probability)**
- `backend/uploads/b6baa78521744ca1b6aabb53bc383a60_crash.png`: **0.8913 (89.1% crash probability)**

### Root Cause Analysis of Recent False Negative:
The classifier **DID NOT FAIL** on this scene. It provided overwhelmingly strong evidence of a collision (0.958 probability). 
The false negative experienced by the user in the end-to-end demo was caused entirely by downstream decision pipeline constraints:
1. **Motion / Trajectory Verification Gate**: Downstream ByteTrack lost track continuity across high-speed impact frames, causing the temporal verifier to reject the event.
2. **Consecutive Frame Confirmation**: The system required 3 contiguous qualifying frames with sustained bounding box overlap; camera frame drops caused the event to fall below the persistence threshold.
3. **Conclusion**: Modifying or retraining the classifier will not fix this failure mode. Classifier confidence is already near 96%. Tuning of downstream temporal thresholds and tracking parameters is the appropriate remedy.
