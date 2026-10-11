"""Deterministic session identities plus the actual production worker path."""
import base64
import threading
import unittest
from unittest.mock import Mock, patch

from backend.services.session_vehicle_tracking import SessionVehicleTracker, SessionTrackingConfig
from backend.tests.test_vehicle_tracking import detection
from backend.validation.live_cctv_implementation_stage1_20261001.test_stage1 import worker, frame


class SessionTrackingTests(unittest.TestCase):
    def setUp(self):
        self.tracker = SessionVehicleTracker("Bago", "A")

    def update(self, seq, boxes, timestamp=None):
        return self.tracker.update("A", seq, seq*.2 if timestamp is None else timestamp,
                                   boxes, frame_width=640, frame_height=480)

    def test_adjacent_observations_keep_id_and_exact_detector_boxes(self):
        first = self.update(1, [detection(10, 20, 80, 80)])
        box = detection(14, 20, 84, 80)
        second = self.update(2, [box])
        self.assertEqual(first.boxes[0]["trackId"], second.boxes[0]["trackId"])
        self.assertEqual(second.boxes[0]["trackLifecycle"], "ACTIVE")
        for key, value in box.items():
            self.assertEqual(second.boxes[0][key], value)

    def test_two_vehicles_distinct_and_reversed_order_independent(self):
        left, right = detection(10, 20, 80, 80), detection(300, 20, 380, 80)
        first = self.update(1, [left, right])
        second = self.update(2, [right, left])
        self.assertNotEqual(first.boxes[0]["trackId"], first.boxes[1]["trackId"])
        self.assertEqual([b["trackId"] for b in second.boxes],
                         [b["trackId"] for b in reversed(first.boxes)])

    def test_short_miss_preserves_id_with_explicit_prediction(self):
        first = self.update(1, [detection(10, 20, 80, 80)])
        self.update(2, [detection(14, 20, 84, 80)])
        missed = self.update(3, [])
        self.assertEqual(missed.boxes, ())
        prediction = missed.predicted_tracks[0]
        self.assertEqual(prediction["observationKind"], "PREDICTED")
        self.assertFalse(prediction["detected"])
        self.assertFalse(prediction["collisionObservation"])
        self.assertEqual(prediction["lastDetectedSequence"], 2)
        self.assertEqual(prediction["trackLifecycle"], "TEMPORARILY_MISSED")
        self.assertGreater(prediction["x"], 14)
        returned = self.update(4, [detection(22, 20, 92, 80)])
        self.assertEqual(first.boxes[0]["trackId"], returned.boxes[0]["trackId"])

    def test_long_absence_retires_before_association_even_without_empty_frames(self):
        first = self.update(1, [detection(10, 20, 80, 80)])
        returned = self.update(20, [detection(10, 20, 80, 80)])
        self.assertIn(first.boxes[0]["trackId"], returned.retired_track_ids)
        self.assertNotEqual(first.boxes[0]["trackId"], returned.boxes[0]["trackId"])

    def test_missed_frame_budget_retires_and_return_gets_new_id(self):
        first = self.update(1, [detection(10, 20, 80, 80)])
        for seq in range(2, 6):
            missed = self.update(seq, [])
        self.assertEqual(self.tracker.tracks, {})
        self.assertEqual(missed.retired_track_ids, (first.boxes[0]["trackId"],))
        returned = self.update(6, [detection(10, 20, 80, 80)])
        self.assertNotEqual(first.boxes[0]["trackId"], returned.boxes[0]["trackId"])

    def test_camera_isolation_even_with_same_numeric_id(self):
        fobos = SessionVehicleTracker("FOBOS", "B")
        a = self.update(1, [detection(10, 20, 80, 80)]).boxes[0]
        b = fobos.update("B", 1, .2, [detection(300, 20, 380, 80)],
                         frame_width=640, frame_height=480).boxes[0]
        self.assertEqual(a["trackId"], b["trackId"])
        self.assertNotEqual((a["cameraId"], a["sessionId"], a["trackId"]),
                            (b["cameraId"], b["sessionId"], b["trackId"]))
        self.update(2, [])
        self.assertEqual(fobos.tracks[1].missed_frames, 0)

    def test_reset_clears_histories_and_old_session_cannot_roll_back(self):
        self.update(1, [detection(10, 20, 80, 80)])
        self.tracker.reset("B")
        self.assertEqual(self.tracker.tracks, {})
        with self.assertRaises(ValueError):
            self.update(2, [detection(10, 20, 80, 80)])
        self.assertEqual(self.tracker.session_id, "B")
        new = self.tracker.update("B", 1, .2, [detection(10, 20, 80, 80)],
                                  frame_width=640, frame_height=480)
        self.assertEqual(new.boxes[0]["sessionId"], "B")
        self.assertEqual(len(self.tracker.tracks[1].history), 1)

    def test_stop_disables_old_session_observations(self):
        self.tracker.reset(None)
        with self.assertRaises(ValueError):
            self.update(1, [])

    def test_duplicate_and_late_frames_do_not_mutate_state(self):
        self.update(2, [detection(10, 20, 80, 80)])
        for seq, at in [(2, .5), (1, .6), (3, .3), (3, float("nan"))]:
            with self.assertRaises(ValueError):
                self.update(seq, [], at)
        self.assertEqual(self.tracker.last_sequence, 2)
        self.assertEqual(len(self.tracker.tracks[1].history), 1)
        self.assertEqual(self.tracker.tracks[1].missed_frames, 0)

    def test_coarse_clock_same_timestamp_new_sequence_is_valid(self):
        self.update(1, [detection(10, 20, 80, 80)], .2)
        result = self.update(2, [detection(12, 20, 82, 80)], .2)
        self.assertEqual(result.boxes[0]["trackId"], 1)
        self.assertEqual(self.tracker.last_sequence, 2)

    def test_detected_and_predicted_history_is_bounded(self):
        for seq in range(1, 80):
            self.update(seq, [] if seq%3 == 0 else [detection(10, 20, 80, 80)])
        track = self.tracker.tracks[1]
        self.assertEqual(len(track.history), 16)
        self.assertLessEqual(len(track.state.history), 16)
        self.assertTrue(any(not point.detected for point in track.history))
        self.assertTrue(all(point.detected for point in track.history if point.sequence%3))

    def test_track_memory_bounded_during_churn(self):
        self.tracker = SessionVehicleTracker("Bago", "A", SessionTrackingConfig(max_tracks=3))
        for seq in range(1, 100):
            self.update(seq, [detection((seq%4)*140, 20, (seq%4)*140+20, 40)])
            self.assertLessEqual(len(self.tracker.tracks), 3)
            self.assertTrue(all(len(t.history) <= 16 for t in self.tracker.tracks.values()))

    def test_capacity_does_not_silently_drop_accepted_vehicles(self):
        self.tracker = SessionVehicleTracker("Bago", "A", SessionTrackingConfig(max_tracks=2))
        with self.assertRaises(ValueError):
            self.update(1, [detection(i*150, 20, i*150+40, 80) for i in range(3)])
        self.assertEqual(self.tracker.tracks, {})
        self.assertEqual(self.tracker.last_sequence, -1)

    def test_class_incompatibility_and_ambiguity_start_new_identity(self):
        first = self.update(1, [detection(10, 20, 80, 80)])
        second = self.update(2, [detection(10, 20, 80, 80, label="bus", class_id=5)])
        self.assertNotEqual(first.boxes[0]["trackId"], second.boxes[0]["trackId"])
        self.tracker.reset("A")
        first = self.update(1, [detection(10, 20, 80, 80), detection(10, 20, 80, 80)])
        second = self.update(2, [detection(10, 20, 80, 80)])
        self.assertNotIn(second.boxes[0]["trackId"], [b["trackId"] for b in first.boxes])

    def test_resolution_change_retires_pixel_motion_history(self):
        self.update(1, [detection(10, 20, 80, 80)])
        result = self.tracker.update("A", 2, .4, [detection(10, 20, 80, 80)],
                                    frame_width=1280, frame_height=720)
        self.assertEqual(result.retired_track_ids, (1,))
        self.assertEqual(result.boxes[0]["trackId"], 2)

    def test_missed_large_vehicle_does_not_claim_different_nearby_vehicle(self):
        # Normal-traffic review found a missed bus transferred to a distinct van
        # also mislabeled bus. Class compatibility alone cannot authorize that.
        self.update(1, [detection(184, 17, 549, 462, label="bus", class_id=5)])
        self.update(2, [detection(147, 37, 433, 365, label="bus", class_id=5)])
        self.update(3, [])
        returned = self.update(4, [detection(288, 140, 605, 542, label="bus", class_id=5)])
        self.assertNotEqual(returned.boxes[0]["trackId"], 1)

    def test_large_to_small_box_handoff_starts_new_identity(self):
        self.update(1, [detection(288, 140, 605, 542, label="bus", class_id=5)])
        result = self.update(2, [detection(539, 168, 777, 373, label="bus", class_id=5)])
        self.assertEqual(result.boxes[0]["trackId"], 2)

    @unittest.expectedFailure
    def test_distinct_physical_vehicles_must_not_reuse_track_identity(self):
        # Final normal-traffic review: silver hatchback at sequence 130 moves
        # left; a different black car fills its former box at 138. Geometry-only
        # association incorrectly gives the black car the silver car's ID.
        # Keep this physical-identity gate visible until association is repaired.
        tracker = SessionVehicleTracker("Bago", "normal-review")
        first = tracker.update("normal-review", 130, 0.0,
            [detection(734, 239, 991, 428)], frame_width=1280, frame_height=720)
        second = tracker.update("normal-review", 138, .55,
            [detection(505, 171, 745, 327), detection(776, 274, 1060, 469)],
            frame_width=1280, frame_height=720)
        self.assertNotEqual(first.boxes[0]["trackId"], second.boxes[1]["trackId"])


class ProductionTrackingTests(unittest.TestCase):
    def prepare(self):
        m, ns = worker()
        ns["base64"] = base64
        ns["detect_vehicle_boxes"] = Mock(return_value=[detection(10, 10, 35, 35)])
        return m, ns

    def analyze(self, m):
        m.seed_first_frame(frame(80))
        return m.analyze_current_frame()

    def test_worker_keeps_ids_and_exact_stage2_provenance(self):
        m, _ = self.prepare()
        a, b = self.analyze(m), self.analyze(m)
        self.assertEqual(a["boxes"][0]["trackId"], b["boxes"][0]["trackId"])
        packet = m.latest_box_packet()
        self.assertEqual(packet["boxes"], b["boxes"])
        self.assertEqual(packet["sourceFrame"], b["sourceFrame"])
        self.assertEqual(packet["boxes"][0]["sessionId"], b["sourceFrame"]["sessionId"])
        self.assertEqual(packet["boxes"][0]["sequence"], b["sourceFrame"]["sequence"])

    def test_predictions_never_enter_vehicle_count_geometry_or_positive_hits(self):
        m, ns = self.prepare()
        self.analyze(m)
        ns["detect_vehicle_boxes"].return_value = []
        ns["classify_crash_frame"] = lambda _: dict(crashClass="accident", accidentProbability=.99)
        result = self.analyze(m)
        self.assertTrue(result["predictedTracks"])
        self.assertEqual(result["boxes"], [])
        self.assertEqual(result["vehicleCount"], 0)
        self.assertFalse(result["motionValid"])
        self.assertEqual(result["consecutiveCrashHits"], 0)
        self.assertFalse(m.hit_window[-1][1])
        ns["persist_sqlite_crash_case"].assert_not_called()

    def test_duplicate_worker_frame_does_not_advance_tracker(self):
        m, ns = self.prepare()
        self.analyze(m)
        count = ns["model"].predict.call_count
        with self.assertRaises(ValueError):
            m.analyze_current_frame()
        self.assertEqual(ns["model"].predict.call_count, count)
        self.assertEqual(len(m.vehicle_tracker.tracks[1].history), 1)

    def test_reconnect_while_inference_running_cannot_restore_old_tracks(self):
        m, ns = self.prepare()
        self.analyze(m)
        old_session = m.frame_epoch
        def predict(*_a, **_kw):
            with m.lock:
                m.frame_epoch = "new-session"
                m.vehicle_tracker.reset(m.frame_epoch)
            return []
        ns["model"].predict = predict
        with self.assertRaises(ValueError):
            self.analyze(m)
        self.assertEqual(m.vehicle_tracker.tracks, {})
        ns["model"].predict = Mock(return_value=[])
        result = self.analyze(m)
        self.assertNotEqual(old_session, result["boxes"][0]["sessionId"])
        self.assertEqual(len(m.vehicle_tracker.tracks[1].history), 1)

    def test_worker_replacement_and_stop_have_independent_state(self):
        a, _ = self.prepare()
        b, _ = self.prepare()
        self.analyze(a)
        self.analyze(b)
        a.stop()
        self.assertEqual(a.vehicle_tracker.tracks, {})
        self.assertEqual(len(b.vehicle_tracker.tracks), 1)
        self.assertNotEqual(a.frame_epoch, b.frame_epoch)

    def test_explicit_seed_after_disconnect_starts_fresh_session(self):
        m, _ = self.prepare()
        old = self.analyze(m)
        m.stop()
        new = self.analyze(m)
        self.assertNotEqual(old["sourceFrame"]["sessionId"], new["sourceFrame"]["sessionId"])
        self.assertEqual(len(m.vehicle_tracker.tracks[1].history), 1)

    def test_actual_capture_reconnect_resets_tracker_at_each_connection(self):
        from backend.services import camera_sources as sources
        m, _ = self.prepare()
        m.stream_url = "webcam://school-demo-webcam"
        self.analyze(m)
        sessions = []
        def capture():
            cap = Mock()
            cap.get.return_value = 30
            count = [0]
            def read():
                count[0] += 1
                if count[0] == 1:
                    self.assertEqual(m.vehicle_tracker.tracks, {})
                    self.assertEqual(m.vehicle_tracker.session_id, m.frame_epoch)
                    sessions.append(m.frame_epoch)
                    cap.received_at, cap.received_monotonic = __import__("time").time(), __import__("time").monotonic()
                    return True, frame(80)
                if len(sessions) == 2:
                    m.running = False
                return False, None
            cap.read.side_effect = read
            return cap
        m.running = True
        with patch.object(sources, "open_webcam", side_effect=[capture(), capture()]), patch.object(m.stop_event, "wait"):
            m._capture_loop()
        self.assertEqual(len(set(sessions)), 2)
        self.assertEqual(m.vehicle_tracker.tracks, {})
        self.assertIsNone(m.vehicle_tracker.session_id)

    def test_stopping_usb_keeps_rtsp_tracking_and_scheduler_progress(self):
        from backend.services.inference_execution import FairLatestFrameScheduler
        usb, _ = self.prepare()
        rtsp, _ = self.prepare()
        usb.stream_url = "webcam://school-demo-webcam"
        self.analyze(usb)
        first = self.analyze(rtsp)
        scheduler = FairLatestFrameScheduler(autostart=False)
        outputs = []
        scheduler.submit("USB", usb.frame_epoch, 2, lambda: self.analyze(usb))
        scheduler.submit("RTSP", rtsp.frame_epoch, 2, lambda: outputs.append(self.analyze(rtsp)))
        usb.stop()
        scheduler.cancel("USB", usb.frame_epoch)
        self.assertEqual(scheduler.run_next()[0], "RTSP")
        self.assertEqual(first["boxes"][0]["trackId"], outputs[0]["boxes"][0]["trackId"])
        self.assertEqual(scheduler.pending_count(), 0)


if __name__ == "__main__":
    unittest.main()
