import cv2
import os
import sys
import time
from pathlib import Path

os.environ['YOLO_OFFLINE'] = '1'
sys.path.insert(0, str(Path('.').resolve()))

from backend.main import (
    model as m2,
    crash_classifier_model as m1,
    LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD,
    LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD,
    VEHICLE_BOX_LABELS,
    PERSON_LABELS,
    normalize_box_label,
    classify_crash_frame,
    analyze_vehicle_tracks,
    CRASH_AFTERMATH_DETECTOR,
    evaluate_crash_case_decision,
    estimate_scene_abnormality
)

vpath = 'backend/uploads/040b8f6c2f1b490b88ecaacfb7cf99e8_AQPE9TZXtHxN4Zcbi2bgijhRDnnphN0EF0jfNzPCSo-Hrr_Xxt3Nm_TdMF6jcx99BHpsmASdANZx0SLZC-WhZde3hxquyKc-P-_DS2LJFw.mp4'
cap = cv2.VideoCapture(vpath)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
step = max(1, round(fps / 3))

frame_idx = 0
cam_key = f'trace_phase1_{int(time.time())}'

print('=== TASK 7 & 8: FRAME-BY-FRAME COLLISION TRACE ===')
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    if frame_idx % step == 0:
        sec = frame_idx / fps
        if 6.0 <= sec <= 11.0:
            ai_frame = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
            res = m2.predict(ai_frame, conf=0.05, verbose=False)
            
            raw_cars = []
            raw_persons = []
            acc_cars = []
            acc_persons = []
            
            for r in res:
                if r.boxes is None:
                    continue
                for b in r.boxes:
                    cid = int(b.cls[0].item())
                    lbl = normalize_box_label(str(m2.names.get(cid, cid)))
                    conf = float(b.conf[0].item())
                    xyxy = [float(v) for v in b.xyxy[0].tolist()]
                    item = {
                        'label': lbl,
                        'confidence': conf,
                        'classId': cid,
                        'x': xyxy[0],
                        'y': xyxy[1],
                        'width': xyxy[2] - xyxy[0],
                        'height': xyxy[3] - xyxy[1]
                    }
                    if lbl in VEHICLE_BOX_LABELS:
                        raw_cars.append(item)
                        if conf >= LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD:
                            acc_cars.append(item)
                    elif lbl in PERSON_LABELS:
                        raw_persons.append(item)
                        if conf >= LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD:
                            acc_persons.append(item)
            
            cls_res = classify_crash_frame(ai_frame)
            accident_prob = float(cls_res.get('accidentProbability', 0.0))
            
            ts = time.time()
            trk_res, temp_dec = analyze_vehicle_tracks(
                cam_key, acc_cars, ai_frame, classifier_score=accident_prob, timestamp=ts
            )
            aftermath_dec = CRASH_AFTERMATH_DETECTOR.observe(
                cam_key,
                classifier_score=accident_prob,
                vehicle_count=len(acc_cars),
                active_tracks=trk_res.active_tracks,
                scene_valid=True,
                frame_quality_status='good',
                scene_abnormality_score=estimate_scene_abnormality(
                    trk_res.active_tracks, acc_cars
                ),
                temporal_collision_active=temp_dec.is_verified,
                timestamp=ts
            )
            
            should_create, reason, decision = evaluate_crash_case_decision(
                crash_class='accident' if accident_prob >= 0.5 else 'non_accident',
                crash_confidence=accident_prob,
                vehicle_count=len(acc_cars),
                person_count=len(acc_persons),
                scene_valid=True,
                motion_valid=temp_dec.is_verified,
                consecutive_positive_frames=3 if temp_dec.is_verified else 0,
                active_case_exists=False,
                cooldown_ready=True,
                frame_quality_status='good',
                temporal_verified=temp_dec.is_verified,
                aftermath_candidate=aftermath_dec.review_candidate
            )
            
            tracks_str = str([t.track_id for t in trk_res.active_tracks])
            
            phase = 'APPROACH' if sec < 7.3 else ('IMPACT' if sec <= 8.3 else 'AFTERMATH')
            print(f'[{sec:4.1f}s | {phase:9s}] rawVeh={len(raw_cars):2d} accVeh={len(acc_cars):1d} rawP={len(raw_persons):1d} accP={len(acc_persons):1d} | '
                  f'tracks={tracks_str:10s} | M1_score={accident_prob:.3f} | tempScore={temp_dec.score:.3f} | afterScore={aftermath_dec.score:.3f} | '
                  f'decision={decision:10s} | reason={reason}')
    frame_idx += 1
cap.release()
