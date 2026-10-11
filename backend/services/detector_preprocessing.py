"""Aspect-safe, configurable preprocessing for the live vehicle detector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import cv2
import numpy as np


DEFAULT_YOLO_IMGSZ = 640
MIN_YOLO_IMGSZ = 320
MAX_YOLO_IMGSZ = 1280
YOLO_STRIDE = 32
MAX_EXPLICIT_FRAME_DIMENSION = 3840


def safe_yolo_imgsz(value: object, default: int = DEFAULT_YOLO_IMGSZ) -> int:
    """Return a bounded stride-compatible square YOLO input size."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if (
        parsed < MIN_YOLO_IMGSZ
        or parsed > MAX_YOLO_IMGSZ
        or parsed % YOLO_STRIDE != 0
    ):
        return default
    return parsed


def safe_target_size(width: object, height: object) -> tuple[int, int] | None:
    """Return an explicit bounding size, or native mode for invalid/zero input."""
    try:
        parsed_width, parsed_height = int(width), int(height)
    except (TypeError, ValueError):
        return None
    if parsed_width == 0 and parsed_height == 0:
        return None
    if not (
        1 <= parsed_width <= MAX_EXPLICIT_FRAME_DIMENSION
        and 1 <= parsed_height <= MAX_EXPLICIT_FRAME_DIMENSION
    ):
        return None
    return parsed_width, parsed_height


@dataclass(frozen=True)
class DetectorInputConfig:
    target_size: tuple[int, int] | None = None
    imgsz: int = DEFAULT_YOLO_IMGSZ

    @classmethod
    def from_values(cls, width: object, height: object, imgsz: object):
        return cls(
            target_size=safe_target_size(width, height),
            imgsz=safe_yolo_imgsz(imgsz),
        )


@dataclass(frozen=True)
class PreparedDetectorFrame:
    frame: np.ndarray
    source_width: int
    source_height: int
    detector_width: int
    detector_height: int
    resized: bool

    @property
    def scale_to_source_x(self) -> float:
        return self.source_width / max(1, self.detector_width)

    @property
    def scale_to_source_y(self) -> float:
        return self.source_height / max(1, self.detector_height)


def prepare_detector_frame(
    frame: np.ndarray, config: DetectorInputConfig
) -> PreparedDetectorFrame:
    """Use native pixels by default; explicit bounds resize without distortion."""
    if not isinstance(frame, np.ndarray) or frame.ndim < 2 or frame.size == 0:
        raise ValueError("Detector input must be a non-empty image array.")
    source_height, source_width = frame.shape[:2]
    if config.target_size is None:
        return PreparedDetectorFrame(
            frame=frame,
            source_width=source_width,
            source_height=source_height,
            detector_width=source_width,
            detector_height=source_height,
            resized=False,
        )

    bound_width, bound_height = config.target_size
    scale = min(bound_width / source_width, bound_height / source_height)
    detector_width = max(1, round(source_width * scale))
    detector_height = max(1, round(source_height * scale))
    if detector_width == source_width and detector_height == source_height:
        prepared = frame
        resized = False
    else:
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        prepared = cv2.resize(
            frame, (detector_width, detector_height), interpolation=interpolation
        )
        resized = True
    return PreparedDetectorFrame(
        frame=prepared,
        source_width=source_width,
        source_height=source_height,
        detector_width=detector_width,
        detector_height=detector_height,
        resized=resized,
    )


def map_boxes_to_source(
    boxes: Iterable[Mapping], prepared: PreparedDetectorFrame
) -> list[dict]:
    """Map xywh/optional xyxy boxes from detector space to source space."""
    sx, sy = prepared.scale_to_source_x, prepared.scale_to_source_y
    mapped = []
    for original in boxes:
        box = dict(original)
        for key in ("x", "width"):
            if key in box:
                box[key] = float(box[key]) * sx
        for key in ("y", "height"):
            if key in box:
                box[key] = float(box[key]) * sy
        if box.get("box") is not None and len(box["box"]) >= 4:
            values = list(box["box"])
            values[:4] = [
                float(values[0]) * sx,
                float(values[1]) * sy,
                float(values[2]) * sx,
                float(values[3]) * sy,
            ]
            box["box"] = values
        mapped.append(box)
    return mapped


def expected_letterbox_shape(
    frame_width: int, frame_height: int, imgsz: int, stride: int = YOLO_STRIDE
) -> tuple[int, int]:
    """Predict Ultralytics rect-mode HxW for one image at a square imgsz."""
    scale = min(imgsz / frame_width, imgsz / frame_height)
    resized_width = round(frame_width * scale)
    resized_height = round(frame_height * scale)
    padded_width = min(imgsz, ((resized_width + stride - 1) // stride) * stride)
    padded_height = min(imgsz, ((resized_height + stride - 1) // stride) * stride)
    return padded_height, padded_width
