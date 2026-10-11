import unittest

from backend.main import camera_client_payload, can_access_camera, stream_source_label


class CameraSecurityTests(unittest.TestCase):
    def test_monitor_access_requires_both_read_and_monitor_permissions(self):
        camera = {"cameraId": "CAM-1"}
        self.assertTrue(
            can_access_camera(
                {"role": "dispatcher", "permissions": ["cameras.view", "cameras.monitor"]},
                camera,
            )
        )
        self.assertFalse(can_access_camera({"role": "responder", "permissions": []}, camera))
        self.assertFalse(can_access_camera({"role": "dispatcher", "permissions": ["cameras.view"]}, camera))

    def test_camera_payload_never_returns_rtsp_credentials(self):
        payload = camera_client_payload(
            {
                "cameraId": "CAM-1",
                "cameraIp": None,
                "streamUrl": "rtsp://operator:secret-password@192.168.10.12:554/stream1",
            }
        )
        self.assertNotIn("streamUrl", payload)
        self.assertTrue(payload["streamConfigured"])
        self.assertEqual(payload["streamSourceLabel"], "CCTV (192.168.10.12:554)")
        self.assertNotIn("operator", str(payload))
        self.assertNotIn("secret-password", str(payload))

    def test_stream_label_redacts_user_info(self):
        self.assertEqual(
            stream_source_label("rtsps://admin:p%40ss@camera.local:8554/live"),
            "CCTV (camera.local:8554)",
        )


if __name__ == "__main__":
    unittest.main()
