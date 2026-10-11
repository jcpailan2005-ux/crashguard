# CrashGuard Live Monitor Restoration Audit + Fix

Working tree inspected September 15–16, 2026. Existing uncommitted work was preserved. This report distinguishes the requested fixes from pre-existing implementation gaps.

## 1. Historical Algorithm Verification

- **Old commit:** `42f8ab41`.
- **OLD_MODEL_PATH:** `backend/best.pt` at that commit; Git blob `0db4ca4b4d25d68a4497220353592645ca4f71bf` (6,549,796 bytes).
- **OLD_MODEL_TYPE:** Ultralytics `DetectionModel`, task `detect`, with 80 COCO classes. Loaded from an extracted historical artifact in the temporary directory. The current `best.pt` has the same Git blob.
- **OLD_MODEL_CLASS_NAMES:** all 80 verified names are listed below. There is **no accident, crash, or collision class**.
- **OLD_DECISION_RULE:** direct accident/crash/collision labels were checked, but this model had none. Vehicle overlap/contact heuristics, including motorcycle and lower-confidence overlap fallbacks, could synthesize an `accident` detection. This was not a trained accident-class detector.
- **3-hit logic:** `42f8ab41` defaulted `LIVE_CAMERA_REQUIRED_HITS` to **1**, counted positives in a bounded window of at least three entries, and allowed a manual threshold hit directly. It did not require three consecutive hits by default. `2f3c4c84` introduced the default of **3 consecutive qualifying observations within five seconds**, retained in the inspected live path. Environment overrides still apply.
- **Previous audit claim corrected: YES.** Both the supposed accident-class model and the old default three-consecutive-hit claim were incorrect.

History checks included `2f3c4c84` (classifier probability and temporal gates), `8be6013b` (role UI), `c11beaa8` (Admin creation authorization), later commits through `0566bdc2`, and the actual uncommitted working tree. Current behavior differs from the documentation: the live monitor still calls the hit-window/box-interaction path. Newer tracking, continuity, tiers, and temporal-verifier modules exist, but the inspected live monitor does not invoke that complete pipeline. This task did not reconstruct or replace those modules.

Verified class names, in model index order:

```text
person, bicycle, car, motorcycle, airplane, bus, train, truck, boat,
traffic light, fire hydrant, stop sign, parking meter, bench, bird, cat,
dog, horse, sheep, cow, elephant, bear, zebra, giraffe, backpack, umbrella,
handbag, tie, suitcase, frisbee, skis, snowboard, sports ball, kite,
baseball bat, baseball glove, skateboard, surfboard, tennis racket,
bottle, wine glass, cup, fork, knife, spoon, bowl, banana, apple, sandwich,
orange, broccoli, carrot, hot dog, pizza, donut, cake, chair, couch,
potted plant, bed, dining table, toilet, tv, laptop, mouse, remote,
keyboard, cell phone, microwave, oven, toaster, sink, refrigerator,
book, clock, vase, scissors, teddy bear, hair drier, toothbrush
```

## 2. Analyze-First Root Cause

**Exact backend bypass:** the `duplicate_active_case` branch in `LiveCameraMonitor.analyze_current_frame` unconditionally set both accident booleans to `True`. The decision helper checked evidence before deduplication, so a completely negative frame did **not** reach this branch merely because a case existed. However, eligible aftermath observations could reach it without current collision confirmation. The creation branch also set `True` for aftermath review. The browser-camera image route could retain its earlier suspicion boolean in the duplicate branch.

**Exact frontend bypass:** `surfacedResult.accident_detected || stability.stableCrash` bypassed sample stabilization, then a per-camera 30-second cooldown allowed repeated alarms. Display normalization could also promote a detection label into the accident boolean. A separate workspace alarm used `possible-crash-detected || activePendingCase || isSavedCrashCase(...)`, so old cases could sound even outside the selected camera.

## 3. Analyze-First Fix

- **Current candidate state:** existing `candidate`/`verifying` states display “Analyzing potential collision...”. Aftermath cases retain a visual review alert without the siren.
- **Authoritative confirmation condition:** the existing backend current-observation gate: valid frame and scene, qualifying vehicle evidence, current consecutive-hit requirement, and the live path's existing interaction condition. No second frontend hit algorithm was added. The frontend uses `finalDecision === 'confirmed_crash'` and the backend accident boolean.
- **Alarm condition:** a freshly timestamped, newly persisted, confirmed event with an unseen case/incident ID. One shared tracker covers the selected camera and background tiles. Old timestamps, missing timestamps, duplicates, and previously consumed IDs cannot sound. The detector does not count repeated analysis of the same captured frame as new evidence.
- **Duplicate-case behavior:** existing `existingCase`, `activeBlockingCaseId`, `persistenceReason`, `finalDecision`, and `temporalCrashVerified` fields distinguish evidence from deduplication. Duplicate suppression remains. A duplicate's accident boolean can be true only when current evidence independently confirms a collision; it still does not emit a new alarm.

## 4. Alarm Regression

| Check | Result |
|---|---|
| Candidate causes alarm | NO |
| Duplicate active case causes fresh alarm | NO |
| New confirmed transition causes alarm | YES |
| Repeated same event replays alarm | NO |
| Separate new confirmed event can alarm | YES |

These are executable regression results, not an audible browser validation.

## 5. Camera Lag Root Cause

- **JPEG hot-path encoding confirmed: YES.** Every retained capture iteration encoded a JPEG, even without a viewer.
- **Decoder backlog confirmed: PARTIAL.** The code discarded five frames after every initial grab, reducing published observations to roughly one in six. This was verified in code and consistent with measured capture rates. Network/decoder queue depth and sensor-to-browser delay were not directly measured.
- **Fixed inference wait found: YES.** A default 500 ms pause preceded each inference. The separate 500 ms SSE emission pause is not an inference pause and remains unchanged.
- The live path already resized input to 640×360; that pre-existing resize was removed.

## 6. Camera Performance Fix

- **Capture architecture:** continuous `read()`/decode into one overwritten native-frame slot, with a sequence number and decode-completion timestamp. No fixed five-frame flush remains.
- **JPEG architecture:** demand-driven encoding, cached by frame sequence. A separate preview lock coalesces consumers; JPEG compression runs outside the capture lock. No viewer means no capture-driven JPEG encoding. Tests cover real JPEG decoding, caching, and capture advancing during compression.
- **Buffer behavior:** `CAP_PROP_BUFFERSIZE=1` is attempted after opening and its acceptance is logged. OpenCV 4.13.0/FFmpeg returned **False** on the actual feed. No claim is made that this property controls its buffering.
- **RTSP options:** existing TCP, `nobuffer`, and `max_delay` options retained. Both the current options and a `flags=low_delay` trial decoded 45 frames successfully (3.907 and 3.945 seconds including opening). The trial did not demonstrate a latency advantage; `low_delay` was not enabled in production code.
- **Inference cadence behavior:** default artificial wait changed from 500 ms to zero only after the serial comparison below. A new-frame event prevents busy spinning. A nonblocking analysis lock prevents overlapping manual/background inference. Explicit environment overrides remain honored.
- **Resolution:** native decoded input, YOLO `imgsz=640`; no confidence thresholds changed. Lightweight status diagnostics expose capture/preview/inference rates, frame ages, JPEG time/count, inference time, resolution, reconnect count, and stale-frame state. Timing histories have fixed bounds.

## 7. Performance Before vs After

Serial, read-only tests against the configured RTSP feed; about 30 seconds each. Case creation and case lookups were mocked so benchmarking could not mutate operational history. A local JPEG consumer requested previews at 30 Hz. This was a monitor-component benchmark, not an authenticated browser benchmark.

| Metric | Before: original path | Native capture + 500 ms wait | After: native + no artificial wait |
|---|---:|---:|---:|
| Capture FPS | 2.26 | 13.78 | 13.87 |
| Inference cycles/sec | 0.99 | 0.72 | 0.98 |
| JPEG encodes/sec, viewer present | 2.33 | 12.81 | 11.97 |
| Preview frame age, mean ms | 203.01 | 42.43 | 45.69 |
| Inference frame age, mean ms | 176.82 | 32.00 | 37.60 |
| Inference duration, mean ms | 402.49 | 755.87 | 914.24 |
| JPEG encode duration, mean ms | 6.85 | 9.85 | 11.15 |
| Process CPU, one core = 100% | 157.29% | 144.00% | 172.77% |

Capture FPS before uses 30 Hz timestamp sampling; after uses exact frame sequence counts. Durations include camera opening and bounded shutdown. Native detector input costs more CPU work; removing the wait recovered approximately the original inference rate while restoring native detail. More fresh frames now reach the preview consumer, so its JPEG rate increases. The no-viewer encoding regression is zero.

**Frame ages begin after decoding; they do not include camera/network latency. Browser preview latency and the reported 5–15 second end-to-end delay remain unverified. No claim is made that total lag or collision recall is solved.** Measurements: `before.json`, `after-500ms.json`, `after-no-wait.json`, and `rtsp-options.json`.

## 8. Camera Management

| Check | Result |
|---|---|
| Admin Add Camera | PASS — control contract and authenticated route test |
| Admin Delete Camera | PASS — permitted normal camera, mocked mutation |
| Dispatcher Add Camera | POLICY_NOT_ALLOWED by default |
| Dispatcher Delete Camera | POLICY_NOT_ALLOWED by default |
| Responder camera management blocked | PASS |
| Protected camera safeguard | PASS |

Both UI surfaces use explicit `cameras.create`, `cameras.update`, and `cameras.disable` permissions. The legacy API now honors the PostgreSQL session cookie and checks the same action permissions. Its unauthenticated local-Dispatcher fallback was removed. PostgreSQL role grants and credentials were not changed. An explicitly granted Dispatcher permission is honored; Responders remain excluded even with an erroneous management grant.

Normal cameras may be managed by an authorized principal. Seeded demo markers (`cameraType=Demo`, `demo://` streams, or `demo-` camera IPs) suppress deletion in the UI and are rejected by the backend delete route. There is no separate generic protected-record flag in the inspected schema. Existing Add/Edit dialogs were reused. No operational camera was created or deleted during verification.

Interactive UI verification was attempted, but the in-app browser could not initialize because its tool connection reported a missing `sandboxPolicy` field. Therefore no browser screenshot, click-through, or audible alarm claim is made.

## 9. Files Changed

Implementation:

- `backend/main.py`
- `components/live-camera.tsx`
- `components/cctv-monitor-workspace.tsx`
- `components/admin-camera-management-table.tsx`
- `lib/incident-alarm-contract.ts`
- `lib/camera-management-permissions.ts` (new)

Tests and reproducible validation:

- `backend/tests/test_live_monitor_restoration.py` (new)
- `backend/tests/test_camera_performance.py` (updated stale API/resolution expectations)
- `backend/tests/test_camera_role_permissions.py` (explicit permission grants)
- `frontend-tests/live-monitor-restoration.test.ts` (new)
- `scripts/benchmark_live_restoration.py` (new)
- `scripts/test_live_restoration.py` (new)
- `docs/live-monitor-restoration/` (this report, measurements, test logs, and `backend-targeted.patch`)

The targeted backend patch is relative to the working tree at task start, so it separates this task's edits from the substantial pre-existing uncommitted changes.

## 10. Tests

| Suite | Result |
|---|---|
| TypeScript: `npm run typecheck` | PASS |
| Frontend: Node test runner | PASS — 35 tests |
| Relevant backend/algorithm suite | FAIL — 203 passed, 1 pre-existing error, 204 total |
| Camera/authorization focused suite | PASS — 29 tests |
| Permissions | PASS — role policy, cookie-authenticated create/delete, denial, protected deletion |

Remaining error: `test_live_vehicle_detector_forwards_configured_imgsz` expects `backend.main.COLLISION_RAW_VEHICLE_CONFIDENCE_FLOOR`, which is absent. The same error was reproduced using the saved pre-change backend. It reflects the broader detector integration mismatch described in section 1. A new raw-detection threshold was not invented to make this test pass. The two pre-existing camera-health errors were fixed by restoring the expected diagnostics.

Tests used disposable SQLite and disabled PostgreSQL connections. No database-reset scripts or PostgreSQL integration mutations were run. Logs are in this directory; `pre-existing-failures.txt` records the comparison with the original working tree.

## 11. Production Safety

- **Models changed: NO.**
- **Thresholds changed: NO.**
- **Phase 8C changed: NO.**
- **Validation datasets changed: NO.**
- **Database credentials changed: NO.**
- **PostgreSQL configuration changed: NO.**
- The protected model and validation paths received no edits. Trained models were read only. Existing validation artifacts and operational records were preserved.
- No running backend service was replaced or restarted. The revised code needs a normal backend restart to take effect there.

## 12. Verdict

**PARTIALLY_FIXED**

The requested alarm, capture, and permission changes are implemented and their focused tests pass. The actual RTSP component benchmark confirms much fresher decoded frames. Completion of full validation still requires an interactive browser check, end-to-end camera-to-browser timing, and resolution of the pre-existing mismatch between the documented multi-stage detector and the active backend integration. The latter was documented rather than repaired through an unvalidated algorithm replacement.
