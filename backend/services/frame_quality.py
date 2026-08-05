"""CCTV frame quality gate.

Blur, brightness, and contrast checks that run BEFORE crash decision logic.
A frame that fails this gate can never contribute to a confirmed_crash
decision, no matter what the crash classifier or vehicle detector say about
it — an out-of-focus or blown-out frame produces unreliable detections, and
unreliable detections must not become crash cases or notifications.

Independent, self-contained module: reads its own thresholds fresh from the
environment (matching the pattern used by
backend.repositories.crash_cases._require_confirmed_crash_payload) so it can
be reasoned about and tested without importing backend.main.
"""

from __future__ import annotations

import os

import cv2
import numpy as np


def _get_env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


FRAME_BLUR_THRESHOLD = _get_env_float("FRAME_BLUR_THRESHOLD", 80.0)
FRAME_DARK_THRESHOLD = _get_env_float("FRAME_DARK_THRESHOLD", 35.0)
FRAME_OVEREXPOSED_THRESHOLD = _get_env_float("FRAME_OVEREXPOSED_THRESHOLD", 220.0)
FRAME_LOW_CONTRAST_THRESHOLD = _get_env_float("FRAME_LOW_CONTRAST_THRESHOLD", 20.0)


def frame_quality_gate_enabled() -> bool:
    """Master switch. Defaults to enabled. When false, analyze_frame_quality
    still computes and returns real scores (for SSE/debug visibility) but
    always reports frameQualityStatus="good" so it never blocks a decision."""
    return os.getenv("ENABLE_FRAME_QUALITY_GATE", "true").strip().lower() != "false"


# UI-facing copy for each rejection reason. "Camera quality too low" per spec;
# kept short enough to render as a live-camera badge/overlay.
QUALITY_REJECTION_MESSAGES = {
    "low_quality_blurry_frame": "Camera quality too low: unclear frame (too blurry).",
    "low_quality_dark_frame": "Camera quality too low: frame is too dark.",
    "low_quality_overexposed_frame": "Camera quality too low: frame is overexposed.",
    "low_quality_low_contrast_frame": "Camera quality too low: unclear frame (low contrast).",
}


def _empty_frame_result() -> dict:
    return {
        "blurScore": 0.0,
        "brightnessScore": 0.0,
        "contrastScore": 0.0,
        "isBlurry": True,
        "isTooDark": True,
        "isOverexposed": False,
        "isLowContrast": True,
        "frameQualityStatus": "bad",
        "qualityRejectionReason": "low_quality_dark_frame",
    }


def analyze_frame_quality(frame: np.ndarray | None) -> dict:
    """Score one BGR (or grayscale) frame for blur, brightness, and contrast.

    - blurScore: variance of the Laplacian (higher = sharper).
    - brightnessScore: grayscale mean (0-255).
    - contrastScore: grayscale standard deviation (higher = more contrast).

    Rejection priority when multiple issues are present, matching the order
    detection would naturally surface them: blurry > dark > overexposed >
    low contrast. Returns frameQualityStatus "good" or "bad" and, when bad,
    qualityRejectionReason as one of:
      low_quality_blurry_frame, low_quality_dark_frame,
      low_quality_overexposed_frame, low_quality_low_contrast_frame
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        return _empty_frame_result()

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness_score = float(gray.mean())
    contrast_score = float(gray.std())

    is_blurry = blur_score < FRAME_BLUR_THRESHOLD
    is_too_dark = brightness_score < FRAME_DARK_THRESHOLD
    is_overexposed = brightness_score > FRAME_OVEREXPOSED_THRESHOLD
    is_low_contrast = contrast_score < FRAME_LOW_CONTRAST_THRESHOLD

    if is_blurry:
        rejection_reason = "low_quality_blurry_frame"
    elif is_too_dark:
        rejection_reason = "low_quality_dark_frame"
    elif is_overexposed:
        rejection_reason = "low_quality_overexposed_frame"
    elif is_low_contrast:
        rejection_reason = "low_quality_low_contrast_frame"
    else:
        rejection_reason = None

    gate_enabled = frame_quality_gate_enabled()
    frame_quality_status = "good" if (rejection_reason is None or not gate_enabled) else "bad"

    return {
        "blurScore": blur_score,
        "brightnessScore": brightness_score,
        "contrastScore": contrast_score,
        "isBlurry": is_blurry,
        "isTooDark": is_too_dark,
        "isOverexposed": is_overexposed,
        "isLowContrast": is_low_contrast,
        "frameQualityStatus": frame_quality_status,
        "qualityRejectionReason": rejection_reason if gate_enabled else None,
    }
