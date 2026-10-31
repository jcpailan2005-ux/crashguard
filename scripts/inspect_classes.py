import os
os.environ["YOLO_OFFLINE"] = "1"
os.environ["ULTRALYTICS_AUTOINSTALL"] = "0"
import torch

for path_str in ["backend/best.pt", "backend/models/crash_classifier.pt"]:
    ckpt = torch.load(path_str, map_location="cpu", weights_only=False)
    print(f"=== {path_str} ===")
    print("task:", ckpt.get("task"))
    print("names:", ckpt.get("names"))
    if "model" in ckpt and hasattr(ckpt["model"], "names"):
        print("model.names:", ckpt["model"].names)
    print("epoch:", ckpt.get("epoch"))
