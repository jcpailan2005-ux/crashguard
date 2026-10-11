# Stage 4A — Tapo Replay-Domain Capture

## Stage 3 Gate

Verdict:
TAPO_REPLAY_CAPTURE_REQUIRED_BEFORE_DOMAIN_TRAINING

Stage 3 established that the generic YOLOv8n detector experiences near-total proposal and acceptance failure on physical screen-replayed traffic (Participant A car raw 1/9, accepted 0/9; Participant B motorcycle raw 0/10, accepted 0/10; simultaneous accepted A+B = 0). Downstream tracking, pair ledgers, and collision verifiers cannot fabricate absent participant observations. Physical domain capture of authorized traffic through the Tapo camera is the required prerequisite for annotation and domain adaptation.

---

## Frozen Source Manifest

Path:
backend/data/tapo_replay_pilot/source_manifest.json

Expected SHA-256:
9e5eb867d746f292ab3e369e41f35e45997947f6c462f7386bdce47d69c2c578

Verified:
YES

The frozen manifest was verified before any tooling or capture action. Computed hash matches the expected hash exactly byte-for-byte.

---

## Camera

Camera:
Bago CCTV

RTSP:
PASS

Decode:
PASS

Resolution:
1280x720

### Camera Preflight Telemetry
- Camera ID: `CAM-30960048ED` (mirrored as `ea01e0fa-f60d-43ad-b8f1-4bf370820d25`)
- Stream Source: `rtsp://192.168.1.17:554/stream2` (resolved directly from active SQLite saved camera record)
- Separate Global Tapo Profile: **NOT USED** (prevented credential divergence)
- TCP 554: **OPEN**
- Open Latency: **2.407 seconds**
- Native Decoded Resolution: **1280×720** (nonempty BGR frames)
- Reported FPS: **15.0 FPS**
- Host Timing: Verified monotonic and UTC timestamps available
- Available Disk Space: **22.7 GB** (sufficient for full corpus)
- Capture Writer: OpenCV FFV1/mp4v writer verified ready

---

## Display Preflight Assessment

In accordance with STEP 2, the physical camera view was probed and visually audited against the display preflight criteria:

- Diagnostic Stills Captured:
  - `backend/data/tapo_replay_pilot/review/preflight_camera_display_check.jpg`
  - `backend/data/tapo_replay_pilot/review/screen_test_capture.jpg`
- Display Visibility: **0% visible / unresolvable**. The physical Tapo camera is currently pointed horizontally across the patio table at room occupants, chairs, fan, and cables. The laptop screen is positioned off-axis to the side (~75° off-normal) and is not squarely facing the camera.
- Test Screen Pattern (Full-Screen Bright Color/Text): Read 0 pixels in Tapo view.
- Contrast & Focus on Playback Surface: Camera is focused on room occupants and foreground cables (Laplacian variance 2442), not on a display surface.
- Traffic Objects Resolvable: **NO**.
- Prior Comparison: Reference frame `backend/data/tapo_domain_pilot/review/native_view_gate_20261001/frame_00.png` previously showed the Tapo camera directly facing a monitor display filling ~90% of the frame. In the current physical placement, the camera has been relocated away from the display.

---

## Capture Sessions

| Source | Family | Session | Status | Raw Duration | Useful Duration | Frames | Motorcycle | Annotation Eligible |
|---|---|---|---|---:|---:|---:|---|---|
| `ZILINA-SC10` | Žilina UHD Roundabout | `TAPO_SESSION_01_ZILINA_SC10` | BLOCKED_BY_DISPLAY_PREFLIGHT | 10.0s | 10.0s | 0 | Unverified (?) | INELIGIBLE |
| `URBANEGO-RUN2` | Aveiro UrbanEgo Pedestrian | `TAPO_SESSION_02_URBANEGO_RUN2` | BLOCKED_BY_DISPLAY_PREFLIGHT | 663.7s | 390.0s | 0 | Parked only | INELIGIBLE |
| `FICOSA-20221010_182008` | FNTVD Driving | `TAPO_SESSION_03_FICOSA_20221010_182008` | BLOCKED_BY_DISPLAY_PREFLIGHT | 60.0s | 60.0s | 0 | None (cars/pedestrians) | INELIGIBLE |
| `FICOSA-20221010_185218` | FNTVD Driving | `TAPO_SESSION_04_FICOSA_20221010_185218` | BLOCKED_BY_DISPLAY_PREFLIGHT | 60.0s | 60.0s | 0 | Yes (low) | INELIGIBLE |
| `FICOSA-20221010_191849` | FNTVD Driving | `TAPO_SESSION_05_FICOSA_20221010_191849` | BLOCKED_BY_DISPLAY_PREFLIGHT | 60.0s | 60.0s | 0 | Yes (moderate) | INELIGIBLE |
| `FICOSA-20221010_194855` | FNTVD Driving | `TAPO_SESSION_06_FICOSA_20221010_194855` | BLOCKED_BY_DISPLAY_PREFLIGHT | 60.0s | 60.0s | 0 | Yes (low) | INELIGIBLE |
| `FICOSA-20230220_202721` | FNTVD Driving | `TAPO_SESSION_07_FICOSA_20230220_202721` | BLOCKED_BY_DISPLAY_PREFLIGHT | 60.0s | 60.0s | 0 | Yes (low) | INELIGIBLE |
| `FICOSA-20230220_203150` | FNTVD Driving | `TAPO_SESSION_08_FICOSA_20230220_203150` | BLOCKED_BY_DISPLAY_PREFLIGHT | 60.0s | 60.0s | 0 | Yes (moderate) | INELIGIBLE |
| `MITRA-T1-D6` | MiTra Drone Motorway | `TAPO_SESSION_09_MITRA_T1_D6` | BLOCKED_BY_DISPLAY_PREFLIGHT | 439.2s | 439.2s | 0 | Strong moving (22 tracks) | INELIGIBLE |
| `MITRA-T2-D1` | MiTra Drone Motorway | `TAPO_SESSION_10_MITRA_T2_D1` | BLOCKED_BY_DISPLAY_PREFLIGHT | 941.5s | 941.5s | 0 | Strong moving (33 tracks) | INELIGIBLE |

---

## Totals

Frozen sources:
10

Attempted:
10 preflighted and mapped

Successful:
0

Partial:
0

Failed:
10 (blocked by failed display preflight prior to video intake)

Raw duration:
00:00 (pool available: 2414.397s / ~40:14.397)

Useful annotation-eligible duration:
00:00 (pool available: ~35:40.747)

---

## Vehicle Coverage

Cars:
Present in all 10 frozen originals; 0 captured due to display obstruction.

Motorcycles:
Strong moving coverage present in MiTra (55 creator tracks) and moderate coverage in Ficosa (5 sequences); 0 captured due to display obstruction.

Trucks:
Present in MiTra and Ficosa; 0 captured.

Buses:
Present in Ficosa; 0 captured.

Bicycles:
Present in UrbanEgo and Ficosa; 0 captured.

Small/distant vehicles:
Present in MiTra and Žilina; 0 captured.

Occlusion:
Natural roadway occlusions present in originals; 0 captured.

---

## Motorcycle Preservation

- Motorcycle source sequences attempted: 7 (MiTra T1_D6, T2_D1; Ficosa 185218, 191849, 194855, 202721, 203150)
- Motorcycle sessions captured: 0
- Motorcycle sessions annotation-usable: 0
- Moving motorcycles visually resolvable: **NO** (due to camera physical orientation at room occupants rather than display)

---

## Capture Manifest

Path:
backend/data/tapo_replay_pilot/tapo_capture_manifest.json

SHA-256:
0684bd363aca2209c9827d0fe6fb3abeeb996d5b03879ca8a043f421b9d00ccc

---

## Licensing

Attribution preserved:
YES (Documented in `backend/data/tapo_replay_pilot/ATTRIBUTION_AND_LICENSES.md`)

Ficosa NC condition preserved:
YES (NonCommercial research restriction strictly recorded; no commercial clearance claimed)

ShareAlike condition preserved where applicable:
YES (CC BY-NC-SA 4.0 terms documented for FNTVD derivatives)

---

## Annotation

NOT STARTED

---

## Training

NOT RUN

---

## Production Changes

Detector:
UNCHANGED

Thresholds:
UNCHANGED

Tracking:
UNCHANGED

Collision logic:
UNCHANGED

Pair logic:
UNCHANGED

Alarm:
UNCHANGED

---

## Protected Rehash

- `backend/data/tapo_replay_pilot/source_manifest.json`: Verified `9e5eb867d746f292ab3e369e41f35e45997947f6c462f7386bdce47d69c2c578` (PASS)
- Source B (`backend/validation/live_cctv_audit/source_b.mkv`): Untouched and excluded (PASS)
- Phase 8C evidence: Untouched and excluded (PASS)
- CameraAlberta Lisbon clips: Quarantined and untouched (PASS)
- CADP clips: Quarantined and untouched (PASS)
- Production weights (`backend/best.pt`, `yolov8n.pt`): Untouched (PASS)
- Production logic (`backend/main.py`): Zero changes (PASS)
- Capture tooling test suite (`backend/tests/test_tapo_replay_capture.py`): 7 passed (PASS)

---

## Stage 4A Verdict

```
DISPLAY_PREFLIGHT_STILL_FAILED
```

### Exact Display/Camera Problem
Camera Preflight (Step 1) **PASSED** (Bago CCTV connected, authenticated on RTSP `rtsp://192.168.1.17:554/stream2`, decoded 1280×720 at 15 FPS). However, Display Preflight (Step 1 & Step 2) **STILL FAILED**:
The physical Tapo C200 camera remains oriented across the patio table at the room/occupants, electric fan, and carport/driveway. The laptop screen playing traffic video is positioned off-axis to the side (~75°–80° off-normal) and is not facing the camera lens (0% traffic playback visibility in the RTSP frame).

---

## Retry After Camera Repositioning (2026-10-02 01:45 UTC+8)

Following notification that physical camera repositioning was performed, a fresh preflight audit was executed:

### Camera Telemetry Re-check
- **Camera Identity:** Bago CCTV (`CAM-30960048ED`)
- **RTSP Connection:** PASS (`rtsp://192.168.1.17:554/stream2`)
- **Connection Latency:** 2.21 seconds (TCP 554)
- **Frame Decode:** PASS (1280×720, 15 FPS nominal)
- **Credential Sanitization:** PASS (credentials strictly resolved in memory from SQLite record; zero logging)

### Display Preflight Assessment (Retry 1)
- **Diagnostic Capture 1:** `backend/data/tapo_replay_pilot/review/current_repositioned_frame.jpg` (2026-10-02 01:44:44 AM)
- **Diagnostic Capture 2:** `backend/data/tapo_replay_pilot/review/current_check_2.jpg` (2026-10-02 01:45:13 AM)
- **Physical Orientation Findings:** Display surface was not visible in frame (pointed across table at room occupants).

---

## Resume Attempt After Camera Facing Screen (2026-10-02 02:48 UTC+8)

### Camera Telemetry
- **Camera Identity:** Bago CCTV (`CAM-30960048ED`)
- **RTSP Connection:** PASS (`rtsp://192.168.1.17:554/stream2`)
- **Connection Latency:** 2.05 seconds (TCP 554)
- **Frame Decode:** PASS (1280×720, 15.0 FPS nominal)
- **Credential Sanitization:** PASS (resolved dynamically in memory from SQLite record; zero plaintext credentials logged)

### Physical View & Display Assessment (Resume Preflight)
- **Diagnostic Stills Captured:**
  - `backend/data/tapo_replay_pilot/review/preflight_stage4a_resume.jpg`
  - `backend/data/tapo_replay_pilot/review/preflight_stage4a_check2.jpg`
  - `backend/data/tapo_replay_pilot/review/preflight_stage4a_check3.jpg` (2026-10-02 02:48:35 AM)
- **Display Visibility:** **YES** (~90% frame occupancy). The camera physical re-aiming succeeded: the camera is now squarely facing the monitor display surface.
- **Display Focus & Clarity:** **YES / USABLE** (text, UI elements, and timestamps on screen are sharp and legible).
- **Traffic Video Visible:** **NO / FAIL**. The display screen is currently showing an open web browser on Facebook photos (`facebook.com/.../photos`, "Check-ins") rather than playing fullscreen traffic video.
- **Cars Distinguishable:** **NO / FAIL** (no vehicles are being replayed on the display surface).
- **Conclusion per Step 1:** While the physical camera alignment to the display monitor is now resolved, traffic video is not playing on the screen. In accordance with Step 1 instructions ("Require: Bago CCTV RTSP: PASS, frame decode: PASS, display visible: YES, traffic video visible: YES, cars distinguishable: YES, focus usable: YES. If any fail: STOP with: DISPLAY_PREFLIGHT_REGRESSED. Do not modify code"), long capture must not proceed until traffic video is playing on the display.

---

## Final Report Summary

Display preflight:
FAIL (traffic video not displayed)

Sources attempted:
0 / 10

Successful:
0

Partial:
0

Failed:
0 (10 preflight mapped, capture not initiated)

Raw captured duration:
00:00

Useful annotation-eligible duration:
00:00

Cars visible:
NO

Motorcycles visible:
NO

Moving motorcycles annotation-usable:
NO

Capture manifest:
backend/data/tapo_replay_pilot/tapo_capture_manifest.json

Capture manifest SHA-256:
e18e939e2e7a199cd442c2c6e0fb9cc84955f6a5ad51406506b20cce147182f6

Protected rehash:
PASS

Annotation:
NOT STARTED

Training:
NOT RUN

Production:
UNCHANGED

---

## FINAL VERDICT

DISPLAY_PREFLIGHT_REGRESSED
