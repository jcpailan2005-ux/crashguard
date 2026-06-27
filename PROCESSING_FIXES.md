# Video & Image Processing Fixes

## Issues Found & Fixed

### 1. **Video Writer Codec Failure (CRITICAL)**
**Problem:** The `create_video_writer()` function only tried MP4 codecs (avc1, H264, mp4v). If all MP4 codecs failed, it would return `None` for the writer, silently preventing video output generation.

**Symptoms:**
- Videos uploaded but no annotated output video generated
- `annotated_media_url` returns `null` in the response
- No error message to user

**Fix Applied:**
- Added MJPEG codec as fallback for when MP4 codecs fail
- Added proper error handling and logging to identify which codecs work/fail
- Function now logs which codec was successfully used

### 2. **Missing Logging & Error Visibility**
**Problem:** Detection endpoints had minimal logging, making debugging impossible. Users couldn't see what went wrong.

**Symptoms:**
- Silent failures during video/image processing
- No way to identify if the problem is codec-related, file-related, or model-related

**Fix Applied:**
- Added detailed logging to `detect_image()` endpoint with progress indicators
- Added detailed logging to `detect_video()` endpoint including:
  - File save status
  - Video properties (dimensions, FPS)
  - Frame processing progress
  - Codec selection status
  - Detection results

### 3. **Potential Frame Writing Issues**
**Problem:** While the code checks `if writer is not None`, there was no validation that frames were actually being written successfully.

**Fix Applied:**
- Existing checks are sufficient but added better logging to identify if writer creation fails

## Backend Endpoints

### Image Detection
**Endpoint:** `POST /api/detect/image`
- Uploads image to `backend/uploads/`
- Runs YOLO detection on image
- Saves annotated image to `backend/outputs/`
- Returns detection results with URL to annotated image

### Video Detection  
**Endpoint:** `POST /api/detect/video`
- Uploads video to `backend/uploads/`
- Processes each frame through YOLO model
- Attempts to save annotated video with fallback codecs
- Returns detection samples and URL to annotated video (if successfully created)

## Testing the Fix

### Step 1: Check Backend Logs
When you upload a file, check the terminal running the backend (uvicorn) for detailed logs:

```
→ Starting image detection for: test.jpg
  ✓ File saved to: ...
  ✓ Detection complete: 2 objects detected, accident=False, confidence=0.00%
  ✓ Annotated image saved to: ...
```

### Step 2: Test Video Upload
When uploading a video, look for:

```
→ Starting video detection for: test.mp4
  ✓ File saved to: ...
  ✓ Video opened: 1280x720 @ 30.0fps
  ✓ Video writer opened successfully with codec: H264
  ✓ Processed 150 frames, accident_detected=False, confidence=0.00%
  ✓ Annotated video saved to: ...
```

If you see `✓ Video writer opened successfully with codec: MJPEG`, it means MP4 codecs failed but MJPEG fallback worked.

If you see `⚠ Video writer failed - output video will not be generated`, then all codecs failed on your system.

## Environment Variables to Check

Make sure in your `.env` or environment:
- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` (or your actual backend URL)
- `FRONTEND_ORIGINS=http://localhost:3000` (FastAPI CORS setting)

## Next Steps if Still Not Working

1. **Check the backend logs** - Run backend with logs visible
2. **Verify CORS** - Check if frontend is getting CORS errors in browser console
3. **Test directly** - Use `curl` to test backend endpoints:
   ```bash
   curl -X POST -F "file=@test.jpg" http://localhost:8000/api/detect/image
   ```
4. **Check codec availability** - Run:
   ```python
   import cv2
   print(cv2.VideoWriter_fourcc(*'H264'))  # Should return non-negative number
   ```

## Files Modified
- `backend/main.py` - Enhanced video writer creation and added comprehensive logging
