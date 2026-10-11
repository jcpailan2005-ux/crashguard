# Live Accident Alarm Audit and Fix

## Required Behavior

Actual collision → analyzing candidate → verified collision → `confirmed_crash` → one fresh PostgreSQL incident → dispatcher notification → one automatic siren attempt while armed. Candidate or analyzing text alone cannot trigger the emergency alarm.

## Current First Broken Stage

**COLLISION_NOT_CONFIRMED** for the preserved Bago reproduction. After baseline observation 2861, neither 113 metadata decisions nor 112 saved decision/frame pairs recorded `confirmed_crash` or a fresh confirmed incident. No true-event alarm was eligible. The physical A/B pair and contact are not identifiable in the seven saved roadway frames, so the **earliest failure within the true physical interaction is not determinable**. This classification names the first verified broken stage in the operational chain, not a proven detector or pair root cause. A separately verified alarm-path weakness was that, before the earlier dispatcher-shell fix, polling and arming were mounted only in New Alerts; the current shell code no longer has that route dependency.

## Current Production Pipeline

`backend/main.py:LiveCameraMonitor._capture_loop` reads decoded RTSP BGR frames into the newest-frame slot. `_detection_loop` calls `analyze_current_frame` / `_analyze_current_frame` in a bounded inference path. The latter checks frame quality; calls YOLO `model.predict` and `detect_vehicle_boxes`; filters vehicle boxes through the ROI; classifies the **full frame** with `classify_crash_frame`; and evaluates instantaneous accepted-box proximity with `crash_like_vehicle_interaction`. A qualifying scene observation requires good frame quality, classifier accident probability at or above the case threshold, at least one accepted in-ROI vehicle, and a valid scene. It appends that Boolean to `self.hit_window`, expires entries older than five seconds, and counts consecutive positive observations backward. The count is **scene-wide**, with no physical-pair key. `evaluate_crash_case_decision` may return `confirmed_crash` only when three hits are ready, the current observation has a proximal vehicle pair, other quality/scene gates pass, and active-case/cooldown gates allow it. With sufficient scene hits but no current proximity it may return `possible_crash_aftermath` for review.

The backend sets a candidate/verifying result and message `Analyzing potential collision...` before that confirmation. `components/live-camera.tsx` also displays the banner for `finalDecision` candidate/verifying. The banner therefore means **NO, `confirmed_crash` has not occurred**. It does not identify A/B, prove contact, or imply incident creation.

When case creation is authorized, `backend/main.py:persist_sqlite_crash_case` delegates to `backend/services/operational_detection.py:persist_operational_detection`, which maps `confirmed_crash` to `temporal_collision`, then to `backend/phase3/service.py:create_ai_incident`. PostgreSQL transactionally deduplicates by detector event/camera pending case and writes an incident, review case, alert, and dispatcher `NEW_CRASH_REVIEW` notifications. Authenticated `GET /api/v3/incidents` and `/notifications` return these to the dispatcher. `components/dispatcher-alarm-monitor.tsx` is mounted by the persistent `RoleLayout` for the dispatcher, polls both endpoints every five seconds, joins a `NEW_CRASH_REVIEW` notification to a fresh `temporal_collision` incident through `DispatcherIncidentAlarmTracker`, and schedules one audio attempt by incident ID. `lib/accident-alert.ts:playAccidentAlertWithResult` resets playback position, sets volume to 1, unmutes, awaits `audio.play()`, and uses the armed WebAudio buzzer if MP3 playback rejects. Candidate and aftermath incidents do not pass this eligibility gate.

## Analyzing State

Condition: `finalDecision` candidate/verifying, reflecting a qualifying or accumulating **scene** observation below verified confirmation. Required streak: **3 consecutive positives in 5 seconds**, plus current accepted-pair proximity for temporal confirmation. A low classifier score, no accepted vehicle, invalid scene/quality, or temporal expiry can interrupt/reset the streak. `confirmed_crash`: **NO** for the analyzed Bago reproduction.

| Observation | Local decision time | View | Accepted vehicles / evaluated pairs | Classifier | Qualification | Streak | Gate/action |
|---:|---|---|---:|---:|---|---|---|
| 4890 | 04:23 before roadway | Room/setup | 1 / 0 | 0.9923 | YES | 0→1 | Candidate start |
| 4947 | Before roadway | Room/setup | 2 / 1 unrelated proximal pair | 0.9987 | YES | 1→2 | Candidate increment |
| 4991 | Before roadway | Room/setup | 0 / 0 | 0.7520 | NO | 2→0 | Below case threshold, no vehicle, window expired |
| 5024 | 04:23:24.849170 | Roadway | 2 / 1 ambiguous, proximity failed | 0.9888 | YES | 0→1 | Candidate start |
| 5060 | 04:23:27.356663 | Roadway | 3 / 3 ambiguous, proximity failed | 0.9561 | YES | 1→2 | Candidate increment |
| 5095 | 04:23:30.120741 | Roadway | 1 / 0 | 0.3641 | NO | 2→0 | Classifier below case threshold; window expired |
| 5134 | 04:23:32.372812 | Roadway | 2 / 1 ambiguous, proximity failed | 0.3672 | NO | 0→0 | Below case threshold |
| 5167 | 04:23:35.274937 | Roadway | 4 / 6 ambiguous, proximity failed | 0.9996 | YES | 0→1 | Candidate start; all six pairs failed proximity |
| 5219 | 04:23:41.561188 | Roadway | 3 / 3 ambiguous, proximity failed | 0.6829 | NO | 1→0 | Below threshold; window expired |
| 5305 | 04:24:04.927974 | Roadway | 3 / 3 ambiguous, proximity failed | 0.8939 | NO | 0→0 | Below threshold; replay appears unchanged |

The preserved report provides exact timestamps for roadway rows and the complete diagnostic sequence. The room/setup timestamps above are intentionally approximate because they are not needed to label the roadway collision and are not restated as invented precision. There is one dropped synchronized frame, observation 4041, before the roadway; its metadata decision was ignored with zero accepted vehicles. The two manifest-replacement write errors do not explain the recorded roadway streak reset. The recorded 5095 classifier/window reset is a downstream scene-level reason for **no confirmation**, not proof of which physical A/B gate failed first.

## Collision Confirmation

Result: **NO** in the preserved reproduction. Maximum post-baseline streak **2/3**; no `confirmed_crash`. Recorded roadway interruption: observation **5095**, classifier **0.3641** and five-second window expiry after 5024/5060. The physical participant proposal, acceptance, same-pair continuity, and contact cannot be measured from the seven unlabeled roadway frames. Inference gaps between saved roadway decisions range about 2.25–23.37 seconds, but cannot be assigned as the earliest true-event cause. Pair-safety limitation: **YES**. Current RTSP production counts scene positives without identity, so evidence from changing pairs can accumulate. A deterministic invocation previously produced candidate/candidate/`confirmed_crash` with pair counts 0/0/1 and streaks 1/2/3. No threshold, window, model, or pair rule was loosened in this task.

## Fresh Incident

Created for the preserved physical reproduction: **NO**. Incident identity, camera-linked created timestamp, and fresh/duplicate status: **NOT APPLICABLE** because no confirmation occurred. Deduplication: code transaction and existing tests cover detector-event/active-camera duplicate protection, but an isolated PostgreSQL integration suite was **not run** without an explicitly configured `crashguard_test` database. No fake incident was inserted into the operational database.

## Alarm Eligibility

Fresh incident recognized in controlled fixture: **YES**. One-time eligibility: **PASS**. `lib/dispatcher-alarm-delivery.ts:enqueueFreshDispatcherAlarms` is the production seam used by the monitor and fixture tests. A fresh confirmed incident schedules one callback; the same incident repeated schedules zero; a second incident schedules one new callback. Old, aftermath, assignment-decline, candidate/analyzing, and unarmed fixtures schedule zero. This is an independent alarm-subsystem proof, **not** a simulated physical collision or database write.

## Arm Siren

Implementation: `components/dispatcher-alarm-monitor.tsx` is mounted in `components/role-layout.tsx` for all dispatcher routes. `armed` is React state mirrored in `armedRef`; the monitor remains mounted across dispatcher route navigation. A full reload/new tab creates a new monitor and intentionally requires a new user gesture. `armAccidentAlertAudio` creates/resumes a reusable WebAudio context from the Arm Siren click. The MP3 element is initialized and preloaded, but browser policy does not guarantee that arming WebAudio also unlocks MP3; the armed buzzer is the fallback. The header visibly shows Arm siren/Siren armed/Alarm sounding or a blocked error. If a fresh incident arrives while unarmed, it displays that condition rather than silently treating it as played. Armed state across routes: **PASS by component placement and code test**. Browser activation on this authenticated device: **UNVERIFIED**. Additional click at accident time after arming: **NO**.

## Audio

Asset: **PASS for existence and delivery**. `public/alert-sound.mp3` is 148,800 bytes, has an MPEG frame-sync header, and `HEAD http://127.0.0.1:3000/alert-sound.mp3` returned **200**, `audio/mpeg`, `Content-Length: 148800`. Browser decoding was not exercised. Playback code sets volume **1**, `muted=false`, and `currentTime=0`, then calls and awaits `audio.play()`. The helper returns an MP3 or buzzer method; `NotAllowedError`, `NotSupportedError`, and `AbortError` are reduced to fixed safe categories without serializing arbitrary browser exception text. The dispatcher shows `ALARM_ELIGIBLE`, `ALARM_ATTEMPTED`, `PLAY_CALLED`, then `PLAY_RESOLVED` or `PLAY_REJECTED`. A late MP3 media error attempts the buzzer. No infinite retry loop exists.

Actual browser `play()` called for a fresh operational incident: **NO OBSERVATION AVAILABLE**. Controlled stub `play()` called: **YES, once**. Controlled stub result: **RESOLVED**. Controlled `NotAllowedError` with no available WebAudio fallback: **REJECTED and detectable**. Actual audible output physically verified: **NO — AUDIBLE_OUTPUT_REQUIRES_USER_DEVICE_VALIDATION**. `play()` resolving would establish an accepted browser playback request, not sound from speakers. The in-app authenticated browser connection was unavailable for this run; no browser playback claim is made.

## Fixes

- `lib/dispatcher-alarm-delivery.ts`: extracted the actual notification/incident-to-attempt queue boundary so it can be exercised with safe fixtures.
- `components/dispatcher-alarm-monitor.tsx`: uses that boundary and displays bounded, sanitized eligibility/attempt/playback status and failures; still polls independently of New Alerts and handles MP3 media error fallback.
- `lib/accident-alert.ts`: reports whether MP3 or WebAudio resolved, explicitly unmutes/sets volume, preserves MP3 failure category if fallback also fails, and prevents arbitrary exception text from reaching the UI.
- `frontend-tests/dispatcher-alarm-delivery.test.ts` and `frontend-tests/accident-alert.test.ts`: controlled fresh/duplicate/second/candidate/unarmed and play-resolution/rejection coverage.

## Tests

TypeScript: **PASS** (`npm run typecheck`). Frontend: **44/44 PASS** (`node --experimental-strip-types --test frontend-tests/*.test.ts`). Relevant backend collision/temporal/live-diagnostic/camera-security tests: **98/98 PASS**. Alarm: **controlled delivery and audio fixture cases PASS**; route persistence is covered by the UI contract test, not a mounted authenticated browser navigation. Isolated PostgreSQL operational integration: **SKIPPED**, because no explicit safe `crashguard_test` database was supplied. Browser/audio-device validation: **NOT RUN** because authenticated browser control was unavailable; local HTTP asset delivery was verified separately.

## Safety

Candidate sounds alarm: **NO**. Analyzing sounds alarm: **NO**. Fresh confirmed incident automatically schedules exactly one attempt while armed: **YES in controlled fixture**. Old/duplicate/aftermath/decline sound: **NO**. Collision thresholds changed: **NO**. Models changed: **NO**. Training: **NO**. Source B / Phase 8C / protected annotations changed: **NO**. Authentication/database schema/production records changed: **NO**.

## Remaining Collision Limitation

**PAIR_SAFETY_LIMITATION_REMAINS.** Scene-level hits, no persistent pair identity, and full-frame classification mean the live worker cannot prove that three qualifying observations belong to the same actual collision participants. Protected Source B evidence also found inadequate true-participant proposal/continuity and an unrelated queue pair that can falsely qualify in an offline research composition. The latest physical capture cannot identify the true pair. Alarm correctness cannot repair missed or false backend confirmation. A safe collision fix requires validated participant recall and pair-specific interaction evidence; this task did not weaken the detector or temporal gates to force an alarm.

## Verdict

**ALARM_PIPELINE_FIXED_DEVICE_AUDIO_VALIDATION_REQUIRED**

The independent controlled fresh-incident → automatic attempt path passes; actual browser playback and speaker audibility still require an authenticated, armed dispatcher device check. The analyzed physical event did **not** reach `confirmed_crash`, and safe collision confirmation remains a separate unresolved requirement. Do not request another collision reproduction on the basis of this alarm-only result.
