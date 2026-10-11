# Live Two-Vehicle Collision Fix

## Current Architecture Before Fix

The current authenticated RTSP path is `backend/main.py`: `api_start_camera_monitor` → `start_live_camera_monitor` → `LiveCameraMonitor.start` → `_capture_loop` (`cv2.VideoCapture.read`, newest native BGR frame/sequence) → `_detection_loop` → `analyze_current_frame` → bounded `_analyze_current_frame`. The decision function runs frame-quality analysis, `model.predict(..., imgsz=640)`, full-frame `classify_crash_frame`, separate `detect_vehicle_boxes` with a conditional low-confidence retry, ROI filtering, and `crash_like_vehicle_interaction` over accepted observation-local boxes. Its `pre_temporal_positive` requires good quality, full-frame accident probability at/above the case threshold, and at least one accepted in-ROI vehicle. `self.hit_window` counts consecutive **scene-level** positives in the five-second window; it has no vehicle or pair ID. On the current observation, any accepted pair with IoU ≥0.08 or normalized edge gap ≤0.05 supplies `motion_valid`. Three scene hits plus that current-pair proximity cause `temporal_verified`, then `evaluate_crash_case_decision` can return `confirmed_crash` subject to active-case/cooldown gates. A three-hit sequence without current proximity can become `possible_crash_aftermath` review. The classifier is full-frame in this RTSP path; `classify_collision_pair_regions` and the separate tracker, logical-continuity, and temporal-verifier services are **not called by this worker**. Vehicle proposal indices in diagnostics are observation-local, not persistent IDs.

`confirmed_crash` goes through `persist_sqlite_crash_case` → `backend/services/operational_detection.py:persist_operational_detection` → `backend/phase3/service.py:create_ai_incident`. PostgreSQL serializes by camera key, deduplicates by detector-event ID or an active camera review, creates one incident, review case, alert, and dispatcher notifications in a transaction. `GET /api/v3/notifications` and `/incidents` supply the dispatcher UI. `LiveCameraMonitor.snapshot_status().latestResult` is served by authenticated camera status and consumed by `components/live-camera.tsx` and `components/cctv-monitor-workspace.tsx`; `lib/incident-alarm-contract.ts:LiveAlarmTracker` requires a fresh created incident ID and `finalDecision=confirmed_crash` before `lib/accident-alert.ts:playAccidentAlert` calls HTML audio playback or WebAudio fallback. Candidate/verifying results display “Analyzing potential collision...” but are not alarm eligible. Separately, `components/dispatcher-alerts-view.tsx` polls operational notifications/incidents, arms audio on a button click, and currently loops a siren for **any active Priority-1 alert count**, including old unread alerts and assignment declines. That behavior is not the requested one-play-per-fresh-confirmed-incident contract.

Answers to the current-path questions: persistent tracking **NO**; vehicle identity across frames **NO**; pair identity across observations **NO**; 3-hit owner **scene-level observations**; tracking/temporal-pair services invoked **NO**; different pairs can contribute to the same streak **YES**; an unrelated pair can supply the final proximity gate **YES, by code construction**; classifier input **full native BGR frame**; analyzing banner **candidate/verifying final decision**, not contact; confirmed crash **three scene positives within five seconds plus any accepted current-frame proximal pair, good quality, valid scene, case/cooldown eligibility**; live alarm playback **only on a fresh created confirmed-crash result as seen by `LiveAlarmTracker`, subject to user audio preference and browser playback permission**, while the dispatcher siren has the independent count-based loop described above.

## Root Causes

| Layer | Classification | Evidence and limit |
|---|---|---|
| Detector proposal recall | ARCHITECTURAL LIMITATION | Protected Source B primary approach raw recall is P-A 1/19 and P-B 2/22; the latest seven synchronized roadway frames do not identify A/B and cannot establish a new live detector failure. |
| Detection acceptance | ARCHITECTURAL LIMITATION | Source B accepted recall is P-A 1/19, P-B 1/22; threshold lowering was unsafe in prior studies. Latest physical run lacks labeled A/B. |
| Participant continuity | DEFECT CONFIRMED | Current RTSP worker has no persistent vehicle identity; separate offline services are not wired into it. |
| Pair attribution | DEFECT CONFIRMED | Current streak is scene-wide and current proximity can come from any pair. Protected Source B shows unrelated-pair verification risk in the offline service composition too. |
| Interaction verification | DEFECT CONFIRMED | RTSP `motion_valid` is instantaneous box proximity, not measured approach/contact/post-interaction. |
| Temporal logic | ARCHITECTURAL LIMITATION | Three hits/five seconds are scene-level; observed 2/3 streaks do not establish that these constants, rather than sparse/misattributed evidence, are the root cause. |
| Incident persistence | CURRENTLY CORRECT for the audited contract | PostgreSQL transaction and unique event identity prevent ordinary duplicate incident insertion; existing integration tests exercise this. Full live end-to-end validation remains outstanding. |
| Frontend alarm trigger | DEFECT CONFIRMED | Live result tracker is confirmation-gated; dispatcher view instead loops based on unread active Priority-1 count, not a new confirmed incident identity. |
| Audio playback | ARCHITECTURAL LIMITATION | Dispatcher audio starts muted until the user arms it; `play()` rejection is swallowed. The one-shot live helper has a WebAudio fallback, but browser autoplay cannot be guaranteed without an interaction/unlock. |

The synchronized 2026-09-29 reproduction is **insufficient** to label physical A/B or contact: 105 saved post-baseline frames show people/room, and only seven show a roadway replay. Its 113 metadata decisions include no `confirmed_crash`; the missing frame is ignored observation 4041 before the roadway. It cannot by itself prove which production layer missed the actual physical event. Source B and other protected studies are separate offline evidence; they cannot be treated as a successful production replay.

## Safe Collision Contract Before Coding

`NORMAL` has no event evidence. `CANDIDATE` is a frame-level suspicion with no alarm. `ANALYZING` means repeated suspicion, not confirmation. `PAIR_TRACKED` requires two actually observed, accepted vehicles with conservative, unambiguous persistent identities and a stable unordered pair key; detector misses may preserve identity briefly but contribute **no new observations**. `COLLISION_VERIFIED` requires the same pair's measured approach/contact-compatible transition and immediate post-interaction evidence; whole-frame classifier score and geometric proximity are supporting signals only. `CONFIRMED_CRASH` requires verified pair evidence plus the existing three-hit/five-second policy and fresh operational persistence. `AFTERMATH` may support an already established pair interaction or remain a review candidate; it never manufactures a collision from a damaged/stopped vehicle alone. A different pair cannot inherit hits, classifier evidence cannot be assigned to a pair without attribution, identities expire on stale/ambiguous handoff, and replay/camera changes reset pair state. Exactly one fresh PostgreSQL incident ID makes one dispatcher alarm eligible; candidate, aftermath, duplicate and old unread alerts do not.

The existing ByteTrack/logical-continuity/temporal services are research implementations, not a validated production drop-in: the Source B architecture study found no correct true-pair confirmation and a known unrelated queue-pair false confirmation in several configurations. Detector-domain adaptation remains necessary for that protected physical pair. The safe next coding scope is limited to changes with independent evidence and regression tests; threshold/window relaxation and untested service wiring are excluded.

## Changes Implemented

No backend collision decision, detector, tracker, model, temporal parameter, or database code was changed. In `lib/incident-alarm-contract.ts`, live alarm eligibility now requires an explicit fresh operational incident ID, an explicit `incidentCreated` flag, and `confirmed_crash`; a review-case ID or legacy `caseCreated` cannot substitute. A dispatcher incident tracker accepts only a new `NEW_CRASH_REVIEW` notification joined to a newly created `temporal_collision` incident and consumes each incident ID once. `components/dispatcher-alarm-monitor.tsx` owns the five-second operational feed poll, arming control, and one-sound queue in the persistent dispatcher shell; `components/dispatcher-alerts-view.tsx` no longer owns playback. Assignment declines, old unread cases, duplicate polling, and aftermath reviews remain visible but silent.

In `lib/accident-alert.ts`, successful MP3 playback returns without also starting the fallback buzzer merely because duration metadata is unavailable. A user gesture can arm a reusable WebAudio context; blocked fallback playback reports failure. `components/live-camera.tsx` exposes an Arm Alarm Sound control and surfaces playback errors. `components/cctv-monitor-workspace.tsx` surfaces an audio failure instead of silently ignoring it. These changes affect alarm eligibility and failure visibility; they do not assert that a collision was detected or that browser speakers were heard in a live session. Existing unrelated working-tree edits in these components are outside this fix.

## Pair-Safety Contract

The contract above is a **required release condition, not current production behavior**. The RTSP worker still has no cross-observation pair identity. A deterministic invocation of the real `_analyze_current_frame` with a high scene classifier score on each frame, one vehicle on frame 1, a different lone vehicle on frame 2, and a proximal pair only on frame 3 produced `candidate`, `candidate`, `confirmed_crash` with pair counts `0, 0, 1` and streaks `1, 2, 3`. Thus changing pairs or even absent pairs can feed the existing streak. The pair-safety contract is **not satisfied**. Inserting the current research tracker/temporal composition is not a safe fix: Source B has no simultaneously usable true-participant identities in its assessable approach, and an unrelated queued pair can falsely score 0.863. A pair-specific confirmation change needs independently validated participant proposals and negative-pair regression evidence. No false-positive suppression was obtained by disabling confirmation.

## Post-Collision Verification

The current `possible_crash_aftermath` branch creates a review candidate when scene-level hits accumulate without current-pair proximity. It is not proof of observed impact. The live worker has no explicit same-pair approach → interaction → immediate aftermath verification or bounded post-interaction state. Those positive requirements remain **unimplemented and unvalidated**. The latest seven saved roadway frames cannot identify the two physical participants or prove contact, so they cannot serve as a positive regression sequence.

## Alarm Contract

The frontend now requests audio only for a fresh operational `confirmed_crash` incident, deduplicated by stable incident ID within the dispatcher layout tracker. Candidate, verifying/analyzing, aftermath, case-only persistence, old incident replay, and assignment decline do not make an alarm eligible. The dispatcher must first arm browser audio with a user click during normal use. Once armed, a new confirmed incident automatically attempts sound without opening a page or clicking the notification. MP3 success produces one playback attempt and no simultaneous fallback; a blocked or subsequently failed MP3 may use the armed WebAudio buzzer, and failure is shown in the UI. The dispatcher checks for an incident/notification join every five seconds. Cross-browser-tab exactly-once delivery and actual audible output on this machine have **not** been verified; browser audio permissions and device output remain external conditions. A new incident arriving while the dispatcher siren is muted is displayed, but no delayed siren is promised after arming.

## Tests

Frontend: `npm run typecheck` passed; `node --experimental-strip-types --test frontend-tests/*.test.ts` passed **40/40**. New/updated tests cover fresh confirmed incident eligibility, candidate/aftermath/case-only exclusions, dispatcher old/new/duplicate/decline filtering, persistent dispatcher-shell placement and automatic polling, and successful MP3 playback without a second buzzer. They do not emulate real browser audio hardware.

Backend: the existing targeted collision-decision, temporal-verifier, live-diagnostic, and camera-security modules passed through `backend/scripts/run_isolated_tests.py` with the operational `DATABASE_URL` removed from that child test process. The PostgreSQL repair-integration test correctly refused to run without an explicitly isolated `crashguard_test` database; it was **not** run against operational data. Existing persistence tests and code were reviewed, not claimed as a fresh end-to-end incident creation result.

Collision regression: the direct production-decision sequence above **reproduced the unsafe scene-streak behavior**; it is not a passing safety regression. No valid labeled positive physical pair from the latest synchronized run exists for a pass claim. Pair regression: protected offline Source B/architecture studies were read as evidence, with no retraining, annotation changes, or production service wiring. Alarm regression: frontend contract and playback-unit tests passed. Security regression: camera-security targeted tests passed and no authentication, camera authorization, stream ticket, credential logging, or database schema code was changed.

## Negative Cases

| Case | Current production collision result | Alarm-contract result |
|---|---|---|
| Parked close vehicles | **FAIL / unproven safe**: proximity plus scene hits can qualify; no approach proof | No alarm unless backend falsely confirms and creates an incident |
| Congestion or queued vehicles | **FAIL**: protected offline services already show a wrong queued-pair confirmation; live RTSP lacks stronger pair attribution | Same limitation |
| Damaged vehicle / aftermath only | **FAIL / unproven safe**: no explicit observed-interaction prerequisite for temporal confirmation | `possible_crash_aftermath` alone is silent |
| Fallen motorcycle alone | **Unproven safe** for all sequences; one vehicle alone cannot satisfy the current final-pair gate | Candidate/review alone is silent |
| High classifier score on unrelated pair | **FAIL**: full-frame score and any current proximal pair can combine | A false backend confirmation can still trigger the alarm |
| Three observations from changing pairs | **FAIL**, directly reproduced with pair counts 0/0/1 | Alarm requires fresh incident, but cannot repair a false backend decision |
| Repeated/old incident | Backend persistence is designed to deduplicate; isolated PostgreSQL end-to-end test not run here | **PASS** in frontend identity/freshness tests |
| Brief miss and pair expiry | **NOT APPLICABLE to current RTSP path**: no persistent pair identity exists | No alarm without fresh confirmation |

## Performance

No production backend inference code changed, so there is **no after-change backend timing measurement**. The last preserved normal-feed synchronized session with diagnostics ON reported median snapshot copy **2.407 ms**, asynchronous save/hash **55.387 ms**, median inference **789.074 ms**, and analyzed-observation interval **0.793 s** over its last 100 of 151 checked observations. Those are historical same-code diagnostic measurements, not a controlled OFF/ON comparison or current camera validation. Capture FPS, frame age, candidate-processing cost, tracking cost, and pair-verification cost after this frontend-only change are **not measured**; RTSP tracking/pair-verification services are not invoked, so no new cost was introduced. No 500 ms wait or JPEG capture step was added.

## Remaining Limitations

The primary collision requirement remains unsatisfied. The live RTSP worker has observation-local vehicle boxes, scene-wide three-hit ownership, a full-frame classifier, and an instantaneous proximity gate. The current protected Source B approach does not supply enough actual A/B proposals to establish reliable identities, and research pair-service compositions can still confirm an unrelated queue pair. The latest physical-camera capture lacks labeled true-pair/contact frames and had one dropped diagnostic frame plus two manifest-replacement errors; it cannot validate a fix. A separately authorized, clean detector-domain dataset and held-out physical-pair evaluation are needed before a production pair verifier can be selected. No controlled physical reproduction is requested now, and **READY** is not warranted.

The alarm path is unit-tested but has no live authenticated browser playback or dispatcher receipt verification in this turn. If the backend falsely confirms a wrong pair, the correctly gated frontend will still alarm for that false incident. Per-surface deduplication does not establish global exactly-once audio across independent browser tabs.

## Production Behavior Changed

**YES, frontend alarm behavior only.** The dispatcher no longer loops on old unread Priority-1 count; its persistent shell automatically polls and attempts one sound for each fresh confirmed operational incident while armed. The live alarm gate requires an explicit fresh confirmed incident instead of case-only persistence. Browser arming and playback errors are visible. **NO** backend collision, model, threshold, 3-hit/five-second, camera, persistence, or authorization behavior changed.

## Protected Assets

| Asset or behavior | Changed? |
|---|---|
| Source B and its annotations | NO |
| Phase 8C and its annotations | NO |
| Models/weights | NO |
| Training performed | NO |
| Thresholds or temporal rules | NO |
| Database schema | NO |
| Authentication | NO |

## Final Verdict

**ALARM_PATH_FIXED_COLLISION_LIMITATION_REMAINS**

This verdict describes the tested frontend contract change, not a validated audible alarm or a reliable physical two-vehicle collision detector. The backend cannot yet assign three qualifying hits and post-interaction evidence to the actual same pair, and Source B participant recall makes safe deployment of the research pair services unjustified. Detector domain adaptation is still required before a true-pair recovery claim can be tested.

## Dispatcher alarm follow-up: automatic attempt across routes

The user clarified that the dispatcher must receive an automatic alarm attempt for a **new confirmed accident** without opening New Alerts, refreshing, acknowledging, or clicking the incident. The earlier alarm implementation did not meet this: its 15-second notification/incident poll and armed audio element existed only in `DispatcherAlertsView`. Navigating to Live Monitor or any other dispatcher route unmounted the listener and lost its arming state. This was an independent alarm-path defect, although it did **not** cause the silence in the preserved Bago reproduction: observations after baseline 2861 contained no `confirmed_crash` and no new confirmed incident. The roadway streak reached 2/3 at 5060 and reset at 5095 when the classifier score fell to 0.3641 and the five-second window expired. Which physical A/B evidence failed first remains unknowable from the seven unlabeled roadway frames.

`components/dispatcher-alarm-monitor.tsx` now lives in the persistent dispatcher `RoleLayout` header, above every dispatcher route. It polls authenticated operational notifications and incidents every five seconds, with one request in flight, and immediately polls again when a hidden tab becomes visible. A joined new `NEW_CRASH_REVIEW` notification and fresh `temporal_collision` incident supplies the stable ID; candidates, aftermath, old incidents, repeats, and assignment declines stay silent. The one-time Arm Siren action occurs during normal dispatcher use, before any crash. Once armed, no accident-time interaction is needed. Browser restrictions still prevent any web app from guaranteeing sound before user activation or while the browser/OS blocks output; an error is visible if playback fails. MP3 rejection falls back to the armed WebAudio buzzer, and a later MP3 media error also attempts that fallback. The audio file exists and is nonempty (148,800 bytes). Only one playback queue exists in this dispatcher layout; the dispatcher live-camera surfaces skip their separate local playback to avoid duplicate sound in one tab. Arming lasts across dispatcher route changes but, by browser policy, must be repeated after a full page reload or new tab.

The New Alerts page remains a read/triage view and no longer owns dispatcher alarm playback. `frontend-tests/ui-contract.test.ts` checks this placement, polling, and arming; the frontend suite passes **40/40**, and TypeScript type checking passes. This is code-level validation of the automatic attempt path, not proof of physical audible output or a repaired collision detector. The final verdict above remains unchanged.
