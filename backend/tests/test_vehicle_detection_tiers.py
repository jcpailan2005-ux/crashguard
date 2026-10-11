import unittest

from backend.main import evaluate_crash_case_decision
from backend.services.vehicle_detection_tiers import (
    VehicleCandidateEvaluator,
    VehicleDetectionState,
    VehicleTierConfig,
    classify_vehicle_confidence,
)


def box(confidence, x, y, width=30, height=20, label="car"):
    return {
        "label": label,
        "classId": 2,
        "confidence": confidence,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


class VehicleDetectionTierTests(unittest.TestCase):
    def setUp(self):
        self.config = VehicleTierConfig(
            trusted_threshold=0.40,
            candidate_threshold=0.25,
            model1_support_threshold=0.60,
            persistence_observations=2,
        )
        self.evaluator = VehicleCandidateEvaluator(self.config)

    def evaluate(self, detections, *, score=0.0, timestamp=1.0, camera="cam"):
        return self.evaluator.evaluate(
            camera,
            detections,
            classifier_score=score,
            frame_width=640,
            frame_height=360,
            timestamp=timestamp,
        )

    def test_trusted_vehicle(self):
        self.assertEqual(
            classify_vehicle_confidence(
                0.75, trusted_threshold=0.40, candidate_threshold=0.25
            ),
            VehicleDetectionState.TRUSTED,
        )

    def test_candidate_vehicle(self):
        self.assertEqual(
            classify_vehicle_confidence(
                0.31, trusted_threshold=0.40, candidate_threshold=0.25
            ),
            VehicleDetectionState.CANDIDATE,
        )

    def test_rejected_vehicle(self):
        self.assertEqual(
            classify_vehicle_confidence(
                0.10, trusted_threshold=0.40, candidate_threshold=0.25
            ),
            VehicleDetectionState.REJECTED,
        )

    def test_supported_candidate_prevents_person_only_short_circuit(self):
        tiers = self.evaluate(
            [box(0.75, 100, 100), box(0.31, 135, 102)], score=0.75
        )
        self.assertEqual(len(tiers.supported_candidates), 1)
        should_create, reason, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.95,
            vehicle_count=0,
            supported_candidate_vehicle_count=1,
            person_count=2,
            scene_valid=True,
            motion_valid=True,
            temporal_verified=True,
            consecutive_positive_frames=3,
            active_case_exists=False,
            cooldown_ready=True,
        )
        self.assertFalse(should_create)
        self.assertNotEqual(reason, "person_only_not_crash")
        self.assertEqual(decision, "candidate")

    def test_true_person_only_scene_still_short_circuits(self):
        should_create, reason, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.99,
            vehicle_count=0,
            supported_candidate_vehicle_count=0,
            person_count=2,
            scene_valid=True,
            motion_valid=True,
            temporal_verified=True,
            consecutive_positive_frames=3,
            active_case_exists=False,
            cooldown_ready=True,
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "person_only_not_crash")
        self.assertEqual(decision, "ignored")

    def test_unsupported_candidate_cannot_confirm_collision(self):
        tiers = self.evaluate([box(0.27, 200, 100)], score=0.10)
        self.assertEqual(len(tiers.candidates), 1)
        self.assertEqual(len(tiers.supported_candidates), 0)
        self.assertEqual(len(tiers.tracker_input), 0)

    def test_trusted_and_candidate_are_available_to_tracking(self):
        tiers = self.evaluate(
            [box(0.72, 100, 100), box(0.31, 145, 102)], score=0.75
        )
        self.assertEqual(len(tiers.trusted), 1)
        self.assertEqual(len(tiers.supported_candidates), 1)
        self.assertEqual(len(tiers.tracker_input), 2)
        self.assertEqual(len(tiers.trusted), 1)  # vehicleCount semantics

    def test_small_overlapping_candidate_is_supported_beside_large_trusted_vehicle(self):
        tiers = self.evaluate(
            [
                box(0.80, 100, 100, width=300, height=200),
                box(0.31, 390, 140, width=30, height=20, label="motorcycle"),
            ],
            score=0.90,
        )
        self.assertEqual(len(tiers.supported_candidates), 1)
        self.assertIn(
            "trusted_proximity", tiers.supported_candidates[0]["supportReasons"]
        )

    def test_two_weak_parked_candidates_do_not_confirm(self):
        detections = [box(0.34, 100, 100), box(0.29, 145, 102)]
        first = self.evaluate(detections, score=0.10, timestamp=1.0)
        second = self.evaluate(detections, score=0.10, timestamp=1.5)
        self.assertEqual(len(first.supported_candidates), 0)
        self.assertEqual(len(second.supported_candidates), 0)
        should_create, reason, _ = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.99,
            vehicle_count=0,
            supported_candidate_vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=True,
            temporal_verified=True,
            consecutive_positive_frames=3,
            active_case_exists=False,
            cooldown_ready=True,
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "trusted_vehicle_evidence_required")

    def test_two_candidates_need_persistence_proximity_and_model1(self):
        detections = [box(0.34, 100, 100), box(0.29, 145, 102)]
        first = self.evaluate(detections, score=0.90, timestamp=1.0)
        second = self.evaluate(detections, score=0.90, timestamp=1.5)
        self.assertEqual(len(first.supported_candidates), 0)
        self.assertEqual(len(second.supported_candidates), 2)
        self.assertEqual(len(second.trusted), 0)


if __name__ == "__main__":
    unittest.main()
