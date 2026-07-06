# Crash Classification Dataset Preparation Report

Output path: `C:\Users\Lenovo\Desktop\MyCrushguard\backend\datasets\crash_classification`

## Settings

- Downsampled carcrash2 non-accident: `True`
- Random seed: `20260707`
- SeverityScore folders excluded: `True`

## Copied Images

| Split | accident | non_accident |
| --- | ---: | ---: |
| train | 4690 | 4729 |
| val | 973 | 968 |
| test | 971 | 970 |

## Skipped

- Duplicate same-label images skipped: 60
- Corrupted/unreadable images skipped: 0
- Cross-label conflict hash groups skipped: 5

## carcrash2 Original Counts

- accident: 6191
- non_accident: 15420
- severity_score_excluded: 6191

## Notes

- Original downloaded datasets were not modified.
- Current YOLO `data.yaml` was not modified.
- No training was started.
- This dataset is prepared for image classification, not YOLO object detection.
