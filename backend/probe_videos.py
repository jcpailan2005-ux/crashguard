import os
import tempfile
from typing import Iterable

import cv2
import requests


def probe_video(path: str) -> None:
    print("\n===", path)
    if not os.path.exists(path):
        print("MISSING")
        return

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print("Could not open with OpenCV")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    dur = (frames / fps) if fps else 0.0
    print(f"opened ok fps={fps:.2f} frames={frames} size={w}x{h} duration_s={dur:.2f}")
    cap.release()


def iter_sample_timestamps(duration_s: float) -> Iterable[float]:
    # A few early timestamps + a few spread across the clip.
    base = [1.0, 2.5, 4.0, 6.0, 8.0]
    if duration_s <= 0:
        return base
    extra = [max(0.0, duration_s * r) for r in (0.2, 0.4, 0.6, 0.8)]
    # de-dupe while keeping order
    seen = set()
    out = []
    for t in base + extra:
        t2 = round(float(t), 2)
        if t2 not in seen:
            seen.add(t2)
            out.append(t2)
    return out


def detect_frame_with_backend(video_path: str, t_sec: float, backend_url: str) -> None:
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, float(t_sec) * 1000.0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        print(f"t={t_sec:>6}s -> no frame")
        return

    fd, jpg_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    cv2.imwrite(jpg_path, frame)

    try:
        with open(jpg_path, "rb") as f:
            resp = requests.post(
                backend_url,
                files={"file": (os.path.basename(jpg_path), f, "image/jpeg")},
                timeout=60,
            )
        if resp.status_code != 200:
            print(f"t={t_sec:>6}s -> backend {resp.status_code} {resp.text[:200]}")
            return
        data = resp.json()
        labels = [d.get("label") for d in data.get("detections", [])]
        conf = data.get("confidence")
        print(
            f"t={t_sec:>6}s accident={data.get('accident_detected')} conf={conf} labels={labels[:8]}"
        )
    finally:
        try:
            os.remove(jpg_path)
        except OSError:
            pass


def main() -> None:
    backend_url = os.getenv("CRASHGUARD_BACKEND_IMAGE_URL", "http://127.0.0.1:8000/api/detect/image")

    paths = [
        r"C:\Users\Administrator\Downloads\These CCTV Footages Road Accident Real Video Caught By Camera -.mp4",
        r"C:\Users\Administrator\Downloads\Dramatic car crash captured on CCTV.mp4",
    ]

    for path in paths:
        probe_video(path)
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        dur = (frames / fps) if fps else 0.0
        cap.release()

        for t in iter_sample_timestamps(dur):
            detect_frame_with_backend(path, t, backend_url)


if __name__ == "__main__":
    main()

