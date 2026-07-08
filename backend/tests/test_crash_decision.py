import gc
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

import backend.db as db
from backend.main import (
    CRASH_CASE_CONFIDENCE_THRESHOLD,
    LIVE_CAMERA_REQUIRED_HITS,
    CameraDecisionTracker,
    evaluate_crash_case_decision,
    filter_boxes_in_roi,
    log_crash_decision,
)
from backend.repositories.crash_cases import (
    CrashCaseRejected,
    create_crash_case,
    find_unresolved_camera_case,
    list_crash_cases,
    list_notifications,
)
from backend.services.frame_quality import analyze_frame_quality
from backend.tests.test_frame_quality import blurry_frame, clear_frame


def decide(**overrides):
    params = {
        "crash_class": "accident",
        "crash_confidence": max(CRASH_CASE_CONFIDENCE_THRESHOLD, 0.90),
        "vehicle_count": 2,
        "person_count": 0,
        "scene_valid": True,
        "motion_valid": True,
        "consecutive_positive_frames": LIVE_CAMERA_REQUIRED_HITS,
        "active_case_exists": False,
        "cooldown_ready": True,
    }
    params.update(overrides)
    return evaluate_crash_case_decision(**params)


# The exact set of fields backend.repositories.crash_cases.create_crash_case
# requires as proof of a confirmed_crash decision (see _require_confirmed_crash_payload).
CONFIRMED_CRASH_GATE_FIELDS = {
    "finalDecision": "confirmed_crash",
    "vehicleCount": 2,
    "sceneValid": True,
    "motionValid": True,
    "crashScore": max(CRASH_CASE_CONFIDENCE_THRESHOLD, 0.90),
    "consecutiveCrashHits": LIVE_CAMERA_REQUIRED_HITS,
}

# high_confidence_review does NOT require motionValid or a 3-frame
# consecutiveCrashHits streak — a single very-high-confidence frame is
# enough on its own, since it only raises a Needs Review case for a human
# responder to verify manually (see _require_confirmed_crash_payload).
HIGH_CONFIDENCE_REVIEW_GATE_FIELDS = {
    "finalDecision": "high_confidence_review",
    "vehicleCount": 1,
    "sceneValid": True,
    "crashScore": max(CRASH_CASE_CONFIDENCE_THRESHOLD, 0.90),
}


def decide_single_frame(**overrides):
    """Like decide(), but defaults to the single-frame, no-motion-evidence
    shape that only the high_confidence_review tier can satisfy —
    consecutive_positive_frames=1 and motion_valid=False."""
    params = {"consecutive_positive_frames": 1, "motion_valid": False}
    params.update(overrides)
    return decide(**params)


class CrashDecisionTests(unittest.TestCase):
    def test_person_only_frame_must_not_create_case(self):
        should_create, reason, decision = decide(vehicle_count=0, person_count=1)
        self.assertFalse(should_create)
        self.assertEqual(reason, "person_only_not_crash")
        self.assertEqual(decision, "ignored")

    def test_no_vehicle_frame_must_not_create_case(self):
        should_create, reason, decision = decide(vehicle_count=0, person_count=0)
        self.assertFalse(should_create)
        self.assertEqual(reason, "no_vehicle_detected")
        self.assertEqual(decision, "ignored")

    def test_classifier_confidence_alone_must_not_create_case(self):
        # Even a 99% "accident" score is rejected when no vehicle is present.
        should_create, reason, decision = decide(
            crash_confidence=0.99, vehicle_count=0, person_count=1
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "person_only_not_crash")
        self.assertEqual(decision, "ignored")

    def test_single_vehicle_without_motion_creates_review_case_not_confirmed(self):
        # A single still/parked vehicle has no second vehicle to corroborate
        # crash-like proximity, so this can never reach confirmed_crash
        # (which requires motion_valid) — but a genuinely high classifier
        # score is still enough on its own to raise a lower-confidence Needs
        # Review case for a human to check.
        should_create, reason, decision = decide(vehicle_count=1, motion_valid=False)
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "high_confidence_review")

    def test_normal_traffic_without_motion_creates_review_case_not_confirmed(self):
        # Multiple vehicles flowing without crash-like proximity/overlap
        # can't reach confirmed_crash either, for the same reason.
        should_create, reason, decision = decide(vehicle_count=4, motion_valid=False)
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "high_confidence_review")

    def test_low_accident_probability_must_not_create_case(self):
        should_create, reason, decision = decide(
            crash_class="non_accident", crash_confidence=0.01
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "non_accident")
        self.assertEqual(decision, "ignored")

    def test_unexpected_class_with_low_accident_probability_must_not_create_case(self):
        should_create, reason, decision = decide(
            crash_class="suspicious", crash_confidence=0.01
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "non_accident")
        self.assertEqual(decision, "ignored")

    def test_one_frame_high_confidence_creates_review_case_not_confirmed(self):
        # A single high-confidence frame can't reach confirmed_crash (which
        # requires the 3-frame temporal streak), but the
        # high_confidence_review tier exists precisely so it isn't ignored
        # either: it raises a Needs Review case immediately, and a human
        # responder verifies it manually.
        should_create, reason, decision = decide(consecutive_positive_frames=1)
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "high_confidence_review")

    def test_vehicle_outside_roi_must_not_create_case(self):
        should_create, reason, decision = decide(scene_valid=False)
        self.assertFalse(should_create)
        self.assertEqual(reason, "vehicle_outside_roi")
        self.assertEqual(decision, "ignored")

    def test_three_frame_confirmed_vehicle_crash_can_create_case(self):
        should_create, reason, decision = decide()
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "confirmed_crash")

    def test_active_pending_case_blocks_duplicate_alert(self):
        should_create, reason, decision = decide(active_case_exists=True)
        self.assertFalse(should_create)
        self.assertEqual(reason, "active_case_exists")
        self.assertEqual(decision, "duplicate_active_case")

    def test_cooldown_blocks_duplicate_alert(self):
        should_create, reason, decision = decide(cooldown_ready=False)
        self.assertFalse(should_create)
        self.assertEqual(reason, "cooldown_active")
        self.assertEqual(decision, "duplicate_cooldown")

    def test_below_case_threshold_must_not_create_case(self):
        should_create, reason, decision = decide(
            crash_confidence=max(0.0, CRASH_CASE_CONFIDENCE_THRESHOLD - 0.01)
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "below_case_threshold")
        self.assertEqual(decision, "ignored")

    def test_clear_frame_quality_allows_crash_decision_to_proceed(self):
        # An explicit "good" frame quality status must not itself block an
        # otherwise-valid confirmed crash (frame quality is a gate, not a
        # replacement for the other checks).
        should_create, reason, decision = decide(
            frame_quality_status="good", quality_rejection_reason=None
        )
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "confirmed_crash")

    def test_blurry_frame_with_high_accident_score_creates_no_case(self):
        # Even a near-certain classifier score and a picture-perfect vehicle
        # scene must not create a case when the frame itself failed the
        # quality gate.
        should_create, reason, decision = decide(
            crash_confidence=0.99,
            frame_quality_status="bad",
            quality_rejection_reason="low_quality_blurry_frame",
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "low_quality_blurry_frame")
        self.assertEqual(decision, "skipped")

    def test_blurry_real_frame_end_to_end_creates_no_case(self):
        # End-to-end: run the real blur detector on a real blurry frame, feed
        # its output straight into the decision function alongside an
        # otherwise-perfect crash signal, and confirm it still refuses.
        quality = analyze_frame_quality(blurry_frame())
        self.assertEqual(quality["frameQualityStatus"], "bad")
        should_create, reason, decision = decide(
            crash_confidence=0.99,
            frame_quality_status=quality["frameQualityStatus"],
            quality_rejection_reason=quality["qualityRejectionReason"],
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "low_quality_blurry_frame")
        self.assertEqual(decision, "skipped")

    def test_clear_real_frame_end_to_end_can_create_case(self):
        # End-to-end: a real sharp frame's quality result must not block an
        # otherwise-valid confirmed crash.
        quality = analyze_frame_quality(clear_frame())
        self.assertEqual(quality["frameQualityStatus"], "good")
        should_create, reason, decision = decide(
            frame_quality_status=quality["frameQualityStatus"],
            quality_rejection_reason=quality["qualityRejectionReason"],
        )
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "confirmed_crash")


class CameraDecisionTrackerTests(unittest.TestCase):
    def test_streak_requires_consecutive_positive_frames(self):
        tracker = CameraDecisionTracker()
        now = 1_000.0
        self.assertEqual(tracker.record_frame("cam", True, now=now), 1)
        self.assertEqual(tracker.record_frame("cam", True, now=now + 1), 2)
        self.assertEqual(tracker.record_frame("cam", False, now=now + 2), 0)
        self.assertEqual(tracker.record_frame("cam", True, now=now + 3), 1)

    def test_single_qualifying_frame_creates_exactly_one_review_case(self):
        # Under the two-tier design, any frame that clears the shared
        # baseline (quality/score/vehicle/scene, plus motion_valid here)
        # immediately creates a case rather than waiting for a 3-frame
        # streak — the streak only decides confirmed_crash vs
        # high_confidence_review, it doesn't gate creation itself. So the
        # very first qualifying frame already creates a
        # high_confidence_review case, and every frame after that is
        # blocked by cooldown.
        tracker = CameraDecisionTracker()
        now = 1_000.0
        decisions = []
        for index in range(4):
            frame_time = now + index
            hits = tracker.record_frame("cam", True, now=frame_time)
            should_create, reason, decision = decide(
                consecutive_positive_frames=hits,
                cooldown_ready=tracker.cooldown_ready("cam", now=frame_time),
            )
            decisions.append((should_create, reason, decision))
            if should_create:
                tracker.mark_alert("cam", now=frame_time)

        created = [entry for entry in decisions if entry[0]]
        self.assertEqual(len(created), 1)
        self.assertEqual(decisions[0][2], "high_confidence_review")
        self.assertEqual(decisions[1][1], "cooldown_active")
        self.assertFalse(decisions[1][0])
        self.assertFalse(decisions[2][0])
        self.assertFalse(decisions[3][0])

    def test_three_consecutive_corroborated_hits_reach_confirmed_crash(self):
        # confirmed_crash remains reachable when motion_valid is true AND
        # the temporal streak has already reached the required count (e.g.
        # a case created earlier resolved, or this is evaluated directly) —
        # exercised here at the decision-function level since the
        # tracker/cooldown mechanics above mean a live camera stream would
        # normally raise a high_confidence_review case before ever reaching
        # 3 corroborated hits without an active case in the way.
        tracker = CameraDecisionTracker()
        now = 1_000.0
        hits = 0
        for index in range(3):
            hits = tracker.record_frame("cam", True, now=now + index)
        should_create, reason, decision = decide(
            consecutive_positive_frames=hits,
            cooldown_ready=tracker.cooldown_ready("cam", now=now + 3),
        )
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "confirmed_crash")

    def test_cooldown_blocks_then_recovers(self):
        tracker = CameraDecisionTracker()
        now = 1_000.0
        tracker.mark_alert("cam", now=now)
        self.assertFalse(tracker.cooldown_ready("cam", now=now + 1))
        self.assertTrue(tracker.cooldown_ready("cam", now=now + 10_000))

    def test_cameras_are_tracked_independently(self):
        tracker = CameraDecisionTracker()
        now = 1_000.0
        tracker.record_frame("cam-a", True, now=now)
        self.assertEqual(tracker.record_frame("cam-b", True, now=now), 1)
        tracker.mark_alert("cam-a", now=now)
        self.assertTrue(tracker.cooldown_ready("cam-b", now=now + 1))


class RoiFilterTests(unittest.TestCase):
    def test_vehicle_outside_configured_roi_is_rejected(self):
        original = os.environ.get("CRASH_ROI_NORMALIZED")
        os.environ["CRASH_ROI_NORMALIZED"] = "0.5,0.5,1.0,1.0"
        try:
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            outside_box = {"label": "car", "confidence": 0.9, "x": 5, "y": 5, "width": 10, "height": 10}
            inside_box = {"label": "car", "confidence": 0.9, "x": 60, "y": 60, "width": 20, "height": 20}

            filtered, scene_valid = filter_boxes_in_roi([outside_box], frame)
            self.assertEqual(filtered, [])
            self.assertFalse(scene_valid)

            filtered, scene_valid = filter_boxes_in_roi([outside_box, inside_box], frame)
            self.assertEqual(filtered, [inside_box])
            self.assertTrue(scene_valid)
        finally:
            if original is None:
                os.environ.pop("CRASH_ROI_NORMALIZED", None)
            else:
                os.environ["CRASH_ROI_NORMALIZED"] = original


class RepositorySafetyGateBase(unittest.TestCase):
    """Shared sqlite-in-tempdir fixture for tests that actually call create_crash_case."""

    def setUp(self):
        # sqlite connections opened via `with get_connection()` are committed but not
        # closed, so on Windows the db file stays locked until GC; ignore cleanup errors.
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp_path = Path(self._tmp.name)
        self._original_data_dir = db.DATA_DIR
        self._original_db_path = db.DATABASE_PATH
        db.DATA_DIR = tmp_path
        db.DATABASE_PATH = tmp_path / "test-crashguard.sqlite"

    def tearDown(self):
        db.DATA_DIR = self._original_data_dir
        db.DATABASE_PATH = self._original_db_path
        gc.collect()
        self._tmp.cleanup()

    def _base_payload(self, **overrides) -> dict:
        payload = {
            "status": "pending_review",
            "confidence": 0.95,
            "location": "Test Road",
            "areaId": "demo",
            "sourceCamera": "Test Camera",
            "cameraId": "CAM-TEST-GATE",
            "cameraIp": "192.168.1.51",
            "triggerStatus": "camera_detection",
            "accidentDetected": True,
        }
        payload.update(overrides)
        return payload


class RepositorySafetyGateTests(RepositorySafetyGateBase):
    """create_crash_case is the final repository-level gate: even with a
    fabricated/forged payload, nothing is persisted unless every required
    confirmed_crash field is present and valid. Proves task requirement:
    'Even if some route accidentally calls create_crash_case, the repository
    refuses to persist anything unless the strict confirmed_crash decision
    fields are present.'"""

    def test_person_only_payload_is_refused(self):
        payload = self._base_payload(
            **{
                **CONFIRMED_CRASH_GATE_FIELDS,
                "vehicleCount": 0,
            }
        )
        with self.assertRaises(CrashCaseRejected) as ctx:
            create_crash_case(payload)
        self.assertEqual(ctx.exception.reason, "missing_confirmed_crash_decision")
        self.assertIsNone(find_unresolved_camera_case(camera_id="CAM-TEST-GATE"))

    def test_no_vehicle_payload_is_refused(self):
        payload = self._base_payload(
            **{
                **CONFIRMED_CRASH_GATE_FIELDS,
                "vehicleCount": 0,
                "motionValid": False,
            }
        )
        with self.assertRaises(CrashCaseRejected) as ctx:
            create_crash_case(payload)
        self.assertEqual(ctx.exception.reason, "missing_confirmed_crash_decision")

    def test_missing_final_decision_field_is_refused(self):
        payload = self._base_payload(
            **{k: v for k, v in CONFIRMED_CRASH_GATE_FIELDS.items() if k != "finalDecision"}
        )
        self.assertNotIn("finalDecision", payload)
        with self.assertRaises(CrashCaseRejected) as ctx:
            create_crash_case(payload)
        self.assertEqual(ctx.exception.reason, "missing_confirmed_crash_decision")

    def test_final_decision_skipped_payload_is_refused(self):
        payload = self._base_payload(
            **{**CONFIRMED_CRASH_GATE_FIELDS, "finalDecision": "skipped"}
        )
        with self.assertRaises(CrashCaseRejected) as ctx:
            create_crash_case(payload)
        self.assertEqual(ctx.exception.reason, "missing_confirmed_crash_decision")

    def test_final_decision_suspicious_only_payload_is_refused(self):
        payload = self._base_payload(
            **{**CONFIRMED_CRASH_GATE_FIELDS, "finalDecision": "suspicious_only"}
        )
        with self.assertRaises(CrashCaseRejected) as ctx:
            create_crash_case(payload)
        self.assertEqual(ctx.exception.reason, "missing_confirmed_crash_decision")

    def test_below_threshold_crash_score_is_refused(self):
        payload = self._base_payload(
            **{**CONFIRMED_CRASH_GATE_FIELDS, "crashScore": 0.1}
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)

    def test_insufficient_consecutive_hits_is_refused(self):
        payload = self._base_payload(
            **{**CONFIRMED_CRASH_GATE_FIELDS, "consecutiveCrashHits": 1}
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)

    def test_scene_invalid_is_refused(self):
        payload = self._base_payload(
            **{**CONFIRMED_CRASH_GATE_FIELDS, "sceneValid": False}
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)

    def test_confirmed_crash_payload_creates_exactly_one_case(self):
        payload = self._base_payload(**CONFIRMED_CRASH_GATE_FIELDS)
        case_item = create_crash_case(payload)
        self.assertIsNotNone(case_item)
        self.assertIsNotNone(case_item["caseId"])
        self.assertIsNotNone(case_item.get("createdNotificationId"))

        all_cases = list_crash_cases(area_id="demo")
        matching = [case for case in all_cases if case["cameraId"] == "CAM-TEST-GATE"]
        self.assertEqual(len(matching), 1)


class CrashCaseCreationSwitchTests(RepositorySafetyGateBase):
    """ENABLE_CRASH_CASE_CREATION=false must block persistence even with an
    otherwise-perfect confirmed_crash payload."""

    def test_master_switch_off_blocks_even_valid_payload(self):
        original = os.environ.get("ENABLE_CRASH_CASE_CREATION")
        os.environ["ENABLE_CRASH_CASE_CREATION"] = "false"
        try:
            payload = self._base_payload(**CONFIRMED_CRASH_GATE_FIELDS)
            with self.assertRaises(CrashCaseRejected) as ctx:
                create_crash_case(payload)
            self.assertEqual(ctx.exception.reason, "crash_case_creation_disabled")
        finally:
            if original is None:
                os.environ.pop("ENABLE_CRASH_CASE_CREATION", None)
            else:
                os.environ["ENABLE_CRASH_CASE_CREATION"] = original

    def test_master_switch_on_allows_valid_payload(self):
        original = os.environ.get("ENABLE_CRASH_CASE_CREATION")
        os.environ["ENABLE_CRASH_CASE_CREATION"] = "true"
        try:
            payload = self._base_payload(**CONFIRMED_CRASH_GATE_FIELDS)
            case_item = create_crash_case(payload)
            self.assertIsNotNone(case_item)
        finally:
            if original is None:
                os.environ.pop("ENABLE_CRASH_CASE_CREATION", None)
            else:
                os.environ["ENABLE_CRASH_CASE_CREATION"] = original


class ActiveCaseBlockingTests(RepositorySafetyGateBase):
    """Repository-level checks that only pending/under review cases block new alerts."""

    def _create_case(self, status: str) -> dict:
        return create_crash_case(
            {
                "status": status,
                "confidence": 0.95,
                "location": "Test Road",
                "areaId": "demo",
                "sourceCamera": "Test Camera",
                "cameraId": "CAM-TEST-1",
                "cameraIp": "192.168.1.50",
                "triggerStatus": "camera_detection",
                "accidentDetected": True,
                **CONFIRMED_CRASH_GATE_FIELDS,
            }
        )

    def test_pending_review_case_blocks_new_camera_alert(self):
        created = self._create_case("pending_review")
        blocking = find_unresolved_camera_case(camera_id="CAM-TEST-1")
        self.assertIsNotNone(blocking)
        self.assertEqual(blocking["caseId"], created["caseId"])

    def test_under_review_case_blocks_new_camera_alert(self):
        created = self._create_case("under_review")
        blocking = find_unresolved_camera_case(camera_id="CAM-TEST-1")
        self.assertIsNotNone(blocking)
        self.assertEqual(blocking["caseId"], created["caseId"])

    def test_resolved_false_alarm_dispatched_do_not_block_future_valid_crash(self):
        for status in ("resolved", "false_alarm", "dispatched", "confirmed_crash"):
            with self.subTest(status=status):
                self._create_case(status)
        self.assertIsNone(find_unresolved_camera_case(camera_id="CAM-TEST-1"))


class NotificationTriggerTests(RepositorySafetyGateBase):
    """A crash notification must only be created via create_crash_case, and
    only when crashScore >= CRASH_CASE_THRESHOLD (0.90) AND every other
    confirmed_crash gate has passed. 80% is a UI-only warning threshold and
    must never create a notification by itself."""

    def _notifications_for_case(self, case_id: str) -> list[dict]:
        return [row for row in list_notifications() if row["caseId"] == case_id]

    def test_score_0_89_creates_no_notification(self):
        should_create, reason, decision = decide(crash_confidence=0.89)
        self.assertFalse(should_create)
        self.assertEqual(reason, "below_case_threshold")
        self.assertEqual(decision, "ignored")

        payload = self._base_payload(
            cameraId="CAM-NOTIFY-089",
            **{**CONFIRMED_CRASH_GATE_FIELDS, "crashScore": 0.89},
        )
        with self.assertRaises(CrashCaseRejected) as ctx:
            create_crash_case(payload)
        self.assertEqual(ctx.exception.reason, "missing_confirmed_crash_decision")
        self.assertEqual(len(list_notifications()), 0)

    def test_score_0_90_with_confirmed_crash_creates_notification(self):
        should_create, reason, decision = decide(crash_confidence=0.90)
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "confirmed_crash")

        payload = self._base_payload(
            cameraId="CAM-NOTIFY-090",
            cameraName="Talomo Crossing CCTV",
            **{**CONFIRMED_CRASH_GATE_FIELDS, "crashScore": 0.90},
        )
        case_item = create_crash_case(payload)
        self.assertIsNotNone(case_item)
        self.assertIsNotNone(case_item.get("createdNotificationId"))

        notifications = self._notifications_for_case(case_item["caseId"])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["title"], "Car Crash Detected")
        self.assertIn("90%", notifications[0]["message"])
        self.assertIn("Talomo Crossing CCTV", notifications[0]["message"])

    def test_score_0_95_person_only_creates_no_notification(self):
        should_create, reason, decision = decide(
            crash_confidence=0.95, vehicle_count=0, person_count=1
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "person_only_not_crash")
        self.assertEqual(decision, "ignored")

        payload = self._base_payload(
            cameraId="CAM-NOTIFY-PERSON",
            **{**CONFIRMED_CRASH_GATE_FIELDS, "crashScore": 0.95, "vehicleCount": 0},
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)
        self.assertEqual(len(list_notifications()), 0)

    def test_score_0_95_final_decision_skipped_creates_no_notification(self):
        # finalDecision == "skipped" is what the frame-quality gate returns,
        # even when the crash score itself is very high.
        should_create, reason, decision = decide(
            crash_confidence=0.95,
            frame_quality_status="bad",
            quality_rejection_reason="low_quality_blurry_frame",
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "low_quality_blurry_frame")
        self.assertEqual(decision, "skipped")

        payload = self._base_payload(
            cameraId="CAM-NOTIFY-SKIPPED",
            **{**CONFIRMED_CRASH_GATE_FIELDS, "crashScore": 0.95, "finalDecision": "skipped"},
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)
        self.assertEqual(len(list_notifications()), 0)

    def test_score_0_95_active_case_exists_creates_no_duplicate_notification(self):
        payload = self._base_payload(
            cameraId="CAM-NOTIFY-DUP",
            **{**CONFIRMED_CRASH_GATE_FIELDS, "crashScore": 0.95},
        )
        first_case = create_crash_case(payload)
        self.assertEqual(len(self._notifications_for_case(first_case["caseId"])), 1)

        # A second high-scoring frame on the same camera, with the first case
        # still pending review, must be rejected before a case (and therefore
        # a notification) can be created again.
        should_create_second, reason_second, decision_second = decide(
            crash_confidence=0.95, active_case_exists=True
        )
        self.assertFalse(should_create_second)
        self.assertEqual(reason_second, "active_case_exists")
        self.assertEqual(decision_second, "duplicate_active_case")

        blocking = find_unresolved_camera_case(camera_id="CAM-NOTIFY-DUP")
        self.assertIsNotNone(blocking)
        self.assertEqual(blocking["caseId"], first_case["caseId"])

        camera_notifications = [
            row for row in list_notifications() if row.get("cameraId") == "CAM-NOTIFY-DUP"
        ]
        self.assertEqual(len(camera_notifications), 1)


class DecisionLoggingTests(unittest.TestCase):
    """The [decision] log line is the primary audit trail for 'why didn't
    this crash notify' questions — every field must be present and
    grep-able under its documented name."""

    def test_log_line_contains_all_required_fields(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            log_crash_decision(
                camera_id="CAM-LOG-TEST",
                vehicle_count=2,
                person_count=0,
                scene_valid=True,
                motion_valid=False,
                crash_score=0.99,
                consecutive_positive_frames=1,
                required_consecutive_frames=LIVE_CAMERA_REQUIRED_HITS,
                active_case_exists=False,
                cooldown_passed=True,
                final_decision="ignored",
                rejection_reason="motion_not_crash_like",
                case_created=False,
                notification_created=False,
            )
        line = buffer.getvalue()

        self.assertIn("crashScore=0.9900", line)
        self.assertIn("finalDecision=ignored", line)
        self.assertIn("rejectionReason=motion_not_crash_like", line)
        self.assertIn("vehicleCount=2", line)
        self.assertIn("motionValid=False", line)
        self.assertIn("sceneValid=True", line)
        self.assertIn("consecutiveCrashHits=1", line)
        self.assertIn(f"requiredConsecutiveCrashHits={LIVE_CAMERA_REQUIRED_HITS}", line)
        self.assertIn("activeCaseExists=False", line)
        self.assertIn("cooldownPassed=True", line)
        self.assertIn("caseCreated=False", line)
        self.assertIn("notificationCreated=False", line)


class HighConfidenceReviewCaseTests(RepositorySafetyGateBase):
    """The high_confidence_review tier: a single high-confidence frame with
    at least one in-ROI vehicle creates a pending_review Needs Review case
    and notification WITHOUT motion corroboration or the 3-frame temporal
    streak (see evaluate_crash_case_decision and
    _require_confirmed_crash_payload). 80% remains a UI-only warning
    threshold — only 90%+ can create anything."""

    def _notifications_for_case(self, case_id: str) -> list[dict]:
        return [row for row in list_notifications() if row["caseId"] == case_id]

    def test_score_0_89_creates_no_case(self):
        should_create, reason, decision = decide_single_frame(crash_confidence=0.89)
        self.assertFalse(should_create)
        self.assertEqual(reason, "below_case_threshold")
        self.assertEqual(decision, "ignored")

        payload = self._base_payload(
            cameraId="CAM-REVIEW-089",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.89},
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)
        self.assertEqual(len(list_notifications()), 0)

    def test_score_0_90_with_vehicle_creates_pending_review_case_and_notification(self):
        should_create, reason, decision = decide_single_frame(crash_confidence=0.90)
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "high_confidence_review")

        payload = self._base_payload(
            cameraId="CAM-REVIEW-090",
            cameraName="Matina Crossing CCTV",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.90},
        )
        case_item = create_crash_case(payload)
        self.assertIsNotNone(case_item)
        self.assertEqual(case_item["status"], "pending_review")
        self.assertIsNotNone(case_item.get("createdNotificationId"))

        notifications = self._notifications_for_case(case_item["caseId"])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["title"], "Car Crash Detected")
        self.assertIn("90%", notifications[0]["message"])
        self.assertIn("Matina Crossing CCTV", notifications[0]["message"])
        self.assertIn("review", notifications[0]["message"].lower())

    def test_score_0_99_with_vehicle_creates_pending_review_case_and_notification(self):
        should_create, reason, decision = decide_single_frame(crash_confidence=0.99)
        self.assertTrue(should_create)
        self.assertIsNone(reason)
        self.assertEqual(decision, "high_confidence_review")

        payload = self._base_payload(
            cameraId="CAM-REVIEW-099",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.99},
        )
        case_item = create_crash_case(payload)
        self.assertIsNotNone(case_item)
        self.assertEqual(case_item["status"], "pending_review")
        notifications = self._notifications_for_case(case_item["caseId"])
        self.assertEqual(len(notifications), 1)
        self.assertIn("99%", notifications[0]["message"])

    def test_score_0_99_no_vehicle_creates_no_case(self):
        should_create, reason, decision = decide_single_frame(
            crash_confidence=0.99, vehicle_count=0, person_count=0
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "no_vehicle_detected")
        self.assertEqual(decision, "ignored")

        payload = self._base_payload(
            cameraId="CAM-REVIEW-NOVEHICLE",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.99, "vehicleCount": 0},
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)
        self.assertEqual(len(list_notifications()), 0)

    def test_score_0_99_person_only_creates_no_case(self):
        should_create, reason, decision = decide_single_frame(
            crash_confidence=0.99, vehicle_count=0, person_count=1
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "person_only_not_crash")
        self.assertEqual(decision, "ignored")

        payload = self._base_payload(
            cameraId="CAM-REVIEW-PERSON",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.99, "vehicleCount": 0},
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)
        self.assertEqual(len(list_notifications()), 0)

    def test_active_pending_review_case_blocks_duplicate(self):
        payload = self._base_payload(
            cameraId="CAM-REVIEW-DUP",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.95},
        )
        first_case = create_crash_case(payload)
        self.assertEqual(first_case["status"], "pending_review")
        self.assertEqual(len(self._notifications_for_case(first_case["caseId"])), 1)

        should_create_second, reason_second, decision_second = decide_single_frame(
            crash_confidence=0.99, active_case_exists=True
        )
        self.assertFalse(should_create_second)
        self.assertEqual(reason_second, "active_case_exists")
        self.assertEqual(decision_second, "duplicate_active_case")

        blocking = find_unresolved_camera_case(camera_id="CAM-REVIEW-DUP")
        self.assertIsNotNone(blocking)
        self.assertEqual(blocking["caseId"], first_case["caseId"])
        camera_notifications = [
            row for row in list_notifications() if row.get("cameraId") == "CAM-REVIEW-DUP"
        ]
        self.assertEqual(len(camera_notifications), 1)

    def test_cooldown_blocks_duplicate(self):
        payload = self._base_payload(
            cameraId="CAM-REVIEW-COOLDOWN",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.95},
        )
        first_case = create_crash_case(payload)
        self.assertEqual(len(self._notifications_for_case(first_case["caseId"])), 1)

        should_create_second, reason_second, decision_second = decide_single_frame(
            crash_confidence=0.99, cooldown_ready=False
        )
        self.assertFalse(should_create_second)
        self.assertEqual(reason_second, "cooldown_active")
        self.assertEqual(decision_second, "duplicate_cooldown")

    def test_ui_warning_at_80_percent_does_not_create_notification(self):
        # 80% remains a UI-only visual warning threshold. Only 90%+ can
        # create a case or notification, of either tier.
        should_create, reason, decision = decide_single_frame(crash_confidence=0.80)
        self.assertFalse(should_create)
        self.assertEqual(reason, "below_case_threshold")
        self.assertEqual(decision, "ignored")

        payload = self._base_payload(
            cameraId="CAM-REVIEW-UI80",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.80},
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)
        self.assertEqual(len(list_notifications()), 0)


class LowConfidenceCandidateTests(RepositorySafetyGateBase):
    """80-89% ("possible crash candidate") must never reach a case-creating
    finalDecision, never create a case/notification, and — this is the data
    contract the frontend's "Car Crash" box-label fix depends on — must
    never look like a case was allowed. A normal bus/car in ordinary traffic
    scored at 86% is the exact scenario this covers."""

    def test_score_0_86_does_not_reach_case_creating_decision(self):
        # This is the data contract the UI fix relies on: at 86%, finalDecision
        # can never be confirmed_crash or high_confidence_review, so the
        # frontend's box-label override (which requires exactly one of those
        # two values) can never fire — a normal vehicle box keeps its real
        # object label instead of being mislabeled "Car Crash 86%".
        should_create, reason, decision = decide_single_frame(crash_confidence=0.86)
        self.assertFalse(should_create)
        self.assertEqual(reason, "below_case_threshold")
        self.assertEqual(decision, "ignored")
        self.assertNotIn(decision, {"confirmed_crash", "high_confidence_review"})

    def test_score_0_86_bus_in_normal_traffic_does_not_reach_case_creating_decision(self):
        # Multiple vehicles (e.g. a bus among normal traffic) with full
        # motion corroboration and a complete temporal streak still cannot
        # create anything at 86% — the score itself is the only thing that
        # matters at this stage, and it's below CRASH_CASE_THRESHOLD.
        should_create, reason, decision = decide(
            crash_confidence=0.86, vehicle_count=3, motion_valid=True
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "below_case_threshold")
        self.assertEqual(decision, "ignored")

    def test_score_0_86_creates_no_notification(self):
        payload = self._base_payload(
            cameraId="CAM-CANDIDATE-086",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.86},
        )
        with self.assertRaises(CrashCaseRejected) as ctx:
            create_crash_case(payload)
        self.assertEqual(ctx.exception.reason, "missing_confirmed_crash_decision")
        self.assertEqual(len(list_notifications()), 0)

    def test_score_0_86_creates_no_review_case(self):
        payload = self._base_payload(
            cameraId="CAM-CANDIDATE-086B",
            **{**HIGH_CONFIDENCE_REVIEW_GATE_FIELDS, "crashScore": 0.86},
        )
        with self.assertRaises(CrashCaseRejected):
            create_crash_case(payload)
        matching = [
            case for case in list_crash_cases(area_id="demo") if case["cameraId"] == "CAM-CANDIDATE-086B"
        ]
        self.assertEqual(len(matching), 0)


if __name__ == "__main__":
    unittest.main()
