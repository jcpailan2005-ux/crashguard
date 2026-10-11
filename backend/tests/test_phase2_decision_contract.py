import unittest

from backend.main import evaluate_crash_case_decision


class Phase2DecisionContractTests(unittest.TestCase):
    def test_high_classifier_score_cannot_bypass_temporal_verifier(self):
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="accident",
            crash_confidence=0.999,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=False,
            consecutive_positive_frames=20,
            active_case_exists=False,
            cooldown_ready=True,
            temporal_verified=False,
        )
        self.assertFalse(should_create)
        self.assertEqual(rejection, "temporal_not_verified")
        self.assertNotEqual(decision, "confirmed_crash")

    def test_strong_temporal_verification_can_confirm_with_weak_classifier_support(self):
        should_create, rejection, decision = evaluate_crash_case_decision(
            crash_class="non_accident",
            crash_confidence=0.20,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=True,
            consecutive_positive_frames=1,
            active_case_exists=False,
            cooldown_ready=True,
            temporal_verified=True,
        )
        self.assertTrue(should_create)
        self.assertIsNone(rejection)
        self.assertEqual(decision, "confirmed_crash")


if __name__ == "__main__":
    unittest.main()
