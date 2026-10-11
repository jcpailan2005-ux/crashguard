# Stage 2B — Physical Browser Alignment Validation

## Camera

Bago CCTV: **PASS** saved-record connection preflight. RTSP: **PASS**. Frame decode: **PASS**. Resolution: **1280×720**. Camera-reported FPS: **15**, not measured delivery FPS.

Probe time: **2026-10-02 00:18:52 Asia/Manila**. Used the authorized saved Bago record, not the global Tapo profile. One frame decoded in memory; no image retained, inference started, camera record changed or credentials exposed. [Preflight evidence](../backend/validation/live_cctv_implementation_stage2b_20261002/preflight.json).

## Test Media

Protected collision media used: **NO**. Normal cleared traffic shown for this validation: **NO**.

The existing cleared `MITRA-T1-D6` original was located for manual fallback. Physical playback/positioning was not verified. No Source B, Phase 8C or collision replay was opened.

## Browser

Browser opened by this validation: **NO**. Automation: **FAIL — AUTOMATION_ENVIRONMENT_FAILURE**.

Exact initialization error: `Mcp error -32602: js: codex/sandbox-state-meta: missing field sandboxPolicy`. The browser tool failed before navigation. This does **not** establish a UI defect.

Local listeners were present on frontend port 3000 and backend port 8010. The existing [dispatcher view](http://localhost:3000/dispatcher/live) is the manual fallback. A manual setup question was sent; no manual observation was available for this report. The [fallback checklist](../backend/validation/live_cctv_implementation_stage2b_20261002/manual-check.md) identifies cleared media, attribution and the exact outstanding checks. No authentication bypass or production changes were attempted.

## Exact-Frame Validation

Image/box same packet: **NOT TESTED in browser**; focused deterministic test passes. Sequence identity visible: **NOT OBSERVED**. Analyzed-frame panel visibility remains unverified.

## Coordinate Alignment

Desktop: **NOT TESTED**. Resized: **NOT TESTED**. Clipping: **NOT TESTED visually**. Deterministic geometry tests pass, but cannot substitute for physical/browser inspection.

## Moving Vehicle Alignment

Cars: **NOT_OBSERVED**. Motorcycles: **NOT_OBSERVED**. Temporal mismatch observed: **NOT ASSESSED**. Persistent offset observed: **NOT ASSESSED**. Same physical vehicle across analyzed packets: **NOT ASSESSED**. Attachment to newer raw preview: **NOT ASSESSED visually**.

## Expiry

Old boxes expire: **NOT TESTED in browser**. Empty packet clears previous boxes: **NOT_OBSERVED**. Duplicate-fetch lifetime: **NOT TESTED in browser**. Focused deterministic expiry/duplicate/empty-packet checks pass; no live expiry measurement is claimed.

## Raw Preview

Smooth/usable: **NOT OBSERVED**. Blocked by inference: **NOT ASSESSED**. UI source age, model-end-to-display latency, packet cadence and browser responsiveness: **NOT MEASURED**. RTSP decode alone does not prove browser preview usability.

## Collision / Alarm

Collision behavior changed: **NO**. Incident created by this validation: **NO**. Alarm triggered by this validation: **NO**. The preflight only reads the saved record and decodes; tests mock models/persistence. Existing running application activity was not audited, so no claim is made about unrelated concurrent events.

Known pair-safety regression: **FAIL**. Expected: **FAIL**. Fresh direct invocation returned the existing `AssertionError: 'confirmed_crash' == 'confirmed_crash'` (exit 1).

## Code Changes

**NONE** to production code. Only this report and new [Stage 2B validation artifacts](../backend/validation/live_cctv_implementation_stage2b_20261002/) were added. Eight scoped production/alarm files match their preflight SHA-256 hashes; this is a scoped check, not a new full-repository audit. Stage 2 implementation and prior reports/evidence were not edited. No reproducible alignment defect was observed that would justify a repair.

## Tests

Focused Stage 2 backend: **9 passed**. Focused Stage 2 frontend: **8 passed**. Direct known pair-safety assertion: **FAIL as expected**. [Exit records](../backend/validation/live_cctv_implementation_stage2b_20261002/checks.json) and logs are retained. No broad suite, model training or expensive benchmark was rerun.

## Stage 2B Verdict

**STAGE2_BROWSER_ENVIRONMENT_BLOCKED**

Camera availability is freshly established. Physical/browser alignment, responsive display and live expiry remain unverified because browser automation cannot initialize and manual observations are unavailable. Stage 2 remains `STAGE2_ALIGNMENT_UNVERIFIED`. No Stage 3 work began.

STAGE 2B VALIDATION COMPLETE — SEND RESULTS BEFORE STAGE 3
