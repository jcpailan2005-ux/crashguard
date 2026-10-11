import unittest

from backend.services.logical_vehicle_continuity import (
    LogicalContinuityConfig,
    LogicalVehicleContinuityService,
)
from backend.services.temporal_crash_verifier import TemporalCrashVerifier
from backend.services.vehicle_tracking import TrackState


def detection(x, y, width=80, height=50, *, label="car", state="TRUSTED", supported=False):
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "confidence": 0.8 if state == "TRUSTED" else 0.3,
        "label": label,
        "detectionState": state,
        "candidateSupported": supported,
    }


def raw_track(track_id, x, y, width=80, height=50, *, label="car", timestamp=0.0):
    track = TrackState.create(
        track_id=track_id,
        camera_id="cam",
        class_id=2,
        class_name=label,
        history_size=16,
        timestamp=timestamp,
    )
    track.add_observation(
        timestamp=timestamp,
        bbox=(x, y, x + width, y + height),
        confidence=0.8,
        frame_width=640,
        frame_height=360,
    )
    return track


class LogicalVehicleContinuityTests(unittest.TestCase):
    def setUp(self):
        self.config = LogicalContinuityConfig(max_handoff_seconds=1.0)
        self.service = LogicalVehicleContinuityService(self.config)

    def update(self, tracks, detections, timestamp, collision_pair_boxes=()):
        return self.service.update(
            "cam",
            tracks,
            detections,
            frame_width=640,
            frame_height=360,
            timestamp=timestamp,
            collision_pair_boxes=collision_pair_boxes,
        )

    def test_stable_raw_track_keeps_logical_id(self):
        first = self.update([raw_track(3, 100, 100)], [detection(100, 100)], 0.0)
        second = self.update([raw_track(3, 105, 100, timestamp=0.2)], [detection(105, 100)], 0.2)
        self.assertEqual(first.active_tracks[0].logical_vehicle_id, second.active_tracks[0].logical_vehicle_id)

    def test_legitimate_raw_id_switch_preserves_logical_id(self):
        first = self.update([raw_track(21, 100, 100)], [detection(100, 100)], 0.0)
        self.update([], [], 0.2)
        switched = self.update([raw_track(28, 108, 101, timestamp=0.4)], [detection(108, 101)], 0.4)
        self.assertEqual(first.active_tracks[0].logical_vehicle_id, switched.active_tracks[0].logical_vehicle_id)
        self.assertEqual(switched.accepted_handoffs, 1)

    def test_supported_candidate_preserves_provisional_identity(self):
        candidate = detection(200, 100, state="CANDIDATE", supported=True, label="motorcycle")
        first = self.update([], [candidate], 0.0, (candidate,))
        continued = detection(204, 101, state="CANDIDATE", supported=True, label="motorcycle")
        second = self.update([], [continued], 0.3, (continued,))
        self.assertEqual(first.active_tracks[0].logical_vehicle_id, second.active_tracks[0].logical_vehicle_id)
        self.assertEqual(second.active_tracks[0].state, "PROVISIONAL")
        self.assertFalse(second.active_tracks[0].motion_observed)

    def test_provisional_promotes_to_track_without_new_identity(self):
        candidate = detection(200, 100, state="CANDIDATE", supported=True)
        first = self.update([], [candidate], 0.0, (candidate,))
        promoted = self.update([raw_track(9, 203, 101, timestamp=0.3)], [detection(203, 101)], 0.3)
        self.assertEqual(first.active_tracks[0].logical_vehicle_id, promoted.active_tracks[0].logical_vehicle_id)
        self.assertEqual(promoted.active_tracks[0].state, "TRACKED")
        self.assertEqual(promoted.active_tracks[0].raw_track_id, 9)

    def test_expired_candidate_does_not_reattach(self):
        candidate = detection(200, 100, state="CANDIDATE", supported=True)
        first = self.update([], [candidate], 0.0, (candidate,))
        later_candidate = detection(201, 100, state="CANDIDATE", supported=True)
        later = self.update([], [later_candidate], 1.1, (later_candidate,))
        self.assertNotEqual(first.active_tracks[0].logical_vehicle_id, later.active_tracks[0].logical_vehicle_id)
        self.assertEqual(later.expired_identities, 1)

    def test_wrong_distant_vehicle_is_rejected(self):
        first = self.update([raw_track(1, 20, 20)], [detection(20, 20)], 0.0)
        self.update([], [], 0.1)
        later = self.update([raw_track(2, 500, 280, timestamp=0.2)], [detection(500, 280)], 0.2)
        self.assertNotEqual(first.active_tracks[0].logical_vehicle_id, later.active_tracks[0].logical_vehicle_id)

    def test_crowded_ambiguous_handoff_is_rejected(self):
        first = self.update(
            [raw_track(1, 100, 100), raw_track(2, 140, 100)],
            [detection(100, 100), detection(140, 100)],
            0.0,
        )
        self.update([], [], 0.1)
        replacement = self.update([raw_track(3, 120, 100, timestamp=0.2)], [detection(120, 100)], 0.2)
        old_ids = {item.logical_vehicle_id for item in first.active_tracks}
        self.assertNotIn(replacement.active_tracks[0].logical_vehicle_id, old_ids)
        self.assertEqual(replacement.ambiguous_handoffs, 1)

    def test_person_never_becomes_vehicle_identity(self):
        result = self.update([], [detection(100, 100, label="person")], 0.0)
        self.assertEqual(result.active_tracks, ())
        self.assertEqual(self.service.get_identities("cam"), ())

    def test_subtype_change_requires_strong_spatial_match(self):
        first = self.update([raw_track(1, 100, 100, label="motorcycle")], [detection(100, 100, label="motorcycle")], 0.0)
        self.update([], [], 0.1)
        changed = self.update([raw_track(2, 103, 101, label="car", timestamp=0.2)], [detection(103, 101, label="car")], 0.2)
        identity = changed.active_tracks[0]
        self.assertEqual(identity.logical_vehicle_id, first.active_tracks[0].logical_vehicle_id)
        self.assertEqual(identity.logical_class, "vehicle")
        self.assertEqual(identity.previous_detector_class, "motorcycle")
        self.assertEqual(identity.class_name, "car")

    def test_wrong_trajectory_switch_is_rejected(self):
        self.update([raw_track(1, 100, 100)], [detection(100, 100)], 0.0)
        self.update([raw_track(1, 130, 100, timestamp=0.2)], [detection(130, 100)], 0.2)
        self.update([], [], 0.3)
        reversed_track = self.update([raw_track(2, 100, 100, timestamp=0.4)], [detection(100, 100)], 0.4)
        self.assertEqual(reversed_track.accepted_handoffs, 0)

    def test_temporal_pair_history_survives_valid_handoff(self):
        verifier = TemporalCrashVerifier()
        first = self.update(
            [raw_track(1, 100, 100), raw_track(2, 180, 100)],
            [detection(100, 100), detection(180, 100)],
            0.0,
        )
        verifier.analyze("cam", first.active_tracks, classifier_score=0.5, frame_width=640, frame_height=360, timestamp=0.0)
        second = self.update(
            [raw_track(1, 105, 100, timestamp=0.2), raw_track(9, 175, 100, timestamp=0.2)],
            [detection(105, 100), detection(175, 100)],
            0.2,
        )
        verifier.analyze("cam", second.active_tracks, classifier_score=0.5, frame_width=640, frame_height=360, timestamp=0.2)
        self.assertEqual(len(verifier.get_interactions("cam")), 1)
        self.assertEqual(len(verifier.get_interactions("cam")[0].distance_history), 2)

    def test_temporal_pair_history_resets_after_true_expiry(self):
        verifier = TemporalCrashVerifier()
        first = self.update(
            [raw_track(1, 100, 100), raw_track(2, 180, 100)],
            [detection(100, 100), detection(180, 100)],
            0.0,
        )
        verifier.analyze("cam", first.active_tracks, classifier_score=0.5, frame_width=640, frame_height=360, timestamp=0.0)
        later = self.update(
            [raw_track(7, 100, 100, timestamp=1.1), raw_track(8, 180, 100, timestamp=1.1)],
            [detection(100, 100), detection(180, 100)],
            1.1,
        )
        verifier.expire_track_ids("cam", later.expired_logical_track_ids)
        verifier.analyze("cam", later.active_tracks, classifier_score=0.5, frame_width=640, frame_height=360, timestamp=1.1)
        histories = [len(item.distance_history) for item in verifier.get_interactions("cam")]
        self.assertEqual(histories, [1])

    def test_raw_observation_maps_to_only_one_logical_identity(self):
        result = self.update([raw_track(1, 100, 100)], [detection(100, 100)], 0.0)
        self.assertEqual(len(result.active_tracks), 1)
        self.assertEqual(len({item.logical_vehicle_id for item in result.active_tracks}), 1)

    def test_crossing_stable_raw_tracks_do_not_swap_logical_ids(self):
        first = self.update(
            [raw_track(1, 100, 100), raw_track(2, 220, 100)],
            [detection(100, 100), detection(220, 100)],
            0.0,
        )
        initial = {item.raw_track_id: item.logical_vehicle_id for item in first.active_tracks}
        crossed = self.update(
            [raw_track(1, 165, 100, timestamp=0.2), raw_track(2, 155, 100, timestamp=0.2)],
            [detection(165, 100), detection(155, 100)],
            0.2,
        )
        current = {item.raw_track_id: item.logical_vehicle_id for item in crossed.active_tracks}
        self.assertEqual(initial, current)

    def test_expiry_keeps_memory_bounded(self):
        for index in range(100):
            self.update([], [detection(index * 2, 100, state="CANDIDATE", supported=True)], index * 1.1)
        self.assertLessEqual(len(self.service.get_identities("cam")), self.config.max_identities_per_camera)

    def test_pair_region_score_cannot_force_handoff(self):
        # The API intentionally accepts no pair-region classifier score.
        with self.assertRaises(TypeError):
            self.service.update(
                "cam", [], [], frame_width=640, frame_height=360, timestamp=0.0,
                pair_region_score=1.0,
            )


if __name__ == "__main__":
    unittest.main()
