"""Pre-screen local fixed-camera positive candidates for CrashGuard Phase 8B.

Ground truth is never inferred from either model. C1 filename groups are rebuilt
as ordered frame sequences. C2 numeric names are explicitly *not* treated as a
sequence because adjacent files are shuffled independent scenes; only a small
diagnostic gallery of high-ranked static candidates is generated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
PHASE8B = ROOT / "backend" / "validation" / "phase8b"
SHEETS = PHASE8B / "contact_sheets"
DERIVED = PHASE8B / "derived"
C1 = Path(r"C:\Users\Lenovo\Downloads\carcrash1cctv\data")
C2 = Path(r"C:\Users\Lenovo\Downloads\carcrash2cctv\Accident\Accident")
CADP = PHASE8B / "incoming" / "cadp_pilot"
CADP_ANNOTATIONS = PHASE8B / "source_metadata" / "cadp_annotations.json"
MODEL1 = ROOT / "backend" / "models" / "crash_classifier.pt"
MODEL2 = ROOT / "backend" / "best.pt"
VEHICLES = {"car", "motorcycle", "bus", "truck", "bicycle"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def c1_identity(path: Path) -> tuple[str, int] | None:
    stem = path.stem.lower().replace(" ", "")
    match = re.match(r"(test\d+|acc\d+)_(\d+)$", stem)
    if not match:
        match = re.match(r"(acc\d+)\((\d+)\)$", stem)
    if not match:
        return None
    return match.group(1).upper(), int(match.group(2))


def c1_groups() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    seen = set()
    for path in sorted(C1.rglob("*.jpg")):
        identity = c1_identity(path)
        if identity is None:
            continue
        event_id, frame_index = identity
        key = (event_id, frame_index, sha256(path))
        if key in seen:
            continue
        seen.add(key)
        label = "accident" if "accident" in path.parent.name.lower() and "non" not in path.parent.name.lower() else "non_accident"
        groups[event_id].append({"path": path, "frame_index": frame_index, "label": label})
    for rows in groups.values():
        rows.sort(key=lambda row: row["frame_index"])
    return {event: rows for event, rows in groups.items() if any(row["label"] == "accident" for row in rows)}


def model_scores_image(model1: YOLO, model2: YOLO, image: np.ndarray | None) -> tuple[float, int, str]:
    if image is None:
        return 0.0, 0, ""
    classifier = model1.predict(image, imgsz=224, verbose=False)[0]
    score = float(classifier.probs.data.detach().cpu().tolist()[0]) if classifier.probs is not None else 0.0
    detection = model2.predict(image, imgsz=640, conf=0.10, verbose=False)[0]
    names = detection.names
    labels = []
    if detection.boxes is not None:
        for class_id, confidence in zip(detection.boxes.cls.tolist(), detection.boxes.conf.tolist()):
            label = str(names[int(class_id)]).lower()
            if label in VEHICLES and confidence >= 0.10:
                labels.append(f"{label}:{confidence:.3f}")
    return score, len(labels), ";".join(labels)


def model_scores(model1: YOLO, model2: YOLO, path: Path) -> tuple[float, int, str]:
    return model_scores_image(model1, model2, cv2.imread(str(path)))


def camera_stationary_images(first: np.ndarray | None, last: np.ndarray | None) -> tuple[str, str]:
    if first is not None and first.ndim == 3:
        first = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    if last is not None and last.ndim == 3:
        last = cv2.cvtColor(last, cv2.COLOR_BGR2GRAY)
    if first is None or last is None or first.shape != last.shape:
        return "UNKNOWN", "unreadable or resolution mismatch"
    orb = cv2.ORB_create(1000)
    kp1, des1 = orb.detectAndCompute(first, None)
    kp2, des2 = orb.detectAndCompute(last, None)
    if des1 is None or des2 is None:
        return "UNKNOWN", "insufficient background features"
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).match(des1, des2)
    matches = sorted(matches, key=lambda item: item.distance)[:100]
    if len(matches) < 12:
        return "UNKNOWN", "insufficient feature matches"
    src = np.float32([kp1[item.queryIdx].pt for item in matches])
    dst = np.float32([kp2[item.trainIdx].pt for item in matches])
    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC)
    if matrix is None:
        return "UNKNOWN", "camera transform unavailable"
    dx, dy = float(matrix[0, 2]), float(matrix[1, 2])
    scale = float(np.hypot(matrix[0, 0], matrix[0, 1]))
    angle = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    diagonal = float(np.hypot(first.shape[1], first.shape[0]))
    stationary = np.hypot(dx, dy) <= diagonal * 0.03 and abs(scale - 1.0) <= 0.04 and abs(angle) <= 2.0
    return ("TRUE" if stationary else "FALSE", f"translation=({dx:.1f},{dy:.1f}) scale={scale:.3f} angle={angle:.2f}")


def camera_stationary(first_path: Path, last_path: Path) -> tuple[str, str]:
    return camera_stationary_images(cv2.imread(str(first_path)), cv2.imread(str(last_path)))


def select_evenly(rows: list[dict], count: int = 9) -> list[dict]:
    if len(rows) <= count:
        return rows
    indexes = np.linspace(0, len(rows) - 1, count).round().astype(int)
    return [rows[int(index)] for index in indexes]


def make_sheet(event_id: str, rows: list[dict], output: Path) -> None:
    tiles = []
    for row in select_evenly(rows):
        image = cv2.imread(str(row["path"]))
        if image is None:
            image = np.zeros((180, 320, 3), dtype=np.uint8)
        image = cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
        color = (0, 80, 255) if row["label"] == "accident" else (120, 120, 120)
        cv2.rectangle(image, (0, 0), (320, 25), (0, 0, 0), -1)
        cv2.putText(image, f"{event_id} f={row['frame_index']} {row['label']}", (5, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.43, color, 1, cv2.LINE_AA)
        tiles.append(image)
    while len(tiles) < 9:
        tiles.append(np.zeros((180, 320, 3), dtype=np.uint8))
    sheet = np.vstack([np.hstack(tiles[index:index + 3]) for index in range(0, 9, 3)])
    cv2.imwrite(str(output), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])


def cadp_pilot_rows(model1: YOLO | None, model2: YOLO | None) -> list[dict]:
    annotations = json.loads(CADP_ANNOTATIONS.read_text(encoding="utf-8"))
    results = []
    for path in sorted(CADP.glob("*.mp4")):
        capture = cv2.VideoCapture(str(path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = count / fps if fps else 0.0
        frames = []
        for frame_index in np.linspace(0, max(0, count - 1), 9).round().astype(int):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index)); ok, frame = capture.read()
            if ok and frame is not None:
                frames.append((int(frame_index), frame))
        capture.release()
        tiles = []
        for frame_index, frame in frames:
            tile = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
            cv2.rectangle(tile, (0, 0), (320, 24), (0, 0, 0), -1)
            cv2.putText(tile, f"CADP-{path.stem} f={frame_index}", (5, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
        while len(tiles) < 9:
            tiles.append(np.zeros((180, 320, 3), dtype=np.uint8))
        sheet = SHEETS / f"CADP_{path.stem}.jpg"
        cv2.imwrite(str(sheet), np.vstack([np.hstack(tiles[index:index + 3]) for index in range(0, 9, 3)]), [cv2.IMWRITE_JPEG_QUALITY, 92])
        representative = frames[len(frames) // 2][1] if frames else None
        m1, vehicle_count, proposals = model_scores_image(model1, model2, representative) if model1 and model2 else (0.0, 0, "")
        stationary, evidence = camera_stationary_images(frames[0][1] if frames else None, frames[-1][1] if frames else None)
        results.append({
            "source": "CADP", "source_path": str(path.resolve()), "source_family": f"CADP-{path.stem}",
            "event_group_id": f"CADP-{path.stem}", "sha256": sha256(path), "frame_count": count,
            "first_frame": 0, "last_frame": max(0, count - 1), "approximate_duration": f"{duration:.3f}",
            "resolution": f"{width}x{height}", "contact_sheet": str(sheet.resolve()),
            "model2_vehicle_proposal_count": vehicle_count, "model2_proposals": proposals,
            "at_least_two_model2_vehicles": "YES" if vehicle_count >= 2 else "NO",
            "model1_diagnostic_score": f"{m1:.4f}", "camera_stationary_estimate": stationary,
            "camera_estimate_evidence": evidence, "provenance": "RESEARCH_USE_CONFIRMED",
            "screening_state": "NEEDS_REVIEW",
            "notes": f"Official CADP pilot preview; provider annotation objects={len(annotations.get(path.name, []))}. Model output is assistance only.",
        })
    return results


def c2_static_gallery(limit: int = 120) -> None:
    manifest = []
    with (ROOT / "dataset_v2_manifest.csv").open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row["source"] == "carcrash2cctv" and row["class"] == "accident" and row.get("accident_score"):
                match = re.match(r"carcrash2cctv_(\d+)_", row["filename"])
                if match:
                    manifest.append((float(row["accident_score"]), int(match.group(1))))
    chosen = []
    used = set()
    for score, index in sorted(manifest, reverse=True):
        if index in used or not (C2 / f"{index}.jpg").exists():
            continue
        used.add(index); chosen.append((score, index))
        if len(chosen) >= limit:
            break
    for page_number, start in enumerate(range(0, len(chosen), 30), 1):
        tiles = []
        for score, index in chosen[start:start + 30]:
            image = cv2.imread(str(C2 / f"{index}.jpg"))
            image = cv2.resize(image, (256, 160), interpolation=cv2.INTER_AREA)
            cv2.rectangle(image, (0, 0), (256, 22), (0, 0, 0), -1)
            cv2.putText(image, f"C2-{index} M1={score:.3f}", (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)
            tiles.append(image)
        while len(tiles) < 30:
            tiles.append(np.zeros((160, 256, 3), dtype=np.uint8))
        page = np.vstack([np.hstack(tiles[index:index + 6]) for index in range(0, 30, 6)])
        cv2.imwrite(str(SHEETS / f"C2_STATIC_TOP_{page_number:02d}.jpg"), page, [cv2.IMWRITE_JPEG_QUALITY, 91])


def overview(prefix: str) -> None:
    paths = sorted(SHEETS.glob(f"{prefix}_*.jpg"))
    paths = [path for path in paths if "OVERVIEW" not in path.name]
    for page_number, start in enumerate(range(0, len(paths), 12), 1):
        tiles = []
        for path in paths[start:start + 12]:
            image = cv2.imread(str(path))
            image = cv2.resize(image, (480, 270), interpolation=cv2.INTER_AREA)
            cv2.rectangle(image, (0, 0), (480, 27), (0, 0, 0), -1)
            cv2.putText(image, path.stem, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.53, (0, 255, 255), 2, cv2.LINE_AA)
            tiles.append(image)
        while len(tiles) < 12:
            tiles.append(np.zeros((270, 480, 3), dtype=np.uint8))
        page = np.vstack([np.hstack(tiles[index:index + 4]) for index in range(0, 12, 4)])
        cv2.imwrite(str(SHEETS / f"{prefix}_OVERVIEW_{page_number:02d}.jpg"), page, [cv2.IMWRITE_JPEG_QUALITY, 93])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-models", action="store_true")
    args = parser.parse_args()
    SHEETS.mkdir(parents=True, exist_ok=True); DERIVED.mkdir(parents=True, exist_ok=True)
    model1 = model2 = None
    if not args.skip_models:
        model1, model2 = YOLO(str(MODEL1)), YOLO(str(MODEL2))
    results = []
    for event_id, rows in sorted(c1_groups().items()):
        sheet = SHEETS / f"C1_{event_id}.jpg"
        make_sheet(event_id, rows, sheet)
        representative = rows[len(rows) // 2]["path"]
        m1, vehicle_count, proposals = model_scores(model1, model2, representative) if model1 and model2 else (0.0, 0, "")
        stationary, evidence = camera_stationary(rows[0]["path"], rows[-1]["path"])
        results.append({
            "source": "carcrash1cctv", "source_path": str(rows[0]["path"].parent.parent.parent.resolve()),
            "source_family": f"C1-{event_id}", "event_group_id": f"C1-{event_id}",
            "sha256": hashlib.sha256("".join(sha256(row["path"]) for row in rows).encode()).hexdigest().upper(), "frame_count": len(rows),
            "first_frame": rows[0]["frame_index"], "last_frame": rows[-1]["frame_index"],
            "approximate_duration": "UNKNOWN_SOURCE_FPS", "resolution": f"{cv2.imread(str(representative)).shape[1]}x{cv2.imread(str(representative)).shape[0]}",
            "contact_sheet": str(sheet.resolve()), "model2_vehicle_proposal_count": vehicle_count,
            "model2_proposals": proposals, "at_least_two_model2_vehicles": "YES" if vehicle_count >= 2 else "NO",
            "model1_diagnostic_score": f"{m1:.4f}", "camera_stationary_estimate": stationary,
            "camera_estimate_evidence": evidence, "provenance": "LICENSE_UNKNOWN",
            "screening_state": "NEEDS_REVIEW", "notes": "Filename-ordered event reconstruction; traced to a YouTube-derived Kaggle corpus without a local license file. Model output is annotation assistance only.",
        })
    results.extend(cadp_pilot_rows(model1, model2))
    fields = list(results[0]) if results else []
    with (PHASE8B / "candidate_prescreen.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields); writer.writeheader(); writer.writerows(results)
    c2_static_gallery()
    overview("C1")
    overview("CADP")
    c1_count = sum(row["source"] == "carcrash1cctv" for row in results)
    cadp_count = sum(row["source"] == "CADP" for row in results)
    (DERIVED / "prescreen_summary.json").write_text(json.dumps({
        "c1_sequence_candidates": c1_count,
        "c1_frames": sum(row["frame_count"] for row in results if row["source"] == "carcrash1cctv"),
        "cadp_video_candidates": cadp_count,
        "cadp_frames": sum(row["frame_count"] for row in results if row["source"] == "CADP"),
        "c2_static_images_available": len(list(C2.glob("*.jpg"))), "c2_static_gallery_count": 120,
        "c2_temporal_reconstruction": "NOT_DEFENSIBLE_SHUFFLED_STANDALONE_IMAGES",
        "ground_truth_from_models": False,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"c1_candidates": c1_count, "cadp_candidates": cadp_count,
                      "c1_contact_sheets": len([path for path in SHEETS.glob('C1_*.jpg') if 'OVERVIEW' not in path.name]),
                      "cadp_contact_sheets": len([path for path in SHEETS.glob('CADP_*.jpg') if 'OVERVIEW' not in path.name]),
                      "c2_gallery_pages": len(list(SHEETS.glob('C2_STATIC_TOP_*.jpg')))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
