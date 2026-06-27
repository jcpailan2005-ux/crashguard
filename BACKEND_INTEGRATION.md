# FastAPI Backend Integration Guide

This document explains how to connect your FastAPI backend to the Car Crash Detection frontend.

## Quick Start

1. **Set the Backend URL** in your environment:
   ```bash
   export NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
   ```

2. **Implement the required endpoints** in your FastAPI app (see below)

3. **Test with curl**:
   ```bash
   curl -X POST http://localhost:3000/api/detect/image \
     -F "file=@/path/to/image.jpg"
   ```

## Required FastAPI Endpoints

### 1. Image Detection
**POST /api/detect/image**

Upload an image file for accident detection.

**Request:**
- Content-Type: `multipart/form-data`
- Field: `file` (binary image file)

**Response:**
```json
{
  "success": true,
  "accident_detected": true,
  "confidence": 0.91,
  "media_type": "image",
  "timestamp": "2026-04-17T12:30:00Z",
  "location": "Intersection A - Main St & 5th Ave",
  "detections": [
    {
      "label": "vehicle",
      "score": 0.95,
      "box": [100, 120, 220, 260]
    },
    {
      "label": "accident",
      "score": 0.91,
      "box": [140, 150, 260, 300]
    }
  ],
  "annotated_media_url": "/outputs/result_001.jpg"
}
```

### 2. Video Detection
**POST /api/detect/video**

Same as image detection but for video files.

**Response:** Same format, with `media_type` as `"video"`

### 3. Get All Incidents
**GET /api/incidents**

Retrieve list of all detected incidents.

**Response:**
```json
[
  {
    "id": "INC001",
    "timestamp": "2026-04-17T12:30:00Z",
    "location": "Intersection A - Main St & 5th Ave",
    "confidence": 0.91,
    "media_type": "video",
    "status": "critical",
    "accident_detected": true,
    "source_file": "collision_001.mp4",
    "latitude": 40.7128,
    "longitude": -74.006
  }
]
```

### 4. Get Notifications
**GET /api/notifications**

Retrieve alert notifications.

**Response:**
```json
[
  {
    "id": "NOT001",
    "incident_id": "INC001",
    "title": "Critical Accident Detected",
    "message": "Severe collision detected at Intersection A (91% confidence)",
    "timestamp": "2026-04-17T12:30:00Z",
    "severity": "critical",
    "read": false
  }
]
```

### 5. Health Check
**GET /api/health**

Check if backend is running.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-04-17T12:30:00Z",
  "version": "1.0.0"
}
```

## Example FastAPI Implementation

```python
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
from ultralytics import YOLO
import uuid
from datetime import datetime
from typing import List

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLO model
model = YOLO("yolov8n.pt")  # or YOLO11

# In-memory storage (replace with database in production)
incidents = []
notifications = []

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.post("/api/detect/image")
async def detect_image(file: UploadFile = File(...)):
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Run YOLO detection
        results = model.predict(image, conf=0.5)
        
        # Process detections
        detections = []
        has_accident = False
        max_confidence = 0
        
        for r in results:
            for box in r.boxes:
                cls_name = model.names[int(box.cls)]
                confidence = float(box.conf)
                
                if cls_name == "accident":
                    has_accident = True
                    max_confidence = max(max_confidence, confidence)
                
                detections.append({
                    "label": cls_name,
                    "score": confidence,
                    "box": box.xyxy[0].tolist()
                })
        
        # Save annotated image
        annotated_frame = results[0].plot()
        output_path = f"outputs/result_{uuid.uuid4().hex[:8]}.jpg"
        cv2.imwrite(output_path, annotated_frame)
        
        # Create incident record
        incident_id = f"INC{len(incidents) + 1:04d}"
        incident = {
            "id": incident_id,
            "timestamp": datetime.now().isoformat(),
            "location": "Detected Location",  # Parse from metadata
            "confidence": max_confidence,
            "media_type": "image",
            "status": "critical" if has_accident else "processed",
            "accident_detected": has_accident,
            "latitude": 40.7128,  # Use actual GPS data if available
            "longitude": -74.006
        }
        incidents.append(incident)
        
        # Create notification if accident
        if has_accident:
            notification = {
                "id": f"NOT{len(notifications) + 1:04d}",
                "incident_id": incident_id,
                "title": "Critical Accident Detected",
                "message": f"Accident detected with {max_confidence*100:.0f}% confidence",
                "timestamp": datetime.now().isoformat(),
                "severity": "critical",
                "read": False
            }
            notifications.append(notification)
        
        return {
            "success": True,
            "accident_detected": has_accident,
            "confidence": max_confidence,
            "media_type": "image",
            "timestamp": datetime.now().isoformat(),
            "location": "Detected Location",
            "detections": detections,
            "annotated_media_url": f"/{output_path}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/detect/video")
async def detect_video(file: UploadFile = File(...)):
    # Similar to image detection but process video frames
    # For brevity, returning same structure
    return await detect_image(file)

@app.get("/api/incidents")
async def get_incidents():
    return incidents

@app.get("/api/notifications")
async def get_notifications():
    return notifications

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Running the Backend

```bash
# Install dependencies
pip install fastapi uvicorn ultralytics opencv-python

# Run server
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

Set in frontend `.env.local`:

```
# Backend URL (default: http://localhost:8000)
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Use mock data when backend unavailable (default: true)
NEXT_PUBLIC_USE_MOCK_DATA=true
```

## CORS Configuration

If running frontend and backend on different origins, ensure CORS is enabled:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Testing the Integration

1. **Start backend:**
   ```bash
   python main.py
   ```

2. **Start frontend:**
   ```bash
   npm run dev
   ```

3. **Open browser:**
   - Navigate to http://localhost:3000
   - Go to Dashboard → Upload
   - Upload a test image or video
   - Check console for API responses

## Troubleshooting

**"Failed to fetch" error:**
- Check backend is running on configured URL
- Verify CORS is enabled
- Check browser console for detailed error

**Mock data showing instead of real results:**
- Set `NEXT_PUBLIC_USE_MOCK_DATA=false`
- Check backend URL is correct
- Ensure endpoints are implemented

**No map pins showing:**
- Ensure incidents have `latitude` and `longitude` fields
- Check incident data is being returned from `/api/incidents`

## Database Integration

For production, replace in-memory storage with a database:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://user:password@localhost/crashdetection"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Use SessionLocal() to get database session
```

## Next Steps

- Add database for persistent storage
- Implement user authentication
- Add upload history tracking
- Create admin dashboard for reviewing detections
- Optimize YOLO inference speed
- Add GPU support for faster processing

---

For more info, see README.md
