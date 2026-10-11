import unittest

from backend.services.vehicle_tracking import TrackingConfig, VehicleTrackingService


def detection(x1, y1, x2, y2, confidence=0.9, class_id=2, label="car"):
    return {
        "x": x1,
        "y": y1,
        "width": x2 - x1,
        "height": y2 - y1,
        "confidence": confidence,
        "classId": class_id,
        "label": label,
    }


class VehicleTrackingServiceTests(unittest.TestCase):
    def setUp(self):
        self.config = TrackingConfig(
            min_confidence=0.2,
            track_high_threshold=0.25,
            track_low_threshold=0.1,
            new_track_threshold=0.25,
            track_buffer_frames=10,
            max_age_seconds=1.0,
            reset_gap_seconds=5.0,
            history_size=4,
            nominal_fps=2,
        )
        self.service = VehicleTrackingService(self.config)

    def test_bytetrack_keeps_stable_id_and_bounds_history(self):
        ids = []
        result = None
        for index in range(7):
            result = self.service.update(
                "CAM-1",
                [detection(100 + index * 3, 100, 180 + index * 3, 160)],
                frame_width=640,
                frame_height=360,
                timestamp=index * 0.5,
            )
            self.assertEqual(result.tracker_name, "ByteTrack")
            self.assertEqual(len(result.active_tracks), 1)
            ids.append(result.active_tracks[0].track_id)

        self.assertEqual(len(set(ids)), 1)
        self.assertLessEqual(len(result.active_tracks[0].history), 4)

    def test_temporary_occlusion_does_not_create_a_new_identity(self):
        first = self.service.update(
            "CAM-OCC",
            [detection(100, 100, 180, 160)],
            frame_width=640,
            frame_height=360,
            timestamp=0.0,
        )
        original_id = first.active_tracks[0].track_id
        missing = self.service.update(
            "CAM-OCC", [], frame_width=640, frame_height=360, timestamp=0.5
        )
        self.assertEqual(missing.active_tracks, ())

        returned = self.service.update(
            "CAM-OCC",
            [detection(106, 100, 186, 160)],
            frame_width=640,
            frame_height=360,
            timestamp=1.0,
        )
        self.assertEqual(returned.active_tracks[0].track_id, original_id)

    def test_stale_tracks_expire_and_reset_clears_camera(self):
        self.service.update(
            "CAM-STALE",
            [detection(100, 100, 180, 160)],
            frame_width=640,
            frame_height=360,
            timestamp=0.0,
        )
        result = self.service.update(
            "CAM-STALE", [], frame_width=640, frame_height=360, timestamp=1.5
        )
        self.assertEqual(result.retained_track_count, 0)

        self.service.update(
            "CAM-STALE",
            [detection(200, 100, 280, 160)],
            frame_width=640,
            frame_height=360,
            timestamp=2.0,
        )
        self.service.reset_camera("CAM-STALE")
        self.assertEqual(self.service.get_tracks("CAM-STALE"), ())

    def test_camera_state_is_isolated(self):
        a = self.service.update(
            "CAM-A",
            [detection(20, 20, 80, 80)],
            frame_width=640,
            frame_height=360,
            timestamp=0.0,
        )
        b = self.service.update(
            "CAM-B",
            [detection(400, 200, 470, 270)],
            frame_width=640,
            frame_height=360,
            timestamp=0.0,
        )
        self.assertEqual(a.active_tracks[0].camera_id, "CAM-A")
        self.assertEqual(b.active_tracks[0].camera_id, "CAM-B")
        self.assertEqual(len(self.service.get_tracks("CAM-A")), 1)
        self.assertEqual(len(self.service.get_tracks("CAM-B")), 1)

    def test_long_timestamp_gap_resets_motion_history(self):
        first = self.service.update(
            "CAM-GAP",
            [detection(10, 10, 70, 70)],
            frame_width=640,
            frame_height=360,
            timestamp=0.0,
        )
        second = self.service.update(
            "CAM-GAP",
            [detection(400, 200, 470, 270)],
            frame_width=640,
            frame_height=360,
            timestamp=10.0,
        )
        self.assertTrue(second.reset_due_to_gap)
        self.assertEqual(len(second.active_tracks[0].history), 1)
        self.assertNotEqual(
            first.active_tracks[0].track_id, second.active_tracks[0].track_id
        )

    def test_camera_registry_is_bounded(self):
        service = VehicleTrackingService(
            TrackingConfig(max_cameras=1, min_confidence=0.2)
        )
        service.update(
            "CAM-OLD",
            [detection(10, 10, 70, 70)],
            frame_width=640,
            frame_height=360,
            timestamp=0.0,
        )
        service.update(
            "CAM-NEW",
            [detection(20, 20, 80, 80)],
            frame_width=640,
            frame_height=360,
            timestamp=1.0,
        )
        self.assertEqual(service.get_tracks("CAM-OLD"), ())
        self.assertEqual(len(service.get_tracks("CAM-NEW")), 1)


if __name__ == "__main__":
    unittest.main()
