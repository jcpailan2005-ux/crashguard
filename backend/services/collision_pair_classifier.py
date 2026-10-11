"""Bounded, explainable vehicle-pair selection and native-frame crop helpers."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import hypot
from typing import Iterable, Mapping

import numpy as np


VEHICLE_LABELS = frozenset(
    {"car", "truck", "bus", "van", "motorcycle", "motorbike", "moped", "vehicle"}
)


@dataclass(frozen=True)
class CollisionPairConfig:
    max_pairs_per_frame: int = 1
    maximum_edge_distance_normalized: float = 0.15
    maximum_center_distance_normalized: float = 0.35
    context_margin: float = 0.20
    minimum_crop_width: int = 48
    minimum_crop_height: int = 48
    maximum_crop_aspect_ratio: float = 5.0

    def __post_init__(self) -> None:
        if not 1 <= self.max_pairs_per_frame <= 4:
            raise ValueError("Pair classifications must be bounded between one and four.")
        if not 0.0 <= self.context_margin <= 1.0:
            raise ValueError("Pair crop context margin must be between zero and one.")
        if min(self.minimum_crop_width, self.minimum_crop_height) < 1:
            raise ValueError("Pair crop minimum dimensions must be positive.")


@dataclass(frozen=True)
class SelectedVehiclePair:
    pair_a: dict
    pair_b: dict
    selection_score: float
    edge_distance_normalized: float
    center_distance_normalized: float
    iou: float
    source: str
    selection_reason: str


@dataclass(frozen=True)
class PairRegion:
    valid: bool
    crop: np.ndarray | None
    coordinates: tuple[int, int, int, int] | None
    reason: str


def _label(box: Mapping) -> str:
    return str(box.get("label") or "").strip().lower().replace("-", "_").replace(" ", "_")


def _xyxy(box: Mapping) -> tuple[float, float, float, float]:
    if box.get("box") is not None and len(box["box"]) >= 4:
        return tuple(float(value) for value in box["box"][:4])  # type: ignore[return-value]
    x1, y1 = float(box.get("x") or 0.0), float(box.get("y") or 0.0)
    return (
        x1,
        y1,
        x1 + float(box.get("width") or 0.0),
        y1 + float(box.get("height") or 0.0),
    )


def _eligible(box: Mapping) -> bool:
    if _label(box) not in VEHICLE_LABELS:
        return False
    state = str(box.get("detectionState") or "")
    return state == "TRUSTED" or (
        state == "CANDIDATE" and bool(box.get("candidateSupported"))
    )


def eligible_vehicle_evidence(boxes: Iterable[Mapping]) -> list[dict]:
    return [dict(box) for box in boxes if _eligible(box)]


def _geometry(a: Mapping, b: Mapping, diagonal: float):
    ax1, ay1, ax2, ay2 = _xyxy(a)
    bx1, by1, bx2, by2 = _xyxy(b)
    dx = max(0.0, bx1 - ax2, ax1 - bx2)
    dy = max(0.0, by1 - ay2, ay1 - by2)
    edge_distance = hypot(dx, dy) / max(1.0, diagonal)
    acx, acy = (ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0
    bcx, bcy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
    center_distance = hypot(acx - bcx, acy - bcy) / max(1.0, diagonal)
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    overlap = intersection / union if union > 0.0 else 0.0
    return edge_distance, center_distance, overlap, area_a, area_b


def select_plausible_pairs(
    boxes: Iterable[Mapping],
    *,
    frame_width: int,
    frame_height: int,
    config: CollisionPairConfig | None = None,
) -> list[SelectedVehiclePair]:
    config = config or CollisionPairConfig()
    eligible = eligible_vehicle_evidence(boxes)
    diagonal = hypot(max(1, frame_width), max(1, frame_height))
    ranked = []
    for a, b in combinations(eligible, 2):
        # Require an established trusted anchor. Two low-confidence candidates
        # alone must not create an expensive or authoritative collision region.
        if "TRUSTED" not in {a.get("detectionState"), b.get("detectionState")}:
            continue
        edge_distance, center_distance, overlap, area_a, area_b = _geometry(a, b, diagonal)
        if (
            edge_distance > config.maximum_edge_distance_normalized
            or center_distance > config.maximum_center_distance_normalized
        ):
            continue
        proximity = 1.0 - min(
            1.0, edge_distance / max(config.maximum_edge_distance_normalized, 1e-9)
        )
        center_proximity = 1.0 - min(
            1.0, center_distance / max(config.maximum_center_distance_normalized, 1e-9)
        )
        confidence = (
            float(a.get("confidence", a.get("score", 0.0)) or 0.0)
            + float(b.get("confidence", b.get("score", 0.0)) or 0.0)
        ) / 2.0
        substantial_anchor = min(
            1.0,
            max(area_a, area_b) / max(1.0, frame_width * frame_height * 0.15),
        )
        supported_candidate_relationship = float(
            "CANDIDATE" in {a.get("detectionState"), b.get("detectionState")}
        )
        # Phase 4 is specifically intended to recover visual evidence around a
        # weak but already context-supported participant. A substantial trusted
        # anchor and supported-candidate relationship therefore break ties among
        # otherwise plausible close pairs; rejected/unsupported boxes never enter.
        score = (
            0.28 * proximity
            + 0.14 * center_proximity
            + 0.14 * min(1.0, overlap / 0.25)
            + 0.08 * confidence
            + 0.26 * substantial_anchor
            + 0.10 * supported_candidate_relationship
        )
        source = "+".join(
            "trusted" if item.get("detectionState") == "TRUSTED" else "supported_candidate"
            for item in (a, b)
        )
        reason_parts = ["edge_proximity", "center_proximity"]
        if overlap > 0.0:
            reason_parts.insert(0, "box_overlap")
        ranked.append(
            SelectedVehiclePair(
                pair_a=a,
                pair_b=b,
                selection_score=score,
                edge_distance_normalized=edge_distance,
                center_distance_normalized=center_distance,
                iou=overlap,
                source=source,
                selection_reason="+".join(reason_parts),
            )
        )
    ranked.sort(key=lambda pair: pair.selection_score, reverse=True)
    return ranked[: config.max_pairs_per_frame]


def build_pair_region(
    native_frame: np.ndarray,
    pair: SelectedVehiclePair,
    *,
    config: CollisionPairConfig | None = None,
) -> PairRegion:
    config = config or CollisionPairConfig()
    if not isinstance(native_frame, np.ndarray) or native_frame.ndim < 2 or native_frame.size == 0:
        return PairRegion(False, None, None, "invalid_source_frame")
    frame_height, frame_width = native_frame.shape[:2]
    ax1, ay1, ax2, ay2 = _xyxy(pair.pair_a)
    bx1, by1, bx2, by2 = _xyxy(pair.pair_b)
    ux1, uy1, ux2, uy2 = min(ax1, bx1), min(ay1, by1), max(ax2, bx2), max(ay2, by2)
    union_width, union_height = ux2 - ux1, uy2 - uy1
    if union_width <= 0.0 or union_height <= 0.0:
        return PairRegion(False, None, None, "invalid_union_box")
    margin_x, margin_y = union_width * config.context_margin, union_height * config.context_margin
    x1 = max(0, int(np.floor(ux1 - margin_x)))
    y1 = max(0, int(np.floor(uy1 - margin_y)))
    x2 = min(frame_width, int(np.ceil(ux2 + margin_x)))
    y2 = min(frame_height, int(np.ceil(uy2 + margin_y)))
    crop_width, crop_height = x2 - x1, y2 - y1
    if crop_width < config.minimum_crop_width or crop_height < config.minimum_crop_height:
        return PairRegion(False, None, (x1, y1, x2, y2), "insufficient_source_pixels")
    aspect = max(crop_width / crop_height, crop_height / crop_width)
    if aspect > config.maximum_crop_aspect_ratio:
        return PairRegion(False, None, (x1, y1, x2, y2), "extreme_aspect_ratio")
    for box in (pair.pair_a, pair.pair_b):
        bx1, by1, bx2, by2 = _xyxy(box)
        center_x, center_y = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
        if not (x1 <= center_x <= x2 and y1 <= center_y <= y2):
            return PairRegion(False, None, (x1, y1, x2, y2), "participant_outside_crop")
    crop = native_frame[y1:y2, x1:x2]
    if crop.size == 0:
        return PairRegion(False, None, (x1, y1, x2, y2), "empty_crop")
    return PairRegion(True, crop.copy(), (x1, y1, x2, y2), "valid_pair_region")


def supporting_visual_evidence(full_frame_score: float, pair_region_score: float | None) -> float:
    """Expose a conservative diagnostic blend; decision paths keep full-frame authority."""
    full = max(0.0, min(1.0, float(full_frame_score)))
    if pair_region_score is None:
        return full
    pair = max(0.0, min(1.0, float(pair_region_score)))
    # Pair evidence can add at most 25% of the positive difference and can
    # never reduce or replace the authoritative full-frame score.
    return min(1.0, full + 0.25 * max(0.0, pair - full))
