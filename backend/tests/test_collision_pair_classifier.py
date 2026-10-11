import unittest
from unittest.mock import patch

import numpy as np

from backend import main
from backend.services.collision_pair_classifier import (
    CollisionPairConfig,
    SelectedVehiclePair,
    build_pair_region,
    select_plausible_pairs,
    supporting_visual_evidence,
)
from backend.services.vehicle_detection_tiers import VehicleTierResult


def vehicle(
    x,
    y,
    width=80,
    height=60,
    *,
    confidence=0.8,
    state="TRUSTED",
    supported=False,
    label="car",
):
    return {
        "label": label,
        "confidence": confidence,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "detectionState": state,
        "candidateSupported": supported,
    }


def selected_pair(a, b):
    return SelectedVehiclePair(a, b, 1.0, 0.0, 0.1, 0.0, "test", "test")


class CollisionPairClassifierTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((360, 640, 3), dtype=np.uint8)
        self.config = CollisionPairConfig(max_pairs_per_frame=1, context_margin=0.20)

    def select(self, boxes, config=None):
        return select_plausible_pairs(
            boxes,
            frame_width=640,
            frame_height=360,
            config=config or self.config,
        )

    def test_trusted_and_trusted_pair_is_eligible(self):
        self.assertEqual(len(self.select([vehicle(100, 100), vehicle(185, 100)])), 1)

    def test_trusted_and_supported_candidate_pair_is_eligible(self):
        boxes = [vehicle(100, 100), vehicle(185, 100, state="CANDIDATE", supported=True)]
        self.assertEqual(self.select(boxes)[0].source, "trusted+supported_candidate")

    def test_unsupported_candidate_is_excluded(self):
        boxes = [vehicle(100, 100), vehicle(185, 100, state="CANDIDATE")]
        self.assertEqual(self.select(boxes), [])

    def test_rejected_detection_is_excluded(self):
        boxes = [vehicle(100, 100), vehicle(185, 100, state="REJECTED")]
        self.assertEqual(self.select(boxes), [])

    def test_person_only_scene_has_no_pair(self):
        boxes = [vehicle(100, 100, label="person"), vehicle(185, 100, label="person")]
        self.assertEqual(self.select(boxes), [])

    def test_pair_count_is_hard_bounded(self):
        boxes = [vehicle(100 + index * 25, 100) for index in range(12)]
        pairs = self.select(boxes, CollisionPairConfig(max_pairs_per_frame=2))
        self.assertEqual(len(pairs), 2)

    def test_pair_union_crop_contains_both_participants(self):
        pair = selected_pair(vehicle(100, 100), vehicle(220, 160))
        region = build_pair_region(self.frame, pair, config=self.config)
        self.assertTrue(region.valid)
        x1, y1, x2, y2 = region.coordinates
        self.assertLessEqual(x1, 100)
        self.assertLessEqual(y1, 100)
        self.assertGreaterEqual(x2, 300)
        self.assertGreaterEqual(y2, 220)

    def test_crop_coordinates_are_clamped_to_native_frame(self):
        pair = selected_pair(vehicle(-10, -5), vehicle(600, 330, 60, 50))
        region = build_pair_region(self.frame, pair, config=self.config)
        self.assertEqual(region.coordinates, (0, 0, 640, 360))

    def test_configured_margin_expands_union_by_twenty_percent(self):
        pair = selected_pair(vehicle(100, 100, 50, 50), vehicle(200, 100, 50, 50))
        region = build_pair_region(self.frame, pair, config=self.config)
        self.assertEqual(region.coordinates, (70, 90, 280, 160))

    def test_degenerate_union_is_rejected(self):
        pair = selected_pair(vehicle(100, 100, 0, 0), vehicle(100, 100, 0, 0))
        region = build_pair_region(self.frame, pair, config=self.config)
        self.assertFalse(region.valid)
        self.assertEqual(region.reason, "invalid_union_box")

    def test_tiny_crop_is_rejected(self):
        pair = selected_pair(vehicle(100, 100, 5, 5), vehicle(108, 100, 5, 5))
        region = build_pair_region(self.frame, pair, config=self.config)
        self.assertFalse(region.valid)
        self.assertEqual(region.reason, "insufficient_source_pixels")

    def test_extreme_aspect_crop_is_rejected(self):
        config = CollisionPairConfig(maximum_crop_aspect_ratio=2.0, context_margin=0.0)
        pair = selected_pair(vehicle(50, 100, 200, 50), vehicle(260, 100, 200, 50))
        region = build_pair_region(self.frame, pair, config=config)
        self.assertFalse(region.valid)
        self.assertEqual(region.reason, "extreme_aspect_ratio")

    def test_no_pair_preserves_full_frame_visual_score(self):
        self.assertEqual(supporting_visual_evidence(0.41, None), 0.41)

    def test_high_pair_score_is_only_a_bounded_diagnostic_blend(self):
        self.assertAlmostEqual(supporting_visual_evidence(0.10, 1.0), 0.325)
        self.assertLess(supporting_visual_evidence(0.10, 1.0), 0.62)

    def test_negative_close_vehicle_pair_cannot_bypass_temporal_confirmation(self):
        should_create, reason, decision = main.evaluate_crash_case_decision(
            crash_class="non_accident",
            crash_confidence=0.10,
            vehicle_count=2,
            person_count=0,
            scene_valid=True,
            motion_valid=False,
            temporal_verified=False,
            consecutive_positive_frames=0,
            active_case_exists=False,
            cooldown_ready=True,
        )
        self.assertFalse(should_create)
        self.assertEqual(reason, "temporal_not_verified")
        self.assertEqual(decision, "ignored")

    def test_production_helper_reports_scores_without_replacing_full_frame_score(self):
        trusted = vehicle(100, 100)
        supported = vehicle(185, 100, state="CANDIDATE", supported=True)
        tiers = VehicleTierResult(
            raw=(trusted, supported),
            trusted=(trusted,),
            candidates=(supported,),
            rejected=(),
            supported_candidates=(supported,),
            tracker_input=(trusted, supported),
            trusted_context_present=True,
            processing_ms=0.0,
        )
        classifier_result = {
            "accidentProbability": 0.99,
            "crashClassifierAvailable": True,
            "crashClassifierError": None,
        }
        with patch.object(main, "classify_crash_frame", return_value=classifier_result) as mocked:
            payload = main.classify_collision_pair_regions(
                self.frame, tiers, full_frame_score=0.10, camera_id="test-camera"
            )
        mocked.assert_called_once()
        self.assertEqual(payload["fullFrameCrashScore"], 0.10)
        self.assertEqual(payload["pairRegionCrashScore"], 0.99)
        self.assertFalse(payload.get("accident_detected", False))
        self.assertLess(payload["visualEvidenceScore"], 0.62)


if __name__ == "__main__":
    unittest.main()
