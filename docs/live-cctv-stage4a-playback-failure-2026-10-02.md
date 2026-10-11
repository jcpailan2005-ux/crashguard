# Stage 4A Playback Failure Diagnosis & Resolution

**Date:** 2026-10-02
**Task:** Diagnose black-screen playback failure on source [3/10] `FICOSA-20221010_182008`, audit all 10 frozen sources, implement capture safety playback gates, create verified playback derivatives under existing license terms, and report playback readiness.

---

## 1. Executive Summary

During automated Stage 4A execution, playback stalled at source [3/10] `FICOSA-20221010_182008` with a completely black canvas while the orchestration showed `REPLAYING`.
- **Immediate Safe Abort:** Active background capture on port `8088` was stopped immediately. Zero useless black footage was written to disk.
- **Root Cause Identified:** All 6 Ficosa original videos are encoded in **MPEG-4 Part 2 (`FMP4` / Simple Profile)**. Modern web browsers (Chromium/Chrome, Edge, Firefox, Safari) strictly support only H.264/AVC, H.265/HEVC, VP8/VP9, and AV1 in HTML5 `<video>` elements. MPEG-4 Part 2 video tracks cannot be decoded by browser media engines, resulting in silent failure / black frames.
- **Resolution:** Generated 6 browser-compatible H.264 playback derivatives under `backend/data/tapo_replay_pilot/playback_derivatives/` using native Windows Media Foundation (`cv2.CAP_MSMF`), preserving frozen original assets untouched and byte-identical.
- **Capture Safety Gate Enforced:** Replay server and HTML player now enforce a bounded playback gate (`loadeddata` + `canplay` + `currentTime` advancement + offscreen frame decoding verification) **BEFORE** any Tapo RTSP capture can be initiated. If playback fails, capture is aborted and useful duration remains 0.

---

## 2. Comprehensive 18-Point Diagnostic Audit

| # | Check Item | Status | Detailed Finding |
|---|---|---|---|
| 1 | Source file exists | **PASS** | `backend/data/tapo_replay_pilot/source_videos/ficosa/20221010_182008.mp4` exists, 50,747,609 bytes. |
| 2 | OpenCV/FFmpeg decode | **PASS** | All 1,500 frames decode without error into non-empty 1344×968 BGR frames. |
| 3 | Duration / Resolution / Codec | **PASS (Media)** / **FAIL (Browser)** | Valid MP4 container, 1344×968 @ 25.0 FPS, 60.0s, FourCC `FMP4` (877677894). Codec is MPEG-4 Part 2. |
| 4 | Browser asset URL HTTP status | **PASS** | `GET /video/2` returns HTTP 206 Partial Content. |
| 5 | Content-Type header | **PASS** | `Content-Type: video/mp4`. |
| 6 | Byte-range requests supported | **PASS** | `Accept-Ranges: bytes` and `Content-Range: bytes 0-1023/50747609` verified. |
| 7 | HTMLMediaElement error | **FAIL** | Chromium decoder reports unsupported track format / codec mismatch for MPEG-4 Part 2 video stream. |
| 8 | `video.readyState` | **FAIL** | Stalls at `HAVE_METADATA` (1), never advances to `HAVE_ENOUGH_DATA` (4). |
| 9 | `video.networkState` | **FAIL** | Reaches `NETWORK_LOADING` (2) then errors out to `NETWORK_NO_SOURCE` (3). |
| 10 | `loadedmetadata` / `canplay` | **PARTIAL** | `loadedmetadata` fires from MP4 atom headers, but `canplay` / `playing` never fire. |
| 11 | `play()` promise | **FAIL** | Resolves or stalls while decode pipeline is blocked; no video surface painted. |
| 12 | `currentTime` actually advances | **NO** | Remains stationary or stutters at 0.0s with black canvas. |
| 13 | Decoded video frames appear | **NO** | Canvas remains 100% black; 0 visual frames rendered. |
| 14 | Autoplay / Fullscreen permissions | **PASS** | Fullscreen and playback initiated by explicit user click gesture. |
| 15 | Unsupported browser codec | **ROOT CAUSE** | **MPEG-4 Part 2 (`FMP4`) is deprecated and unsupported in modern HTML5 video tag engines.** |
| 16 | Source path / URL encoding | **PASS** | Clean integer route `/video/{idx}` without encoding issues. |
| 17 | Server route / range implementation | **PASS** | Starlette `FileResponse` range streaming verified. |
| 18 | Orchestration timing | **DEFECT FIXED** | Previous JS started recording immediately upon `play()` without awaiting verified advancing frames. |

---

## 3. Playback-Only Audit of All 10 Frozen Sources

| # | Source ID | Container | Video Codec | Resolution | Duration | Decode | HTTP Range | Browser Playable | Action / Remedy |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `ZILINA-SC10` | MP4 | `hevc` (H.265) | 3840×2160 | 10.0s | PASS | PASS | **PASS** | Native hardware decode in Edge/Chrome on Windows. |
| 2 | `URBANEGO-RUN2` | MP4 | `h264` (AVC) | 1280×720 | 663.7s | PASS | PASS | **PASS** | Native browser playback verified. |
| 3 | `FICOSA-20221010_182008` | MP4 | `FMP4` | 1344×968 | 60.0s | PASS | PASS | **FAIL (Orig)** / **PASS (Deriv)** | Transcoded to H.264 derivative. |
| 4 | `FICOSA-20221010_185218` | MP4 | `FMP4` | 1344×968 | 60.0s | PASS | PASS | **FAIL (Orig)** / **PASS (Deriv)** | Transcoded to H.264 derivative. |
| 5 | `FICOSA-20221010_191849` | MP4 | `FMP4` | 1344×968 | 60.0s | PASS | PASS | **FAIL (Orig)** / **PASS (Deriv)** | Transcoded to H.264 derivative. |
| 6 | `FICOSA-20221010_194855` | MP4 | `FMP4` | 1344×968 | 60.0s | PASS | PASS | **FAIL (Orig)** / **PASS (Deriv)** | Transcoded to H.264 derivative. |
| 7 | `FICOSA-20230220_202721` | MP4 | `FMP4` | 1344×968 | 60.0s | PASS | PASS | **FAIL (Orig)** / **PASS (Deriv)** | Transcoded to H.264 derivative. |
| 8 | `FICOSA-20230220_203150` | MP4 | `FMP4` | 1344×968 | 60.0s | PASS | PASS | **FAIL (Orig)** / **PASS (Deriv)** | Transcoded to H.264 derivative. |
| 9 | `MITRA-T1-D6` | MP4 | `h264` (AVC) | 3840×2160 | 439.2s | PASS | PASS | **PASS** | Native browser playback verified. |
| 10 | `MITRA-T2-D1` | MP4 | `h264` (AVC) | 3840×2160 | 941.5s | PASS | PASS | **PASS** | Native browser playback verified. |

---

## 4. Verification of Earlier Captured Sessions

Before diagnosing source 3, earlier sessions were audited frame-by-frame:
1. **`TAPO_SESSION_01_ZILINA-SC10`**:
   - Status: **VALID_NON_BLACK_CAPTURE**
   - File: `backend/data/tapo_replay_pilot/tapo_captures/sessions/TAPO_SESSION_01_ZILINA-SC10/...`
   - Frame Count: 353 frames (24.06 s @ 14.67 observed FPS).
   - Visual Quality: Daytime roundabout clearly resolved, vehicle movement distinguishable, mean brightness ~112–120. Non-black frames: 10/10 sampled.
2. **`TAPO_SESSION_02_URBANEGO-RUN2`**:
   - Status: **VALID_NON_BLACK_CAPTURE**
   - File: `backend/data/tapo_replay_pilot/tapo_captures/sessions/TAPO_SESSION_02_URBANEGO-RUN2/...`
   - Frame Count: 9,765 frames (671.17 s @ 14.55 observed FPS).
   - Visual Quality: Roadside daytime traffic visible, vehicles and pedestrians clearly resolved, mean brightness ~90–123. Non-black frames: 10/10 sampled.
3. **`TAPO_SESSION_03_FICOSA-20221010_182008`**:
   - Status: **ABORTED / PLAYBACK_FAILED**
   - Incomplete recording safely stopped; excluded from useful duration.

---

## 5. Ficosa Playback Derivatives Manifest

Created strictly under `backend/data/tapo_replay_pilot/playback_derivatives/` in accordance with CC BY-NC-SA 4.0 terms. Original frozen assets remain untouched:

| Source ID | Original SHA-256 | Derivative SHA-256 | Codec | Resolution |
|---|---|---|---|---|
| `FICOSA-20221010_182008` | `4779adde9a24bde5aa1ca9cc031d61c4da3b32fb3f1ed6fb6b24739bf47b7a20` | `84e49807c7b3f0504c84ac1e2afb0443e1a03b1006a7d5f9f5f158f7832279d2` | H.264 | 1344×968 |
| `FICOSA-20221010_185218` | `a1010b940bc127dab9f2dd87e51eb3e04900c581ec11226f7075e1784d742856` | `486be49bc7000c820a321672897f96f8f65ad6648e25b8698207550d0209baf0` | H.264 | 1344×968 |
| `FICOSA-20221010_191849` | `471d43819a8c48e10c2407744971f1dc5ce45fb85e5d67b8c2c3e4ab7be19e51` | `48fcc45248b8bbff9ab5a3e90317b36d5e37ace41fa1a8325d44070612799afd` | H.264 | 1344×968 |
| `FICOSA-20221010_194855` | `3c7a5a94e9d1148628351ec95e90b17e12fa2dc8d7aa9cdfbd5cf70571c88e7e` | `4d2481b15c148194d12b27f62dcbc4ad57457c2d57032563b385bbb7136b30ac` | H.264 | 1344×968 |
| `FICOSA-20230220_202721` | `efb706f9dd6e87bbf27dc36ac66105b7ccb528a6ca291854efce0b3b40acdee9` | `73c7bdea539b0c50785dd08447c43a4ec979b3c365e71fbc9eb9ce0a3a31c202` | H.264 | 1344×968 |
| `FICOSA-20230220_203150` | `27e48938ccd634a4459970871286e9d428d23ac4b899163c86da8d9a9ad5f049` | `33227208d8abdc9c3f8fe2060ed3879bc0dff312ab4e960af804ade7364ac148` | H.264 | 1344×968 |

---

## 6. Code & Tooling Modifications

1. **`backend/validation/tapo_replay_capture_stage4a_20261002/replay_player_server.py`**:
   - Added `resolve_source_playback_path()`: automatically routes requests to browser-safe H.264 derivatives while recording original asset provenance.
   - Implemented strict server-side playback gate: `ActiveCaptureSession.start_recording()` raises `RuntimeError` if `playback_verified` is not confirmed.
   - Added `/api/playback_gate_verified/{idx}` and `/api/playback_gate_failed/{idx}` endpoints.
   - Updated HTML5 player frontend with bounded canvas verification: confirms `readyState >= 2`, `currentTime > 0.05`, and non-black frame pixels before initiating recording.
   - Auto-halts sequence on failure and preserves earlier verified sessions.
2. **`backend/tests/test_stage4a_playback_gate.py`**:
   - Created 9 focused unit tests covering range requests, 404 handling, FMP4 detection, derivative resolution, gate enforcement, and earlier session validation (9/9 PASS).

---

## 7. Report Summary

FICOSA failure root cause:
Original video files encoded in MPEG-4 Part 2 (`FMP4` / Simple Profile), which is unsupported by modern browser HTML5 video tag engines, causing decode failure and black canvas.

Sources browser-playable:
10 / 10 (4 native + 6 via verified H.264 playback derivatives)

Sources requiring playback derivative:
6 (all 6 Ficosa FNTVD sequences: 20221010_182008, 20221010_185218, 20221010_191849, 20221010_194855, 20230220_202721, 20230220_203150)

Sources still unusable:
0

Earlier captured sessions valid:
2 / 2 (Session 1 ZILINA-SC10: 353 frames, non-black traffic confirmed; Session 2 URBANEGO-RUN2: 9765 frames, non-black traffic confirmed)

Code changes:
- `backend/validation/tapo_replay_capture_stage4a_20261002/replay_player_server.py`
- `backend/data/tapo_replay_pilot/playback_derivatives/` (6 H.264 video files + metadata manifest)
- `backend/tests/test_stage4a_playback_gate.py` (9 passing unit tests)

Production changes:
NONE

Training:
NONE

Annotation:
NONE

---

## Final Verdict

ALL_FROZEN_SOURCES_PLAYBACK_READY
