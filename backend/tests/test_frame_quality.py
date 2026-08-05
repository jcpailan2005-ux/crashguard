import os
import unittest

import cv2
import numpy as np

from backend.services.frame_quality import analyze_frame_quality


def _checkerboard(size: int = 200, block: int = 10) -> np.ndarray:
    img = np.zeros((size, size), dtype=np.uint8)
    for y in range(0, size, block):
        for x in range(0, size, block):
            if ((x // block) + (y // block)) % 2 == 0:
                img[y : y + block, x : x + block] = 255
    return img


def clear_frame() -> np.ndarray:
    """Sharp, mid-brightness, high-contrast frame that should pass every gate."""
    return _checkerboard()


def blurry_frame() -> np.ndarray:
    """Heavily blurred version of the same scene: low Laplacian variance."""
    return cv2.GaussianBlur(_checkerboard(), (31, 31), 15)


def dark_frame() -> np.ndarray:
    """Textured (non-blurry) but very low brightness frame."""
    rng = np.random.default_rng(1)
    frame = rng.integers(0, 20, (200, 200), dtype=np.uint8)
    cv2.rectangle(frame, (50, 50), (150, 150), 25, 2)
    return frame


def overexposed_frame() -> np.ndarray:
    """Textured (non-blurry) but blown-out bright frame."""
    rng = np.random.default_rng(2)
    frame = rng.integers(235, 255, (200, 200), dtype=np.uint8)
    cv2.rectangle(frame, (50, 50), (150, 150), 240, 2)
    return frame


def low_contrast_frame() -> np.ndarray:
    """Textured (non-blurry), mid-brightness, but narrow value range."""
    rng = np.random.default_rng(3)
    frame = rng.integers(120, 135, (200, 200), dtype=np.uint8)
    cv2.rectangle(frame, (50, 50), (150, 150), 128, 2)
    return frame


class FrameQualityGateTests(unittest.TestCase):
    def setUp(self):
        self._original_gate_env = os.environ.get("ENABLE_FRAME_QUALITY_GATE")
        os.environ["ENABLE_FRAME_QUALITY_GATE"] = "true"

    def tearDown(self):
        if self._original_gate_env is None:
            os.environ.pop("ENABLE_FRAME_QUALITY_GATE", None)
        else:
            os.environ["ENABLE_FRAME_QUALITY_GATE"] = self._original_gate_env

    def test_blurry_frame_rejected(self):
        result = analyze_frame_quality(blurry_frame())
        self.assertTrue(result["isBlurry"])
        self.assertEqual(result["frameQualityStatus"], "bad")
        self.assertEqual(result["qualityRejectionReason"], "low_quality_blurry_frame")

    def test_dark_frame_rejected(self):
        result = analyze_frame_quality(dark_frame())
        self.assertFalse(result["isBlurry"])
        self.assertTrue(result["isTooDark"])
        self.assertEqual(result["frameQualityStatus"], "bad")
        self.assertEqual(result["qualityRejectionReason"], "low_quality_dark_frame")

    def test_overexposed_frame_rejected(self):
        result = analyze_frame_quality(overexposed_frame())
        self.assertFalse(result["isBlurry"])
        self.assertFalse(result["isTooDark"])
        self.assertTrue(result["isOverexposed"])
        self.assertEqual(result["frameQualityStatus"], "bad")
        self.assertEqual(result["qualityRejectionReason"], "low_quality_overexposed_frame")

    def test_low_contrast_frame_rejected(self):
        result = analyze_frame_quality(low_contrast_frame())
        self.assertFalse(result["isBlurry"])
        self.assertFalse(result["isTooDark"])
        self.assertFalse(result["isOverexposed"])
        self.assertTrue(result["isLowContrast"])
        self.assertEqual(result["frameQualityStatus"], "bad")
        self.assertEqual(result["qualityRejectionReason"], "low_quality_low_contrast_frame")

    def test_clear_frame_is_good(self):
        result = analyze_frame_quality(clear_frame())
        self.assertFalse(result["isBlurry"])
        self.assertFalse(result["isTooDark"])
        self.assertFalse(result["isOverexposed"])
        self.assertFalse(result["isLowContrast"])
        self.assertEqual(result["frameQualityStatus"], "good")
        self.assertIsNone(result["qualityRejectionReason"])

    def test_empty_frame_is_rejected(self):
        result = analyze_frame_quality(None)
        self.assertEqual(result["frameQualityStatus"], "bad")
        self.assertIsNotNone(result["qualityRejectionReason"])

    def test_gate_disabled_forces_good_status_but_keeps_scores(self):
        os.environ["ENABLE_FRAME_QUALITY_GATE"] = "false"
        result = analyze_frame_quality(blurry_frame())
        self.assertTrue(result["isBlurry"])  # diagnostic flag still reported
        self.assertEqual(result["frameQualityStatus"], "good")  # but gate bypassed
        self.assertIsNone(result["qualityRejectionReason"])


if __name__ == "__main__":
    unittest.main()
