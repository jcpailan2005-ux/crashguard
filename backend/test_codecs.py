#!/usr/bin/env python3
"""Print which OpenCV video writer codecs are available on this machine."""

from pathlib import Path

import cv2

print("=" * 60)
print("Video Codec Availability Test")
print("=" * 60)

codecs = [
    {"codec": "avc1", "suffix": ".mp4", "preview_safe": True},
    {"codec": "H264", "suffix": ".mp4", "preview_safe": True},
    {"codec": "mp4v", "suffix": ".mp4", "preview_safe": True},
    {"codec": "MJPG", "suffix": ".avi", "preview_safe": False},
]
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

print(f"\nOpenCV Version: {cv2.__version__}")
print("Testing writer codecs on this system:\n")

for candidate in codecs:
    codec = candidate["codec"]
    output_path = output_dir / f"codec_test_{codec}{candidate['suffix']}"
    writer = None

    try:
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*codec),
            10.0,
            (64, 64),
        )

        if writer is not None and writer.isOpened():
            preview_note = "browser preview candidate" if candidate["preview_safe"] else "download fallback only"
            print(f"  [ok]   {codec:6s} - Writer opened ({preview_note})")
        else:
            print(f"  [fail] {codec:6s} - Writer did not open")
    except Exception as error:
        print(f"  [fail] {codec:6s} - Error: {str(error)[:60]}")
    finally:
        if writer is not None:
            writer.release()
        if output_path.exists():
            output_path.unlink()

print("\n" + "=" * 60)
print("MP4 codecs are preferred for browser preview.")
print("If only MJPG works, backend video detection can still complete,")
print("but the UI may expose the file as a download-only fallback.")
print("=" * 60)
