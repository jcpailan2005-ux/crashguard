import os
import sys
import time
import json
from pathlib import Path
import cv2
import numpy as np

os.environ["YOLO_OFFLINE"] = "1"

import torch
from ultralytics import YOLO

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.main import (
    classify_crash_frame,
    analyze_vehicle_tracks,
    CRASH_AFTERMATH_DETECTOR,
    evaluate_crash_case_decision,
    normalize_box_label,
    LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD,
    LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD,
    VEHICLE_BOX_LABELS,
    PERSON_LABELS,
    estimate_scene_abnormality,
    model as deployed_detector,
    crash_classifier_model as deployed_classifier
)

def run_audit():
    print("=== STARTING COMPLETE PIPELINE AUDIT ===")
    out_dir = Path("backend/outputs/pipeline_audit_debug")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Model Verification
    m1_path = Path("backend/models/crash_classifier.pt")
    m2_path = Path("backend/best.pt")
    
    print(f"Model 1 (Classifier): {m1_path.resolve()}")
    print(f"  Loaded: {deployed_classifier is not None}, Task: {getattr(deployed_classifier, 'task', 'classify')}, Classes: {getattr(deployed_classifier, 'names', {})}")
    
    print(f"Model 2 (Detector):   {m2_path.resolve()}")
    print(f"  Loaded: {deployed_detector is not None}, Task: {getattr(deployed_detector, 'task', 'detect')}, Total Classes: {len(getattr(deployed_detector, 'names', {}))}")
    
    # 2. Confidence Thresholds
    print("\n--- Runtime Thresholds ---")
    print(f"LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD: {LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD}")
    print(f"LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD:  {LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD}")
    print(f"VEHICLE_BOX_LABELS: {sorted(list(VEHICLE_BOX_LABELS))}")
    print(f"PERSON_LABELS:      {sorted(list(PERSON_LABELS))}")
    
    # 3. Test on 3 representative collision video clips
    video_paths = [
        "backend/uploads/040b8f6c2f1b490b88ecaacfb7cf99e8_AQPE9TZXtHxN4Zcbi2bgijhRDnnphN0EF0jfNzPCSo-Hrr_Xxt3Nm_TdMF6jcx99BHpsmASdANZx0SLZC-WhZde3hxquyKc-P-_DS2LJFw.mp4",
        "backend/uploads/85a9bf119bd0499a9290b766b974940c_AQN4aD63JBct-flgF262OLInpTjhiSJ2gApMnXmO1ghr4sK05qx6eMyArBq3jesQqkLd3B3TpM1Ss6HUcurU0xyTHf8sCzvJhwBWZUUFig.mp4",
        "backend/uploads/a1eef52ef0f1477a94b2811f2ac7f17b_AQMjpJRrD0njZQx3laRa6nkU9uNk2xipe6xveoUndPm8G7W404m5TqwkLfnsJG7Vzn01TkF1_Z2MWy51HfCZYS2GTUgYgN6--l2TtVNZGg.mp4"
    ]
    
    audit_results = {
        "models": {
            "model1": {"path": str(m1_path), "active": deployed_classifier is not None, "classes": getattr(deployed_classifier, 'names', {})},
            "model2": {"path": str(m2_path), "active": deployed_detector is not None, "classes_used": list(VEHICLE_BOX_LABELS)}
        },
        "thresholds": {
            "vehicle_conf": LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD,
            "person_conf": LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD
        },
        "video_traces": []
    }
    
    # Latency tracking across all runs
    latencies = {"m2": [], "m1": [], "tracking": [], "total": []}
    
    for vid_idx, vpath in enumerate(video_paths):
        if not os.path.exists(vpath):
            continue
        vname = Path(vpath).stem[:20]
        print(f"\n==========================================")
        print(f"Processing Video {vid_idx+1}: {vname}...")
        cap = cv2.VideoCapture(vpath)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"  Source: {orig_w}x{orig_h} @ {fps} fps, {total_frames} total frames")
        
        # Sample at ~3 fps (step = fps / 3)
        step = max(1, round(fps / 3))
        cam_key = f"audit_cam_{vid_idx}_{int(time.time())}"
        
        frame_idx = 0
        analyzed_count = 0
        
        trace = {
            "video": vname,
            "resolution": f"{orig_w}x{orig_h}",
            "frames": []
        }
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % step == 0:
                analyzed_count += 1
                t_sec = frame_idx / fps
                t_total_start = time.perf_counter()
                
                # Resize to AI detection size (640x360)
                ai_frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
                
                # --- Model 2 Raw Execution ---
                t_m2_start = time.perf_counter()
                results = deployed_detector.predict(ai_frame, conf=0.05, verbose=False)
                t_m2 = (time.perf_counter() - t_m2_start) * 1000.0
                latencies["m2"].append(t_m2)
                
                raw_boxes = []
                raw_cars = []
                raw_persons = []
                accepted_cars = []
                accepted_persons = []
                
                for r in results:
                    if r.boxes is None or len(r.boxes) == 0:
                        continue
                    for box in r.boxes:
                        cid = int(box.cls[0].item())
                        label = normalize_box_label(str(deployed_detector.names.get(cid, cid)))
                        conf = float(box.conf[0].item())
                        xyxy = [float(v) for v in box.xyxy[0].tolist()]
                        b_dict = {
                            "label": label, "classId": cid, "confidence": conf,
                            "x": xyxy[0], "y": xyxy[1], "width": xyxy[2]-xyxy[0], "height": xyxy[3]-xyxy[1]
                        }
                        raw_boxes.append(b_dict)
                        if label in VEHICLE_BOX_LABELS:
                            raw_cars.append(b_dict)
                            if conf >= LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD:
                                accepted_cars.append(b_dict)
                        elif label in PERSON_LABELS:
                            raw_persons.append(b_dict)
                            if conf >= LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD:
                                accepted_persons.append(b_dict)
                
                # --- Model 1 Crash Classifier Execution ---
                t_m1_start = time.perf_counter()
                cls_res = classify_crash_frame(ai_frame)
                t_m1 = (time.perf_counter() - t_m1_start) * 1000.0
                latencies["m1"].append(t_m1)
                accident_prob = float(cls_res.get("accidentProbability", 0.0))
                
                # Section 20: Collision-Region Crop Experiment
                crop_accident_prob = None
                if len(accepted_cars) >= 2:
                    min_x = max(0, int(min(accepted_cars[0]["x"], accepted_cars[1]["x"]) * 0.9))
                    min_y = max(0, int(min(accepted_cars[0]["y"], accepted_cars[1]["y"]) * 0.9))
                    max_x = min(ai_frame.shape[1], int(max(accepted_cars[0]["x"]+accepted_cars[0]["width"], accepted_cars[1]["x"]+accepted_cars[1]["width"]) * 1.1))
                    max_y = min(ai_frame.shape[0], int(max(accepted_cars[0]["y"]+accepted_cars[0]["height"], accepted_cars[1]["y"]+accepted_cars[1]["height"]) * 1.1))
                    if max_x > min_x + 20 and max_y > min_y + 20:
                        crop = ai_frame[min_y:max_y, min_x:max_x]
                        crop_res = classify_crash_frame(crop)
                        crop_accident_prob = float(crop_res.get("accidentProbability", 0.0))
                
                # --- ByteTrack & Temporal Verification ---
                t_trk_start = time.perf_counter()
                ts = time.time()
                tracking_result, temporal_decision = analyze_vehicle_tracks(
                    cam_key,
                    accepted_cars,
                    ai_frame,
                    classifier_score=accident_prob,
                    timestamp=ts,
                )
                
                aftermath_decision = CRASH_AFTERMATH_DETECTOR.observe(
                    cam_key,
                    classifier_score=accident_prob,
                    vehicle_count=len(accepted_cars),
                    active_tracks=tracking_result.active_tracks,
                    scene_valid=True,
                    frame_quality_status="good",
                    scene_abnormality_score=estimate_scene_abnormality(
                        tracking_result.active_tracks,
                        accepted_cars,
                    ),
                    temporal_collision_active=temporal_decision.is_verified,
                    timestamp=ts,
                )
                t_trk = (time.perf_counter() - t_trk_start) * 1000.0
                latencies["tracking"].append(t_trk)
                
                # --- Decision Arbiter ---
                should_create, reason, decision = evaluate_crash_case_decision(
                    crash_class="accident" if accident_prob >= 0.5 else "non_accident",
                    crash_confidence=accident_prob,
                    vehicle_count=len(accepted_cars),
                    person_count=len(accepted_persons),
                    scene_valid=True,
                    motion_valid=temporal_decision.is_verified,
                    consecutive_positive_frames=3 if temporal_decision.is_verified else 0,
                    active_case_exists=False,
                    cooldown_ready=True,
                    frame_quality_status="good",
                    temporal_verified=temporal_decision.is_verified,
                    aftermath_candidate=aftermath_decision.review_candidate
                )
                t_tot = (time.perf_counter() - t_total_start) * 1000.0
                latencies["total"].append(t_tot)
                
                frame_record = {
                    "sec": round(t_sec, 2),
                    "raw_cars": len(raw_cars),
                    "accepted_cars": len(accepted_cars),
                    "raw_persons": len(raw_persons),
                    "accepted_persons": len(accepted_persons),
                    "raw_car_confs": [round(c["confidence"], 3) for c in raw_cars],
                    "accepted_car_confs": [round(c["confidence"], 3) for c in accepted_cars],
                    "active_tracks": [t.track_id for t in tracking_result.active_tracks],
                    "crash_prob": round(accident_prob, 3),
                    "crop_crash_prob": round(crop_accident_prob, 3) if crop_accident_prob is not None else None,
                    "temp_score": round(temporal_decision.score, 3),
                    "temp_verified": temporal_decision.is_verified,
                    "aftermath_cand": aftermath_decision.review_candidate,
                    "decision": decision,
                    "reason": reason,
                    "latency": {"m2": round(t_m2, 1), "m1": round(t_m1, 1), "track": round(t_trk, 1), "total": round(t_tot, 1)}
                }
                trace["frames"].append(frame_record)
                
                # Print key transition frames
                if analyzed_count <= 25 or temporal_decision.is_verified or aftermath_decision.review_candidate:
                    print(f"  [{t_sec:4.1f}s] rawCars={len(raw_cars)} accCars={len(accepted_cars)} rawP={len(raw_persons)} accP={len(accepted_persons)} "
                          f"crashProb={accident_prob:.2f} dec={decision} reason={reason}")
                
                # Save diagnostic frames with annotations
                if analyzed_count in [5, 12, 18, 25]:
                    dbg_img = ai_frame.copy()
                    # Draw raw boxes orange
                    for b in raw_cars:
                        cv2.rectangle(dbg_img, (int(b["x"]), int(b["y"])), (int(b["x"]+b["width"]), int(b["y"]+b["height"])), (0, 140, 255), 1)
                        cv2.putText(dbg_img, f"raw {b['label']} {b['confidence']:.2f}", (int(b["x"]), max(12, int(b["y"]-2))), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 140, 255), 1)
                    # Draw accepted boxes solid green
                    for b in accepted_cars:
                        cv2.rectangle(dbg_img, (int(b["x"]), int(b["y"])), (int(b["x"]+b["width"]), int(b["y"]+b["height"])), (0, 255, 0), 2)
                        cv2.putText(dbg_img, f"{b['label']} {b['confidence']:.2f}", (int(b["x"]), max(12, int(b["y"]-2))), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                    # Draw persons cyan
                    for b in accepted_persons:
                        cv2.rectangle(dbg_img, (int(b["x"]), int(b["y"])), (int(b["x"]+b["width"]), int(b["y"]+b["height"])), (255, 255, 0), 2)
                        cv2.putText(dbg_img, f"person {b['confidence']:.2f}", (int(b["x"]), max(12, int(b["y"]-2))), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
                    
                    cv2.putText(dbg_img, f"Prob: {accident_prob:.2f} | Dec: {decision} ({reason})", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255) if decision != "ignored" else (200, 200, 200), 1)
                    out_path = out_dir / f"{vname}_f{frame_idx}.jpg"
                    cv2.imwrite(str(out_path), dbg_img)
            
            frame_idx += 1
            if analyzed_count >= 50:  # ~16 seconds per video
                break
        
        cap.release()
        audit_results["video_traces"].append(trace)

    # 4. Summary Latency Stats
    audit_results["performance"] = {
        "model2_ms": round(float(np.mean(latencies["m2"])), 2),
        "model1_ms": round(float(np.mean(latencies["m1"])), 2),
        "tracking_ms": round(float(np.mean(latencies["tracking"])), 2),
        "total_ai_ms": round(float(np.mean(latencies["total"])), 2),
        "fps_achievable": round(1000.0 / max(1.0, float(np.mean(latencies["total"]))), 1)
    }
    print("\n--- Performance Benchmarks on CPU ---")
    print(f"Model 2 Detection Latency: {audit_results['performance']['model2_ms']} ms")
    print(f"Model 1 Classifier Latency: {audit_results['performance']['model1_ms']} ms")
    print(f"Tracking / Temporal Latency: {audit_results['performance']['tracking_ms']} ms")
    print(f"Total AI Cycle Latency:     {audit_results['performance']['total_ai_ms']} ms ({audit_results['performance']['fps_achievable']} FPS)")

    # 5. Save results to JSON
    with open("scratch_pipeline_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)
    print("\nSaved pipeline audit trace to scratch_pipeline_audit.json")
    print(f"Saved diagnostic debug images to {out_dir}")

if __name__ == "__main__":
    run_audit()
