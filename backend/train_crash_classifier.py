from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import torch
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "datasets" / "crash_classification"
RUNS_DIR = BASE_DIR / "runs" / "crash_classifier"
MODELS_DIR = BASE_DIR / "models"
FINAL_MODEL_PATH = MODELS_DIR / "crash_classifier.pt"
REPORT_PATH = MODELS_DIR / "crash_classifier_report.json"
REPORT_MD_PATH = MODELS_DIR / "crash_classifier_report.md"

CLASS_NAMES = ["accident", "non_accident"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class EvalResult:
    split: str
    total: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    per_class: dict[str, dict[str, float | int]]
    confusion_matrix: dict[str, dict[str, int]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train an accident vs non_accident image classifier."
    )
    parser.add_argument("--data", type=Path, default=DATASET_DIR)
    parser.add_argument("--base-model", default="yolov8n-cls.pt")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--name", default="train")
    parser.add_argument("--exist-ok", action="store_true")
    return parser.parse_args()


def resolve_device(device_arg: str | None) -> str | int:
    if device_arg is not None:
        return int(device_arg) if device_arg.isdigit() else device_arg
    return 0 if torch.cuda.is_available() else "cpu"


def assert_dataset(data_dir: Path) -> None:
    missing = []
    for split in ("train", "val", "test"):
        for class_name in CLASS_NAMES:
            folder = data_dir / split / class_name
            if not folder.exists():
                missing.append(str(folder))
    if missing:
        raise FileNotFoundError(
            "Crash classification dataset is missing required folders:\n"
            + "\n".join(missing)
        )


def iter_split_images(data_dir: Path, split: str) -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []
    for class_name in CLASS_NAMES:
        folder = data_dir / split / class_name
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                items.append((path, class_name))
    return items


def evaluate_split(model: YOLO, data_dir: Path, split: str, imgsz: int, device: str | int) -> EvalResult:
    items = iter_split_images(data_dir, split)
    matrix = {actual: Counter() for actual in CLASS_NAMES}

    for path, actual in items:
        results = model.predict(
            source=str(path),
            imgsz=imgsz,
            device=device,
            verbose=False,
        )
        probs = results[0].probs
        predicted_index = int(probs.top1)
        predicted = model.names[predicted_index]
        matrix[actual][predicted] += 1

    total = len(items)
    correct = sum(matrix[class_name][class_name] for class_name in CLASS_NAMES)
    per_class: dict[str, dict[str, float | int]] = {}
    precisions: list[float] = []
    recalls: list[float] = []

    for class_name in CLASS_NAMES:
        true_positive = matrix[class_name][class_name]
        false_positive = sum(matrix[other][class_name] for other in CLASS_NAMES if other != class_name)
        false_negative = sum(matrix[class_name][other] for other in CLASS_NAMES if other != class_name)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        support = sum(matrix[class_name].values())
        precisions.append(precision)
        recalls.append(recall)
        per_class[class_name] = {
            "precision": precision,
            "recall": recall,
            "support": support,
        }

    return EvalResult(
        split=split,
        total=total,
        accuracy=correct / total if total else 0.0,
        macro_precision=sum(precisions) / len(precisions),
        macro_recall=sum(recalls) / len(recalls),
        per_class=per_class,
        confusion_matrix={
            actual: {predicted: matrix[actual][predicted] for predicted in CLASS_NAMES}
            for actual in CLASS_NAMES
        },
    )


def write_reports(report: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Crash Classifier Training Report",
        "",
        f"Dataset: `{report['dataset']}`",
        f"Final model: `{report['final_model']}`",
        f"Base model: `{report['base_model']}`",
        f"Epochs: `{report['epochs']}`",
        f"Image size: `{report['imgsz']}`",
        f"Batch: `{report['batch']}`",
        f"Device: `{report['device']}`",
        "",
        "## Metrics",
        "",
        "| Split | Accuracy | Macro Precision | Macro Recall | Total |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for split in ("val", "test"):
        metrics = report["evaluation"][split]
        lines.append(
            f"| {split} | {metrics['accuracy']:.4f} | "
            f"{metrics['macro_precision']:.4f} | {metrics['macro_recall']:.4f} | {metrics['total']} |"
        )
    lines.extend(["", "## Confusion Matrices", ""])
    for split in ("val", "test"):
        lines.append(f"### {split}")
        lines.append("")
        lines.append("| Actual \\ Predicted | accident | non_accident |")
        lines.append("| --- | ---: | ---: |")
        matrix = report["evaluation"][split]["confusion_matrix"]
        for actual in CLASS_NAMES:
            lines.append(
                f"| {actual} | {matrix[actual]['accident']} | {matrix[actual]['non_accident']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Run Instructions",
            "",
            "```powershell",
            "cd C:\\Users\\Lenovo\\Desktop\\MyCrushguard",
            "python backend\\train_crash_classifier.py --epochs 5 --imgsz 224 --batch 32",
            "```",
            "",
            "This trains a separate classifier only. It does not modify YOLO `data.yaml`, "
            "`backend/best.pt`, Live Camera logic, UI, notifications, or review cases.",
        ]
    )
    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    data_dir = args.data.resolve()
    assert_dataset(data_dir)

    device = resolve_device(args.device)
    model = YOLO(args.base_model)
    results = model.train(
        data=str(data_dir),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=device,
        project=str(RUNS_DIR),
        name=args.name,
        exist_ok=args.exist_ok,
    )

    save_dir = Path(results.save_dir)
    best_model = save_dir / "weights" / "best.pt"
    if not best_model.exists():
        raise FileNotFoundError(f"Training completed but no best model was found at {best_model}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_model, FINAL_MODEL_PATH)

    trained_model = YOLO(str(FINAL_MODEL_PATH))
    evaluation = {
        split: as_eval_dict(evaluate_split(trained_model, data_dir, split, args.imgsz, device))
        for split in ("val", "test")
    }

    report = {
        "dataset": str(data_dir),
        "base_model": args.base_model,
        "run_dir": str(save_dir),
        "best_model": str(best_model),
        "final_model": str(FINAL_MODEL_PATH),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": str(device),
        "evaluation": evaluation,
    }
    write_reports(report)

    csv_path = MODELS_DIR / "crash_classifier_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["split", "accuracy", "macro_precision", "macro_recall", "total"])
        for split, metrics in evaluation.items():
            writer.writerow([
                split,
                metrics["accuracy"],
                metrics["macro_precision"],
                metrics["macro_recall"],
                metrics["total"],
            ])

    print(json.dumps(report, indent=2))


def as_eval_dict(result: EvalResult) -> dict:
    return {
        "split": result.split,
        "total": result.total,
        "accuracy": result.accuracy,
        "macro_precision": result.macro_precision,
        "macro_recall": result.macro_recall,
        "per_class": result.per_class,
        "confusion_matrix": result.confusion_matrix,
    }


if __name__ == "__main__":
    main()
