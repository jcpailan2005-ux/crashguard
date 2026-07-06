# Crash Classifier Training Report

Dataset: `C:\Users\Lenovo\Desktop\MyCrushguard\backend\datasets\crash_classification`
Final model: `C:\Users\Lenovo\Desktop\MyCrushguard\backend\models\crash_classifier.pt`
Base model: `yolov8n-cls.pt`
Epochs: `5`
Image size: `224`
Batch: `32`
Device: `cpu`

## Metrics

| Split | Accuracy | Macro Precision | Macro Recall | Total |
| --- | ---: | ---: | ---: | ---: |
| val | 0.9650 | 0.9651 | 0.9650 | 1941 |
| test | 0.9614 | 0.9617 | 0.9614 | 1941 |

## Confusion Matrices

### val

| Actual \ Predicted | accident | non_accident |
| --- | ---: | ---: |
| accident | 929 | 44 |
| non_accident | 24 | 944 |

### test

| Actual \ Predicted | accident | non_accident |
| --- | ---: | ---: |
| accident | 921 | 50 |
| non_accident | 25 | 945 |

## Run Instructions

```powershell
cd C:\Users\Lenovo\Desktop\MyCrushguard
python backend\train_crash_classifier.py --epochs 5 --imgsz 224 --batch 32
```

This trains a separate classifier only. It does not modify YOLO `data.yaml`, `backend/best.pt`, Live Camera logic, UI, notifications, or review cases.
