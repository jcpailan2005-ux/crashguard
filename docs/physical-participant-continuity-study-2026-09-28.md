# Physical Participant Detection + Continuity Study

**LABELED_PHYSICAL_PARTICIPANTS_REQUIRED**

The required collision imagery is not preserved in an alignable form in the checked project artifacts. The authoritative [full diagnostic JSONL](../backend/validation/live_collision_diagnostics/preserved-full-20260928-postcapture/observations.jsonl) contains observation-local detections and timestamps, but no pixels or persistent physical identities. The task explicitly requires stopping here if the physical participants cannot be labeled and aligned. No detector experiment, continuity prototype, or pair-attribution replay was run for this task.

## Ground Truth

Participant A: **UNLABELED — actual physical vehicle identity unknown**.

Participant B: **UNLABELED — actual physical vehicle identity unknown**.

Collision phases labeled: **NONE**. PRE_APPROACH, APPROACH, IMMEDIATE_PRE_CONTACT, CONTACT_OR_CLOSEST_INTERACTION, IMMEDIATE_POST_INTERACTION, and AFTERMATH cannot be attached to preserved images or live observation numbers.

Physical contact visually provable: **NO from available aligned evidence**. This means unassessable, not that contact did not occur. **CONTACT_NOT_VISUALLY_PROVABLE** from the available artifacts.

The full JSONL's SHA-256 remains `940aa0ab5f5d3e293e99b1e50db901fe1c5b8b2f93bf41ad9f810a0cafb5f390`. It has 863 total records, 591 decisions after baseline OBS 3547, and ends at OBS 9949. The user reported a complete physical-camera reproduction. That report establishes what was shown to the camera, but it does not identify which specific pixels in the saved observation records correspond to the two actual participants.

The live worker keeps its current frame in memory and writes `live_camera_keyframe_*.jpg` only on case-related snapshot paths. The captured post-baseline decisions contain no `confirmed_crash`; normal scanning did not create a frame archive. A targeted read-only check of `backend/outputs/` and `backend/uploads/` found **no media file modified during the post-baseline 23:20:10–23:27:07 local decision span**. Two `backend/outputs/live_camera*.jpg` images were saved at **23:19:46**, before the **23:19:59** baseline. They cannot label the later physical approach, contact, or aftermath. Older camera captures and sample media elsewhere in the repository have no verified synchronization with this diagnostic run. No image was relabeled as the reproduced event merely because it shows vehicles or damage.

## Baseline Detection

Participant A raw recall: **NOT MEASURABLE**.

Participant A accepted recall: **NOT MEASURABLE**.

Participant B raw recall: **NOT MEASURABLE**.

Participant B accepted recall: **NOT MEASURABLE**.

Both raw simultaneous: **NOT MEASURABLE**.

Both accepted simultaneous: **NOT MEASURABLE**.

Per-phase recall for PRE_APPROACH, APPROACH, PRE_CONTACT, CONTACT/CLOSEST_INTERACTION, POST_INTERACTION, and AFTERMATH: **NOT MEASURABLE for either participant**. There is no labeled denominator or person-to-proposal match. The known two pair evaluations at OBS 3839 and 4022 are observation-local geometry, not physical-participant recall.

## Failure Breakdown

Participant A: NO_DETECTOR_PROPOSAL **UNKNOWN**; WEAK_PROPOSAL **UNKNOWN**; DOWNSTREAM_REJECTION **UNKNOWN**; OTHER **UNKNOWN**.

Participant B: NO_DETECTOR_PROPOSAL **UNKNOWN**; WEAK_PROPOSAL **UNKNOWN**; DOWNSTREAM_REJECTION **UNKNOWN**; OTHER **UNKNOWN**.

The JSONL does record exact proposal acceptance and rejection for each analyzed observation. Without physical bounding boxes it cannot tell whether a particular proposal overlaps A, B, or an unrelated vehicle. Therefore `NOT_PROPOSED_BY_DETECTOR`, `PROPOSED_BUT_REJECTED`, confidence failure, class mismatch, occlusion, and association failure cannot be counted for either physical participant. A missing accepted vehicle is not proof that a specific participant had no raw proposal.

## Physical Pair Continuity

Baseline longest simultaneous A+B sequence: **NOT MEASURABLE**.

Prototype longest simultaneous A+B sequence: **NOT RUN** under the required stop condition.

Three-hit physical-pair sequence available: **UNKNOWN**. The prior [pair and temporal study](full-capture-pair-temporal-study-2026-09-28.md) found no three-decision sequence of production-evaluated pairs, but could not score the actual physical participants. That result cannot replace the requested labeled continuity test.

## Pair Attribution

TRUE_LABELED_PAIR sequences: **NOT MEASURABLE**.

UNRELATED_PAIR sequences: **NOT MEASURABLE**.

AMBIGUOUS sequences: **NOT MEASURABLE against physical labels**. The two production-evaluated pairs remain physically undetermined. No nearby pair is assumed to be the collision pair.

## Negative Safety

New false pair continuities: **NOT TESTED in this task**.

New false 3-hit qualifications: **NOT TESTED in this task**.

No new detector or continuity variant was created, so there is no new prototype to compare with queued traffic, nearby non-colliding vehicles, substitution, same-class vehicles, or aftermath-only scenes. The prior isolated synthetic and Source B safety findings remain context, not a validation of physical participant recall for this reproduction.

## Detector Assessment

**INSUFFICIENT_LABELED_EVIDENCE**.

The present capture proves that only two decisions contained an evaluated pair among 591 post-baseline decisions. It does not prove whether the *actual two colliding vehicles* were proposed, accepted, rejected, occluded, or confused with other vehicles at the relevant physical phases. It cannot establish that the current detector is sufficient, recoverable by conservative continuity, or insufficient for the true physical pair.

## Recommended Next Step

**E. MORE_LABELED_COLLISION_EVIDENCE_REQUIRED**.

The minimum prerequisite is an authentic, authorized recording or preserved frames of this physical-camera reproduction with reliable frame-to-telemetry timing, plus manual A/B boxes and phase labels. If that source exists outside the checked project artifacts, it can be aligned and labeled without a new live reproduction. Do not use unrelated samples or older camera captures as substitutes. Until the physical labels exist, further detector configurations or association experiments would produce generic vehicle numbers rather than answer the stated question.

## Safety

Production code changed: **NO**. Production detector changed: **NO**. Production thresholds changed: **NO**. Production temporal window changed: **NO**. Production streak changed: **NO**. Production tracking added: **NO**. Production pair logic added: **NO**. Alarm changed: **NO**. Database changed: **NO**. Authentication/dispatcher/responder behavior changed: **NO**. Source B changed: **NO**. Phase 8C changed: **NO**. Training performed: **NO**. Diagnostics: **OFF**, verified from the running backend process environment. The preserved JSONL was read and hash-checked; no capture file was modified. Only this report was created.

## Verdict

**MORE_LABELED_EVIDENCE_REQUIRED**
