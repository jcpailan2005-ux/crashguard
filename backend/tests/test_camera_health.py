import time
import unittest
from unittest.mock import patch

import numpy as np

import backend.main as app_module


class CameraHealthTests(unittest.TestCase):
    def make_monitor(self) -> app_module.LiveCameraMonitor:
        return app_module.LiveCameraMonitor(
            monitor_key="health-test-camera",
            camera_id="CAM-HEALTH-TEST",
            camera_ip=None,
            stream_url="demo://health-test",
            label="Health Test",
            area_id="test",
            barangay=None,
            road_name=None,
            latitude=None,
            longitude=None,
            location="Test",
            redacted_stream_url="demo://health-test",
            output_base="http://testserver",
        )

    @patch("backend.main.find_unresolved_camera_case", return_value=None)
    def test_snapshot_exposes_live_health_metrics(self, _find_case) -> None:
        monitor = self.make_monitor()
        monitor.seed_first_frame(np.zeros((48, 64, 3), dtype=np.uint8))
        status = monitor.snapshot_status()

        self.assertEqual(status["cameraHealth"], "LIVE")
        self.assertIsInstance(status["frameAgeMs"], int)
        self.assertIsNotNone(status["lastConnectionAt"])
        self.assertEqual(status["reconnectCount"], 0)
        self.assertEqual(status["staleFrameEvents"], 0)

    @patch("backend.main.find_unresolved_camera_case", return_value=None)
    def test_stale_frame_is_not_reported_live_and_counts_once(self, _find_case) -> None:
        monitor = self.make_monitor()
        monitor.seed_first_frame(np.zeros((48, 64, 3), dtype=np.uint8))
        monitor.status = "monitoring-live"
        monitor.last_frame_at = (
            time.time() - app_module.LIVE_CAMERA_FREEZE_TIMEOUT_SECONDS - 1.0
        )

        first = monitor.snapshot_status()
        second = monitor.snapshot_status()

        self.assertEqual(first["cameraHealth"], "STALE")
        self.assertFalse(first["cameraConnected"])
        self.assertFalse(first["monitoringLive"])
        self.assertEqual(first["staleFrameEvents"], 1)
        self.assertEqual(second["staleFrameEvents"], 1)


if __name__ == "__main__":
    unittest.main()
