import unittest

from backend.services.crash_aftermath_detector import (
    AftermathConfig,
    CrashAftermathDetector,
    estimate_scene_abnormality,
)
from backend.services.crash_event_state import CrashEventManager
from backend.services.crash_evidence_resolver import resolve_crash_evidence
from backend.services.temporal_crash_verifier import TemporalCrashDecision
from backend.services.vehicle_tracking import TrackState
from backend.repositories.crash_cases import CrashCaseRejected, _require_confirmed_crash_payload


def stationary_track(track_id=1, camera_id="CAM-AFTER", history_size=20):
    return TrackState.create(
        track_id=track_id,
        camera_id=camera_id,
        class_id=2,
        class_name="car",
        history_size=history_size,
        timestamp=0.0,
    )


def add_position(track, timestamp, x, y=0.5, width=0.12, height=0.10):
    track.add_observation(
        timestamp=timestamp,
        bbox=(
            (x - width / 2) * 1000,
            (y - height / 2) * 1000,
            (x + width / 2) * 1000,
            (y + height / 2) * 1000,
        ),
        confidence=0.9,
        frame_width=1000,
        frame_height=1000,
    )


def temporal_decision(*, verified=False, candidate=False, score=0.0):
    return TemporalCrashDecision(
        is_candidate=candidate,
        is_verified=verified,
        score=score,
        involved_track_ids=(1, 2) if candidate else (),
        evidence={"temporal_score": score},
        contact_timestamp=1.0 if verified else None,
        reason=("verified_before_contact_after_pattern" if verified else "no_consistent_approach"),
        analysis_ms=0.0,
        feature_calculation_ms=0.0,
        temporal_verification_ms=0.0,
        active_pairs=1 if candidate else 0,
    )


class CrashAftermathDetectorTests(unittest.TestCase):
    def setUp(self):
        self.config = AftermathConfig(
            min_classifier_score=0.80,
            minimum_score=0.80,
            required_positive_frames=6,
            window_seconds=10.0,
            minimum_persistence_seconds=2.5,
            clear_seconds=1.0,
            clear_consecutive_negatives=2,
            cooldown_seconds=0.5,
            minimum_track_history=3,
            stationary_speed_threshold=0.018,
        )
        self.detector = CrashAftermathDetector(self.config)

    def observe(self, track, timestamp, classifier=0.92, x=0.5, vehicle_count=1,
                abnormality=1.0, quality="good", temporal_active=False):
        add_position(track, timestamp, x)
        return self.detector.observe(
            track.camera_id,
            classifier_score=classifier,
            vehicle_count=vehicle_count,
            active_tracks=[track],
            scene_valid=True,
            frame_quality_status=quality,
            scene_abnormality_score=abnormality,
            temporal_collision_active=temporal_active,
            timestamp=timestamp,
        )

    def test_current_problem_stationary_aftermath_becomes_review_candidate(self):
        track = stationary_track()
        decisions = [self.observe(track, index * 0.5) for index in range(8)]

        self.assertFalse(any(item.review_candidate for item in decisions[:5]))
        self.assertTrue(decisions[-1].review_candidate)
        self.assertEqual(decisions[-1].state, "REVIEW_CANDIDATE")
        self.assertEqual(decisions[-1].reason, "persistent_crash_aftermath")
        self.assertEqual(decisions[-1].track_ids, (1,))

    def test_one_high_frame_cannot_create_review_candidate(self):
        track = stationary_track()
        decision = self.observe(track, 0.0)
        self.assertFalse(decision.review_candidate)
        self.assertLess(decision.positive_observations, self.config.required_positive_frames)

    def test_normal_parked_car_with_low_classifier_is_rejected(self):
        track = stationary_track()
        decisions = [self.observe(track, index * 0.5, classifier=0.20) for index in range(10)]
        self.assertFalse(any(item.review_candidate for item in decisions))
        self.assertEqual(decisions[-1].reason, "classifier_below_threshold")

    def test_close_stopped_traffic_with_fluctuating_classifier_is_rejected(self):
        first = stationary_track(1)
        second = stationary_track(2)
        decisions = []
        for index in range(12):
            timestamp = index * 0.5
            add_position(first, timestamp, 0.45)
            add_position(second, timestamp, 0.56)
            decisions.append(
                self.detector.observe(
                    "CAM-AFTER",
                    classifier_score=0.86 if index % 2 == 0 else 0.45,
                    vehicle_count=2,
                    active_tracks=[first, second],
                    scene_valid=True,
                    frame_quality_status="good",
                    scene_abnormality_score=0.0,
                    timestamp=timestamp,
                )
            )
        self.assertFalse(any(item.review_candidate for item in decisions))

    def test_high_classifier_false_positive_with_normal_motion_is_rejected(self):
        track = stationary_track()
        decisions = [
            self.observe(track, index * 0.5, classifier=0.99, x=0.10 + index * 0.06)
            for index in range(10)
        ]
        self.assertFalse(any(item.review_candidate for item in decisions))
        self.assertEqual(decisions[-1].reason, "normal_vehicle_motion")

    def test_persistent_aftermath_produces_one_event_claim(self):
        track = stationary_track(camera_id="CAM-PERSIST")
        manager = CrashEventManager(
            required_positive_observations=3,
            temporal_window_seconds=5.0,
            clear_consecutive_negatives=2,
            clear_seconds=0.0,
            cooldown_seconds=0.0,
        )
        claims = []
        event_ids = []
        for index in range(70):
            timestamp = index * 0.5
            decision = self.observe(track, timestamp)
            resolved = resolve_crash_evidence(temporal_decision(), decision)
            event = manager.observe(
                "CAM-PERSIST",
                positive=resolved.should_signal_event,
                interaction_candidate=resolved.should_signal_event,
                classifier_score=decision.classifier_score,
                now=timestamp,
            )
            if event.detector_event_id:
                event_ids.append(event.detector_event_id)
            if event.should_persist:
                claims.append(event)
                manager.mark_persisted(
                    "CAM-PERSIST", event.detector_event_id, "CASE-AFTER-1", now=timestamp
                )
        self.assertEqual(len(claims), 1)
        self.assertEqual(len(set(event_ids)), 1)

    def test_clear_then_later_aftermath_creates_distinct_event(self):
        track = stationary_track(camera_id="CAM-TWO-AFTER")
        manager = CrashEventManager(
            required_positive_observations=3,
            temporal_window_seconds=5.0,
            clear_consecutive_negatives=2,
            clear_seconds=0.5,
            cooldown_seconds=0.0,
        )

        def feed(start, case_id):
            claim = None
            for offset in range(10):
                now = start + offset * 0.5
                decision = self.observe(track, now)
                resolved = resolve_crash_evidence(temporal_decision(), decision)
                event = manager.observe(
                    "CAM-TWO-AFTER",
                    positive=resolved.should_signal_event,
                    interaction_candidate=resolved.should_signal_event,
                    classifier_score=decision.classifier_score,
                    now=now,
                )
                if event.should_persist:
                    claim = event
                    manager.mark_persisted(
                        "CAM-TWO-AFTER", event.detector_event_id, case_id, now=now
                    )
            return claim

        first = feed(0.0, "CASE-AFTER-1")
        self.assertIsNotNone(first)
        for now in (6.0, 7.1, 8.2):
            decision = self.detector.observe(
                "CAM-TWO-AFTER",
                classifier_score=0.05,
                vehicle_count=0,
                active_tracks=[],
                scene_valid=True,
                frame_quality_status="good",
                scene_abnormality_score=0.0,
                timestamp=now,
            )
            manager.observe(
                "CAM-TWO-AFTER",
                positive=False,
                interaction_candidate=False,
                classifier_score=0.05,
                now=now,
            )
        second = feed(9.0, "CASE-AFTER-2")
        self.assertIsNotNone(second)
        self.assertNotEqual(first.detector_event_id, second.detector_event_id)

    def test_temporal_path_wins_and_prevents_double_signal(self):
        track = stationary_track()
        aftermath = None
        for index in range(8):
            aftermath = self.observe(track, index * 0.5)
        resolved = resolve_crash_evidence(
            temporal_decision(verified=True, candidate=True, score=0.86), aftermath
        )
        self.assertEqual(resolved.detection_mode, "temporal_collision")
        self.assertEqual(resolved.final_decision, "confirmed_crash")
        self.assertTrue(resolved.should_signal_event)

    def test_aftermath_mode_is_distinct_from_temporal_collision(self):
        track = stationary_track()
        aftermath = None
        for index in range(8):
            aftermath = self.observe(track, index * 0.5)
        resolved = resolve_crash_evidence(temporal_decision(), aftermath)
        self.assertEqual(resolved.detection_mode, "aftermath_review")
        self.assertEqual(resolved.final_decision, "possible_crash_aftermath")

    def test_configuration_validation(self):
        with self.assertRaises(ValueError):
            AftermathConfig(required_positive_frames=1)
        with self.assertRaises(ValueError):
            AftermathConfig(min_classifier_score=1.5)

    def test_moderate_classifier_normal_parked_car_is_rejected_by_geometry_gate(self):
        track = stationary_track(camera_id="CAM-PARKED")
        decisions = [
            self.observe(track, index * 0.5, classifier=0.85, abnormality=0.0)
            for index in range(12)
        ]
        self.assertFalse(any(item.review_candidate for item in decisions))
        self.assertEqual(decisions[-1].reason, "insufficient_abnormal_geometry")

    def test_high_confidence_aftermath_qualifies_without_abnormal_geometry(self):
        track = stationary_track(camera_id="CAM-HIGH")
        decisions = [
            self.observe(track, index * 0.5, classifier=0.95, abnormality=0.0)
            for index in range(12)
        ]
        self.assertTrue(decisions[-1].review_candidate)

    def test_persistent_two_vehicle_abnormal_scene_becomes_review_candidate(self):
        first = stationary_track(1, camera_id="CAM-TWO")
        second = stationary_track(2, camera_id="CAM-TWO")
        decisions = []
        for index in range(8):
            now = index * 0.5
            add_position(first, now, 0.49)
            add_position(second, now, 0.51)
            decisions.append(self.detector.observe(
                "CAM-TWO", classifier_score=0.92, vehicle_count=2,
                active_tracks=[first, second], scene_valid=True,
                frame_quality_status="good", scene_abnormality_score=1.0,
                timestamp=now,
            ))
        self.assertTrue(decisions[-1].review_candidate)

    def test_quality_failure_never_accumulates_aftermath(self):
        track = stationary_track(camera_id="CAM-BLUR")
        decisions = [self.observe(track, index * 0.5, quality="bad") for index in range(10)]
        self.assertFalse(any(item.is_suspected for item in decisions))
        self.assertEqual(decisions[-1].rejection_reasons, ("quality_gate_failed",))

    def test_temporal_collision_suppresses_and_clears_aftermath_state(self):
        track = stationary_track(camera_id="CAM-TEMPORAL-WINS")
        for index in range(4):
            self.observe(track, index * 0.5)
        decision = self.observe(track, 2.5, temporal_active=True)
        self.assertEqual(decision.state, "NONE")
        self.assertEqual(decision.rejection_reasons, ("temporal_collision_already_active",))
        self.assertEqual(self.detector.snapshot(track.camera_id), "NONE")

    def test_large_timestamp_gap_starts_a_new_camera_session(self):
        track = stationary_track(camera_id="CAM-GAP")
        for index in range(5):
            self.observe(track, index * 0.5)
        decision = self.observe(track, 20.0)
        self.assertEqual(decision.state, "SUSPECTED")
        self.assertEqual(decision.positive_observations, 1)

    def test_persisted_aftermath_enters_active_state_until_scene_clears(self):
        track = stationary_track(camera_id="CAM-ACTIVE")
        for index in range(8):
            decision = self.observe(track, index * 0.5)
        self.assertTrue(decision.review_candidate)
        self.detector.mark_active(track.camera_id)
        self.assertEqual(self.detector.snapshot(track.camera_id), "ACTIVE")
        active = self.observe(track, 4.0)
        self.assertEqual(active.state, "ACTIVE")
        self.assertEqual(active.rejection_reasons, ())

    def test_disabled_detector_returns_explainable_rejection(self):
        detector = CrashAftermathDetector(AftermathConfig(enabled=False))
        track = stationary_track(camera_id="CAM-DISABLED")
        add_position(track, 0.0, 0.5)
        decision = detector.observe(
            track.camera_id, classifier_score=0.99, vehicle_count=1,
            active_tracks=[track], scene_valid=True, frame_quality_status="good",
            scene_abnormality_score=1.0, timestamp=0.0,
        )
        self.assertEqual(decision.rejection_reasons, ("aftermath_disabled",))

    def test_geometry_estimator_rejects_normal_shape_and_supports_rollover_shape(self):
        normal = stationary_track(camera_id="CAM-GEOMETRY")
        rollover = stationary_track(2, camera_id="CAM-GEOMETRY")
        add_position(normal, 0.0, 0.3, width=0.18, height=0.08)
        add_position(rollover, 0.0, 0.7, width=0.07, height=0.15)
        self.assertEqual(estimate_scene_abnormality([normal]), 0.0)
        self.assertGreater(estimate_scene_abnormality([rollover]), 0.35)

    def test_repository_gate_accepts_only_persistent_aftermath_proof(self):
        payload = {
            "finalDecision": "possible_crash_aftermath",
            "detectionMode": "aftermath_review",
            "vehicleCount": 1,
            "sceneValid": True,
            "crashScore": 0.88,
            "consecutiveCrashHits": 3,
            "aftermathCandidate": True,
            "aftermathScore": 0.88,
            "aftermathClassifierScore": 0.85,
            "aftermathAbnormalityScore": 0.90,
            "aftermathPositiveObservations": 6,
            "aftermathPersistenceSeconds": 2.5,
        }
        _require_confirmed_crash_payload(payload)

        with self.assertRaises(CrashCaseRejected):
            _require_confirmed_crash_payload(
                {**payload, "aftermathPositiveObservations": 1}
            )
        with self.assertRaises(CrashCaseRejected):
            _require_confirmed_crash_payload(
                {**payload, "aftermathPersistenceSeconds": 0.0}
            )
        with self.assertRaises(CrashCaseRejected):
            _require_confirmed_crash_payload(
                {**payload, "aftermathAbnormalityScore": 0.0}
            )

        # High confidence aftermath (>= 0.90) accepts 0.0 abnormality score
        _require_confirmed_crash_payload(
            {**payload, "aftermathClassifierScore": 0.95, "aftermathAbnormalityScore": 0.0}
        )


if __name__ == "__main__":
    unittest.main()
