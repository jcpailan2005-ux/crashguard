"""Offline reproduction on saved JPEG evidence, not a live inference trace.

Uses the running pre-restoration process's existing 640x360 input for reproduction only.
No lowered confidence, no production imports, no persistence, no annotation edits.
"""
from datetime import datetime
import json
from pathlib import Path
import cv2
from ultralytics import YOLO

output=Path('docs/live-candidate-audit')
output.mkdir(parents=True,exist_ok=True)
files=sorted([p for p in Path('backend/outputs').glob('live_camera_keyframe*.jpg')
    if datetime(2026,9,16,0,42).timestamp()<p.stat().st_mtime<datetime(2026,9,16,0,47).timestamp()],key=lambda p:p.stat().st_mtime)
selected=files[::max(1,len(files)//12)]
if files[-1] not in selected: selected.append(files[-1])
models={'best':YOLO('backend/best.pt'),'vehicle':YOLO('yolov8n.pt')}
classifier=YOLO('backend/models/crash_classifier.pt')
rows=[]
for path in selected:
    image=cv2.imread(str(path))
    frame=cv2.resize(image,(640,360),interpolation=cv2.INTER_AREA)
    item=dict(file=str(path),savedAt=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        provenance='offline reproduction from compressed saved JPEG; not raw live observation',models={})
    for name,model in models.items():
        result=model.predict(frame,verbose=False)[0]
        detections=[]
        for box in result.boxes:
            label=model.names[int(box.cls[0])]
            score=float(box.conf[0])
            bbox=[float(x)*2 for x in box.xyxy[0]]
            vehicle=label in {'car','motorcycle','bicycle','bus','truck','train'}
            detections.append(dict(label=label,confidence=score,bbox=bbox,
                accepted=bool(vehicle and score>=.40),
                reason='vehicle_confidence_gate' if vehicle and score<.40 else 'non_vehicle_class' if not vehicle else 'vehicle_class_and_confidence_pass',
                tier='NOT_IMPLEMENTED_IN_ACTIVE_LIVE_PATH',trackerId=None,logicalId=None))
        item['models'][name]=detections
    pred=classifier.predict(frame,imgsz=224,verbose=False)[0]
    item['wholeFrameProbabilities']={classifier.names[i]:float(v) for i,v in enumerate(pred.probs.data)}
    rows.append(item)
    print(path.name,[(d['label'],round(d['confidence'],3)) for d in item['models']['vehicle']],flush=True)
(output/'saved-frame-reproduction.json').write_text(json.dumps(rows,indent=2))
