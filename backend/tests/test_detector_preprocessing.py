import unittest
from unittest.mock import MagicMock, patch

import numpy as np

import backend.main as app_module

from backend.services.detector_preprocessing import (
    DetectorInputConfig,
    expected_letterbox_shape,
    map_boxes_to_source,
    prepare_detector_frame,
    safe_target_size,
    safe_yolo_imgsz,
)


class DetectorPreprocessingTests(unittest.TestCase):
    def test_configurable_imgsz_accepts_supported_values(self):
        self.assertEqual(safe_yolo_imgsz(640), 640)
        self.assertEqual(safe_yolo_imgsz("768"), 768)
        self.assertEqual(safe_yolo_imgsz(960), 960)

    def test_invalid_configuration_falls_back_safely(self):
        self.assertEqual(safe_yolo_imgsz("bad"), 640)
        self.assertEqual(safe_yolo_imgsz(641), 640)
        self.assertEqual(safe_yolo_imgsz(2048), 640)
        self.assertIsNone(safe_target_size(-1, 540))
        self.assertIsNone(safe_target_size(960, 0))

    def test_native_mode_has_no_duplicate_resize_or_mutation(self):
        frame = np.arange(240 * 320 * 3, dtype=np.uint8).reshape(240, 320, 3)
        before = frame.copy()
        prepared = prepare_detector_frame(frame, DetectorInputConfig())
        self.assertIs(prepared.frame, frame)
        self.assertFalse(prepared.resized)
        np.testing.assert_array_equal(frame, before)

    def test_explicit_bounds_preserve_aspect_ratio(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        config = DetectorInputConfig.from_values(640, 360, 640)
        prepared = prepare_detector_frame(frame, config)
        self.assertEqual(prepared.frame.shape[:2], (360, 480))
        self.assertAlmostEqual(
            prepared.detector_width / prepared.detector_height,
            prepared.source_width / prepared.source_height,
        )

    def test_bounding_boxes_map_back_to_source_coordinates(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        prepared = prepare_detector_frame(
            frame, DetectorInputConfig.from_values(320, 240, 640)
        )
        mapped = map_boxes_to_source(
            [{"x": 50, "y": 25, "width": 100, "height": 50, "box": [50, 25, 150, 75]}],
            prepared,
        )[0]
        self.assertEqual(mapped["x"], 100)
        self.assertEqual(mapped["y"], 50)
        self.assertEqual(mapped["width"], 200)
        self.assertEqual(mapped["height"], 100)
        self.assertEqual(mapped["box"], [100, 50, 300, 150])

    def test_expected_letterbox_matches_verified_baseline(self):
        self.assertEqual(expected_letterbox_shape(640, 360, 640), (384, 640))
        self.assertEqual(expected_letterbox_shape(960, 540, 768), (448, 768))

    def test_live_vehicle_detector_forwards_configured_imgsz(self):
        fake_model = MagicMock()
        fake_model.predict.return_value = []
        fake_model.names = {}
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        with patch.object(app_module, "vehicle_model", fake_model):
            self.assertEqual(app_module.detect_vehicle_boxes(frame, imgsz=768), [])
        fake_model.predict.assert_called_once_with(
            frame,
            verbose=False,
            imgsz=768,
        )

    def test_vehicle_filter_override_does_not_change_model_inference_threshold(self):
        # The current runtime uses the loaded model's inference defaults, then
        # applies min_confidence during box extraction. The removed raw-floor
        # constant belonged to an older pipeline; reintroducing it would alter
        # detections. Protect both current boundaries without changing weights
        # or thresholds to satisfy a stale test expectation.
        fake_model = MagicMock()
        fake_model.predict.return_value = []
        fake_model.names = {}
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        with patch.object(app_module, "vehicle_model", fake_model), \
             patch.object(app_module, "extract_vehicle_boxes_from_results", return_value=[]) as extract:
            app_module.detect_vehicle_boxes(frame, min_confidence=0.15, imgsz=768)
        fake_model.predict.assert_called_once_with(frame, verbose=False, imgsz=768)
        extract.assert_called_once_with([], {}, frame, min_confidence=0.15)


if __name__ == "__main__":
    unittest.main()
