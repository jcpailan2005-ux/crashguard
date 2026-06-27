from pathlib import Path

import torch
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "best.pt"
DATA_CONFIG = BASE_DIR / "data.yaml"

device = 0 if torch.cuda.is_available() else "cpu"
model = YOLO(str(MODEL_PATH))
model.train(
    data=str(DATA_CONFIG),
    epochs=50,
    imgsz=640,
    device=device,
    workers=0,
    project=str(BASE_DIR),
    name="carcrash_train"
)
