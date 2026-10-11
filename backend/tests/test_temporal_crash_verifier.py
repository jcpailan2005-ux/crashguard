import unittest

from backend.services.crash_event_state import CrashEventManager
from backend.services.temporal_crash_verifier import (
    TemporalCrashConfig,
    TemporalCrashVerifier,
)
from backend.services.vehicle_tracking import TrackState


FRAME_WIDTH = 1000
FRAME_HEIGHT = 1000


def box_from_center(x, y, width=0.12, height=0.10):
    return (
        (x - width / 2) * FRAME_WIDTH,
        (y - height / 2) * FRAME_HEIGHT,
        (x + width / 2) * FRAME_WIDTH,
        (y + height / 2) * FRAME_HEIGHT,
    )


class SyntheticScene:
    def __init__(self, verifier=None, camera_id="CAM-TEST"):
        self.camera_id = camera_id
        self.verifier = verifier or TemporalCrashVerifier(
            TemporalCrashConfig(
                min_track_history=3,
                min_closing_observations=3,
                post_contact_min_observations=2,
                pair_retention_seconds=2.0,
            )
        )
        self.tracks = {}

    def frame(self, timestamp, positions, classifier_score=0.95, sizes=None):
        active = []
        sizes = sizes or {}
        for track_id, (x, y) in positions.items():
            track = self.tracks.get(track_id)
            if track is None:
                track = TrackState.create(
                    track_id=track_id,
                    camera_id=self.camera_id,
                    class_id=2,
                    class_name="car",
                    history_size=20,
                    timestamp=timestamp,
                )
                self.tracks[track_id] = track
            width, height = sizes.get(track_id, (0.12, 0.10))
            bbox = box_from_center(x, y, width, height)
            track.add_observation(
                timestamp=timestamp,
                bbox=bbox,
                confidence=0.9,
                frame_width=FRAME_WIDTH,
                frame_height=FRAME_HEIGHT,
            )
            active.append(track)
        return self.verifier.analyze(
            self.camera_id,
            active,
            classifier_score=classifier_score,
            frame_width=FRAME_WIDTH,
            frame_height=FRAME_HEIGHT,
            timestamp=timestamp,
        )


def rear_end_sequence(scene, classifier_score=0.95):
    decisions = []
    positions_a = [0.18, 0.28, 0.38, 0.47, 0.535, 0.55, 0.55, 0.55, 0.55]
    for index, x_a in enumerate(positions_a):
        decisions.append(
            scene.frame(
                index * 0.5,
                {1: (x_a, 0.50), 2: (0.62, 0.50)},
                classifier_score=classifier_score,
            )
        )
    return decisions


class TemporalCrashVerifierTests(unittest.TestCase):
    def test_close_following_is_candidate_only(self):
        scene = SyntheticScene()
        decisions = []
        for index in range(9):
            x = 0.18 + index * 0.035
            decisions.append(scene.frame(index * 0.5, {1: (x, 0.5), 2: (x + 0.11, 0.5)}))
        self.assertTrue(any(item.is_candidate for item in decisions))
        self.assertFalse(any(item.is_verified for item in decisions))

    def test_stopped_visual_overlap_is_not_a_crash(self):
        scene = SyntheticScene()
        decisions = [
            scene.frame(index * 0.5, {1: (0.50, 0.50), 2: (0.54, 0.50)})
            for index in range(8)
        ]
        self.assertFalse(any(item.is_verified for item in decisions))
        self.assertFalse(decisions[-1].evidence["approach_detected"])

    def test_lane_merge_continuing_normally_is_rejected(self):
        scene = SyntheticScene()
        decisions = []
        for index in range(10):
            x = 0.15 + index * 0.055
            y_b = max(0.51, 0.68 - index * 0.025)
            decisions.append(scene.frame(index * 0.5, {1: (x, 0.50), 2: (x + 0.08, y_b)}))
        self.assertFalse(any(item.is_verified for item in decisions))

    def test_near_miss_without_post_contact_disruption_is_rejected(self):
        scene = SyntheticScene()
        decisions = []
        for index in range(10):
            x_a = 0.18 + index * 0.065
            y_b = 0.18 + index * 0.065
            decisions.append(scene.frame(index * 0.5, {1: (x_a, 0.47), 2: (0.50, y_b)}))
        self.assertTrue(any(item.evidence["approach_detected"] for item in decisions))
        self.assertFalse(any(item.is_verified for item in decisions))

    def test_rear_end_collision_is_verified(self):
        decisions = rear_end_sequence(SyntheticScene())
        verified = [item for item in decisions if item.is_verified]
        self.assertTrue(verified)
        self.assertEqual(verified[-1].involved_track_ids, (1, 2))
        self.assertTrue(verified[-1].evidence["contact_candidate"])
        self.assertGreaterEqual(verified[-1].score, 0.62)

    def test_side_impact_with_motion_disruption_is_verified(self):
        scene = SyntheticScene()
        decisions = []
        a_x = [0.15, 0.25, 0.35, 0.44, 0.49, 0.50, 0.50, 0.50]
        b_y = [0.15, 0.25, 0.35, 0.44, 0.49, 0.50, 0.50, 0.50]
        for index in range(len(a_x)):
            decisions.append(
                scene.frame(index * 0.5, {1: (a_x[index], 0.50), 2: (0.50, b_y[index])})
            )
        self.assertTrue(any(item.is_verified for item in decisions))

    def test_bbox_overlap_without_approach_is_never_verified(self):
        scene = SyntheticScene()
        decisions = [
            scene.frame(
                index * 0.5,
                {1: (0.45, 0.50), 2: (0.55, 0.50)},
                sizes={1: (0.35, 0.20), 2: (0.35, 0.20)},
            )
            for index in range(8)
        ]
        self.assertTrue(any(item.is_candidate for item in decisions))
        self.assertFalse(any(item.is_verified for item in decisions))

    def test_classifier_false_positive_cannot_verify_normal_motion(self):
        scene = SyntheticScene()
        decisions = []
        for index in range(8):
            x = 0.1 + index * 0.06
            decisions.append(
                scene.frame(index * 0.5, {1: (x, 0.4), 2: (x + 0.12, 0.4)}, classifier_score=0.999)
            )
        self.assertFalse(any(item.is_verified for item in decisions))

    def test_track_id_switch_alone_cannot_create_crash(self):
        scene = SyntheticScene()
        for index in range(3):
            scene.frame(index * 0.5, {1: (0.25 + index * 0.08, 0.5), 2: (0.65, 0.5)})
        switched = []
        for offset in range(3):
            switched.append(
                scene.frame(1.5 + offset * 0.5, {10: (0.50, 0.5), 2: (0.65, 0.5)})
            )
        self.assertFalse(any(item.is_verified for item in switched))

    def test_temporary_occlusion_does_not_create_false_collision(self):
        scene = SyntheticScene()
        for index in range(3):
            scene.frame(index * 0.5, {1: (0.20 + index * 0.04, 0.5), 2: (0.55, 0.5)})
        missing = scene.frame(1.5, {2: (0.55, 0.5)})
        returned = scene.frame(2.0, {1: (0.34, 0.5), 2: (0.55, 0.5)})
        self.assertFalse(missing.is_verified)
        self.assertFalse(returned.is_verified)

    def test_multiple_cameras_and_stale_pairs_are_isolated_and_bounded(self):
        verifier = TemporalCrashVerifier(
            TemporalCrashConfig(pair_retention_seconds=0.5, min_track_history=3)
        )
        camera_a = SyntheticScene(verifier, "CAM-A")
        camera_b = SyntheticScene(verifier, "CAM-B")
        for index in range(4):
            camera_a.frame(index * 0.1, {1: (0.4, 0.5), 2: (0.5, 0.5)})
        self.assertGreater(verifier.active_pair_count("CAM-A"), 0)
        self.assertEqual(verifier.active_pair_count("CAM-B"), 0)
        camera_b.frame(2.0, {3: (0.1, 0.1)})
        verifier.analyze(
            "CAM-A", [], classifier_score=0.0, frame_width=1000, frame_height=1000, timestamp=2.0
        )
        self.assertEqual(verifier.active_pair_count("CAM-A"), 0)
        self.assertEqual(verifier.active_pair_count("CAM-B"), 0)

    def test_independent_crash_does_not_change_other_camera_candidate(self):
        verifier = TemporalCrashVerifier()
        camera_a = SyntheticScene(verifier, "CAM-A")
        camera_b = SyntheticScene(verifier, "CAM-B")
        a_decisions = [
            camera_a.frame(index * 0.5, {1: (0.45, 0.5), 2: (0.54, 0.5)})
            for index in range(9)
        ]
        b_decisions = rear_end_sequence(camera_b)
        self.assertFalse(any(item.is_verified for item in a_decisions))
        self.assertTrue(any(item.is_verified for item in b_decisions))
        self.assertGreater(verifier.active_pair_count("CAM-A"), 0)
        self.assertGreater(verifier.active_pair_count("CAM-B"), 0)
        verifier.reset_camera("CAM-A")
        self.assertEqual(verifier.active_pair_count("CAM-A"), 0)
        self.assertGreater(verifier.active_pair_count("CAM-B"), 0)

    def test_verified_crash_remains_one_phase1_event(self):
        scene = SyntheticScene()
        manager = CrashEventManager(
            required_positive_observations=3,
            temporal_window_seconds=5.0,
            clear_consecutive_negatives=2,
            clear_seconds=0.0,
            cooldown_seconds=0.0,
        )
        persist_claims = []
        event_ids = []
        for index, decision in enumerate(rear_end_sequence(scene)):
            observation = manager.observe(
                "CAM-EVENT",
                positive=decision.is_verified,
                interaction_candidate=decision.is_candidate,
                classifier_score=decision.evidence["classifier_score"],
                now=index * 0.5,
            )
            if observation.detector_event_id:
                event_ids.append(observation.detector_event_id)
            if observation.should_persist:
                persist_claims.append(observation)
                manager.mark_persisted(
                    "CAM-EVENT", observation.detector_event_id, "CASE-1", now=index * 0.5 + 0.01
                )
        self.assertEqual(len(persist_claims), 1)
        self.assertEqual(len(set(event_ids)), 1)

    def test_temporal_config_rejects_impossible_values(self):
        with self.assertRaises(ValueError):
            TemporalCrashConfig(min_track_history=1)
        with self.assertRaises(ValueError):
            TemporalCrashConfig(temporal_crash_threshold=1.5)

    def test_long_sequence_keeps_track_and_pair_histories_bounded(self):
        config = TemporalCrashConfig(distance_history_size=8)
        scene = SyntheticScene(TemporalCrashVerifier(config), "CAM-LONG")
        for index in range(250):
            x = 0.2 + (index % 20) * 0.005
            scene.frame(index * 0.25, {1: (x, 0.5), 2: (x + 0.10, 0.5)})
        interactions = scene.verifier.get_interactions("CAM-LONG")
        self.assertEqual(len(interactions), 1)
        self.assertLessEqual(len(interactions[0].distance_history), 8)
        self.assertTrue(all(len(track.history) <= 20 for track in scene.tracks.values()))


if __name__ == "__main__":
    unittest.main()
