# Phase 4 Stage B — Tapo RTSP Recovery

**RTSP access is recovered for the active “Bago CCTV” record, but the camera view is not eligible for dataset capture.** The active saved record supplies an authenticated `/stream2` URL that opens and decodes native-size frames. Stage A instead used a separate global Tapo profile with a different password. A controlled same-host, same-path, same-options comparison opens with the active record credential and fails with the global-profile credential. The fresh still shows a current Tapo timestamp over traffic imagery carrying an older 2016 timestamp, consistent with a displayed replay. No long capture or training began.

Evidence: [active-record probe](../backend/validation/tapo_rtsp_stage_b_20261001/record_probe.json), [controlled comparison](../backend/validation/tapo_rtsp_stage_b_20261001/controlled_comparison.json), [minimal diagnostic still](../backend/data/tapo_domain_pilot/review/stage_b_diagnostic_still_20261001.jpg), and [visual assessment](../backend/validation/tapo_rtsp_stage_b_20261001/view_assessment.json). These records contain no password, credential-bearing RTSP URL or authentication header.

## Stage A Baseline

Host reachable: **YES** at TCP port 554. Global-profile `stream1` opened: **NO**. Global-profile `stream2` opened: **NO**. Decoded frame: **NO**. Stage A's [report](tapo-domain-detector-phase4-2026-10-01.md) and [preflight](../backend/validation/tapo_detector_phase4_stage_a_20261001/preflight.json) remain unchanged.

## Camera Record

The intended active camera is legacy ID **`CAM-30960048ED`**, name **Bago CCTV**, mirrored as PostgreSQL ID `ea01e0fa-f60d-43ad-b8f1-4bf370820d25`. Host: **192.168.1.17**. Port: **554**. Configured path: **`/stream2`**. SQLite `isActive=true`, `detectionEnabled=true`, status `monitoring`; PostgreSQL mirror reports `ONLINE` and detection enabled. Those are saved status fields, not proof by themselves of a current worker connection. The active record's `cameraIp` is null, so `resolve_saved_camera_stream` selects its `streamUrl` directly. Its username and password are present in that URL and load successfully through the backend's normal saved-record path; no decryption step is used for this record. Secret exposed in this report/artifacts: **NO**.

The separate `backend/local_camera_config.json` profile targets the same host but selects `stream1`. Its username matches the record's after URL decoding; its password **does not**. Both credentials were compared only in memory. The active record URL's userinfo is canonically percent-encoded. The saved record is the effective source for the active camera; the global profile is used by camera-IP/default Tapo connection paths. No credential value or hash is recorded.

## Duplicate Configuration

Physical-host camera records: **one logical Bago CCTV camera**. It appears once in the legacy SQLite camera table and once as the matching PostgreSQL mirror; their saved stream references are byte-identical. A separate global Tapo profile targets the same host, with a different stream selection and password. That profile is **not another camera record**. The apparent duplication explains Stage A's mismatch: it probed the global profile, while the active saved Bago record uses its own authenticated URL. No record was deleted or changed.

## Network

Host reachable: **YES**. TCP 554: **OPEN** during the bounded active-record probe. Host/TCP reachability alone did not establish RTSP in Stage A; successful authenticated frame decode below establishes it for the active saved record. Earlier September TCP timeouts are historical observations, not the current state.

## RTSP Probe

Using the same TCP transport, FFmpeg `nobuffer`/`max_delay=500000`, one decoder thread and five-second open/read limits as the production worker:

| Credential source and known path | Open | Frame decoded |
|---|---|---|
| Active Bago record, `/stream2` | **YES** | **YES** |
| Same active-record credential, `/stream1` | **YES** | **YES** |
| Separate global-profile credential, `/stream2` | **NO** | **NO** |

Each was one bounded probe, not a credential search. This isolates the profile credential difference at the same host/path/options; it also rules out a blanket `/stream1` or `/stream2` path failure at the time tested. The low-level RTSP response code for the failed global-profile attempt was not exposed by OpenCV, so no literal `401` status is claimed.

## Failure Layer

**SAVED_CAMERA_ACCOUNT_INVALID for the separate global Tapo profile**, established by controlled comparison: the profile credential loads, has canonical URL encoding, differs from the active record's credential, and cannot open `/stream2` where the active record credential succeeds. The active Bago record's account is **valid for both known paths**. This is a configuration divergence, not a proven CrashGuard URL-construction bug. The exact server-side reason for rejecting the global-profile attempt was not separately obtained, so no password history or camera-side setting is inferred.

## Authentication

Server authentication reached: **YES for the successful active-record connection**, which opened and decoded. Saved active-record credential accepted: **YES**. Global-profile credential accepted: **NO** under the controlled probe. Credential loading problem: **NO evidence**; both sources loaded in memory and the active record worked. URL encoding problem: **NO evidence**; record encoding is canonical and synthetic ordinary/reserved-character tests pass. No replacement credential was guessed, reset or written.

## Production-vs-Diagnostic Path

Stage A versus active production record: **NO, they were not the same effective source**. Stage A read the global profile (`stream1`, different password) and used OpenCV without the worker's FFmpeg transport options/decoder-thread setting. The live worker resolves the active Bago record's `cameraIp=null` to its saved credential-bearing `streamUrl` (`/stream2`) and uses TCP, `nobuffer`, `max_delay=500000`, one decoder thread and five-second timeouts. Stage B reproduced those production options and successfully decoded the record stream. The controlled comparison holds worker options and path constant, identifying the credential-source difference as the blocker in Stage A. No production code was changed to make the probe pass.

## Existing Worker

A local backend Uvicorn process was present. The legacy record's saved status was `monitoring`, but that status alone does not establish that a worker is currently connected. A local socket snapshot found **no established connection to 192.168.1.17:554** at that instant. Existing live worker: **UNKNOWN** without in-process state. Competing RTSP connection: **not observed; cannot be ruled out at other instants**. Sequential Stage B probes succeeded, so a camera session limit did not block this test. No process was terminated.

## Repair

Production camera connection code repair required: **NO** on this evidence. The active saved record connects with unchanged code/option semantics. The separate global Tapo profile contains a different password and fails, so **that profile needs a legitimate account update through the normal camera settings workflow before it is used as a direct/default Tapo source**; its existing value was preserved. The active Bago record does **not** require a credential update. More decisively for Stage C, the physical Tapo view must be returned to **direct real-road observation**; a working RTSP session to replayed imagery is not eligible for detector training. Neither camera configuration nor physical view was changed in this task.

## Tests

**26 passed**: five new synthetic connection-contract tests plus relevant existing camera security, health, role-permission and repair-security tests. Synthetic checks cover ordinary password construction, reserved URL characters without double encoding, `stream1`, `stream2`, missing credentials, saved-record versus global-profile selection, and redacted labels. Existing repair-security tests cover sanitized failure/validation output; the real failed global-profile probe records only sanitized open/decode booleans. No real password appears in tests. The [Stage B diagnostic scripts](../backend/validation/tapo_rtsp_stage_b_20261001/) do not write to camera records or production code.

## Frame Decode

Successful: **YES**, five nonempty frames from the active saved `/stream2` record. Resolution: **1280×720**. Camera-reported FPS: **15.0**, which is metadata, not measured continuous capture rate. The five immediate reads span approximately **0.031 seconds** of host receive time and may include decoder buffering; no sustained RTSP cadence is claimed. A single JPEG still was saved solely for view verification, with its SHA-256 in the probe record.

## Physical View Verification

**SCREEN_REPLAY_OR_DISPLAY_VIEW**. The diagnostic still has a current Tapo overlay reading **2026-10-01 02:54:55 AM** at the top and an embedded **2016/03/18** timestamp at lower right within the traffic imagery. This nested historical-video marking and display-like framing indicate Tapo is viewing a displayed/recorded traffic scene, rather than directly observing current road traffic. The assessment is assistant visual diagnosis, not an independently human-verified annotation. This frame is **ineligible for the native Tapo vehicle dataset**, even though RTSP authentication and decoding work. No request to stage or replay a collision was made.

## Dataset Capture

**NOT STARTED.** Only the permitted minimal diagnostic still was saved. No 45–60 minute recording, frame sampling, calibration set or training corpus was created. Source B and Phase 8C were not substituted.

## Training

**NOT RUN.** No model was loaded for training or replaced. The human-label and leakage gates remain unmet.

## Production Changes

Collision logic: **UNCHANGED**. Detector: **UNCHANGED**. Thresholds: **UNCHANGED**. Pair logic: **UNCHANGED**. Alarm: **UNCHANGED**. Camera connection plumbing changed: **NONE**. Camera records/global profile changed: **NONE**. The known production pair-safety defect remains unresolved.

## Protected Assets

Stage B extended the Stage A snapshot to [263 protected paths](../backend/validation/tapo_rtsp_stage_b_20261001/protected_before.json), covering Source B, Phase 8C, Phase 1–3, Stage A artifacts, production models, collision code and alarm. [Final rehash](../backend/validation/tapo_rtsp_stage_b_20261001/protection_audit.json): **zero changed**. Secrets were not copied into the protection manifest.

## Stage B Verdict

**STREAM_DECODES_BUT_VIEW_NOT_ELIGIBLE**

Stop before Stage C capture. The active authenticated stream works, but a fresh Tapo frame must show the **current physical road directly** before any native dataset recording. The global-profile credential divergence should be resolved through the authorized settings workflow if that profile is to be used; it does not prevent the active Bago record from decoding.
