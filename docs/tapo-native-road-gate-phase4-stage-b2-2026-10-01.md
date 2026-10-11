# Phase 4 Stage B2 — Native Road Eligibility Gate

**The active Bago CCTV stream still shows historical traffic footage inside the Tapo view. Stage C dataset capture is ineligible.** This is an assistant visual assessment of four fresh diagnostic frames, not a human annotation of road provenance. The [sample manifest](../backend/validation/tapo_native_road_gate_stage_b2_20261001/sample_manifest.json) records the host receive times, dimensions, and SHA-256 hashes; the [four diagnostic PNGs](../backend/data/tapo_domain_pilot/review/native_view_gate_20261001/) are kept outside all training splits.

## Stage B Baseline

Authenticated Bago RTSP: **PASS**. Frame decode: **PASS**. Resolution: **1280×720**. Previous view: **SCREEN_REPLAY_OR_DISPLAY_VIEW**. Stage C eligible before this test: **NO**. Stage B's [report](tapo-rtsp-recovery-phase4-stage-b-2026-10-01.md) and diagnostic still documented a current Tapo clock over traffic footage marked 2016/03/18.

## Camera Source

Camera ID: **`CAM-30960048ED`**. Camera name: **Bago CCTV**. Host: **192.168.1.17**. Port: **554**. Stream path: **`/stream2`**. Authorized saved record: **YES** (active SQLite camera record, read only). Credential source: **that saved record's `streamUrl`, held in memory only**. Global profile used: **NO**. Secret exposed in the new report, manifest, scripts, or decoder output: **NO**. The record's `cameraIp` is null, so its saved URL is also the backend's normal source-selection path; no camera record or profile was edited.

## Verification Sample

Authenticated RTSP open: **PASS**. Video packets and nonempty decoded frames: **PASS**; 207 frames were decoded in the bounded reader, and only **four** lossless PNGs were saved. Each is **1280×720**. Camera-reported FPS: **15.0** (source metadata, not a measured capture-rate claim). Saved frame offsets: **0, 4, 8, and 12 seconds**; first-to-last host elapsed span: **11.984 seconds**.

| Frame | Host receive time (UTC) | Diagnostic file |
|---|---|---|
| 00 | 2026-09-30 19:05:26.793 | [frame_00.png](../backend/data/tapo_domain_pilot/review/native_view_gate_20261001/frame_00.png) |
| 01 | 2026-09-30 19:05:30.812 | [frame_01.png](../backend/data/tapo_domain_pilot/review/native_view_gate_20261001/frame_01.png) |
| 02 | 2026-09-30 19:05:34.859 | [frame_02.png](../backend/data/tapo_domain_pilot/review/native_view_gate_20261001/frame_02.png) |
| 03 | 2026-09-30 19:05:38.792 | [frame_03.png](../backend/data/tapo_domain_pilot/review/native_view_gate_20261001/frame_03.png) |

These timestamps are host receive times, not independently verified camera clock or source-frame capture times. The four file hashes differ. This was a provenance sample, not a training session or collision analysis.

## Timestamp Consistency

Classification: **STALE_OR_EMBEDDED_OLD_TIMESTAMP**. The upper Tapo overlay displays the current local date, **2026-10-01**, at approximately **03:05:23, 03:05:29, 03:05:33, and 03:05:37 AM**. Each frame also visibly contains **2016/03/18** at the lower right of the traffic imagery. The current Tapo overlay is broadly consistent with the UTC+08:00 host receive date/time, but it does not make the older footage current. The old embedded traffic date is the decisive failure evidence; no exact source-clock synchronization is claimed.

## Display / Replay Evidence

Monitor/display boundary: **AMBIGUOUS**; a distinct bezel is not needed for this decision and is not asserted. Old embedded timestamp: **YES, 2016/03/18 in every frame**. Player UI or playback controls: **NO visible evidence**. Other replay evidence: the older timestamp persists within the moving road imagery underneath a separate, current Tapo overlay. This repeats the nested-time pattern seen in Stage B's still. The visible framing may be display-like, but the classification does not depend on that weaker cue.

## Physical Road Evidence

Direct roadway: **NO positive evidence** that the Tapo lens observes the current physical road. A roadway and vehicles are visible **within the historical traffic footage**. Natural temporal motion: **YES within that footage**; vehicle positions change plausibly and the background remains coherent across the sample. This does not establish live physical provenance. Nested display/replay content: **YES**, evidenced by the persistent old traffic-footage date beneath the present Tapo clock; the physical screen boundary itself remains ambiguous. No obvious repeating short motion cycle was established from this brief sample, and none is required to reject the view.

## View Classification

**SCREEN_REPLAY_OR_DISPLAY_VIEW**. The simultaneously visible current camera clock and 2016 traffic-video date rule out treating these frames as verified direct observation of today's road. This is stronger evidence than the presence or motion of cars.

## Global Profile

Credential mismatch remains: **YES**, as established in Stage B; neither credential is reproduced here. Required for Stage C: **NO**, if Stage C uses the authorized active Bago saved record. This gate opened that record directly without the global profile. The older standalone [RTSP recorder](../backend/validation/cctv_runtime_audit/capture_rtsp.py) also selects a saved camera `streamUrl`, rather than the global profile, although it is limited to 180 seconds and writes into a protected validation directory and must not be invoked unchanged for Stage C. Action required before Stage C: **restore and reverify a direct current physical-road view, then use a new bounded pilot recorder targeting the pilot raw/metadata directories with the same saved-record source**. The mismatched global profile should be corrected through the legitimate settings workflow only if that separate profile is later used; no automatic credential copy was made.

`GLOBAL_PROFILE_BLOCKS_STAGE_C = NO` as a credential/source dependency. The current view itself blocks Stage C.

## Stage C Capture Eligibility

`STAGE_C_CAPTURE_ELIGIBLE = NO`. Reason: the four fresh frames still contain a historical 2016 traffic-video timestamp within the Tapo image. Stop before any long dataset capture. Correct the physical camera view and repeat this eligibility gate before issuing Stage C capture work.

## Dataset

Long capture: **NOT STARTED**. Training frames: **NONE**. Annotations: **NONE**. The four diagnostic frames remain in `review/native_view_gate_20261001/` and are **not** assigned to training, calibration, validation, or test.

## Training

**NOT RUN**. No weights or training configuration changed.

## Production

Collision logic: **UNCHANGED**. Detector: **UNCHANGED**. Thresholds: **UNCHANGED**. Pair integration: **NONE**. Alarm: **UNCHANGED**. No collision replay or inference was run.

## Protected Assets

The [before snapshot](../backend/validation/tapo_native_road_gate_stage_b2_20261001/protected_before.json) covers **276 paths** from Source B, Phase 8C, Phases 1–3, Stage A, Stage B, production model/collision/threshold/pair/alarm code, and the prior evidence. The [final rehash](../backend/validation/tapo_native_road_gate_stage_b2_20261001/protection_audit.json) reports **zero changed protected paths**. New Stage B2 scripts, manifest, and four diagnostic frames are additions outside that protected set.

## Stage B2 Verdict

**SCREEN_REPLAY_STILL_PRESENT**

The physical Tapo view must be corrected to show the current road directly. Stage C remains stopped.
