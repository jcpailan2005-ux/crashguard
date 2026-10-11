import unittest

from backend.services.crash_event_state import CrashEventManager


class CrashEventManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = CrashEventManager(
            required_positive_observations=3,
            temporal_window_seconds=5.0,
            clear_consecutive_negatives=2,
            clear_seconds=1.0,
            cooldown_seconds=1.0,
        )

    def observe_positive(self, camera_id: str, now: float):
        return self.manager.observe(
            camera_id,
            positive=True,
            interaction_candidate=True,
            classifier_score=0.95,
            now=now,
        )

    def confirm(self, camera_id: str = "CAM-1", start: float = 0.0):
        first = self.observe_positive(camera_id, start)
        second = self.observe_positive(camera_id, start + 0.2)
        third = self.observe_positive(camera_id, start + 0.4)
        self.assertFalse(first.should_persist)
        self.assertFalse(second.should_persist)
        self.assertTrue(third.should_persist)
        return third

    def test_single_high_confidence_frame_is_only_a_candidate(self):
        result = self.observe_positive("CAM-SINGLE", 10.0)

        self.assertEqual(result.event_state, "CANDIDATE")
        self.assertFalse(result.should_persist)
        self.assertFalse(result.incident_created)
        self.assertIsNone(result.incident_id)

    def test_close_vehicles_without_temporal_confirmation_do_not_confirm(self):
        result = self.observe_positive("CAM-CLOSE", 20.0)

        self.assertEqual(result.event_state, "CANDIDATE")
        self.assertFalse(result.should_persist)

    def test_one_confirmed_crash_persists_exactly_once(self):
        confirmed = self.confirm()
        active = self.manager.mark_persisted(
            "CAM-1", confirmed.detector_event_id, "CASE-1", now=0.5
        )

        self.assertTrue(active.incident_created)
        self.assertEqual(active.event_state, "ACTIVE")
        self.assertEqual(active.incident_id, "CASE-1")

        duplicate = self.observe_positive("CAM-1", 0.6)
        self.assertFalse(duplicate.should_persist)
        self.assertFalse(duplicate.incident_created)
        self.assertTrue(duplicate.duplicate_event)
        self.assertEqual(duplicate.detector_event_id, confirmed.detector_event_id)
        self.assertEqual(duplicate.incident_id, "CASE-1")

    def test_visible_crash_keeps_same_event_and_incident(self):
        confirmed = self.confirm("CAM-VISIBLE")
        self.manager.mark_persisted(
            "CAM-VISIBLE", confirmed.detector_event_id, "CASE-VISIBLE", now=0.5
        )

        observations = [
            self.observe_positive("CAM-VISIBLE", 0.6 + index * 0.2)
            for index in range(6)
        ]

        self.assertEqual(
            {item.detector_event_id for item in observations},
            {confirmed.detector_event_id},
        )
        self.assertEqual({item.incident_id for item in observations}, {"CASE-VISIBLE"})
        self.assertTrue(all(item.duplicate_event for item in observations))
        self.assertTrue(all(not item.should_persist for item in observations))

    def test_scene_clear_allows_second_crash_with_new_ids(self):
        first = self.confirm("CAM-TWO", start=0.0)
        self.manager.mark_persisted(
            "CAM-TWO", first.detector_event_id, "CASE-FIRST", now=0.5
        )

        self.manager.observe(
            "CAM-TWO",
            positive=False,
            interaction_candidate=False,
            classifier_score=0.01,
            now=1.0,
        )
        cleared = self.manager.observe(
            "CAM-TWO",
            positive=False,
            interaction_candidate=False,
            classifier_score=0.01,
            now=2.1,
        )
        self.assertEqual(cleared.event_state, "CLEARED")

        second_start = self.observe_positive("CAM-TWO", 3.2)
        self.assertEqual(second_start.event_state, "CANDIDATE")
        self.observe_positive("CAM-TWO", 3.4)
        second = self.observe_positive("CAM-TWO", 3.6)
        self.assertTrue(second.should_persist)
        active_second = self.manager.mark_persisted(
            "CAM-TWO", second.detector_event_id, "CASE-SECOND", now=3.7
        )

        self.assertNotEqual(first.detector_event_id, second.detector_event_id)
        self.assertNotEqual("CASE-FIRST", active_second.incident_id)

    def test_persistence_failure_does_not_create_incident(self):
        confirmed = self.confirm("CAM-DB-FAIL")
        failed = self.manager.mark_persistence_failed(
            "CAM-DB-FAIL", confirmed.detector_event_id, "database unavailable", now=0.5
        )

        self.assertEqual(failed.event_state, "CONFIRMED")
        self.assertFalse(failed.incident_created)
        self.assertIsNone(failed.incident_id)

        retry = self.observe_positive("CAM-DB-FAIL", 0.6)
        self.assertTrue(retry.should_persist)
        self.assertFalse(retry.incident_created)

    def test_negative_or_proximity_only_observation_cannot_start_event(self):
        result = self.manager.observe(
            "CAM-PROXIMITY",
            positive=False,
            interaction_candidate=True,
            classifier_score=0.10,
            now=30.0,
        )

        self.assertEqual(result.event_state, "IDLE")
        self.assertIsNone(result.detector_event_id)
        self.assertFalse(result.should_persist)

    def test_aftermath_then_temporal_uses_one_event_and_temporal_mode_wins(self):
        first = self.manager.observe(
            "CAM-BOTH-PATHS",
            positive=True,
            interaction_candidate=True,
            classifier_score=0.91,
            detection_mode="aftermath_review",
            now=40.0,
        )
        second = self.manager.observe(
            "CAM-BOTH-PATHS",
            positive=True,
            interaction_candidate=True,
            classifier_score=0.91,
            detection_mode="temporal_collision",
            now=40.2,
        )
        confirmed = self.manager.observe(
            "CAM-BOTH-PATHS",
            positive=True,
            interaction_candidate=True,
            classifier_score=0.91,
            detection_mode="temporal_collision",
            now=40.4,
        )

        self.assertEqual(first.detector_event_id, second.detector_event_id)
        self.assertEqual(first.detector_event_id, confirmed.detector_event_id)
        self.assertEqual(confirmed.detection_mode, "temporal_collision")
        self.assertTrue(confirmed.should_persist)

    def test_explicit_camera_reset_clears_detector_identity(self):
        first = self.observe_positive("CAM-RESET", 50.0)
        self.manager.reset_camera("CAM-RESET")
        second = self.observe_positive("CAM-RESET", 50.2)

        self.assertNotEqual(first.detector_event_id, second.detector_event_id)
        self.assertEqual(second.event_state, "CANDIDATE")


if __name__ == "__main__":
    unittest.main()
