# Phase 2: vehicle tracking and temporal crash verification

Phase 2 uses Ultralytics 8.4.38's direct `BYTETracker` integration. Each camera
owns an independent tracker, bounded `TrackState` histories, and bounded vehicle
pair interaction state. The latest-frame capture strategy is unchanged; only
frames selected for AI analysis enter ByteTrack.

Supported COCO road classes are `bicycle` (1), `car` (2), `motorcycle` (3),
`bus` (5), and `truck` (7). Class IDs come from the installed model's names and
are not inferred from display order.

## Decision flow

1. Detect vehicles and update persistent ByteTrack identities.
2. Store normalized centers and raw bounding boxes in a bounded timestamped
   history.
3. Create candidate pairs only when normalized center/edge distance or IoU is
   reasonably close.
4. Require a consistent decreasing distance trend and convergent relative
   velocity before declaring an approach.
5. Require approach history before overlap/edge proximity can mark possible
   contact.
6. Observe later frames for normalized velocity change, heading disruption, or
   stopping.
7. Apply the deterministic score and mandatory approach/contact/post-contact
   gates.
8. Feed only `TemporalCrashDecision.is_verified` into the Phase 1
   `CrashEventManager`. Phase 1's detector-event UUID remains the durable event
   identity; track IDs are camera-session evidence only.

The crash classifier remains a 5% supporting score feature. It cannot bypass
the temporal gates, and strong temporal evidence can still verify when the
frame classifier is weak.

## Score weights

Every feature is normalized to `[0, 1]`.

| Feature | Default | Reason |
| --- | ---: | --- |
| Static proximity | 0.10 | Opens/strengthens a candidate but is never sufficient. |
| Closing trend | 0.20 | Multi-observation distance reduction is core pre-contact evidence. |
| Relative convergence | 0.15 | Rejects same-direction close following. |
| Contact candidate | 0.15 | Marks the possible impact interval after an approach. |
| Velocity change | 0.15 | Captures sudden normalized image-plane motion disruption. |
| Heading change | 0.10 | Supports side-impact/directional disruption patterns. |
| Post-contact behavior | 0.10 | Requires evidence after the possible impact. |
| Classifier | 0.05 | Supporting visual evidence only. |

The default score threshold is `0.62`, but score alone cannot confirm. Approach,
possible contact, enough post-contact observations, and motion disruption are
all mandatory gates.

## Configuration

The main environment settings are `TRACK_MIN_CONFIDENCE`, `TRACK_MAX_AGE_SECONDS`,
`TRACK_RESET_GAP_SECONDS`, `TRACK_HISTORY_SIZE`, `MIN_TRACK_HISTORY`,
`INTERACTION_DISTANCE_THRESHOLD`, `INTERACTION_IOU_THRESHOLD`,
`MIN_CLOSING_OBSERVATIONS`, `CONTACT_IOU_THRESHOLD`,
`CONTACT_DISTANCE_THRESHOLD`, `VELOCITY_CHANGE_THRESHOLD`,
`HEADING_CHANGE_THRESHOLD`, `POST_CONTACT_WINDOW_SECONDS`,
`PAIR_RETENTION_SECONDS`, and `TEMPORAL_CRASH_THRESHOLD`.

Invalid ranges fail configuration construction instead of silently enabling an
impossible verifier. `TRACKING_DEBUG_OVERLAY=true` adds IDs, candidate-pair
markers, and confirmation labels to saved annotated evidence.

## Limits

All distance, velocity, and motion-change features are normalized image-plane
quantities. They are not km/h, mph, m/s, or m/s². Camera perspective can still
distort them. `distance_metric()` is isolated so a calibrated road-plane or
homography implementation can replace it in a later phase without rewriting
the verifier.

Install `requirements.txt`, then `requirements-phase2.txt`; the latter pins the
linear-assignment dependency used by ByteTrack and the test runner omitted from
the legacy requirements file.
