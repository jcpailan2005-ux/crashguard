import unittest
from backend.services.crash_aftermath_detector import (
    AftermathConfig,
    CrashAftermathDetector,
    estimate_scene_abnormality,
)
from backend.services.crash_evidence_resolver import resolve_crash_evidence
from backend.services.temporal_crash_verifier import TemporalCrashDecision
from backend.services.vehicle_tracking import TrackState
from backend.main import evaluate_crash_case_decision


def create_stationary_track(track_id=1, camera_id="CAM-TEST", history_len=5, bbox=(100, 100, 300, 250)):
    track = TrackState.create(
        track_id=track_id,
        camera_id=camera_id,
        class_id=2,
        class_name="car",
        history_size=20,
        timestamp=0.0,
    )
    for i in range(history_len):
        track.add_observation(
            timestamp=0.5 * i,
            bbox=bbox,
            confidence=0.9,
            frame_width=1280,
            frame_height=720,
        )
    return track


def create_moving_track(track_id=1, camera_id="CAM-TEST", history_len=5, start_x=100, end_x=500):
    track = TrackState.create(
        track_id=track_id,
        camera_id=camera_id,
        class_id=2,
        class_name="car",
        history_size=20,
        timestamp=0.0,
    )
    for i in range(history_len):
        x = start_x + (end_x - start_x) * (i / max(1, history_len - 1))
        track.add_observation(
            timestamp=0.5 * i,
            bbox=(x, 100, x + 200, 250),
            confidence=0.9,
            frame_width=1280,
            frame_height=720,
        )
    return track


class DualPathAftermathTests(unittest.TestCase):
    def setUp(self):
        self.config = AftermathConfig(
            min_classifier_score=0.80,
            high_confidence_classifier_threshold=0.90,
            minimum_score=0.80,
            required_positive_frames=3,
            window_seconds=10.0,
            minimum_persistence_seconds=1.0,
            minimum_track_history=3,
            minimum_abnormality_score=0.35,
        )
        self.detector = CrashAftermathDetector(self.config)

    def test_1_high_confidence_static_crash_image(self):
        """A high confidence static crash image qualifies for review without motion vectors."""
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.95,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=False,
            consecutive_positive_frames=0,
            active_case_exists=False,
            cooldown_ready=True,
            is_static_image=True,
        )
        self.assertTrue(should_create)
        self.assertIsNone(rejection)
        self.assertEqual(decision, "possible_crash")

    def test_2_static_non_crash_vehicle_image(self):
        """A normal non-crash vehicle image is rejected as non_accident."""
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="non_accident",
            crash_confidence=0.15,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=False,
            consecutive_positive_frames=0,
            active_case_exists=False,
            cooldown_ready=True,
            is_static_image=True,
        )
        self.assertFalse(should_create)
        self.assertEqual(rejection, "non_accident")
        self.assertEqual(decision, "ignored")

    def test_3_upright_crashed_cars_do_not_require_rollover(self):
        """Upright crashed cars (width > height) qualify under high-confidence aftermath."""
        # Both cars are upright (aspect ratio = 200/100 = 2.0 > 1.15)
        track1 = create_stationary_track(track_id=1, bbox=(100, 100, 300, 200))
        track2 = create_stationary_track(track_id=2, bbox=(250, 100, 450, 200))

        # Feed 3 consecutive observations
        dec = None
        for i in range(3):
            dec = self.detector.observe(
                "CAM-TEST",
                classifier_score=0.95,
                vehicle_count=2,
                active_tracks=[track1, track2],
                scene_valid=True,
                frame_quality_status="good",
                scene_abnormality_score=0.0,  # Zero rollover geometry
                timestamp=1.0 + i * 0.5,
            )
        self.assertTrue(dec.review_candidate)
        self.assertEqual(dec.state, "REVIEW_CANDIDATE")

    def test_4_single_vehicle_aftermath(self):
        """Single vehicle crash against a wall/barrier qualifies for review."""
        track = create_stationary_track(track_id=1, bbox=(100, 100, 300, 250))
        dec = None
        for i in range(3):
            dec = self.detector.observe(
                "CAM-TEST",
                classifier_score=0.94,
                vehicle_count=1,
                active_tracks=[track],
                scene_valid=True,
                frame_quality_status="good",
                scene_abnormality_score=0.0,
                timestamp=1.0 + i * 0.5,
            )
        self.assertTrue(dec.review_candidate)

    def test_5_multi_vehicle_aftermath_without_stable_multiple_bytetrack_ids(self):
        """YOLO boxes provide proximity/overlap even if ByteTrack drops to 1 track ID."""
        track1 = create_stationary_track(track_id=1, bbox=(100, 100, 300, 200))
        raw_boxes = [
            {"x": 100, "y": 100, "width": 200, "height": 100},
            {"x": 220, "y": 100, "width": 200, "height": 100},  # Overlapping box
        ]
        abnormality = estimate_scene_abnormality(
            active_tracks=[track1],
            detection_boxes=raw_boxes,
        )
        self.assertGreater(abnormality, 0.35)

    def test_6_yolo_box_proximity_evidence(self):
        """Direct bounding box contact produces strong contact score."""
        boxes = [
            {"box": [100, 100, 300, 200]},
            {"box": [250, 100, 450, 200]},
        ]
        score = estimate_scene_abnormality(detection_boxes=boxes)
        self.assertGreater(score, 0.40)

    def test_7_temporal_crash_still_confirms_normally(self):
        """Dynamic temporal verification confirms crash with highest priority."""
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.85,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=True,
            consecutive_positive_frames=3,
            active_case_exists=False,
            cooldown_ready=True,
            temporal_verified=True,
        )
        self.assertTrue(should_create)
        self.assertIsNone(rejection)
        self.assertEqual(decision, "confirmed_crash")

    def test_8_temporal_failure_does_not_block_valid_aftermath_review(self):
        """Temporal motion failure does NOT discard a valid aftermath review candidate."""
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.95,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=False,
            consecutive_positive_frames=3,
            active_case_exists=False,
            cooldown_ready=True,
            temporal_verified=False,
            aftermath_candidate=True,
        )
        self.assertTrue(should_create)
        self.assertIsNone(rejection)
        self.assertEqual(decision, "possible_crash_aftermath")

    def test_9_aftermath_does_not_auto_confirm_incident(self):
        """Aftermath candidates must NOT receive confirmed_crash tier automatically."""
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.96,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=False,
            consecutive_positive_frames=3,
            active_case_exists=False,
            cooldown_ready=True,
            temporal_verified=False,
            aftermath_candidate=True,
        )
        self.assertNotEqual(decision, "confirmed_crash")
        self.assertEqual(decision, "possible_crash_aftermath")

    def test_10_duplicate_event_prevention(self):
        """Active existing case blocks duplicate case creation."""
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.95,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=True,
            consecutive_positive_frames=3,
            active_case_exists=True,
            cooldown_ready=True,
            temporal_verified=True,
        )
        self.assertFalse(should_create)
        self.assertEqual(rejection, "active_case_exists")
        self.assertEqual(decision, "duplicate_active_case")

    def test_11_traffic_queue_negative(self):
        """Moving traffic queues do NOT qualify for aftermath."""
        moving_track = create_moving_track(track_id=1, start_x=100, end_x=400)
        dec = self.detector.observe(
            "CAM-TEST",
            classifier_score=0.20,
            vehicle_count=2,
            active_tracks=[moving_track],
            scene_valid=True,
            frame_quality_status="good",
            scene_abnormality_score=0.0,
            timestamp=1.0,
        )
        self.assertFalse(dec.review_candidate)
        self.assertEqual(dec.reason, "normal_vehicle_motion")

    def test_12_parked_vehicles_negative(self):
        """Parked cars with low classifier score are rejected."""
        track = create_stationary_track(track_id=1)
        dec = self.detector.observe(
            "CAM-TEST",
            classifier_score=0.05,
            vehicle_count=2,
            active_tracks=[track],
            scene_valid=True,
            frame_quality_status="good",
            scene_abnormality_score=0.0,
            timestamp=1.0,
        )
        self.assertFalse(dec.review_candidate)
        self.assertEqual(dec.reason, "classifier_below_threshold")

    def test_13_tow_repair_negative(self):
        """Stationary vehicles without high crash classifier score are rejected."""
        track = create_stationary_track(track_id=1)
        dec = self.detector.observe(
            "CAM-TEST",
            classifier_score=0.72,  # Below 0.80 min_classifier_score
            vehicle_count=2,
            active_tracks=[track],
            scene_valid=True,
            frame_quality_status="good",
            scene_abnormality_score=0.0,
            timestamp=1.0,
        )
        self.assertFalse(dec.review_candidate)
        self.assertEqual(dec.reason, "classifier_below_threshold")

    def test_14_static_image_does_not_require_temporal_motion(self):
        """Static image analysis does not fail on motionValid=False."""
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.92,
            vehicle_count=1,
            person_count=0,
            scene_valid=True,
            motion_valid=False,
            consecutive_positive_frames=0,
            active_case_exists=False,
            cooldown_ready=True,
            is_static_image=True,
        )
        self.assertTrue(should_create)
        self.assertIsNone(rejection)
        self.assertEqual(decision, "possible_crash")


if __name__ == "__main__":
    unittest.main()
