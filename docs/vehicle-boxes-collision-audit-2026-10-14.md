# Vehicle boxes and collision workflow audit — October 14, 2026

## Findings and corrections

The detector artifact loads as an 80-class detection model. Its actual vehicle
IDs are listed below. `backend/models/crash_classifier.pt` is a separate binary
classifier (`accident`, `non_accident`), not a vehicle-localization model. Vans
and SUVs have no distinct class in the installed detector; they may be predicted
as another trained category, but dedicated van/SUV recognition is not established.

| Model class ID | Label | Bounding-box display | Road collision processing |
|---|---|---|---|
| 1 | bicycle | enabled | enabled |
| 2 | car | enabled | enabled |
| 3 | motorcycle | enabled | enabled |
| 4 | airplane | enabled | outside supported traffic domain |
| 5 | bus | enabled | enabled |
| 6 | train | enabled | outside supported traffic domain |
| 7 | truck | enabled | enabled |
| 8 | boat | enabled | outside supported traffic domain |

Labels now use the names belonging to each inference result rather than an
unrelated global model's class map. Dict/list name maps are accepted; nonfinite
boxes/confidence are rejected and coordinates are clipped to the source image.
Previously inconsistent bicycle filters and non-road vehicle display/track-ID
maps are corrected. Collision-domain/ROI filtering does not hide display boxes.
The existing 0.40 trusted vehicle threshold remains; the live worker's unsafe
classifier-triggered 0.15 fallback was removed rather than promoting weak boxes
to trusted collision evidence. Low-confidence and occluded objects can still be
missed; none are manufactured for display or verification.

Browser-camera boxes previously overlaid newer live video pixels after an HTTP
request completed. The preview now uses the exact uploaded JPEG and its own
dimensions, with an image-load guard. The video element stays available for
capture. CCTV/USB worker previews retain exact image/box/session/sequence pairing.
Expanded detection images and overlays share the same contain rectangle; window
resizing/letterboxing cannot assign annotations to a different source geometry.

Evidence dialogs also treated coordinates of one pixel or less as normalized
coordinates, placing a one-pixel offset at 100% of the image. They now consistently
convert source pixels using loaded image dimensions, clip boxes, and wait for the
matching source to load. Known annotated stills are displayed once without a
second overlay; raw evidence retains its separate coordinate overlay.

The active background worker and browser-frame path previously treated a
camera-wide classifier streak plus instantaneous box proximity as temporal
collision proof. Different physical pairs could borrow that streak, including
stationary overlapping vehicles. The already-existing before/contact/after
verifier and aftermath detector are now connected to these routes. The adapter
uses only current, accepted, road-vehicle **DETECTED** observations. Predicted
packets, missed detections, stale displays, invalid quality, duplicate sequences,
old epochs and resolution changes provide no motion proof. Equal capture times
preserve detection display but cannot add motion observations. Pair histories
retain the configured required-hit/window settings. A strong temporal pattern
can supply weak-classifier support without lowering detector or motion thresholds.

Uploaded videos previously depended on an `accident` object class that is absent
from the installed primary detector. They now use the existing classifier plus
the same tracker/verifier boundary. Sampling honors `VIDEO_ANALYSIS_FPS` rather
than fixed length-dependent skip floors that can starve track continuity. A
verified frame cannot be replaced by a later unrelated high classifier score.
Incident boxes belong to the representative key frame. Unsampled output frames
contain their actual pixels without annotations copied from another time; this
preserves playback but can make boxes intermittent. `VIDEO_FRAME_SKIP=1` is the
existing option for annotating every video frame at a greater processing cost.

Verified interactions clear from live classification after the vehicles separate
beyond the existing post-contact window. New verified interactions take priority
over already reported pairs, so an old visible accident does not mask another.
Contacts sharing a participant within that window conservatively share one event
identity. Additional verified participants augment the incident evidence without
replacing the original snapshot coordinates, media or timestamp. Independent
pair events have independent keys and cooldown identities; SQLite event-key
uniqueness still prevents repeat incidents and repeated official notifications.
Compound-contact grouping is an image-plane heuristic, not physical ground truth.

## Detection to official notification

The route requires an authorized monitor user. A configured verified collision
or persistent aftermath review flows through `persist_sqlite_crash_case` and
`persist_operational_detection` into SQLite `create_ai_incident`. The operation
records an incident, review case, alert, timestamp, evidence, timeline and audit.
Active Dispatcher accounts receive the existing `NEW_CRASH_REVIEW` inbox entries.
Dispatcher review/dispatch then follows the existing responder-assignment workflow.
There is no added email, SMS, Firebase or external notification channel.

Notification inserts use a nested savepoint. A recoverable delivery write error
preserves the incident/review/evidence and records a failure in the timeline.
Re-observation retries delivery without creating another incident or duplicate
notifications. Unknown/deleted events are not recreated by delivery retries.
No active recipients and delivery failures have explicit status/warnings.
Snapshot failures also surface warnings and do not abort an otherwise qualifying
incident. A failure of the whole database cannot persist a new incident; the API
and camera UI report persistence failure rather than claiming successful recording.

Normal detection, potential collision, persistent aftermath review and a
system-classified collision now have distinct upload labels. Success toasts no
longer claim a case was created when saving failed. Live/grid/upload views expose
delivery/evidence failures. Existing siren rules still require a newly committed
confirmed-collision incident and suppress duplicate identities. Aftermath remains
human review and cannot masquerade as a motion-confirmed collision.

## Files changed

| File | Purpose |
|---|---|
| `backend/main.py` | class mapping, display/ROI separation, route/verifier integration, video classifier/sampling, exact evidence, event identities, warning propagation |
| `backend/services/collision_observation_session.py` | isolated real-observation histories, pair-hit gate, temporal/aftermath adapter, related-contact identity |
| `backend/services/collision_pair_classifier.py` | bicycle eligibility |
| `backend/services/vehicle_tracking.py` | actual airplane/train/boat class IDs and display tracking labels |
| `backend/services/temporal_crash_verifier.py` | separation clearing and priority for new independently verified interactions |
| `backend/phase3/service.py` | independent event deduplication, savepoint delivery/retry, additional participant evidence |
| `backend/services/operational_detection.py` | delivery warnings and retry boundary |
| `components/live-camera.tsx` | exact browser-frame display and delivery/evidence warnings |
| `components/camera-detection-grid.tsx` | matching expanded image geometry and notification-failure status |
| `components/cctv-monitor-workspace.tsx` | visible grid delivery warning |
| `app/dashboard/upload/page.tsx` | accurate result states, recording/delivery warnings and truthful toasts |
| `app/dashboard/map/page.tsx` | source-loaded pixel geometry and no duplicate annotated-evidence overlay |
| `components/detected-media-viewer.tsx` | forwards the annotated-image flag to the preview dialog |
| `components/media-preview-dialog.tsx` | pixel coordinate conversion, source-load guard and annotation ownership |
| `components/incident-review-dialog.tsx` | clipped raw-evidence geometry and single annotated-image display |
| `lib/camera-analysis-view.ts` | finite source-pixel-to-percentage conversion |
| `lib/crash-case-mapper.ts` | chooses known annotated evidence and identifies raw fallback |
| `lib/incident-alarm-contract.ts` | shared result-state label, with existing audio contract preserved |
| `lib/types.ts` | additive delivery/evidence warning fields |
| `backend/tests/test_vehicle_pipeline_audit.py` | class/geometry/motion, actual route, event grouping, delivery and evidence regressions |
| `backend/tests/test_live_collision_diagnostics.py` | updated worker fixture and passing pair-safety regression |
| `backend/tests/test_live_monitor_restoration.py` | post-verification boundary fixtures; persistence assertions retained |
| `frontend-tests/dedicated-detection-view.test.ts` | resize geometry and exact browser-image contract |
| `frontend-tests/incident-alarm-contract.test.ts` | normal/candidate/aftermath/classified status distinctions |
| `frontend-tests/evidence-box-geometry.test.ts` | one-pixel geometry, actual mapper behavior and annotated/raw display contracts |
| `FINAL_VERIFICATION_REPORT.md` | current audit reference, preserving older verification history |
| this report | scope, evidence, limits and manual checks |

## Automated evidence

The final isolated backend suite passed **417 tests** in 175.985 seconds, with
zero failures, errors or expected failures. The frontend suite passed **67 tests**,
with zero failures or skips. TypeScript checking passed. Commands:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.run_isolated_tests
node --experimental-strip-types --test frontend-tests/*.test.ts
npm run typecheck
```

A separate actual-model smoke test ran both loaded networks through the live
worker on a synthetic black 640-by-640 frame, using temporary SQLite. It produced
zero vehicle boxes, no verified collision and no incident; the frame was rejected
as blurry. The primary model was reused for identical vehicle weights. This is
an empty-frame/load negative control, not evidence of positive traffic recall or
real collision recognition. Node's existing module-type warning is non-failing.

`git diff --check` passed with no whitespace errors. The Git index is empty;
model artifacts, tracker association code, pair ledger, schemas and dependencies
have no changes. Existing unrelated local validation/data files were left alone.

The focused suite executes the actual uploaded-video route with synthetic model
results and classifier scores, while using the real session tracker, temporal
verifier and temporary SQLite storage. It verifies a qualifying moving/contact/
stopping event, static overlap rejection, actual pixels on skipped frames, and
incident preservation when key-frame saving fails. Separate controlled tests
cover all eight display classes, all 15 road-class pair combinations, close
following, near misses, ID changes, predictions, no vehicles, temporary occlusion,
quality/epoch/resolution boundaries, equal timestamps, compound contacts, a new
collision while an old pair is visible, and same-pair separation/reinteraction.
SQLite integration exercises Dispatcher notification and responder dispatch,
repeated/concurrent persistence, failed delivery rollback/retry and additional
participants. These cases validate configured code behavior, not model recall or
real-world physical collision accuracy.

The former distinct-physical-pair safety XFAIL is now a normal passing regression
with its safety assertion retained. Existing capture/persistence fixtures that
used forced classifier streaks now mock the verifier boundary explicitly; real
motion verification has dedicated positive and negative route tests.

## Limits and manual validation

Fresh Bago probes first showed an indoor scene without traffic, then ordinary
traffic obscured by a large Windows security notice. No full live traffic
inference validation was performed on those inputs. The user selected completion
with automated tests and manual instructions. Reserved collision footage and
protected sources were not opened or used for inference.

Windows Computer Use returned `Computer Use native pipe is unavailable ...
(os error 2)`; browser inventory was empty. Live browser placement, generated
video playback, physical camera class recall, audible delivery and real collision
accuracy remain manual checks. Prior slow-cadence track fragmentation and the
classifier's high accident scores on normal traffic remain quality limitations.
The motion/quality gates are preserved; no thresholds were relaxed to hide them.
The smallest next quality step is a labeled, permitted road-camera evaluation
with participant identities, impact times and hard negatives, followed by
measured cadence/recall and classifier calibration. Dedicated van/SUV labels
require compatible trained weights and data, not fabricated class IDs.

1. Stop the existing backend process, restart it to load these code changes, then
   refresh the frontend. Avoid starting a second server on the occupied port.
   Use the existing project command:
   `.\backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8010`.
2. Close the blocking notice manually and aim Bago/FOBOS at ordinary traffic.
   In Live Monitor and Detections, compare labels/boxes with physical vehicles;
   resize the window and expand each source. Browser-camera mode intentionally
   shows the last exact analyzed frame while capture continues.
3. Check empty scenes, close passing, parked traffic and short occlusions. These
   must not become unsupported motion-confirmed collision events. A provisional
   candidate or aftermath review is distinct from a classified collision.
4. Use only a permitted, labeled test clip for collision validation. Verify
   before/contact/after evidence, incident timestamp/participants/snapshot,
   Dispatcher inbox/review, and the configured responder workflow. Repeated
   frames should retain one incident; a separate event should get a new identity.
5. Arm the existing browser alarm control and verify actual sound playback. For
   per-frame video annotation, set the existing `VIDEO_FRAME_SKIP=1` locally and
   restart the backend; restore the normal sampling setting after the check.

Model weights, detector confidence settings, tracker association thresholds,
database schemas and notification channels are unchanged. Changes from this task
are not staged, committed or pushed.

## Checkpoint review - October 20, 2026

The pre-commit review found two pre-existing hardcoded passwords in the unused
legacy `seed_default_users` routine in `backend/main.py`. They now read
`CRASHGUARD_LEGACY_ADMIN_PASSWORD` and `CRASHGUARD_LEGACY_RESPONDER_PASSWORD` from
the environment and skip each seed when its password is absent. The active
application does not call this routine, and existing accounts are unchanged.
No password values were copied into configuration examples or this report.
The exposed credentials were already present in earlier history; rotation is
recommended separately. This checkpoint does not rewrite history or rotate them.

Checkpoint verification passed: 417 backend tests in 190.988 seconds, 67 frontend
tests, TypeScript checking and staged whitespace checking. A controlled check of
the legacy seed routine confirmed that absent secrets create no accounts and
that configuring one synthetic password seeds only its intended account. The
27 selected text files exclude local camera configuration, databases, captures,
protected media and generated validation material.
