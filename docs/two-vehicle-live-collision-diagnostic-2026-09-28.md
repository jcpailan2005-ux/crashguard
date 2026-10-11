# Two-Vehicle Collision Capture Result

**No `confirmed_crash` was recorded after baseline 3547 through the final diagnostic observation 9949.** The exact decision failures are captured, but the physical collision participants and contact window cannot be established from observation-local detections alone. Analyzing was already active before the reproduction baseline; it is not evidence that impact was observed.

## Preserved capture

- Baseline observation: **3547**, `2026-09-28T23:19:59.417931`.
- Final observation: **9949**, `2026-09-28T23:27:07.055884`.
- Post-baseline observations: **591 recorded decisions**, OBS **3620?9949**. The first 71 end at 5810 and contain every candidate, streak change, and evaluated pair; the following 520 decisions are all ignored. The full span is a capture envelope, not a proven physical-event boundary.
- First post-baseline decision: `2026-09-28T23:20:10.041568`.
- Full preserved JSONL count: **863 records**, **2,105,917 bytes**; no malformed lines. The earlier 343-record snapshot is retained as an intermediate copy.
- Dropped records before: **16**. Dropped records after: **16**, no increase in the preserved post-baseline window. Write errors: **0**. All **591 post-baseline records** are marked complete.
- Run: `e45af5de2f1a466db95088addfc45a8c`; Bago CCTV `CAM-30960048ED`.
- Complete diagnostic file was preserved after shutdown in [full post-capture JSONL](../backend/validation/live_collision_diagnostics/preserved-full-20260928-postcapture/observations.jsonl), with [manifest](../backend/validation/live_collision_diagnostics/preserved-full-20260928-postcapture/manifest.json). The [earlier 343-record snapshot](../backend/validation/live_collision_diagnostics/preserved-20260928-232231/observations.jsonl) remains unchanged.
- Full JSONL SHA-256: `940aa0ab5f5d3e293e99b1e50db901fe1c5b8b2f93bf41ad9f810a0cafb5f390`. Earlier snapshot SHA-256: `cee504b5395f232ce9fcee07f6be4fae4b569ba90445f58467eaebcf584ef475`.
- The original live JSONL was not overwritten or truncated. Its final record predates the diagnostics-OFF backend restart. There is no later ON session in the checked process.

Times above are local Asia/Manila (UTC+08:00); raw timestamps lack a timezone suffix. Epoch decision/inference fields were used for interval calculations. Captured-frame sequence gaps are not themselves dropped diagnostic records. Calls failing before a decision boundary are not logged by this diagnostic.

[Detailed evidence appendix](two-vehicle-live-collision-evidence-2026-09-28.md) contains the first 71 post-baseline decisions, including every candidate, reset, and evaluated pair. The remaining 520 decisions are described below and are preserved line by line in the full JSONL. The appendix is a derived report, not a new telemetry system.

## Capture completeness check

The initial analysis used an intermediate snapshot ending at OBS 5810. A later read of the original JSONL after the diagnostics-OFF restart found **520 additional, previously unanalyzed records**, OBS 5833?9949. A complete copy was made before revising this report. Those 520 records are all `ignored`, `observation_qualified=false`, streak `0 ? 0`, action `UNCHANGED`, with zero accepted vehicles, zero evaluated pairs, `telemetry_complete=true`, cumulative drops 16, and write errors 0. Thus the original candidate, pair, and reset findings are unchanged, but the earlier 71-record count was incomplete as a full post-baseline count. The earlier 343-record snapshot remains an auditable intermediate artifact, not the final capture boundary.

The user's latest message says the complete reproduction has ended, but provides no synchronized clock markers that separate physical PRE_COLLISION, APPROACH, CONTACT, POST_COLLISION, and AFTERMATH phases. The full JSONL still contains no pixels or persistent identities. Those phase and participant limits therefore remain.

## Participants

**PERSISTENT_PARTICIPANT_IDENTITY_NOT_AVAILABLE**

PARTICIPANT_A: the actual physical participant cannot be uniquely assigned. Motorcycle-class proposals provide a plausible observation-local vehicle description, not tracked identity. Motorcycle proposals occur in OBS 3620, 3778, 3839, 3917, 3997, 4022, 4093, and 4348. At least one motorcycle is ultimately accepted in each of those observations. Two motorcycles are accepted at 3839; the data cannot identify which, if either, is the actual colliding vehicle.

PARTICIPANT_B: **PARTICIPANT_IDENTITY_UNDETERMINED**. Car proposals occur at 3620, 3839, 4022, and 4348. They are rejected below 0.40 at 3620 (0.337297), 3839 (0.317228), and 4348 (0.322116). At 4022 a car at 0.271769 is rejected in pass 0, then accepted by the existing pass-1 extraction threshold of 0.15. This is existing production behavior, not a threshold change made during this task. The second motorcycle at 3839 is an alternative observation-local detection, not automatically participant B.

Both actual participants detected: **UNKNOWN**, not established. Both actual participants accepted: **UNKNOWN**, not established. These cannot honestly be reduced to YES/NO. Two observation-local vehicles are accepted at 3839 and 4022; that does not identify the physical participants.

Persistent identity available: **NO**. No conclusion about an individual vehicle changing class, disappearing physically, or maintaining identity across frames is supported. Motorcycle detections cease after 4348 in this envelope, but the reason and correspondence to the physical participant are unknown.

Representative exact failure-observation boxes are below; all classes, confidences, boxes, passes and rejection reasons appear in the appendix. Box format here is raw `[x1,y1,x2,y2]`:

| Observation | Class | Confidence | Raw bbox | Accepted | Reason |
|---|---|---|---|---|---|
| 3620 | motorcycle | 0.6458120942 | [659.87939453125,415.5119323730469,896.974609375,669.86669921875] | YES | none |
| 3620 | car | 0.3372968137 | [566.9822387695312,379.01025390625,942.6421508789062,570.8321533203125] | NO | below_vehicle_confidence, threshold 0.40 |
| 4420, pass 0 and pass 1 | other_class | 0.4826793969 | [998.4481201171875,239.29833984375,1075.2803955078125,341.97808837890625] | NO | class_not_vehicle |
| 4420, pass 0 and pass 1 | person | 0.3743331432 | [375.36181640625,352.3791198730469,1278.5648193359375,669.49462890625] | NO | class_not_vehicle |

At 4420 neither detector pass returns a vehicle-class proposal. This supports `no_vehicle_detected` for that observation, not identification of which real participant was missed.

## Collision Interaction

**PHYSICAL_CONTACT_NOT_DIRECTLY_PROVABLE_FROM_TELEMETRY**

Interaction window: **UNDETERMINED** within the post-baseline envelope. The user confirms the complete sequence was shown, but there are no synchronized physical phase markers, pixels, tracked identities, or contact labels in this JSONL.

| Physical phase | Supported observation mapping | Participant A/B availability |
|---|---|---|
| PRE_COLLISION | Not identifiable; 3547 is only the user-provided baseline | UNKNOWN / UNKNOWN |
| APPROACH | Not identifiable | UNKNOWN / UNKNOWN |
| COLLISION/INTERACTION | Not identifiable; 3839 and 4022 are proximity passes, not proven contact | UNKNOWN / UNKNOWN |
| POST_COLLISION | Not identifiable | UNKNOWN / UNKNOWN |
| AFTERMATH | Not identifiable from scores/boxes alone | UNKNOWN / UNKNOWN |

Physical contact directly provable: **NO**. Likely actual pair evaluated: **UNDETERMINED**. No static frame is substituted for impact.

## Every evaluated pair

Exactly **two pairs** were evaluated in the full 591-observation envelope. Both pass the production OR condition: IoU ? 0.08 **or** normalized edge distance ? 0.05. No temporal pair score or physical-contact score is recorded or used here. Boxes below are `[x,y,width,height]`.

| OBS / local time | Vehicle 0 | Vehicle 1 | IoU | Edge distance / scale / normalized | Result | Attribution |
|---|---|---|---|---|---|---|
| 3839 / 23:20:19.464352 | motorcycle 0.7802813053; [672.5455322265625,488.3734130859375,247.79638671875,229.9443359375] | motorcycle 0.4561566114; [918.5928955078125,304.7529602050781,258.407470703125,410.7926940917969] | 0.002441590 < 0.08 | 0 / 410.792694092 / 0 ? 0.05 | PASS via distance | UNDETERMINED |
| 4022 / 23:20:31.380793 | motorcycle 0.3592699766; [691.0401611328125,508.0972900390625,267.417236328125,208.014404296875] | car 0.2717687190; [596.58251953125,487.5682373046875,357.4659423828125,162.932861328125] | 0.490123595 ? 0.08 | 0 / 357.465942383 / 0 ? 0.05 | PASS via both | UNDETERMINED |

At 3839 the car proposal is rejected, and production instead evaluates the two accepted motorcycles. This establishes which classes were paired, but does **not** establish a wrong pair or unrelated vehicles. At 4022 both vehicles are accepted on the existing retry pass. All other observations have fewer than two accepted vehicles and no evaluated pair. No failed evaluated proximity pair was captured.

## Analyzing

Reached: **YES, production candidate state**. Exact browser rendering was not independently observed because browser automation was unavailable.

First candidate in the whole preserved session: **3243**, `23:19:36.461946`, before baseline. Baseline 3547 is itself `candidate` with streak 1 ? 2. First post-baseline candidate: **3620**, `23:20:10.041568`, score **0.9971217513**, good quality, valid scene, one accepted motorcycle, qualified YES, streak **2 ? 1**, RESET due to expiry, final rejection `temporal_not_verified`. There is no evaluated pair at 3620.

The existing UI in `components/live-camera.tsx` displays ?Analyzing potential collision...? when `latestResult.finalDecision` is `candidate` or `verifying`. Production supplied `candidate` here because the qualifying frame had not reached temporal confirmation. Analyzing does not require that a two-vehicle physical interaction was established. The effective case threshold is **0.90**, UI threshold **0.80**. No pair-classifier score is invented.

## Streak

Required: **3 consecutive qualified observations within 5.0 seconds**, using the decision-window timestamps. Maximum after baseline: **2**. Resets: **6**, of which four are window expiry, one below-case-threshold, and one no-vehicle reset.

| OBS | Local time | Score | Qualified | Streak | Action | Actual reset reason |
|---|---|---|---|---|---|---|
| 3547 (baseline) | 23:19:59.417931 | 0.993782818 | YES | 1 ? 2 | INCREMENT | none |
| 3620 | 23:20:10.041568 | 0.997121751 | YES | 2 ? 1 | RESET | temporal_window_expired |
| 3778 | 23:20:14.357950 | 0.683715940 | NO | 1 ? 0 | RESET | below_case_threshold |
| 3839 | 23:20:19.464352 | 0.999501467 | YES | 0 ? 1 | START | none |
| 3917 | 23:20:24.957596 | 0.999039948 | YES | 1 ? 1 | RESET | temporal_window_expired |
| 3997 | 23:20:26.706501 | 0.957409978 | YES | 1 ? 2 | INCREMENT | none |
| 4022 | 23:20:31.380793 | 0.987033725 | YES | 2 ? 2 | RESET | temporal_window_expired |
| 4093 | 23:20:50.971614 | 0.999884605 | YES | 2 ? 1 | RESET | temporal_window_expired |
| 4348 | 23:20:53.625708 | 0.998201013 | YES | 1 ? 2 | INCREMENT | none |
| 4420 | 23:20:55.755720 | 0.913120925 | NO | 2 ? 0 | RESET | no_vehicle_detected |

All remaining **582** observations, 4451?9949, remain unqualified, streak 0 ? 0, `UNCHANGED`, final decision `ignored`. The first 62 (through 5810) are listed individually in the detailed appendix. The later 520 (5833?9949) are complete JSONL records: all have zero accepted vehicles, no evaluated pairs, and dropped-record count 16. No intervening decision is omitted from the full preserved file.

First reset after baseline: **3620**, already candidate, qualified YES. Both earlier hits expire; the current qualifying hit leaves one. First subsequent reset after that candidate: **3778**, classifier **0.683715940 < 0.90**, causing 1 ? 0 despite good quality and one accepted vehicle.

At **4022**, proximity passes and the frame qualifies, but the 3917 hit is **6.423198 seconds** old and is pruned. The 3997 and 4022 hits remain, leaving 2 rather than 3. At **4420**, the classifier passes (**0.913120925 ? 0.90**) and quality/scene pass, but there are zero accepted vehicles: qualification fails and resets 2 ? 0. Proximity is not a streak qualification gate; one accepted vehicle is sufficient for the production qualifier.

## Confirmation

confirmed_crash: **NO in all 591 preserved post-baseline decisions**.

Confirmation observation: **NONE**.

Confirmation classification: **NOT_CONFIRMED**. No true-pair or wrong-pair confirmation occurred in these records. The seven candidates and 584 ignored decisions are not operational confirmations. Pre-baseline decisions are excluded from this reproduction result.

## Earliest Failure

The earliest failure for the **actual physical collision** cannot be assigned without participant/phase identity. The earliest observed production obstacles after baseline are at **3620** (`2026-09-28T23:20:10.041568`), before the later pair-qualified observations:

1. A motorcycle proposal is accepted; a car proposal is rejected below vehicle confidence (0.337297 < 0.40). These cannot be equated to physical A/B with certainty.
2. Only one accepted vehicle remains. No pair is evaluated, so current-frame interaction is false. This independently prevents confirmed-crash interaction evidence, but does not fail the production frame qualifier.
3. Frame quality, classifier, nonzero vehicle count and scene validity pass; the observation qualifies.
4. Earlier hits expire from the five-second window, changing 2 ? 1; temporal confirmation is unavailable.
5. Final decision is `candidate`, not confirmed.

For the concrete pair-qualified observation **4022**, pair geometry and all frame qualifier gates pass. **Window expiry is the exact confirmation-preventing condition**, with 2 ? 2 rather than 2 ? 3. For **3778**, classifier failure precedes the streak reset. For **4420**, no returned vehicle-class proposal precedes the streak reset; the alarm is not the failed stage.

Observed failure classification: **MULTIPLE_FAILURES** across production observations (acceptance/pair availability, classifier failure, expiry, and no vehicles). This is not proof that each failure concerned the true colliding participants. A root cause attributed specifically to PARTICIPANT_A or PARTICIPANT_B is unsupported.

## Evidence Type

**UNDETERMINED**. Strong scores were already present before the user-provided baseline. The highest post-baseline candidate score (0.999884605 at 4093) has only one accepted motorcycle and no pair. It cannot establish actual interaction, aftermath, or unrelated geometry. Detection interpretation: **COLLISION_CANDIDATE_ONLY**, without physical attribution.

## Cadence

Classification: **CONTRIBUTING_FACTOR** to recorded temporal nonconfirmation; **UNKNOWN** as a cause of missing the actual physical contact phase.

Across the first 71 observations containing all candidates/resets/pairs, telemetry start-to-start intervals range **0.386757?19.489980 seconds**, median **1.335878 seconds**. Inference durations range **381.881?19,357.720 ms**, median **1,330.981 ms**. Largest start-to-start gap is **4093 ? 4348: 19.489980 s**. Largest decision-to-decision gap is **4022 ? 4093: 19.482450 s**. These measures differ because an observation starts before its inference finishes.

| OBS | Start-to-start interval s | Inference ms |
|---|---|---|
| 3620 | 4.935052 | 10489.122 |
| 3778 | 10.614139 | 4196.626 |
| 3839 | 4.216131 | 5082.920 |
| 3917 | 5.273517 | 5303.859 |
| 3997 | 5.502001 | 1551.255 |
| 4022 | 1.653486 | 4568.556 |
| 4093 | 4.804004 | 19357.720 |
| 4348 | 19.489980 | 2521.201 |
| 4420 | 2.635596 | 2018.823 |

Window expiry is explicitly recorded, so elapsed decision timing demonstrably removes qualifying hits. This is not a generic FPS diagnosis. CPU/GPU contention, inference slowdown cause, and whether contact occurred between analyzed frames are not established. The largest gap **during impact** cannot be computed because impact itself cannot be localized.

## Operational Incident

Fresh incident from a captured confirmed crash: **NOT_REACHED**. Duplicate suppressed: **UNKNOWN / not reached for a confirmed event**. No post-baseline decision through 9949 is `duplicate_active_case`. Per scope, no operational database or incident investigation was performed because confirmation did not occur. Existing unrelated or pre-baseline incidents are not claimed absent.

## Alarm

Expected: **NO for this unconfirmed reproduction**.

Triggered: **NOT_REACHED** in the requested confirmed-crash chain.

Audio attempted: **NOT_REACHED** in that chain.

Result: **ALARM_NOT_EXPECTED_BECAUSE_COLLISION_NOT_CONFIRMED**.

This does not assert that no unrelated browser audio played. No alarm was manually triggered, changed, or diagnosed as broken; no conditional alarm investigation was warranted.

## Why The Two-Vehicle Collision Did Or Did Not Confirm

The captured production decisions never accumulate three qualified hits inside their five-second window. Both proximity-passing observations therefore remain candidates. Other observations also fail the classifier or have no accepted vehicles; many have only one accepted vehicle. The exact reset sequence is established, but there is insufficient evidence to claim which observations represent the physical contact, whether the evaluated pair is the true pair, or whether the strongest scores reflect aftermath.

## Recommended Fix Category

**INSUFFICIENT_EVIDENCE ? DESIGN ONLY, DO NOT IMPLEMENT.**

First correlate this preserved capture with an already available, time-aligned view of the original reproduction if one exists; no new event is requested. The smallest engineering investigation supported by these records is why inference/decision timing causes the existing five-second window to expire, especially at pair-qualified OBS 4022. Do not lower thresholds, extend the streak window, add grace frames, or introduce tracking/pair verification on this evidence alone. Physical participant attribution must precede a detector or pair-specific fix.

## Shutdown and live-system verification

Analysis completed before shutdown. The backend was restarted using the documented project virtual-environment launcher, preserving the current backend environment and changing `LIVE_COLLISION_DIAGNOSTICS` to `0`. The new port-8010 listener is PID **24572**; its environment verifies **DIAGNOSTICS = OFF**. Backend `/api/health` and frontend `/login` both returned **HTTP 200** afterward. Both preserved JSONL snapshots have verified SHA-256 hashes; the complete 863-record copy is the authoritative post-capture evidence.

Full live preview/scanning recovery: **VERIFIED BY USER** after shutdown. The user confirmed “ONLINE, LIVE, SCANNING, and moving preview restored” in the existing authenticated Live Monitor. Browser automation remains unavailable, so this is explicitly manual verification alongside the independent HTTP health checks. No new reproduction was requested. The original live JSONL remained at **2,105,917 bytes** across two post-shutdown checks; both the intermediate and complete preserved copies remain unchanged.

## Safety

Production code changed: **NO**. Collision logic changed: **NO**. Models changed: **NO**. Thresholds changed: **NO**. Tracking added: **NO**. Pair verification added: **NO**. Alarm behavior changed: **NO**. Database/schema changed by this analysis: **NO**. Authentication changed: **NO**. Camera settings changed: **NO**. Source B changed: **NO**. Phase 8C changed: **NO**. Training performed: **NO**. Diagnostics: **OFF**, verified after analysis.

Normal application activity may write its existing storage; no direct database mutations were made by this analysis. Evidence/report files are the only written artifacts apart from the existing runtime logs and telemetry. The earlier activation restart's environment-equivalence limitation remains recorded in the preparation history below.

## Verdict

**INSUFFICIENT_DIAGNOSTIC_DATA**

This verdict concerns proof of the actual two-vehicle collision and participant identity. The captured production nonconfirmation and six reset actions are established; the exact physical-event root cause is not.

---

## Preparation history (historical state; superseded by the result above)

# Two-Vehicle Live Collision Diagnostic

## Capture readiness — verified

After reconnecting, the user confirmed Bago CCTV ONLINE, LIVE, SCANNING, and a moving preview. The existing JSONL is now receiving authoritative live decision records. No diagnostic wiring correction or production change was needed.

- Output: `C:\Users\Lenovo\Desktop\MyCrushguard\backend\validation\live_collision_diagnostics\observations.jsonl`.
- Backend listener: PID **24544**, expected project working directory, **DIAGNOSTICS = ON** verified from its process environment.
- Run ID: `e45af5de2f1a466db95088addfc45a8c`.
- Camera ID: `CAM-30960048ED`; a read-only query of existing camera metadata maps this ID to **Bago CCTV**. All 270 records in the full validation snapshot belong to this one camera and run.
- Growth: **518,105 bytes / 232 records → 607,184 bytes / 270 records → 613,343 bytes / 272 records**.
- Session's first recorded observation: **1**, timestamp `2026-09-28T23:15:53.664698` (local Asia/Manila time).
- Pre-reproduction baseline/start marker: observation **3547**, timestamp `2026-09-28T23:19:59.417931`. This marks readiness, not physical collision onset. The user has not yet reproduced the event.
- Latest decision age at final check: **2.021 seconds**. In the full validation snapshot, latest decision age was **0.930 seconds**, and source frame receive age was **4.124 seconds**. Epoch fields establish freshness independently of the timezone-naive timestamp string.
- Multiple distinct latest observations: **3329, 3363, 3389, 3437, 3547**. These are captured-frame sequence numbers, not consecutive decision counters or persistent vehicle identities.
- All 270 records inspected in full parsed as JSON, had distinct observation sequences, `decision_boundary_reached=true`, and `telemetry_complete=true`.
- Every inspected record populated `streak_before`, `streak_after`, `streak_action`, `observation_qualified`, `qualification_failures`, `reset_reasons`, and `required_consecutive_hits`. Empty reason arrays are valid when no reason applies. No collision-state interpretation was performed.
- Source verification: `LiveCameraMonitor._analyze_current_frame` has the existing `live_collision_diagnostics.observe` decorator. Its existing decision emit supplies the real result payload and hit window. The wrapper submits only records that reached the decision boundary. Current records therefore establish connectivity to that production path, rather than merely camera decoding or preview activity.
- Privacy checks across the full snapshot found no sensitive key names, RTSP URLs, bearer/basic token patterns, JWT patterns, cookie/password/token assignment patterns, or exact configured camera username/password matches. The serializer uses explicit diagnostic fields; no credentials, RTSP secrets, tokens, or cookies were found in the inspected JSONL. This is a check of captured records, not a guarantee about arbitrary future data or other log files.
- Integrity limitation: cumulative dropped-record values in the session were **0, 2, 16**. The count remained **16** throughout readiness sampling and the latest five records; write errors remained **0**. Earlier dropped records cannot be reconstructed or treated as negative observations. Future event analysis must inspect counter changes and must not claim an uninterrupted trace across missing data.

**READY: existing bounded telemetry is active and writing. Diagnostics remain ON.** No collision analysis or fixes have been performed. Await the full reproduction and the user's `REPRODUCTION FINISHED` message before analysis.

## Earlier capture preparation — historical

The user manually verified an authenticated dispatcher session, Bago CCTV ONLINE, LIVE, SCANNING, and a moving/current preview before this preparation. The prior browser-tool failure remains an automation environment failure.

Diagnostics were verified OFF in the original backend listener (PID 14384). No existing `observations.jsonl*` files were present.

The documented opt-in environment variable `LIVE_COLLISION_DIAGNOSTICS=1` was used. Replaying the original process-reported Python command with its environment failed at startup with `ModuleNotFoundError: No module named 'psycopg'`. The backend was then restored with the documented project virtual-environment Python launcher, `-m uvicorn backend.main:app --host 127.0.0.1 --port 8010`, using the task shell environment plus the diagnostic opt-in. The original process environment was not retained after the failed launch; exact equivalence of process-only overrides is therefore not verified. No configuration files, thresholds, or production code were edited.

The restored backend listener (PID 24544) returned HTTP 200 from `/api/health`; its process environment confirms **DIAGNOSTICS = ON**.

Existing bounded output path:

`backend/validation/live_collision_diagnostics/observations.jsonl`

At the latest preparation check, this file had not yet been created. Backend restart clears in-memory camera workers. The user was asked to reopen Bago CCTV through the existing authenticated Live Monitor and resume its existing connection if needed. No protected request was bypassed or synthetic identity created.

At that earlier check, capture was not yet verified. The readiness verification above supersedes this pending state.

Run ID at that earlier check: pending first telemetry record; now recorded above.

Reproduction started: NO.

Analysis: NOT STARTED. Awaiting capture readiness and then the user's `REPRODUCTION FINISHED` message.

Diagnostics currently: ON; intentionally not disabled during preparation.

## Scope

No production source, model, threshold, streak rule, tracking, pair verification, RTSP/FPS setting, camera configuration, authentication, permissions, database/schema, dispatcher/responder behavior, alarm behavior, Source B, Phase 8C, or training data was edited. No incident or alarm was manually triggered. Normal runtime activity is not asserted to leave application storage unchanged.

The final participant, interaction, streak, incident, and conditional alarm findings will be recorded only after reproduction and analysis. No outcome verdict is assigned to an event that has not yet been reproduced.
