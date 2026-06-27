# Live Camera Feature - Quick Start Guide

## ✨ What's New

Your CCTV Samples page now includes a **Live Camera Detection** section that lets you:
- 📹 Access your laptop webcam directly in the browser
- 📸 Capture frames from the live video feed
- 🎥 Record short videos
- 🤖 Send captured media to the backend for real-time accident detection
- 🚨 Get instant alerts with accident detection results
- 📊 View detection confidence and annotated results

## 🚀 How to Use

### 1. Navigate to CCTV Samples
Go to **Dashboard → CCTV Samples** (or navigate to `/samples`)

### 2. Open Live Camera
Click the **"Open Live Camera"** button to activate the webcam section

### 3. Start Your Camera
- Click **"Start Camera"** button
- Your browser will request camera permission (approve it)
- You'll see the live preview from your webcam

### 4. Capture a Frame or Record Video

#### To Capture a Single Image:
1. Click **"Capture Image"**
2. The current frame is captured and sent to the backend
3. Wait for detection result (shows in a result card below)
4. If accident detected → alert sound plays and notification shows
5. View the annotated result via the "View Annotated Result" link

#### To Record a Video:
1. Click **"Record Video"** - a red "REC" indicator appears
2. Keep recording for 2-5 seconds
3. Click **"Stop Recording"**
4. The recorded video is sent to the backend for analysis
5. Wait for detection result
6. Download annotated footage or view the result

### 5. Stop Camera
Click **"Stop Camera"** to deactivate the webcam and close the stream

## 🔧 Technical Details

### Components Added
- **`components/live-camera.tsx`** - Main live camera component with all features

### Features Implemented

#### Camera Controls
- ✅ Start/Stop camera using `navigator.mediaDevices.getUserMedia`
- ✅ Live preview using HTML `<video>` element
- ✅ Real-time video stream from webcam
- ✅ Permission handling (denied, unavailable, etc.)

#### Image Capture
- ✅ Use hidden `<canvas>` to capture frames
- ✅ Convert canvas to JPEG blob
- ✅ Send to `POST /api/detect/image` endpoint
- ✅ Display captured preview

#### Video Recording
- ✅ MediaRecorder API for video capture
- ✅ Record in WebM format (VP8 + Opus codecs)
- ✅ Send to `POST /api/detect/video` endpoint
- ✅ Recording indicator during recording

#### Detection Results
- ✅ Show accident/safe status with visual badge
- ✅ Display confidence percentage
- ✅ Show media type (image/video)
- ✅ Link to download/view annotated media
- ✅ Play alert sound if accident detected
- ✅ Show toast notifications

#### Error Handling
- ✅ Camera permission denied
- ✅ No camera found on device
- ✅ Backend unavailable (falls back to mock)
- ✅ Network errors
- ✅ User-friendly error messages

### UI/UX
- ✅ Consistent with existing dashboard design (dark/orange/black theme)
- ✅ Loading states while processing
- ✅ Disabled buttons during detection/recording
- ✅ Responsive design
- ✅ Recording indicator animation

## 🔌 Backend Integration

The feature uses your existing backend endpoints:

### POST /api/detect/image
**What it does:** Detects accidents in uploaded image
**Input:** Multipart form data with `file` field
**Output:** DetectionResponse with:
- `accident_detected: boolean`
- `confidence: number` (0-1)
- `media_type: 'image'`
- `annotated_media_url?: string` (optional - URL to annotated image)
- `detections: BoundingBox[]`

### POST /api/detect/video
**What it does:** Detects accidents in uploaded video
**Input:** Multipart form data with `file` field
**Output:** DetectionResponse with:
- `accident_detected: boolean`
- `confidence: number` (0-1)
- `media_type: 'video'`
- `annotated_media_url?: string` (optional - URL to annotated video)
- `detections: BoundingBox[]`

### Example Backend Response
```json
{
  "success": true,
  "accident_detected": true,
  "confidence": 0.92,
  "media_type": "image",
  "timestamp": "2024-04-18T10:30:00Z",
  "location": "Demo Location",
  "detections": [
    {
      "label": "vehicle",
      "score": 0.95,
      "box": [100, 120, 220, 260]
    },
    {
      "label": "accident",
      "score": 0.92,
      "box": [140, 150, 260, 300]
    }
  ],
  "annotated_media_url": "/outputs/annotated_image_12345.jpg"
}
```

## 🎛️ Configuration

### Backend URL
The component automatically uses `NEXT_PUBLIC_BACKEND_URL` environment variable:
```bash
# .env.local
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
# or
NEXT_PUBLIC_BACKEND_URL=https://your-api.com
```

### Alert Sound
The alert sound is played from `/public/alert-sound.mp3` (already configured)

### Camera Constraints
Current settings in `live-camera.tsx`:
```javascript
video: { 
  facingMode: 'user',           // Front camera
  width: { ideal: 1280 },        // Preferred width
  height: { ideal: 720 }         // Preferred height
}
```

You can modify these in the `startCamera` function if needed.

## 📋 Browser Compatibility

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | ✅ Full | All features working |
| Firefox | ✅ Full | All features working |
| Safari | ✅ Partial | May need HTTPS for camera |
| Edge | ✅ Full | All features working |

**Note:** `navigator.mediaDevices.getUserMedia` requires HTTPS on production (except localhost)

## 🔒 Privacy & Permissions

- ✅ User must explicitly grant camera permission
- ✅ Camera stream only exists when "Start Camera" is active
- ✅ Stream is properly cleaned up when stopping camera
- ✅ No data sent without user action (capture/record)

## 🐛 Troubleshooting

### "Camera permission denied"
- Check browser camera permissions
- Try incognito/private window
- Restart browser and try again

### "No camera found"
- Verify camera is plugged in
- Check if another app is using camera
- Try different browser

### "Detection failed"
- Check if backend is running (http://localhost:8000)
- Check backend logs for errors
- Try uploading from Upload page to test backend
- Check NEXT_PUBLIC_BACKEND_URL is correct

### "Recording not working"
- Try different browser (Chrome/Firefox recommended)
- Check browser codec support (VP8/Opus)
- Safari uses different codec - may need workaround

### Alert sound not playing
- Check browser volume
- Check `/public/alert-sound.mp3` exists
- Check browser autoplay policies
- Try manually allowing autoplay in browser settings

## 📦 File Structure

```
components/
├── live-camera.tsx              # ← NEW: Main live camera component
└── ui/
    ├── button.tsx               # Reused
    ├── card.tsx                 # Reused
    ├── alert.tsx                # Reused
    └── ... (other UI components)

app/
└── samples/
    └── page.tsx                 # ← UPDATED: Added live camera section

lib/
├── api-client.ts                # Already has detectFromFile function
├── types.ts                     # Already has DetectionResponse type
└── utils.ts

public/
└── alert-sound.mp3              # Existing alert sound
```

## 🎯 Next Steps (Optional Enhancements)

1. **Add incident logging** - Save detected accidents to database
2. **Add incident history** - Show past detections in dashboard
3. **Add geolocation** - Attach GPS coordinates to detections
4. **Add email alerts** - Send emails on accident detection
5. **Add multi-camera support** - Support multiple camera feeds
6. **Add RTSP stream support** - Connect to CCTV/IP cameras
7. **Add YOLO model selection** - Choose between different models
8. **Add performance analytics** - Track detection metrics

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Check browser console for errors (`F12` → Console tab)
3. Check backend logs
4. Verify all configuration variables are set
