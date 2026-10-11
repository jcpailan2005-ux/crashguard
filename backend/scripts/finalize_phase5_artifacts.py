"""Finalize the evidence-backed, credential-free Phase 5 validation artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_DIR / "validation" / "phase5"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def write_json(name: str, payload: object) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    generated_at = now_utc()
    inventory = read_json("camera_inventory.json")
    replay_results = read_json("replay_results.json")
    performance = read_json("performance_results.json")

    connection_findings = {
        "CAM-BD2B2B7271": {
            "connection": "FAIL",
            "connection_time_ms": 4009.4,
            "first_frame_time_ms": None,
            "reason": "Private RTSP host did not accept a TCP connection within the reachability timeout.",
            "address_class": "valid private IPv4",
        }
    }
    placeholder_ids = {
        "CAM-MATINA-CROSSING",
        "CAM-TALOMO-CROSSING",
        "CAM-TALOMO-HIGHWAY",
        "CAM-TALOMO-MARKET",
        "CAM-TORIL-MAIN",
    }
    for camera in inventory["cameras"]:
        camera_id = camera["camera_id"]
        if camera_id in connection_findings:
            camera.update(
                {
                    "source_type": "real_rtsp",
                    "credentials_configured": True,
                    "validation_status": "CONNECTION_FAILED",
                    "connection": connection_findings[camera_id],
                }
            )
        elif camera_id in placeholder_ids:
            camera.update(
                {
                    "source_type": "placeholder_record",
                    "validation_status": "INVALID_CAMERA_ADDRESS",
                    "connection": {
                        "connection": "FAIL",
                        "connection_time_ms": 0.1,
                        "first_frame_time_ms": None,
                        "reason": "Stored address is not a valid IPv4 address accepted by the camera connector.",
                    },
                }
            )
        camera.update(
            {
                "reconnect_time_ms": None,
                "dropped_frames": None,
                "stale_frame_events": None,
                "stream_quality_status": "UNVERIFIED_NO_FRAME",
                "roi": None,
                "perspective_calibration": None,
            }
        )
    inventory["generated_at"] = generated_at
    inventory["summary"] = {
        "camera_records": 6,
        "valid_real_rtsp_endpoints": 1,
        "successful_connections": 0,
        "placeholder_or_invalid_records": 5,
        "credentials_redacted": True,
    }
    write_json("camera_inventory.json", inventory)
    write_json(
        "camera_connection_results.json",
        {
            "generated_at": generated_at,
            "credentials_redacted": True,
            "results": [
                {"camera_id": item["camera_id"], **item["connection"]}
                for item in inventory["cameras"]
            ],
            "disconnect_reconnect_restart_network_tests": "NOT_RUN_NO_INITIAL_CONNECTION",
        },
    )

    manifest = read_json("real_replay_manifest.json")
    annotations = {
        "REAL-REPLAY-001": {
            "camera_source": "public intersection CCTV-style footage; provenance unverified",
            "expected_detection_mode": "temporal_collision",
            "expected_incident": True,
            "notes": "Intersection crash/near-collision safety clip. Same underlying event family as REAL-REPLAY-002; not counted as an independent crash event.",
        },
        "REAL-REPLAY-002": {
            "camera_source": "public intersection CCTV-style footage; provenance unverified",
            "expected_detection_mode": "temporal_collision",
            "expected_incident": True,
            "notes": "Shorter trim of the REAL-REPLAY-001 event family; not counted independently.",
        },
        "REAL-REPLAY-003": {
            "camera_source": "public road CCTV-style footage; provenance unverified",
            "event_start_seconds": 0.0,
            "impact_time_seconds": 15.5,
            "event_end_seconds": 29.633,
            "vehicles_involved": "at least two road users; exact count unverified",
            "expected_detection_mode": "temporal_collision",
            "expected_incident": True,
            "notes": "Motorcycle crash visually confirmed in the supplied pixels. Impact time is an estimate, not an authoritative annotation.",
        },
    }
    for replay in manifest["replays"]:
        replay.update(annotations[replay["video_id"]])
    manifest["generated_at"] = generated_at
    manifest["independent_event_count"] = 2
    manifest["evaluated_event_count"] = 1
    write_json("real_replay_manifest.json", manifest)

    false_negative_cases = []
    for scenario in replay_results["scenarios"]:
        primary_category = (
            "AFTERMATH_GEOMETRY_TOO_WEAK"
            if scenario["scenario"] == "after_impact"
            else "UNKNOWN"
        )
        false_negative_cases.append(
            {
                "video_id": replay_results["source_video_id"],
                "scenario": scenario["scenario"],
                "category": primary_category,
                "failure_stage": (
                    "AFTERMATH_DETECTOR"
                    if scenario["scenario"] == "after_impact"
                    else "EVENT_CONFIRMATION_GATE"
                ),
                "expected_detection_mode": scenario["expected_detection_mode"],
                "actual_detection_mode": scenario["actual_detection_mode"],
                "final_decision": scenario["actual_final_decision"],
                "rejection_reason": scenario["rejection_reason"],
                "classifier_score": scenario["max_classifier_score"],
                "temporal_score": scenario["temporal_score"],
                "aftermath_score": scenario["aftermath_score"],
                "quality_status": scenario["frame_quality_status"],
                "incident_created": False,
                "threshold_change_made": False,
                "notes": (
                    "Temporal evidence was present but only one consecutive event-positive sample survived; the three-hit confirmation contract was not met."
                    if scenario["scenario"] != "after_impact"
                    else "The replay began after visible impact; aftermath score remained weak and never entered a suspected state."
                ),
            }
        )
    write_json(
        "false_negative_cases.json",
        {
            "generated_at": generated_at,
            "unique_crash_events_missed": 1,
            "replay_scenarios_missed": 3,
            "cases": false_negative_cases,
        },
    )

    fp_taxonomy = [
        "CLASSIFIER_FALSE_POSITIVE",
        "STATIC_GEOMETRY_FALSE_POSITIVE",
        "TRACKING_ID_SWITCH",
        "QUALITY_FAILURE",
        "PERSPECTIVE_FAILURE",
        "ROI_FAILURE",
        "AFTERMATH_FALSE_POSITIVE",
        "TEMPORAL_FALSE_POSITIVE",
        "UNKNOWN",
    ]
    hard_negatives = [
        "parked vehicles", "vehicles close together", "traffic congestion",
        "intersection waiting", "red light queues", "parking lots", "motorcycles",
        "buses", "trucks", "taxis", "tow trucks", "roadside repair",
        "vehicle loading/unloading", "construction zones", "cars partially outside ROI",
        "perspective overlap", "occlusions", "night scenes", "rain", "glare",
        "low light", "blur", "camera shake", "headlights", "emergency vehicle presence",
    ]
    write_json(
        "false_positive_cases.json",
        {
            "generated_at": generated_at,
            "cases": [],
            "taxonomy_counts": {category: 0 for category in fp_taxonomy},
            "hard_negative_coverage": {category: "NOT_TESTED" for category in hard_negatives},
            "metric_status": "INSUFFICIENT HARD-NEGATIVE CAMERA-HOURS",
        },
    )

    write_json(
        "camera_calibration.json",
        {
            "generated_at": generated_at,
            "changes": [],
            "global_defaults_preserved": {
                "tracking_confidence": 0.4,
                "temporal_threshold": 0.62,
                "aftermath_threshold": 0.8,
                "aftermath_required_frames": 6,
                "aftermath_min_persistence_seconds": 2.5,
                "processing_fps": 2.0,
                "stale_frame_seconds": 10.0,
            },
            "decision": "NO CALIBRATION CHANGE",
            "reason": "No real camera produced a frame, and one replay event is insufficient evidence for per-camera or global tuning.",
        },
    )

    write_json(
        "alarm_validation.json",
        {
            "generated_at": generated_at,
            "contract_tests": {
                "raw_candidate_no_alarm": "PASS",
                "committed_incident_one_alarm": "PASS",
                "duplicate_event_no_alarm": "PASS",
                "distinct_new_event_alarm": "PASS",
            },
            "audio_asset": {
                "path": "public/alert-sound.mp3",
                "bytes": 148800,
                "mpeg_frame_validation": "PASS",
                "mpeg_frames": 310,
                "duration_seconds": 7.44,
                "sample_rate_hz": 24000,
                "channels": 2,
            },
            "audible_browser_playback": "UNVERIFIED_BROWSER_RUNTIME_UNAVAILABLE",
        },
    )

    load_rows = performance["scenarios"]
    load_lines = "\n".join(
        f"| {row['camera_count']} | {row['process_cpu_percent_all_cores']}% process / {row['system_cpu_percent_end']}% system | "
        f"{row['rss_end_mb']} MB | {row['median_full_cycle_ms']} / {row['p95_full_cycle_ms']} ms | "
        f"{row['median_frame_age_ms']} / {row['p95_frame_age_ms']} ms | {row['effective_camera_fps']} | {len(row['worker_errors'])} |"
        for row in load_rows
    )
    camera_lines = "\n".join(
        f"| {camera['camera_id']} | {camera['validation_status']} | UNVERIFIED | UNVERIFIED | NOT TESTED | "
        f"{camera['online_state']} | none | none | no change |"
        for camera in inventory["cameras"]
    )
    replay_lines = "\n".join(
        f"| {row['scenario']} | {row['expected_detection_mode']} | {row['actual_detection_mode']} / {row['actual_final_decision']} | MISS |"
        for row in replay_results["scenarios"]
    )
    summary = f"""# CrashGuard Phase 5 Validation Summary

Generated: {generated_at}

## A. Status

PARTIALLY COMPLETED

Real RTSP, isolated PostgreSQL, browser-role, reconnect, network-failure, and sustained-soak validation could not be completed. No thresholds were lowered and no model was retrained.

## B. Environment

- CPU: 12th Gen Intel Core i5-12450H, 8 cores / 12 logical processors
- RAM: 8,267,882,496 bytes (7.70 GiB)
- GPU: Intel UHD Graphics only; no discrete inference GPU identified
- Python: 3.12.10
- PostgreSQL: server processes present, but the configured endpoint timed out; isolated `crashguard_test` could not be created
- Camera records: 6; one valid private RTSP endpoint and five invalid placeholder addresses; zero successful streams

## C. Camera Validation

| Camera | Connection | Resolution/FPS | Quality | Reconnect | Monitoring | ROI | Perspective | Calibration |
|---|---|---|---|---|---|---|---|---|
{camera_lines}

The valid endpoint failed initial reachability after 4009.4 ms. With no first frame, playback, disconnect, reconnect, restart, network interruption, codec, quality, and camera-specific ROI tests are unverified. Stale-feed behavior is covered by two passing unit tests and the backend now exposes frame age, connection time, reconnect count, dropped/stale counts, capture/decode time, processing latency, and health state.

## D. Crash Replay

| Start mode | Expected | Actual | Event outcome |
|---|---|---|---|
{replay_lines}

One visually confirmed motorcycle crash was replayed from before, near, and after estimated impact. Provenance and the 15.5-second impact annotation are not independently authenticated. Before/near runs reached temporal evidence but only one positive event sample; after-impact aftermath score stayed at 0.1748.

## E. Event-Level Metrics

- Real CCTV camera-hours: 0
- Crash replay camera-hours: 0.01636
- Representative load camera-hours: 0.03374
- Real crash events evaluated: 1 unique event, 3 start-mode attempts
- Event recall: 0/1 unique events (0% observed; INSUFFICIENT REAL-WORLD SAMPLE SIZE)
- Missed events: 1 unique event; 3/3 replay modes
- False incidents: 0 observed, but false incidents/camera-hour is unavailable because hard-negative camera-hours were 0
- Duplicate rate: unavailable; no incident committed
- Median/P95 detection latency: unavailable; no incident committed
- Temporal committed detections: 0; temporal verifying outcomes: 2
- Aftermath detections: 0
- Review conversion rate: unavailable
- Reconnect success rate: unavailable; no initial camera connection

## F. False Positives

No false incident was observed. All taxonomy counts are zero, but the result is not a false-positive rate: the required hard-negative categories were not available as independent camera-hours and remain `NOT_TESTED` in `false_positive_cases.json`.

## G. False Negatives

- 2 × `UNKNOWN`, localized to `EVENT_CONFIRMATION_GATE`: temporal evidence appeared but the three-hit contract was not met.
- 1 × `AFTERMATH_GEOMETRY_TOO_WEAK`: post-impact start remained `NONE` with aftermath score 0.1748.
- No threshold was changed; these cases are retained for Phase 6 evidence.

## H. Calibration

No camera-specific or global calibration changed. One inaccessible RTSP endpoint and one evaluated crash event cannot justify ROI, perspective, confidence, persistence, quality, or processing-rate tuning. Existing defaults remain 0.40 tracking confidence, 0.62 temporal threshold, 0.80 aftermath threshold, six aftermath frames, 2.5 seconds persistence, and 2 FPS processing.

## I. Multi-Camera Performance

Short representative replay test; not real RTSP and not a soak test.

| Cameras | CPU | RSS end | Median/P95 cycle | Median/P95 frame age | Effective FPS/camera | Errors |
|---:|---|---:|---|---|---:|---:|
{load_lines}

Latest-frame queue length stayed 0 and the slot stayed bounded at one frame. Eight cameras completed without worker errors but reached 94.9% system CPU and 411.36 ms P95 cycle latency; four is the observed practical ceiling for this short run. Thirty-minute memory stability remains unverified.

## J. PostgreSQL Workflow

- Isolated database creation: BLOCKED by configured PostgreSQL connection timeout
- Incident creation → review → confirmation → assignment → responder lifecycle: UNVERIFIED
- Audit, timeline, notifications, assignments: UNVERIFIED
- Migration history: PASS static chain `0001_phase3 → 0002_user_preferences → 0003_camera_permissions (head)`
- `alembic upgrade head` / `alembic current`: NOT RUN because no isolated database was reachable

## K. Role Validation

- Admin: UNVERIFIED in browser; automated permission tests PASS
- Dispatcher: UNVERIFIED in browser; read-only camera permission tests PASS
- Responder: UNVERIFIED in browser; camera restriction and route ownership tests PASS
- Isolated concurrent sessions: UNVERIFIED; the in-app browser runtime could not initialize

## L. Alarm Validation

- Single committed alarm: PASS (contract test)
- No candidate alarm: PASS (contract test)
- No duplicate alarm: PASS (contract test)
- New-event alarm: PASS (contract test)
- Audio asset: PASS MPEG structure, 148,800 bytes, 310 frames, approximately 7.44 seconds
- Audible browser playback: UNVERIFIED

## M. Tests

- Backend: 131 passed excluding PostgreSQL; 4 unittest subtests also passed
- Frontend: 15 passed
- PostgreSQL integration: 0 run; 1 setup error; 10 test cases blocked by missing isolated `crashguard_test`
- Phase 1: 69 passed
- Phase 2: 30 passed
- Phase 3 auth/RBAC/camera security: 11 passed
- Phase 4 aftermath: 19 passed
- Phase 5 camera health: 2 passed
- Typecheck: PASS
- Lint: PASS
- Build: PASS, 48 routes
- `git diff --check`: PASS

## N. Phase 6 Dataset Findings

Collect independently sourced and annotated examples for: `EVENT_CONFIRMATION_STREAK_GAP`, `AFTERMATH_GEOMETRY_TOO_WEAK`, small/distant motorcycles, high-angle multi-lane perspective, occlusion around impact, and post-impact-only starts. The full hard-negative list in `false_positive_cases.json` is still required, especially queues, close vehicles, perspective overlap, night/rain/glare/blur, camera shake, roadside repair, tow trucks, construction, and emergency vehicles. No retraining was performed.

## O. Remaining Risks

- Zero real camera frames were received; stream quality, ROI, perspective, reconnect, and camera restart behavior are unverified.
- One real crash event is statistically insufficient and was missed in all three start modes.
- No hard-negative camera-hours exist, so false-incident rate is unknown.
- PostgreSQL workflow/migrations were not exercised against an isolated database.
- Browser role isolation and audible playback were not executable in the available browser runtime.
- Eight-camera results are short representative load only; sustained memory and SSE cleanup are unverified.
"""
    (OUTPUT_DIR / "phase5_summary.md").write_text(summary, encoding="utf-8")
    print(f"Finalized Phase 5 artifacts in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
