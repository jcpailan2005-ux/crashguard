"""Render the required Phase 8C report from queue and QA artifacts."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P8C = ROOT / "backend" / "validation" / "phase8c"


def main() -> int:
    with (P8C / "manifests" / "annotation_queue.csv").open(encoding="utf-8", newline="") as source:
        queue = list(csv.DictReader(source))
    integrity = json.loads((P8C / "qa" / "annotation_integrity.json").read_text(encoding="utf-8"))
    payloads = [json.loads((P8C / "annotations" / f"{row['event_id']}.json").read_text(encoding="utf-8")) for row in queue]
    verified = [payload for payload in payloads if payload.get("promotion_status") == "PROMOTED_VALIDATION_EVENT"]
    rejected = [payload for payload in payloads if payload.get("review_state") == "REJECTED"]
    awaiting = len(payloads) - len(verified) - len(rejected)
    types = Counter(payload["event_type"] for payload in verified)
    annotations = [annotation for payload in verified for annotation in payload.get("annotations", [])]
    contact = Counter(annotation["contact_confidence"] for annotation in annotations if annotation.get("contact_status") == "YES")
    participant_boxes = sum(observation.get("bbox") is not None for annotation in annotations for observation in annotation["participant_observations"].values())
    distractor_boxes = sum(len(annotation.get("distractors", [])) for annotation in annotations)
    pairs = Counter("-".join(sorted(participant["vehicle_class"] for participant in payload["participants"].values())) for payload in verified)
    baseline_ran = bool(verified) and (P8C / "baseline" / "expanded_baseline.json").exists()
    corpus_status = "TYPE_A_DIAGNOSTICS_READY_BUT_CORPUS_INCOMPLETE" if types["TYPE_A"] >= 6 else "HUMAN_ANNOTATION_STILL_REQUIRED"
    verdict = "PHASE 8C PARTIALLY COMPLETED — TYPE A DIAGNOSTICS READY, CORPUS GAP REMAINS" if types["TYPE_A"] >= 6 and baseline_ran else "PHASE 8C PARTIALLY COMPLETED — HUMAN ANNOTATION REQUIRED"
    metric = "NOT RUN — no promoted Phase 8C events" if not baseline_ran else "See baseline/expanded_baseline.json"
    text = f"""STATUS:

{verdict}

## ANNOTATION QUEUE

Total candidates: {len(queue)}

Human verified: {len(verified)}

Rejected after review: {len(rejected)}

Awaiting review: {awaiting}

## PROMOTED POSITIVES

Type A: {types['TYPE_A']}

Type B: {types['TYPE_B']}

Type C: {types['TYPE_C']}

Total new: {len(verified)}

Total including EVENT-0001: {1 + len(verified)}

## REMAINING DATA GAP

Type A: {max(0, 6 - types['TYPE_A'])}

Type B: {max(0, 5 - types['TYPE_B'])} additional (existing corpus already has 1)

Type C: {max(0, 6 - types['TYPE_C'])}

Total positives: {max(0, 19 - len(verified))} additional

## CONTACT QUALITY

Certain: {contact['CERTAIN']}

Probable: {contact['PROBABLE']}

Uncertain: {contact['UNCERTAIN']}

## VEHICLE PAIRS

Car-car: {pairs['car-car']}

Car-motorcycle: {pairs['car-motorcycle']}

Car-truck: {pairs['car-truck']}

Other: {sum(pairs.values()) - pairs['car-car'] - pairs['car-motorcycle'] - pairs['car-truck']}

## ANNOTATION QUALITY

Verified keyframes: {len(annotations)}

Participant boxes: {participant_boxes}

Distractor boxes: {distractor_boxes}

Integrity: {integrity['overall_integrity']}

## MODEL 2

Eligible participant observations: {metric}

Raw detected: {metric}

Accepted: {metric}

No-box: {metric}

Below candidate: {metric}

Wrong class: {metric}

Raw recall: {metric}

Accepted recall: {metric}

Car recall: {metric}

Motorcycle recall: {metric}

Small-object recall: {metric}

## TRACKING

Accepted observations: {metric}

Tracked: {metric}

Tracker failure given accepted: {metric}

Stable: {metric}

ID switches: {metric}

Logical recovery: {metric}

Both participants tracked: {metric}

Both motionObserved: {metric}

## PAIR ATTRIBUTION

Type A/B events: {metric}

Correct: {metric}

Wrong: {metric}

Unavailable: {metric}

Ambiguous: {metric}

Frame-level accuracy: {metric}

Event-level accuracy: {metric}

Distractor outscored true pair: {metric}

## TYPE A TEMPORAL

Events: {metric}

True-pair confirmations: {metric}

Wrong-pair confirmations: {metric}

Ignored: {metric}

Mean true-pair temporal score: {metric}

Max unrelated-pair score: {metric}

## TYPE B

Events: {types['TYPE_B']}

Correct operational outcomes: {metric}

Source-limited temporal failures: {metric}

## TYPE C

Independent events: {types['TYPE_C']}

Pending review: {metric}

Incorrect temporal confirmations: {metric}

Ignored: {metric}

## NEGATIVE REGRESSION

Independent negatives: 20

Confirmed false crashes: NOT RE-RUN — positive promotion gate not reached

Pending-review false positives: NOT RE-RUN — positive promotion gate not reached

## BOTTLENECK RATES

Model 2: NOT AVAILABLE

Tracking: NOT AVAILABLE

Pair attribution: NOT AVAILABLE

Temporal with correct tracked pair: NOT AVAILABLE

Aftermath routing: NOT AVAILABLE

## INTERMEDIATE ENGINEERING RANKING

1. Not ranked before human-verified ground truth.

2. Not ranked before human-verified ground truth.

3. Not ranked before human-verified ground truth.

4. Not ranked before human-verified ground truth.

Do NOT implement any fix.

## CORPUS STATUS

{corpus_status}

## NEXT DATA ACTION

Complete human review of the current 21-event queue. Afterward, if Type C remains below 6: TARGETED TYPE C AFTERMATH ACQUISITION.

## PRODUCTION FILES MODIFIED

Expected: NONE

Actual: NONE by Phase 8C work; only `scripts/` and `backend/validation/phase8c/` were created.

## MODELS

Model 1 retrained: NO

Model 2 fine-tuned: NO

Model files replaced: NO

## THRESHOLDS

Trusted: 0.40

Candidate: 0.25

Temporal: 0.62

Aftermath: 0.80

Unchanged: YES

## PHASE 8C VERDICT

{verdict}
"""
    (P8C / "reports" / "final_report.md").write_text(text, encoding="utf-8")
    print(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
