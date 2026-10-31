"""Reproducible Phase 2 vehicle-tier replay for the known Phase 1 collision clip."""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import cv2
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import main


DEFAULT_VIDEO = Path(
    "backend/uploads/040b8f6c2f1b490b88ecaacfb7cf99e8_"
    "AQPE9TZXtHxN4Zcbi2bgijhRDnnphN0EF0jfNzPCSo-Hrr_Xxt3Nm_"
    "TdMF6jcx99BHpsmASdANZx0SLZC-WhZde3hxquyKc-P-_DS2LJFw.mp4"
)


def main_replay(video_path: Path) -> int:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Could not open {video_path}")
        return 2
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    step = max(1, round(fps / 3.0))
    camera_key = f"phase2-replay:{time.time_ns()}"
    baseline_key = f"phase2-baseline:{time.time_ns()}"
    process = psutil.Process()
    process.cpu_percent(None)
    rss_before = process.memory_info().rss / (1024 * 1024)
    frame_index = 0
    rows = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            seconds = frame_index / fps
            frame_index += 1
            if seconds < 6.0 or seconds > 11.0 or frame_index % step != 1:
                continue
            ai_frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
            model2_started = time.perf_counter()
            raw_boxes = main.detect_vehicle_boxes(ai_frame)
            model2_ms = (time.perf_counter() - model2_started) * 1000.0
            classifier_started = time.perf_counter()
            classifier = main.classify_crash_frame(ai_frame)
            classifier_ms = (time.perf_counter() - classifier_started) * 1000.0
            model1_score = float(classifier.get("accidentProbability") or 0.0)
            baseline_boxes = [
                item
                for item in raw_boxes
                if float(item.get("confidence") or 0.0)
                >= main.LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD
            ]
            baseline_tracking, _ = main.analyze_vehicle_tracks(
                baseline_key,
                baseline_boxes,
                ai_frame,
                classifier_score=model1_score,
                timestamp=seconds,
            )
            baseline_total_ms = model2_ms + classifier_ms + baseline_tracking.tracking_ms
            candidate_started = time.perf_counter()
            tiers = main.VEHICLE_CANDIDATE_EVALUATOR.evaluate(
                camera_key,
                raw_boxes,
                classifier_score=model1_score,
                frame_width=640,
                frame_height=360,
                timestamp=seconds,
            )
            candidate_ms = (time.perf_counter() - candidate_started) * 1000.0
            tracking, temporal = main.analyze_vehicle_tracks(
                camera_key,
                list(tiers.tracker_input),
                ai_frame,
                classifier_score=model1_score,
                timestamp=seconds,
            )
            temporal = main.enforce_candidate_confirmation_safety(temporal, tiers)
            total_ms = model2_ms + classifier_ms + candidate_ms + tracking.tracking_ms
            row = {
                "seconds": seconds,
                "raw": len(tiers.raw),
                "trusted": len(tiers.trusted),
                "candidate": len(tiers.candidates),
                "supported": len(tiers.supported_candidates),
                "tracker_input": len(tiers.tracker_input),
                "tracks": len(tracking.active_tracks),
                "model1": model1_score,
                "temporal_score": temporal.score,
                "confirmed": temporal.is_verified,
                "model2_ms": model2_ms,
                "classifier_ms": classifier_ms,
                "candidate_ms": candidate_ms,
                "tracking_ms": tracking.tracking_ms,
                "total_ms": total_ms,
                "baseline_total_ms": baseline_total_ms,
                "baseline_tracking_ms": baseline_tracking.tracking_ms,
            }
            rows.append(row)
            print(
                f"{seconds:4.1f}s raw={row['raw']:2d} trusted={row['trusted']:2d} "
                f"candidate={row['candidate']:2d} supported={row['supported']:2d} "
                f"trackerInput={row['tracker_input']:2d} tracks={row['tracks']:2d} "
                f"M1={model1_score:.3f} temporal={temporal.score:.3f} "
                f"confirmed={temporal.is_verified}"
            )
    finally:
        cap.release()
        main.VEHICLE_CANDIDATE_EVALUATOR.reset_camera(camera_key)
        main.VEHICLE_TRACKING_SERVICE.reset_camera(camera_key)
        main.TEMPORAL_CRASH_VERIFIER.reset_camera(camera_key)
        main.VEHICLE_TRACKING_SERVICE.reset_camera(baseline_key)
        main.TEMPORAL_CRASH_VERIFIER.reset_camera(baseline_key)

    if not rows:
        print("No frames analyzed.")
        return 3
    rss_after = process.memory_info().rss / (1024 * 1024)
    elapsed_ai_seconds = sum(row["total_ms"] for row in rows) / 1000.0
    print("SUMMARY")
    print(f"frames={len(rows)}")
    print(f"maxRaw={max(row['raw'] for row in rows)}")
    print(f"maxTrusted={max(row['trusted'] for row in rows)}")
    print(f"maxCandidates={max(row['candidate'] for row in rows)}")
    print(f"maxSupported={max(row['supported'] for row in rows)}")
    print(f"meanModel2Ms={statistics.fmean(row['model2_ms'] for row in rows):.3f}")
    print(f"meanClassifierMs={statistics.fmean(row['classifier_ms'] for row in rows):.3f}")
    print(f"meanCandidateMs={statistics.fmean(row['candidate_ms'] for row in rows):.3f}")
    print(
        f"meanBaselineTrackingMs="
        f"{statistics.fmean(row['baseline_tracking_ms'] for row in rows):.3f}"
    )
    print(f"meanTrackingMs={statistics.fmean(row['tracking_ms'] for row in rows):.3f}")
    print(f"meanBaselineAiMs={statistics.fmean(row['baseline_total_ms'] for row in rows):.3f}")
    print(f"meanTotalAiMs={statistics.fmean(row['total_ms'] for row in rows):.3f}")
    print(f"aiFps={len(rows) / max(elapsed_ai_seconds, 1e-9):.3f}")
    print(f"processCpuPercent={process.cpu_percent(None):.1f}")
    print(f"rssBeforeMb={rss_before:.3f}")
    print(f"rssAfterMb={rss_after:.3f}")
    print(f"anyConfirmed={any(row['confirmed'] for row in rows)}")
    return 0


if __name__ == "__main__":
    selected = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_VIDEO
    raise SystemExit(main_replay(selected))
