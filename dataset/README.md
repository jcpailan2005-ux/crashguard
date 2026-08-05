# MyCrushguard Evaluation Dataset

Frames in this folder are replayed through the **exact production crash
decision pipeline** (vehicle gate, person-only rejection, ROI, crash score
threshold, motion gate, 3-frame temporal confirmation, active-case blocking,
cooldown) by `backend/scripts/replay_crash_decision.py`. Nothing here creates
crash cases or notifications.

Image and video files inside `dataset/` are git-ignored on purpose — only the
folder structure, `.gitkeep` markers, and this README are tracked. Keep the
actual frames local (or in shared storage), never in the repo.

**This is an evaluation set. Frames placed here must never be used for
training.** See "Avoiding leakage" below.

## 1. Folder guide

Every folder that directly contains images is replayed as one continuous
camera sequence (sorted filename order, one simulated second per frame). The
top-level folder name is the category in reports.

| Folder | What belongs here | Minimum suggested |
|---|---|---|
| `person_only/` | Pedestrians, people near/approaching the camera, crowds — **no vehicle anywhere in frame**. Include close-up and far subjects. | 200 frames from ≥10 distinct scenes |
| `no_vehicle/` | Frames with neither vehicles nor people: yards, walls, gates, animals, vegetation moving in wind. | 200 frames from ≥10 distinct scenes |
| `normal_cctv/` | Ordinary outdoor CCTV activity that isn't road traffic: storefronts, driveways, pedestrians + parked scooters, etc. | 200 frames from ≥10 distinct scenes |
| `indoor_or_porch_cctv/` | Indoor rooms, porches, entryways — the classic misfire scenario for the classifier. | 200 frames from ≥10 distinct scenes |
| `empty_road/` | Roads with no vehicles: day, dusk, night, wet asphalt reflections. | 150 frames from ≥8 distinct roads |
| `normal_traffic/` | Vehicles flowing normally: multiple lanes, queues at lights, motorcycles weaving. This stresses the motion gate. | 300 frames from ≥15 distinct clips |
| `parked_vehicle/` | Stationary vehicles, including tightly parked side-by-side ("mag tabi") rows and vehicles parked near walls. | 200 frames from ≥10 distinct scenes |
| `night_glare_rain_noise/` | Headlight glare, heavy rain, IR night mode, sensor noise, lens droplets — with and without vehicles. | 200 frames from ≥10 distinct clips |
| `confirmed_crash/` | Real CCTV crash footage. **One subfolder per incident** (`incident_01/`, `incident_02/`, …) so each incident gets its own temporal/cooldown/active-case state. Include motorcycle, car-to-car, multi-vehicle, vehicle-vs-fixed-object, and post-impact scenes. | ≥20 incidents, 5–15 frames each (from ~1s before impact to a few seconds after) |

Expected replay outcome: every hard-negative category confirms **zero**
crashes; every `confirmed_crash/incident_*` sequence ideally confirms once.
Note the known recall limitation: single-vehicle crashes (vehicle vs. post,
rollover) currently cannot pass the two-vehicle motion gate — keep them in the
dataset anyway so the gap stays measurable (see
`backend/docs/FABLE_DECISION_AUDIT.md`).

## 2. Extracting frames from CCTV videos

Sample at ~3 fps (matches the backend's `VIDEO_ANALYSIS_FPS` and approximates
the live monitor cadence). Zero-padded names keep sorted order = time order,
which the 3-frame temporal gate depends on.

With ffmpeg:

```bash
ffmpeg -i crash_clip.mp4 -vf fps=3 dataset/confirmed_crash/incident_01/frame_%04d.jpg
```

Or with OpenCV (no ffmpeg needed):

```python
import cv2
from pathlib import Path

out = Path("dataset/confirmed_crash/incident_01"); out.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture("crash_clip.mp4")
fps = cap.get(cv2.CAP_PROP_FPS) or 30
step = max(1, round(fps / 3))          # ~3 analyzed frames per second
index = saved = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    if index % step == 0:
        cv2.imwrite(str(out / f"frame_{saved:04d}.jpg"), frame)
        saved += 1
    index += 1
cap.release()
```

## 3. Avoiding duplicate / leaked frames

- **Split by source clip and camera, never by frame.** All frames from one
  clip (or one incident) belong to exactly one of: classifier training set
  (`backend/datasets/crash_classification/`), classifier validation set, or
  this evaluation set. If any frame of a clip was used for training, none of
  its frames may appear here.
- Prefer different cameras/locations between training and evaluation, not just
  different clips — the classifier memorizes backgrounds easily.
- Drop near-duplicate frames within a folder (long static periods add rows
  without adding information). A quick dedupe check by content hash:

  ```bash
  python -c "import hashlib,pathlib,collections; h=collections.defaultdict(list); [h[hashlib.md5(p.read_bytes()).hexdigest()].append(p) for p in pathlib.Path('dataset').rglob('*.jpg')]; [print(v) for v in h.values() if len(v)>1]"
  ```

## 4. Baseline replay

From the project root, with the **current** classifier
(`backend/models/crash_classifier.pt`):

```bash
python backend/scripts/replay_crash_decision.py dataset --output baseline_report.csv --strict
```

- `--strict` exits 1 if any hard-negative category produces `confirmed_crash`.
- Keep `baseline_report.csv` (git-ignored) as the pre-retraining reference.

## 5. Retrained replay

1. Retrain the classifier with the expanded hard negatives
   (`backend/train_crash_classifier.py`), keeping hard negatives at roughly
   50–60% of training data.
2. Back up the old weights, then replace `backend/models/crash_classifier.pt`
   with the retrained weights.
3. Re-run the replay on the *same* dataset:

```bash
python backend/scripts/replay_crash_decision.py dataset --output retrained_report.csv --strict
```

## 6. Comparing baseline vs retrained

```bash
python backend/scripts/compare_replay_reports.py baseline_report.csv retrained_report.csv --strict
```

Reports, per category: hard-negative false-positive counts, confirmed-crash
recall (incidents confirmed / total incidents), average crashScore, and an
improvement/regression verdict. With `--strict` the exit code is 1 when any
hard-negative category gained false positives or confirmed-crash recall
dropped, so the pair of commands can act as a model-acceptance gate:

- **Goal:** hard-negative false positives go down (ideally to 0) while
  `confirmed_crash` recall does not decrease.
- If average crashScore on hard negatives drops well below the 0.90 case
  threshold, the classifier itself improved (not just the gating).
