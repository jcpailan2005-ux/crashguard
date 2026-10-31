import os
os.environ["YOLO_OFFLINE"] = "1"
os.environ["ULTRALYTICS_AUTOINSTALL"] = "0"

import torch
from pathlib import Path

print("=== Checking Models via PyTorch ===", flush=True)
for m in ["backend/best.pt", "backend/models/crash_classifier.pt", "yolov8n.pt", "yolov8n-cls.pt"]:
    p = Path(m)
    if p.exists():
        try:
            ckpt = torch.load(p, map_location="cpu", weights_only=False)
            model_info = ckpt.get("model", None)
            names = ckpt.get("names", getattr(model_info, "names", None))
            task = ckpt.get("task", getattr(model_info, "task", None))
            epoch = ckpt.get("epoch", None)
            train_args = ckpt.get("train_args", None)
            date = ckpt.get("date", None)
            print(f"\nModel: {m}", flush=True)
            print(f"  task: {task}", flush=True)
            print(f"  names: {names}", flush=True)
            print(f"  epoch: {epoch}", flush=True)
            print(f"  date: {date}", flush=True)
            if train_args:
                print(f"  train_args.epochs: {train_args.get('epochs')}", flush=True)
                print(f"  train_args.imgsz: {train_args.get('imgsz')}", flush=True)
                print(f"  train_args.batch: {train_args.get('batch')}", flush=True)
                print(f"  train_args.lr0: {train_args.get('lr0')}", flush=True)
                print(f"  train_args.optimizer: {train_args.get('optimizer')}", flush=True)
                print(f"  train_args.data: {train_args.get('data')}", flush=True)
        except Exception as e:
            print(f"Error loading {m}: {e}", flush=True)

print("\nDone!", flush=True)
