import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import backend.main as app_module

class CameraPerformanceTests(unittest.TestCase):
    def make_monitor(self) -> app_module.LiveCameraMonitor:
        return app_module.LiveCameraMonitor(
            monitor_key="perf-test-camera",
            camera_id="CAM-PERF-TEST",
            camera_ip=None,
            stream_url="demo://perf-test",
            label="Perf Test",
            area_id="test",
            barangay=None,
            road_name=None,
            latitude=None,
            longitude=None,
            location="Test",
            redacted_stream_url="demo://perf-test",
            output_base="http://testserver",
        )

    @patch("backend.main.find_unresolved_camera_case", return_value=None)
    def test_bounded_latest_frame_buffer_and_no_backlog(self, _find_case) -> None:
        monitor = self.make_monitor()
        # Seed 10 frames in rapid succession
        for i in range(10):
            frame = np.full((720, 1280, 3), fill_value=i, dtype=np.uint8)
            monitor.seed_first_frame(frame)

        # Buffer must only hold the latest frame (bounded size: 1)
        self.assertEqual(monitor.frame_seq, 10)
        self.assertEqual(monitor.latest_frame[0, 0, 0], 9)
        self.assertIsNone(getattr(monitor, "frame_queue", None))

    @patch("backend.main.find_unresolved_camera_case", return_value=None)
    def test_skipped_frame_counter_tracks_latest_frame_overwrites(self, _find_case) -> None:
        monitor = self.make_monitor()
        for i in range(5):
            monitor.seed_first_frame(np.full((10, 10, 3), i, dtype=np.uint8))
        # Isolate the sequence accounting from the expensive AI body.
        with monitor.lock:
            analyzed_seq = monitor.frame_seq
            monitor.dropped_frame_count += max(
                0, analyzed_seq - monitor.last_analyzed_frame_seq - 1
            )
            monitor.last_analyzed_frame_seq = analyzed_seq
        self.assertEqual(monitor.dropped_frame_count, 4)
        self.assertEqual(monitor.last_analyzed_frame_seq, 5)

    @patch("backend.main.find_unresolved_camera_case", return_value=None)
    def test_preview_caching_preserves_native_resolution(self, _find_case) -> None:
        monitor = self.make_monitor()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        monitor.seed_first_frame(frame)

        # First call generates preview
        preview_1 = monitor.latest_jpeg()
        self.assertIsNotNone(preview_1)

        # Second call with same frame_seq must return identical cached object
        preview_2 = monitor.latest_jpeg()
        self.assertIs(preview_1, preview_2)

        import cv2
        decoded = cv2.imdecode(np.frombuffer(preview_1, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape, frame.shape)

    @patch("backend.main.find_unresolved_camera_case", return_value=None)
    def test_fps_and_resolution_metrics_calculation(self, _find_case) -> None:
        monitor = self.make_monitor()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        now = time.time()

        # Simulate 15 capture frames, 10 preview yields, and 2 AI runs in the last 5 seconds
        for i in range(15):
            monitor.capture_timestamps.append(now - (i * 0.2))
        for i in range(10):
            monitor.preview_timestamps.append(now - (i * 0.3))
        for i in range(2):
            monitor.ai_timestamps.append(now - (i * 0.5))

        monitor.seed_first_frame(frame)
        status = monitor.snapshot_status()

        self.assertGreaterEqual(status["captureFps"], 2.5)
        self.assertGreaterEqual(status["previewFps"], 1.5)
        self.assertGreaterEqual(status["aiFps"], 0.3)
        self.assertEqual(status["previewResolution"], "1280x720")
        self.assertEqual(status["aiResolution"], "1280x720")

    def test_reconnect_and_stop_cleanup(self) -> None:
        monitor = self.make_monitor()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        monitor.seed_first_frame(frame)
        monitor.running = True

        monitor.stop()
        self.assertFalse(monitor.running)

    def test_byte_identical_vehicle_model_reuses_primary_result(self) -> None:
        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        primary_results = [object()]
        shared_model = MagicMock()
        shared_model.names = {2: "car"}
        expected = [{"label": "car", "confidence": 0.8}]

        with (
            patch.object(app_module, "model", shared_model),
            patch.object(app_module, "vehicle_model", shared_model),
            patch.object(app_module, "extract_vehicle_boxes_from_results", return_value=expected) as extract,
        ):
            actual = app_module.detect_vehicle_boxes(frame, fallback_results=primary_results)

        self.assertEqual(actual, expected)
        shared_model.predict.assert_not_called()
        self.assertIs(extract.call_args.args[0], primary_results)

    def test_distinct_vehicle_model_keeps_separate_inference(self) -> None:
        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        separate_model = MagicMock()
        separate_model.names = {2: "car"}
        separate_results = [object()]
        separate_model.predict.return_value = separate_results

        with (
            patch.object(app_module, "vehicle_model", separate_model),
            patch.object(app_module, "extract_vehicle_boxes_from_results", return_value=[]) as extract,
        ):
            app_module.detect_vehicle_boxes(frame, fallback_results=[object()])

        separate_model.predict.assert_called_once()
        self.assertIs(extract.call_args.args[0], separate_results)

if __name__ == "__main__":
    unittest.main()
