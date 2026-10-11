# Synchronized Physical-Pair Collision Result

## Capture

Baseline observation: **2861**, at 2026-09-29 04:20:58.271850 Asia/Manila. Baseline JSONL/frame counts: **179 / 179**.

Final observation: **5305**, at 2026-09-29 04:24:04.927974. Final JSONL/frame counts: **291 / 291**. Post-baseline synchronized observations: **112**. Session: `backend/validation/live_collision_diagnostics/physical_pair_capture_20260928T201746Z_1a6ef175/` (run `1a6ef175d2434d5abec86f2e9148557e`, Bago camera `CAM-30960048ED`). The bounded capture was stopped at 04:24:15; the original session files remain preserved.

Dropped frame records: **1**. Write errors: **2**. Both recorded errors occurred at observation 3990 and 4001, at the diagnostic `manifest_replace` stage: `PermissionError`, errno 13, WinError 5, “Permission denied.” The cause of that Windows denial is not established. Cross-checking the separate metadata-only diagnostic JSONL identified the missing synchronized frame as **observation 4041 at 04:22:16.695363**. Its decision was `ignored`, with zero accepted vehicles and an unchanged zero streak. These faults occurred after the baseline, before the roadway video appeared.

Evidence integrity: **FAIL for complete frame coverage; PASS for the 112 saved post-baseline pairs.** The separate metadata-only JSONL contains **113** post-baseline decisions for the same run, including the one missing frame's decision. Every saved synchronized row has its frame, matching SHA-256, shape, and decision metadata; there are no orphan frames. The JSONL, manifest, diagnostic error file, and launch logs have no RTSP URL, stream token, cookie, Authorization, Bearer, or password pattern. Access logging stayed OFF. The dropped frame was before the roadway replay, so it does not explain the absence of a visible collision frame during the seven saved roadway decisions.

## Physical Event

Participant A: **unidentified**. Participant B: **unidentified**. Physical contact visually provable: **NO — PHYSICAL_CONTACT_NOT_VISUALLY_PROVABLE**.

Post-baseline observations 2880 through 4991 show the physical camera pointed at people and the room, not the roadway video. The roadway replay first appears in saved observation **5024** at 04:23:24.849170. Only seven decision frames show it: 5024, 5060, 5095, 5134, 5167, 5219, and 5305. The gaps between these samples range from about 2.25 to 23.37 seconds. The replay's own displayed timestamp advances from about 04:23:22 to 04:23:41; the final decision frame at 04:24:04 still displays approximately 04:23:41. Vehicles are visible, but these seven images do not establish which two are the claimed collision participants, a clear contact instant, or a defensible approach → contact → aftermath sequence. A high classifier score is not a physical contact label.

Human annotation status for every roadway frame is below. `null` is an explicit **unlabeled** box, not a zero-area vehicle. Physical type and occlusion for A/B are likewise unknown. No vehicle was assigned A or B merely because production detected it.

| Observation | Decision time | Physical phase | A bbox/type/visibility | B bbox/type/visibility |
|---:|---|---|---|---|
| 5024 | 04:23:24.849170 | Roadway visible; event phase undetermined | null / unknown / unidentifiable | null / unknown / unidentifiable |
| 5060 | 04:23:27.356663 | Roadway visible; event phase undetermined | null / unknown / unidentifiable | null / unknown / unidentifiable |
| 5095 | 04:23:30.120741 | Roadway visible; event phase undetermined | null / unknown / unidentifiable | null / unknown / unidentifiable |
| 5134 | 04:23:32.372812 | Roadway visible; event phase undetermined | null / unknown / unidentifiable | null / unknown / unidentifiable |
| 5167 | 04:23:35.274937 | Roadway visible; event phase undetermined | null / unknown / unidentifiable | null / unknown / unidentifiable |
| 5219 | 04:23:41.561188 | Roadway visible; event phase undetermined | null / unknown / unidentifiable | null / unknown / unidentifiable |
| 5305 | 04:24:04.927974 | Roadway replay time appears unchanged from 5219 | null / unknown / unidentifiable | null / unknown / unidentifiable |

No pre-approach, approach, immediate pre-interaction, contact, immediate post-interaction, or aftermath frame can be reliably assigned to the **true physical A/B event** from this archive. The seven roadway frames are the full usable visual sample after the room/setup view, not seven verified collision phases.

## Participant A

Raw recall: **not computable (zero ground-truth A boxes)**. Accepted recall: **not computable**. Main failure: **physical identity and location cannot be established in the saved frames**. Proposal presence, class, confidence, IoU, acceptance, and rejection for A are therefore **AMBIGUOUS_MATCH / not assignable**, rather than fabricated yes/no values. By phase, both recall measures are undefined because no phase contains a labeled A opportunity.

## Participant B

Raw recall: **not computable (zero ground-truth B boxes)**. Accepted recall: **not computable**. Main failure: **physical identity and location cannot be established in the saved frames**. Proposal presence, class, confidence, IoU, acceptance, and rejection for B are **AMBIGUOUS_MATCH / not assignable**. By phase, both recall measures are undefined.

## Simultaneous Participants

Both raw simultaneous: **not computable**. Both accepted simultaneous: **not computable**. There are no labeled A/B opportunities; generic `vehicle_count` cannot substitute for physical-participant recall.

## True Pair

True A/B pair evaluated: **NO PROVEN TRUE-PAIR EVALUATION**. Observations: **none attributable to A/B**. Production evaluated **17 vehicle pairs** across the seven roadway frames (1, 3, 0, 1, 6, 3, 3 by observation); all are **AMBIGUOUS_PAIR** because A/B cannot be identified. None passed production's pair proximity gate. The one post-baseline evaluated pair before the roadway video, at observation **4947**, is an **UNRELATED_PAIR** in the room/setup view and passed proximity. Thus proven true-pair observations: **0**; proven unrelated-pair observations: **4947**; ambiguous-pair observations: **5024, 5060, 5134, 5167, 5219, 5305**. This classification does not imply the actual pair was absent; it means it cannot be matched from these frames.

## Production Decision

Maximum post-baseline streak: **2**, below the required **3**. `confirmed_crash`: **NO**. Confirmation observation: **none**. Confirmation classification: **NOT_CONFIRMED**. Neither the 112 synchronized rows nor the 113 metadata-only post-baseline decision records reported `confirmed_crash` or a fresh confirmed case.

The exact recorded sequence near the change from room/setup to roadway is:

| Observation | View | Accepted vehicles / evaluated pairs | Classifier score | Qualified | Streak before → after | Action / reset |
|---:|---|---:|---:|---|---|---|
| 4890 | Room/setup | 1 / 0 | 0.9923 | Yes | 0 → 1 | START; candidate analyzing |
| 4947 | Room/setup | 2 / 1 unrelated pair, proximity passed | 0.9987 | Yes | 1 → 2 | INCREMENT; candidate analyzing |
| 4991 | Room/setup | 0 / 0 | 0.7520 | No | 2 → 0 | RESET: below case threshold, no vehicle, temporal window expired |
| 5024 | Roadway | 2 / 1 ambiguous pair, proximity failed | 0.9888 | Yes | 0 → 1 | START; candidate analyzing |
| 5060 | Roadway | 3 / 3 ambiguous pairs, all proximity failed | 0.9561 | Yes | 1 → 2 | INCREMENT; candidate analyzing |
| 5095 | Roadway | 1 / 0 | 0.3641 | No | 2 → 0 | RESET: below case threshold and temporal window expired |
| 5134 | Roadway | 2 / 1 ambiguous pair, proximity failed | 0.3672 | No | 0 → 0 | UNCHANGED; below case threshold |
| 5167 | Roadway | 4 / 6 ambiguous pairs, all proximity failed | 0.9996 | Yes | 0 → 1 | START; candidate analyzing |
| 5219 | Roadway | 3 / 3 ambiguous pairs, all proximity failed | 0.6829 | No | 1 → 0 | RESET: below case threshold and temporal window expired |
| 5305 | Roadway | 3 / 3 ambiguous pairs, all proximity failed | 0.8939 | No | 0 → 0 | UNCHANGED; below case threshold |

“Analyzing potential collision...” corresponds to the `candidate_analyzing=true` candidate observations **4890, 4947, 5024, 5060, and 5167**. The first two are room/setup imagery, not the roadway interaction. The later three are roadway imagery, but cannot be attributed to a verified A/B interaction. Production `observation_qualified` and streak are scene-wide; they do not prove pair-specific continuity.

## Earliest True-Event Failure

Observation: **not determinable**. Phase: **not determinable**. Failure: **OTHER — true physical A/B identity and contact are not established in the synchronized images**. Evidence: the replay appears only in seven sparse saved decisions; the earlier 105 saved post-baseline decisions are room/setup imagery; the one unsaved frame is an `ignored` decision at 04:22:16 before the roadway; and no saved frame clearly shows contact. It would be unsound to call participant proposal, acceptance, pair attribution, classifier, or temporal logic the **earliest true-event failure** without knowing which vehicles were the participants. The production streak did reset at **5095** after two roadway candidates, with a failing classifier score and window expiry, but this is a downstream recorded scene-wide result, not an established cause for the true A/B event.

## Strongest Production Evidence

**UNDETERMINED.** The strongest roadway classifier score is **0.9996 at observation 5167**, where all six evaluated pairs failed proximity. The strongest scores at 4890/4947 were from room/setup imagery. Neither establishes actual interaction, immediate post-interaction, or aftermath for the physical pair.

## Detection Continuity

**DETECTION_CONTINUITY_INSUFFICIENT for the captured true-event evidence.** Only seven roadway decisions were archived over roughly 40 seconds, with no reliable A/B labels or contact frame. They cannot establish three conservative, pair-specific A+B hits within five seconds. This is an evidence-continuity finding, **not proof that the detector itself failed**; participant-specific detector recall remains unmeasurable.

## Alarm

Expected for true event: **NO — ALARM_NOT_EXPECTED_FOR_TRUE_EVENT**. Result: **no attributable true-pair confirmation or fresh confirmed incident in the post-baseline records; no true-event alarm path to trace**. Alarm behavior was not changed.

## Next Engineering Target

**INSUFFICIENT_EVIDENCE.** The saved decision frames do not identify the two physical vehicles or their contact, and capture was incomplete. A detector, acceptance, pair, or temporal change would be speculative from this archive. No fix was implemented.

## Safety

Production collision behavior changed: **NO**. Models changed: **NO**. Thresholds changed: **NO**. Temporal window changed: **NO**. Three-hit requirement changed: **NO**. Production tracking changed: **NO**. Production pair logic changed: **NO**. Alarm behavior changed: **NO**. Database changed: **NO**. Authentication changed: **NO**. Source B changed: **NO**. Phase 8C changed: **NO**. Training performed: **NO**.

Diagnostics: **OFF**. Frame capture: **OFF**. The diagnostic backend was stopped after capture, and the replacement backend was launched with `LIVE_COLLISION_DIAGNOSTICS=0`, `LIVE_COLLISION_FRAME_CAPTURE=0`, and `--no-access-log`. At 04:29:16 Asia/Manila it returned `/api/health` HTTP 200 on port 8010. The preserved session manifest's last modification remained 04:24:05.

## Verdict

**INSUFFICIENT_SYNCHRONIZED_EVIDENCE.** The report does not claim that the collision did not occur. It says the preserved synchronized frames cannot identify or measure the actual physical A/B event, and no true-pair confirmation occurred in the saved post-baseline decisions.
