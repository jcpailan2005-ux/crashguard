"""Deterministic session identities plus the actual production worker path."""
import base64
import threading
import unittest
import numpy as np
import cv2
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

    def test_distinct_physical_vehicles_must_not_reuse_track_identity(self):
        # Final normal-traffic review: silver hatchback at sequence 130 moves
        # left; a different black car fills its former box at 138. Geometry-only
        # association incorrectly gives the black car the silver car's ID.
        # This repaired identity gate is a normal assertion. The separate
        # scene-level pair-safety expected failure remains unchanged.
        tracker = SessionVehicleTracker("Bago", "normal-review")
        first = tracker.update("normal-review", 130, 0.0,
            [detection(734, 239, 991, 428)], frame_width=1280, frame_height=720)
        second = tracker.update("normal-review", 138, .55,
            [detection(505, 171, 745, 327), detection(776, 274, 1060, 469)],
            frame_width=1280, frame_height=720)
        self.assertNotEqual(first.boxes[0]["trackId"], second.boxes[1]["trackId"])


class ConservativeAssociationTests(unittest.TestCase):
    def setUp(self):
        self.tracker = SessionVehicleTracker("Bago", "quality", diagnostics=True)

    def observe(self, seq, participants, at=None, reverse=False):
        image = np.full((240, 400, 3), 100, dtype=np.uint8)
        values = list(participants)
        if reverse:
            values.reverse()
        boxes = []
        for owner, bbox, color in values:
            x1, y1, x2, y2 = bbox
            image[y1:y2, x1:x2] = color
            boxes.append(detection(*bbox))
        result = self.tracker.update("quality", seq, seq*.1 if at is None else at,
            boxes, frame_width=400, frame_height=240, source_frame=image)
        return result, {owner: box["trackId"] for (owner, _, _), box in zip(values, result.boxes)}

    def assert_owned_sequences(self, sequences):
        owners = {}
        for seq, participants in enumerate(sequences, 1):
            result, ids = self.observe(seq, participants, reverse=bool(seq%2))
            self.assertEqual(len(set(ids.values())), len(ids))
            for owner, tid in ids.items():
                self.assertEqual(owners.setdefault(tid, owner), owner,
                                 "A continued ID transferred to another physical participant")
        return owners

    def test_two_vehicles_cross_without_transferring_ids(self):
        self.assert_owned_sequences([
            [("east", (40+i*8, 60, 80+i*8, 90), (210, 210, 210)),
             ("west", (136-i*8, 60, 176-i*8, 90), (25, 25, 25))]
            for i in range(12)])

    def test_same_lane_close_following_keeps_correct_ownership(self):
        sequences = [[("front", (110+i*3, 60, 150+i*3, 90), (210, 210, 210)),
                      ("rear", (50+i*3, 60, 90+i*3, 90), (25, 25, 25))] for i in range(10)]
        owners = self.assert_owned_sequences(sequences)
        self.assertEqual(len(owners), 2)

    def test_overtaking_with_reversed_detection_order(self):
        self.assert_owned_sequences([
            [("fast", (40+i*6, 50, 75+i*6, 75), (210, 210, 210)),
             ("slow", (70+i*2, 85, 105+i*2, 110), (25, 25, 25))]
            for i in range(18)])

    def test_id_allocation_and_assignment_are_detection_order_independent(self):
        boxes = [detection(10, 20, 50, 50), detection(200, 20, 240, 50)]
        a = SessionVehicleTracker("C", "S")
        b = SessionVehicleTracker("C", "S")
        for seq in range(1, 5):
            first = a.update("S", seq, seq*.1, boxes, frame_width=400, frame_height=240)
            second = b.update("S", seq, seq*.1, list(reversed(boxes)), frame_width=400, frame_height=240)
            self.assertEqual({box['x']:box['trackId'] for box in first.boxes},
                             {box['x']:box['trackId'] for box in second.boxes})

    def test_one_and_two_frame_misses_recover_only_same_appearance(self):
        car = [("car", (30, 60, 90, 110), (200, 200, 200))]
        _, ids = self.observe(1, car)
        self.observe(2, car)
        self.observe(3, [])
        first, returned = self.observe(4, car)
        self.assertEqual(returned, ids)
        self.observe(5, [])
        self.observe(6, [])
        second, returned = self.observe(7, car)
        self.assertEqual(returned, ids)
        self.assertTrue(first.boxes[0]['detected'] and second.boxes[0]['detected'])

    def test_new_vehicle_filling_missed_box_gets_new_id(self):
        _, old = self.observe(1, [("silver", (30, 60, 90, 110), (200, 200, 200))])
        self.observe(2, [])
        result, new = self.observe(3, [("black", (30, 60, 90, 110), (20, 20, 20))])
        self.assertNotEqual(old['silver'], new['black'])
        self.assertIn('appearance', result.association_diagnostics[0]['rejected_gates'])

    def test_replacement_without_empty_frame_is_rejected_by_real_pixels(self):
        _, old = self.observe(1, [("silver", (30, 60, 90, 110), (200, 200, 200))])
        _, new = self.observe(2, [("blue", (30, 60, 90, 110), (180, 45, 25))])
        self.assertNotEqual(old['silver'], new['blue'])

    def test_gradual_perspective_scale_change_preserves_identity(self):
        ids = []
        for i in range(6):
            _, identity = self.observe(i+1, [("car", (30, 60, 90+i*2, 110+i), (200, 200, 200))])
            ids.append(identity['car'])
        self.assertEqual(len(set(ids)), 1)

    def test_abrupt_scale_and_aspect_changes_fragment(self):
        for replacement in [detection(30, 60, 115, 110), detection(20, 65, 100, 105)]:
            tracker = SessionVehicleTracker("C", "S")
            old = tracker.update("S", 1, .1, [detection(30, 60, 90, 110)], frame_width=400, frame_height=240)
            new = tracker.update("S", 2, .2, [replacement], frame_width=400, frame_height=240)
            self.assertNotEqual(old.boxes[0]['trackId'], new.boxes[0]['trackId'])

    def test_duplicate_boxes_do_not_inherit_or_seed_continuity(self):
        box = detection(30, 60, 90, 110)
        old = self.tracker.update("quality", 1, .1, [box], frame_width=400, frame_height=240)
        duplicate = self.tracker.update("quality", 2, .2, [box, box], frame_width=400, frame_height=240)
        new = self.tracker.update("quality", 3, .3, [box], frame_width=400, frame_height=240)
        ids = [b['trackId'] for b in duplicate.boxes]
        self.assertNotIn(old.boxes[0]['trackId'], ids)
        self.assertNotIn(new.boxes[0]['trackId'], ids)
        self.assertEqual(len(set(ids)), 2)

    def test_multiple_simultaneous_vehicles_keep_unique_ownership(self):
        owners = self.assert_owned_sequences([
            [(str(i), (i*55+seq, 60, i*55+seq+35, 90), (50+i*20,)*3)
             for i in range(6)] for seq in range(10)])
        self.assertEqual(len(owners), 6)

    def test_ambiguous_crossing_retires_continuity_instead_of_resurrecting(self):
        old = self.tracker.update("quality", 1, .1,
            [detection(40, 60, 100, 110), detection(60, 60, 120, 110)], frame_width=400, frame_height=240)
        ambiguous = self.tracker.update("quality", 2, .2,
            [detection(50, 60, 110, 110)], frame_width=400, frame_height=240)
        old_ids = [box['trackId'] for box in old.boxes]
        self.assertNotIn(ambiguous.boxes[0]['trackId'], old_ids)
        self.assertTrue(set(old_ids).issubset(ambiguous.retired_track_ids))

    def test_stale_bootstrap_and_moving_track_cannot_continue_after_frame_gap(self):
        for history in (1, 3):
            tracker = SessionVehicleTracker("C", "S")
            for seq in range(1, history+1):
                old = tracker.update("S", seq, seq*.1, [detection(30, 60, 90, 110)], frame_width=400, frame_height=240)
            new = tracker.update("S", history+1, history*.1+.7,
                [detection(30, 60, 90, 110)], frame_width=400, frame_height=240)
            self.assertNotEqual(old.boxes[0]['trackId'], new.boxes[0]['trackId'])

    def test_appearance_anchor_rejects_gradual_identity_drift(self):
        _, original = self.observe(1, [("car", (30, 60, 90, 110), (200, 200, 200))])
        for seq, value in enumerate((190, 180, 170, 160, 150), 2):
            _, current = self.observe(seq, [("car", (30, 60, 90, 110), (value, value, value))])
        self.assertNotEqual(original, current)

    def test_missing_or_invalid_pixels_never_override_identity_evidence(self):
        box = detection(30, 60, 90, 110)
        _, original = self.observe(1, [("car", (30, 60, 90, 110), (200, 200, 200))])
        new = self.tracker.update("quality", 2, .2, [box], frame_width=400, frame_height=240)
        self.assertNotEqual(original['car'], new.boxes[0]['trackId'])
        with self.assertRaises(ValueError):
            self.tracker.update("quality", 3, .3, [box], frame_width=400, frame_height=240,
                                source_frame=np.zeros((10, 10, 3), dtype=np.uint8))
        self.assertEqual(self.tracker.last_sequence, 2)

    def test_diagnostics_are_bounded_and_never_serialize_caller_secrets(self):
        tracker = SessionVehicleTracker("rtsp://synthetic:synthetic@camera.invalid", "synthetic?token=fake", diagnostics=True)
        boxes = [detection(i*45, 60, i*45+30, 90) for i in range(8)]
        tracker.update(tracker.session_id, 1, .1, boxes, frame_width=400, frame_height=240)
        result = tracker.update(tracker.session_id, 2, .2, boxes, frame_width=400, frame_height=240)
        self.assertLessEqual(len(result.association_diagnostics), 64)
        self.assertTrue(all(row['camera_id']=='redacted' and row['session_id']=='redacted'
                            for row in result.association_diagnostics))


class LowCadenceContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tracker = SessionVehicleTracker("Bago", "slow", diagnostics=True)
        self.sequence = 0

    def observe(self, timestamp, participants, reverse=False):
        self.sequence += 1
        image = np.full((300, 600, 3), 100, dtype=np.uint8)
        participants = list(reversed(participants)) if reverse else list(participants)
        for _, bbox, color in participants:
            x1, y1, x2, y2 = bbox
            # Deterministic visible texture supplies actual image-motion evidence.
            # The texture is shared: labels are never available to the tracker.
            texture = np.random.default_rng(7).integers(-24,25,(16,20)).astype(np.float32)
            texture = cv2.resize(texture,(x2-x1,y2-y1),interpolation=cv2.INTER_LINEAR)
            image[y1:y2,x1:x2] = np.clip(np.asarray(color)+texture[:,:,None],0,255).astype(np.uint8)
        result = self.tracker.update("slow", self.sequence, timestamp,
            [detection(*bbox) for _, bbox, _ in participants],
            frame_width=600, frame_height=300, source_frame=image)
        return result, {owner: b["trackId"] for (owner, _, _), b in zip(participants, result.boxes)}

    def test_same_vehicle_at_point_eight_to_one_point_two_seconds_continues(self):
        for gap in (.8, 1.0, 1.2):
            self.setUp()
            _, first = self.observe(0, [("car", (40, 60, 100, 110), (200,)*3)])
            second, ids = self.observe(gap, [("car", (70, 60, 130, 110), (200,)*3)])
            self.assertEqual(ids, first)
            self.assertEqual(second.boxes[0]["trackLifecycle"], "ACTIVE")
            third, ids = self.observe(gap*2, [("car", (100, 60, 160, 110), (200,)*3)])
            self.assertEqual(ids, first)
            self.assertTrue(any(d['matched'] and d['continuation_path']=='pixel_motion'
                                for d in third.association_diagnostics))

    def test_perspective_scale_change_at_low_cadence_continues(self):
        _, first = self.observe(0, [("car", (40, 60, 100, 110), (200,)*3)])
        _, second = self.observe(1, [("car", (65, 58, 137, 114), (200,)*3)])
        self.assertEqual(second, first)

    def test_one_missed_one_fps_observation_recovers_only_motion_consistent_owner(self):
        _, first = self.observe(0, [("car", (40, 60, 100, 110), (200,)*3)])
        _, second = self.observe(1, [("car", (75, 60, 135, 110), (200,)*3)])
        self.assertEqual(first, second)
        missed, _ = self.observe(2, [])
        self.assertFalse(missed.predicted_tracks[0]['collisionObservation'])
        returned, third = self.observe(3, [("car", (145, 60, 205, 110), (200,)*3)])
        self.assertEqual(first, third)
        self.assertEqual(returned.boxes[0]['lastDetectedSequence'], 4)

    def test_fast_motion_without_real_box_overlap_uses_learned_velocity(self):
        _, first = self.observe(0, [("car", (40, 60, 100, 110), (200,)*3)])
        _, trained = self.observe(.2, [("car", (55, 60, 115, 110), (200,)*3)])
        self.assertEqual(first, trained)
        self.assertEqual(SessionVehicleTracker._geometry(np.asarray((55,60,115,110)),
            np.asarray((145,60,205,110)))[0], 0)
        _, result = self.observe(1.4, [("car", (145, 60, 205, 110), (200,)*3)])
        self.assertEqual(first, result)
        _, result = self.observe(2.6, [("car", (235, 60, 295, 110), (200,)*3)])
        self.assertEqual(first, result)

    def test_two_same_appearance_neighbors_only_motion_consistent_track_continues(self):
        _, first = self.observe(0, [("east", (40, 60, 100, 110), (200,)*3),
                                   ("west", (140, 60, 200, 110), (200,)*3)])
        _, trained = self.observe(.2, [("east", (50, 60, 110, 110), (200,)*3),
                                       ("west", (150, 60, 210, 110), (200,)*3)], reverse=True)
        self.assertEqual(first, trained)
        _, current = self.observe(1.2, [("east", (100, 60, 160, 110), (200,)*3)])
        self.assertEqual(current['east'], first['east'])
        self.assertNotEqual(current['east'], first['west'])

    def test_two_bootstrap_vehicles_with_unresolved_ownership_fragment(self):
        _, first = self.observe(0, [("east", (40, 60, 100, 110), (200,)*3),
                                   ("west", (160, 60, 220, 110), (200,)*3)])
        # The east trajectory could reach this box even without old-box overlap.
        _, uncertain = self.observe(1, [("unknown", (130, 60, 190, 110), (200,)*3)])
        self.assertNotIn(uncertain['unknown'], first.values())

    def test_learned_converging_trajectories_still_fragment_and_retire(self):
        _, first = self.observe(0, [("east", (40, 60, 100, 110), (200,)*3),
                                   ("west", (160, 60, 220, 110), (200,)*3)])
        _, trained = self.observe(.2, [("east", (50, 60, 110, 110), (200,)*3),
                                       ("west", (150, 60, 210, 110), (200,)*3)])
        self.assertEqual(first, trained)
        uncertain, ids = self.observe(1.2, [("unknown", (100, 60, 160, 110), (200,)*3)])
        self.assertNotIn(ids['unknown'], first.values())
        self.assertTrue(set(first.values()).issubset(uncertain.retired_track_ids))

    def test_slow_cadence_preserves_reversed_detection_order(self):
        owners = {}
        for i in range(4):
            _, ids = self.observe(i, [("light", (40+i*25, 60, 100+i*25, 110), (200,)*3),
                                      ("dark", (280+i*25, 60, 340+i*25, 110), (25,)*3)], reverse=bool(i%2))
            if not owners:
                owners = ids
            self.assertEqual(ids, owners)

    def test_replacement_and_velocity_contradiction_never_inherit_slow_id(self):
        _, first = self.observe(0, [("old", (40, 60, 100, 110), (200,)*3)])
        _, trained = self.observe(.2, [("old", (50, 60, 110, 110), (200,)*3)])
        self.assertEqual(trained, first)
        _, replacement = self.observe(1.2, [("other", (50, 60, 110, 110), (200,)*3)])
        self.assertNotEqual(replacement['other'], first['old'])
        self.setUp()
        _, first = self.observe(0, [("light", (40, 60, 100, 110), (200,)*3)])
        _, replacement = self.observe(1, [("dark", (70, 60, 130, 110), (25,)*3)])
        self.assertNotEqual(replacement['dark'], first['light'])

    def test_near_threshold_appearance_rival_still_blocks_continuation(self):
        _, first = self.observe(0, [("car", (40, 60, 100, 110), (200,)*3)])
        _, current = self.observe(1, [("same", (65, 60, 125, 110), (200,)*3),
                                      ("rival", (85, 60, 145, 110), (195,)*3)])
        self.assertNotIn(first['car'], current.values())

    def test_two_missed_observations_and_long_gap_do_not_resurrect_old_identity(self):
        _, first = self.observe(0, [("car", (40, 60, 100, 110), (200,)*3)])
        self.observe(1, [("car", (70, 60, 130, 110), (200,)*3)])
        self.observe(2, [])
        self.observe(3, [])
        _, current = self.observe(4, [("car", (160, 60, 220, 110), (200,)*3)])
        self.assertNotEqual(first, current)

    def test_textureless_bootstrap_does_not_claim_low_cadence_continuation(self):
        old_image = np.full((300,600,3),100,dtype=np.uint8)
        new_image = old_image.copy()
        old_image[60:110,40:100] = 200
        new_image[60:110,70:130] = 200
        old = self.tracker.update('slow',1,0,[detection(40,60,100,110)],
            frame_width=600,frame_height=300,source_frame=old_image)
        new = self.tracker.update('slow',2,1,[detection(70,60,130,110)],
            frame_width=600,frame_height=300,source_frame=new_image)
        self.assertNotEqual(old.boxes[0]['trackId'],new.boxes[0]['trackId'])

    def test_short_gap_similar_colored_replacement_needs_pixel_motion_proof(self):
        images=[]
        for seed,x in [(7,40),(83,55)]:
            image=np.full((300,600,3),100,np.uint8)
            texture=np.random.default_rng(seed).integers(-80,81,(16,20)).astype(np.float32)
            texture=cv2.resize(texture,(60,50))
            image[60:110,x:x+60]=np.clip(160+texture[:,:,None],0,255).astype(np.uint8)
            images.append(image)
        old=self.tracker.update('slow',1,0,[detection(40,60,100,110)],
            frame_width=600,frame_height=300,source_frame=images[0])
        new=self.tracker.update('slow',2,.3,[detection(55,60,115,110)],
            frame_width=600,frame_height=300,source_frame=images[1])
        self.assertNotEqual(old.boxes[0]['trackId'],new.boxes[0]['trackId'])

    def test_verified_fast_bootstrap_has_no_cadence_boundary_gap(self):
        for elapsed in (.2, .4, .41):
            with self.subTest(elapsed=elapsed):
                self.setUp()
                _, first = self.observe(0, [("car", (40, 60, 100, 110), (200,)*3)])
                _, current = self.observe(elapsed, [("car", (64, 60, 124, 110), (200,)*3)])
                self.assertEqual(first, current)


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
