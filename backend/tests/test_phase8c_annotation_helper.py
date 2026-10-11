from __future__ import annotations

import copy
import json

from scripts.annotate_phase8c_events import (
    AnnotationSession,
    DisplayTransform,
    apply_vehicle_class,
    box_valid,
    pair_confirmation_errors,
    save_payload,
    verification_errors,
)


def make_payload() -> dict:
    return {
        "event_type": "TYPE_A", "event_type_verified": False,
        "ground_truth_collision_pair": ["P-A", "P-B"], "ground_truth_pair_verified": False,
        "participants": {
            "P-A": {"vehicle_class": "car", "visual_description": "green sedan"},
            "P-B": {"vehicle_class": "truck", "visual_description": "white truck"},
        },
        "fps": 30.0, "frame_count": 360, "resolution": [352, 240],
        "analysis_start_frame": None, "analysis_end_frame": None,
        "contact_start_frame": None, "contact_peak_frame": None, "contact_end_frame": None,
        "aftermath_start_frame": None, "dynamic_history_available": True,
        "distractors_reviewed": False, "annotations": [],
    }


def make_session(data: dict | None = None) -> AnnotationSession:
    return AnnotationSession(data or make_payload(), 30.0, 360, DisplayTransform.fit(352, 240))


def test_frame_navigation():
    state = make_session()
    state.navigate(1)
    assert state.frame_index == 1
    state.navigate(10)
    assert state.frame_index == 11
    state.navigate(-50)
    assert state.frame_index == 0
    state.jump(999)
    assert state.frame_index == 359


def test_display_source_coordinate_conversions():
    transform = DisplayTransform.fit(352, 240)
    source = [12, 24, 200, 180]
    display = transform.source_to_display(source)
    restored = transform.display_to_source(display)
    assert restored is not None
    assert all(abs(expected - actual) <= 1 for expected, actual in zip(source, restored))


def test_valid_bbox_creation_and_zero_size_rejection():
    state = make_session()
    state.mode = "P-A"
    state.begin_drag(10, 20)
    assert state.finish_drag(250, 300) == "P-A"
    assert box_valid(state.current["participant_observations"]["P-A"]["bbox"], 352, 240)
    state.begin_drag(100, 100)
    assert state.finish_drag(100, 100) is None


def test_participant_persistence_and_save_reload():
    state = make_session()
    for target, start, end in (("P-A", (10, 20), (250, 300)), ("P-B", (300, 100), (600, 450))):
        state.mode = target
        state.begin_drag(*start)
        state.finish_drag(*end)
    apply_vehicle_class(state, "P-B", "bus")
    assert len(state.annotations) == 0
    state.save_current()
    assert len(state.annotations) == 1
    state.sync_payload()
    restored = make_session(json.loads(json.dumps(state.payload)))
    assert restored.annotations[0]["participant_observations"]["P-A"]["bbox"]
    assert restored.payload["participants"]["P-B"]["vehicle_class"] == "bus"


def test_viewing_an_unsaved_frame_does_not_make_it_dirty():
    state = make_session()
    _ = state.current
    assert state.current_is_dirty() is False
    state.current["phase"] = "APPROACH"
    assert state.current_is_dirty() is True


def test_undo_restores_last_annotation_operation():
    state = make_session()
    state.mode = "P-A"
    state.begin_drag(10, 10)
    state.finish_drag(200, 200)
    assert state.current["participant_observations"]["P-A"]["bbox"]
    assert state.undo()
    assert state.current["participant_observations"]["P-A"]["bbox"] is None


def test_phase_analysis_window_and_file_persistence(tmp_path):
    state = make_session()
    state.current["phase"] = "CONTACT"
    state.payload["analysis_start_frame"] = 0
    state.payload["analysis_end_frame"] = 20
    state.save_current()
    annotation_path = tmp_path / "annotation.json"
    save_payload(annotation_path, state)
    restored = make_session(json.loads(annotation_path.read_text(encoding="utf-8")))
    assert restored.annotations[0]["phase"] == "CONTACT"
    assert restored.payload["analysis_start_frame"] == 0
    assert restored.payload["analysis_end_frame"] == 20


def test_pair_confirmation_and_distractor_review_state_persist():
    state = make_session()
    state.payload["ground_truth_pair_verified"] = True
    state.payload["distractors_reviewed"] = True
    state.sync_payload()
    restored = make_session(copy.deepcopy(state.payload))
    assert restored.payload["ground_truth_pair_verified"] is True
    assert restored.payload["distractors_reviewed"] is True


def test_pair_confirmation_requires_descriptions_and_saved_boxes():
    data = make_payload()
    state = make_session(data)
    assert len(pair_confirmation_errors(data, state.annotations)) == 2
    for target, start, end in (("P-A", (10, 20), (250, 300)), ("P-B", (300, 100), (600, 450))):
        state.mode = target
        state.begin_drag(*start)
        state.finish_drag(*end)
    state.save_current()
    assert pair_confirmation_errors(data, state.annotations) == []


def test_distractor_and_collision_region_drawing():
    state = make_session()
    state.mode = "distractor"
    state.begin_drag(20, 30)
    assert state.finish_drag(200, 250) == "distractor"
    assert state.current["distractors"][0]["id"] == "D-01"
    state.mode = "collision"
    state.begin_drag(100, 100)
    assert state.finish_drag(400, 350) == "collision"
    assert box_valid(state.current["collision_region_bbox"], 352, 240)


def test_human_verified_is_blocked_before_requirements_pass():
    data = make_payload()
    errors = verification_errors(data)
    assert any("pair" in error for error in errors)
    assert any("at least 6" in error for error in errors)
    assert data.get("review_state") != "HUMAN_VERIFIED"
