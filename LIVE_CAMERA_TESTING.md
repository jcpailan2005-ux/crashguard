# Live Camera - Setup & Testing Guide

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Node.js 16+ or pnpm 8+
- Laptop with webcam
- Backend running on http://localhost:8000 (or configured URL)

### 1. Start Backend (if not running)
```bash
cd backend
python -m pip install -r requirements.txt
python main.py
```
Backend should be running on http://localhost:8000

### 2. Start Frontend
```bash
# In project root
pnpm dev
# or
npm run dev
```
Frontend should be running on http://localhost:3000

### 3. Open Samples Page
Navigate to: **http://localhost:3000/samples**

Or from dashboard: **Dashboard → CCTV Samples** → Scroll down

### 4. Test Live Camera
1. Click **"Open Live Camera"** button
2. Click **"Start Camera"**
3. Browser asks for camera permission → Click **"Allow"**
4. Camera preview appears
5. Click **"Capture Image"**
6. Wait 2-5 seconds for detection result
7. Result card appears below video

Done! 🎉

---

## 🧪 Detailed Testing Procedures

### Test 1: Camera Permission Flow

**Goal**: Verify camera permission request and handling

**Steps**:
1. Navigate to `/samples`
2. Click "Open Live Camera"
3. Click "Start Camera"
4. Verify browser permission dialog appears
5. Click "Allow"
6. Verify video preview starts
7. Verify no errors in console

**Expected Result**:
- ✅ Permission dialog appears
- ✅ Video preview shows live feed
- ✅ No console errors

**If Failed**:
- Check browser permissions settings
- Check if camera is connected
- Try different browser
- Check browser console for errors

---

### Test 2: Permission Denied

**Goal**: Verify error handling when permission denied

**Steps**:
1. Navigate to `/samples`
2. Click "Open Live Camera"
3. Click "Start Camera"
4. Click "Block" or "Deny" on permission dialog
5. Verify error message appears

**Expected Result**:
- ✅ Error message: "Camera permission denied..."
- ✅ Toast notification shows
- ✅ Camera section shows error
- ✅ No crash or console errors

---

### Test 3: Image Capture & Detection

**Goal**: Verify capturing image and sending to backend

**Steps**:
1. Start camera (see Test 1)
2. Position something in front of camera
3. Click "Capture Image"
4. Verify captured image preview appears
5. Wait for detection result (3-10 seconds)
6. Check if detection result card appears

**Expected Result**:
- ✅ Captured image preview shows
- ✅ Result card appears with:
  - Accident/Safe badge
  - Confidence percentage
  - Media type: "image"
  - Timestamp
- ✅ Toast notification shows result
- ✅ No errors in console

**If Takes Too Long**:
- Check backend is running
- Check network tab in DevTools
- Check backend logs for errors

---

### Test 4: Accident Detection Alert

**Goal**: Verify alert sound plays when accident detected

**Prerequisites**: Backend returns accident_detected: true

**Steps**:
1. Start camera
2. Position yourself to trigger accident detection (or test with sample)
3. Click "Capture Image"
4. Wait for result
5. If accident detected, verify alert sound plays

**Expected Result**:
- ✅ Alert sound plays when accident detected
- ✅ Toast shows "🚨 Accident Detected"
- ✅ Badge shows red/destructive color
- ✅ Confidence displayed

**If Sound Doesn't Play**:
- Check browser volume
- Check if `/public/alert-sound.mp3` exists
- Check browser autoplay policy
- Open browser console and check for errors

---

### Test 5: Video Recording & Detection

**Goal**: Verify video recording and detection

**Steps**:
1. Start camera
2. Click "Record Video"
3. Verify red "REC" indicator appears top-right
4. Keep recording for 3-5 seconds
5. Click "Stop Recording"
6. Wait for detection result
7. Verify result appears

**Expected Result**:
- ✅ Red "REC" indicator visible while recording
- ✅ Recording stops and processes
- ✅ Detection result appears with:
  - Media type: "video"
  - Accident/Safe status
  - Confidence
- ✅ Download annotated video link appears

**If Recording Fails**:
- Check browser compatibility (Chrome/Firefox best)
- Check browser console for errors
- Try shorter recording duration
- Try restarting camera

---

### Test 6: Annotated Result Link

**Goal**: Verify annotated media can be viewed

**Prerequisites**: Backend returns annotated_media_url

**Steps**:
1. Capture image or record video
2. Wait for detection result
3. Check if "View Annotated Result" or "Download Annotated Footage" link appears
4. Click the link
5. Verify annotated media opens/downloads

**Expected Result**:
- ✅ Link appears in result card
- ✅ Link is clickable
- ✅ Opens in new tab or downloads file
- ✅ Shows annotated media with bounding boxes

**If Link Missing**:
- Backend not returning annotated_media_url
- Check backend configuration
- Check if output files are being saved
- Review backend logs

---

### Test 7: Camera Cleanup

**Goal**: Verify camera stream stops properly

**Steps**:
1. Start camera
2. Open DevTools → Application tab
3. Check camera indicator (should show recording/camera active)
4. Click "Stop Camera"
5. Verify camera indicator disappears
6. Verify "Stop Camera" button changes back to "Start Camera"

**Expected Result**:
- ✅ Camera stops streaming
- ✅ Button label changes to "Start Camera"
- ✅ Video preview goes black
- ✅ Camera indicator disappears

**If Stream Continues**:
- Check browser processes
- Restart browser
- Check for memory leaks in DevTools

---

### Test 8: Loading States

**Goal**: Verify loading indicators show during operations

**Steps**:
1. Start camera
2. Click "Capture Image"
3. Verify "Analyzing frame..." loading overlay appears on video
4. Wait for completion
5. Verify loading overlay disappears when result appears

**Expected Result**:
- ✅ Loading indicator appears
- ✅ Buttons are disabled during processing
- ✅ Loading disappears when result shows
- ✅ User can capture again after

---

### Test 9: Error Handling - Backend Down

**Goal**: Verify graceful handling when backend unavailable

**Prerequisites**: Stop backend server

**Steps**:
1. Stop backend (Ctrl+C)
2. Start camera
3. Click "Capture Image"
4. Wait for result
5. Verify error handling

**Expected Result**:
- ✅ Mock response shown (if NEXT_PUBLIC_USE_MOCK_DATA=true)
- ✅ OR error message shown (if mock disabled)
- ✅ Toast notification explains issue
- ✅ User can retry after backend restarts

---

### Test 10: Multiple Captures

**Goal**: Verify multiple captures work correctly

**Steps**:
1. Start camera
2. Capture image → verify result
3. Click "Clear Result"
4. Verify result card disappears
5. Capture different frame → verify new result
6. Repeat 5+ times

**Expected Result**:
- ✅ Each capture creates new detection
- ✅ Previous result cleared properly
- ✅ No memory leaks
- ✅ Performance stays consistent

---

## 🔍 Browser DevTools Inspection

### Console Check (F12 → Console)
Look for:
- ✅ No red error messages
- ✅ No warnings about camera
- ✅ No blocked requests

### Network Check (F12 → Network)
Look for:
- ✅ POST /api/detect/image or /api/detect/video calls
- ✅ Requests return 200 status
- ✅ Response contains detection results

### Performance Check (F12 → Performance)
Record while:
- Starting camera
- Capturing image
- Verify no long tasks
- Check memory usage stable

### Application Check (F12 → Application)
- Camera indicator should show when streaming
- Should stop when "Stop Camera" clicked

---

## 📊 Test Results Template

Copy this and fill in your results:

```
Test Results
============

Environment:
- Browser: ___________
- OS: ___________
- Backend URL: ___________
- Frontend URL: ___________

Test Results:
1. Camera Permission: [ ] Pass [ ] Fail
2. Permission Denied: [ ] Pass [ ] Fail
3. Image Capture: [ ] Pass [ ] Fail
4. Accident Alert: [ ] Pass [ ] Fail
5. Video Recording: [ ] Pass [ ] Fail
6. Annotated Result: [ ] Pass [ ] Fail
7. Camera Cleanup: [ ] Pass [ ] Fail
8. Loading States: [ ] Pass [ ] Fail
9. Backend Down: [ ] Pass [ ] Fail
10. Multiple Captures: [ ] Pass [ ] Fail

Overall: [ ] Ready for Production [ ] Needs Fixes

Issues Found:
- __________
- __________

Notes:
- __________
- __________
```

---

## 🐛 Debugging Tips

### Check If Camera is Working
```javascript
// In browser console
navigator.mediaDevices.getUserMedia({video: true})
  .then(stream => console.log('Camera works!'))
  .catch(err => console.log('Camera error:', err))
```

### Check Backend Health
```bash
# Test backend health endpoint
curl http://localhost:8000/api/health

# Should return:
# {"status":"ok","timestamp":"...","version":"..."}
```

### Monitor API Calls
```bash
# In another terminal, monitor requests
# On macOS/Linux:
tail -f backend.log | grep "detect"

# On Windows:
Get-Content backend.log -Wait | Select-String "detect"
```

### Test Manual Image Upload
1. Go to **Dashboard → Upload**
2. Upload test image
3. If this fails, backend might be misconfigured
4. If this works, live camera should work too

---

## ✅ Production Checklist

Before deploying to production:

- [ ] Backend URL configured correctly
- [ ] Backend running with production database
- [ ] Backend returning annotated_media_url
- [ ] HTTPS enabled on frontend
- [ ] HTTPS enabled on backend
- [ ] Alert sound file exists
- [ ] Camera permission flow tested
- [ ] Error messages clear and helpful
- [ ] Incident logging working
- [ ] Alert notifications configured
- [ ] Performance acceptable (< 5s detection)
- [ ] Memory leaks verified absent
- [ ] All tests passed
- [ ] User documentation read

---

## 📞 Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Camera permission denied | Check browser settings, try incognito mode |
| No camera found | Verify hardware, check USB connection |
| Detection takes too long | Check backend logs, verify YOLO model loaded |
| Alert sound doesn't play | Check volume, check file path, check autoplay policy |
| Annotated result missing | Backend not saving files, check output directory |
| Can't record video | Try different browser, check codec support |
| Stream doesn't stop | Restart browser, check DevTools camera indicator |
| Backend error | Check backend running, check logs, restart server |
| Camera not appearing | Refresh page, clear browser cache |
| Mixed content error | Use HTTPS or localhost |

---

## 📱 Mobile/Tablet Testing

The component should work on mobile if:
- ✅ HTTPS enabled
- ✅ Camera permission granted
- ✅ Modern mobile browser (Chrome/Firefox/Safari 11+)

Note: Video recording on mobile may have limitations due to codec support.

---

**Last Updated**: 2024-04-18
**Version**: 1.0.0
