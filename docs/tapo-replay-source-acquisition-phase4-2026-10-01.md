# Phase 4 — Independent Replay Source Acquisition

**Source verdict: MORE_CLEARED_REPLAY_SOURCES_REQUIRED.** One inspected, unchanged original can enter a future replay-source pool under CC BY 4.0 attribution conditions: a **10-second** University of Žilina aerial roundabout clip. This falls far short of the target of about five independent sequences and 30–60 minutes of useful traffic. Five other downloaded clips were **quarantined**, not admitted, after their imagery showed `CameraAlberta.com` branding that raises an unresolved upstream-rights question despite the depositor's CC BY label. No physical Tapo replay, training-data capture, annotation, model training, or production change occurred.

## Previous Result

Prior Phase 4 verdict: **INDEPENDENT_REPLAY_TRAINING_SOURCES_REQUIRED**. Existing project videos audited: **145**. Previously training-eligible: **0**. This work used that completed [audit](../backend/validation/tapo_replay_detector_phase4/source_audit.json) and sought new official sources; it did not rerun the old 145-file search.

## Experimental Domain

**TAPO_SCREEN_REPLAY_DOMAIN**: source video → display → physical Tapo → authorized Bago RTSP → CrashGuard. Native roadside access: **NO** per the stated project constraint. Any later result here remains a controlled replay-domain result, not native CCTV validation.

## Candidate Source Audit

The official records and [CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/) allow copying and adaptation, including model-training use as an interpretation of the adaptation grant, provided attribution, license link, and change notices are supplied. A repository license label does not resolve a visibly separate upstream camera owner. The [machine-readable manifest](../backend/data/tapo_replay_pilot/source_manifest.json) records each original and each prospect's source, rights, conditions, lineage, media metadata, and admission decision.

| Source | Publisher / owner | Official source | License | ML training | Download | Lineage | Protected overlap | Traffic suitability | Classification |
|---|---|---|---|---|---|---|---|---|---|
| `ZILINA-SC10` | Lukas Sevcik, University of Žilina | [UHD smart transport deposit](https://zenodo.org/records/10663664) | CC BY 4.0; credit and mark recapture/changes | YES under stated terms | Original verified, 150,058,280 bytes | **NO_KNOWN_OVERLAP**; distinct aerial roundabout view | SHA-256 absent from prior video inventory; no visual Source B match in limited review | Ordinary moving cars and small/distant vehicles; **10 seconds only** | **TRAINING_ELIGIBLE_WITH_CONDITIONS**; admitted to limited pool |
| `LISBON-2024-04-21T10-25-27` | Tiago Silva / Instituto Politécnico de Lisboa depositor; upstream camera rights unknown | [Traffic Evaluation v2](https://zenodo.org/records/14041920) | Depositor metadata says CC BY 4.0; upstream authorization unresolved | UNCLEAR | Original verified, then quarantined | Same camera view as other four below | No exact prior-file hash; source-family clearance incomplete | Night/rain road, 276.2 s | **AUTHORIZATION_UNRESOLVED** |
| `LISBON-2024-04-23T10-31-54` | Same deposit and upstream issue | [Traffic Evaluation v2](https://zenodo.org/records/14041920) | Same | UNCLEAR | Original verified, then quarantined | Same camera view | Same unresolved lineage | Day road, 172.667 s | **AUTHORIZATION_UNRESOLVED** |
| `LISBON-2024-04-24T10-35-00` | Same deposit and upstream issue | [Traffic Evaluation v2](https://zenodo.org/records/14041920) | Same | UNCLEAR | Original verified, then quarantined | Same camera view | Same unresolved lineage | Night road, 206.033 s | **AUTHORIZATION_UNRESOLVED** |
| `LISBON-2024-09-09T15-17-01` | Same deposit and upstream issue | [Traffic Evaluation v2](https://zenodo.org/records/14041920) | Same | UNCLEAR | Original verified, then quarantined | Same camera view | Same unresolved lineage | Day road, 184.1 s | **AUTHORIZATION_UNRESOLVED** |
| `LISBON-2024-11-04T12-00-31` | Same deposit and upstream issue | [Traffic Evaluation v2](https://zenodo.org/records/14041920) | Same | UNCLEAR | Original verified, then quarantined | Same camera view | Same unresolved lineage | Low-light road, 107.3 s | **AUTHORIZATION_UNRESOLVED** |
| `NEVSKY-FIGSHARE` | Artur Grigorev | [Nevsky surveillance deposit](https://figshare.com/articles/dataset/Nevsky_prospect_traffic_surveillance_video/5841846) | CC BY 4.0 on official record | YES under stated terms, contingent on file/lineage review | **NOT ACQUIRED**; about 283 GB in multivolume archives | **LINEAGE_UNRESOLVED** | Individual videos uninspected | Dense traffic documented, but no local original assessed | **TRAINING_ELIGIBLE_WITH_CONDITIONS** as an authorization prospect; not admitted |
| `URBANSAS-MAVD` | Urbansas creators and original MAVD authors | [Urbansas deposit](https://zenodo.org/records/6658386) | Official terms specify CC BY 4.0 for **MAVD** video; TAU has a different noncommercial license | YES for isolated MAVD subset under stated terms | **NOT ACQUIRED**; archives mix footage subsets | **LINEAGE_UNRESOLVED** | Individual video sources uninspected | Montevideo traffic and vehicles documented; 10-second clips | **TRAINING_ELIGIBLE_WITH_CONDITIONS** as a subset prospect; not admitted |
| `TRANSSET-FIGSHARE` | Tewodros Gebre, Quincy Blackston, Leila Hashemi-Beni | [TRANSSET deposit](https://figshare.com/articles/dataset/TRANSSET_A_Drone-Captured_Dataset_for_Enhancing_Vehicle_Detection_and_Traffic_Monitoring_Algorithms/26082217) | CC BY 4.0 | Terms permit ML, but not a replay-video source | **NOT ACQUIRED** | **LINEAGE_UNRESOLVED** | Not checked | [Official README](https://api.figshare.com/v2/articles/26082217) lists extracted JPG images and labels, not original video files | **TRAINING_INELIGIBLE** for this video-source gate |

For each acquired file, official checksum and byte size matched the official Zenodo API metadata, and SHA-256 plus OpenCV duration, resolution, and FPS are in the manifest. The Žilina authors' [published dataset paper](https://www.mdpi.com/2079-9292/13/5/904) says they created these video sequences with a DJI Mavic Air 2, strengthening the creator-to-footage lineage. The five quarantined originals total **946.3 seconds (15 min 46.3 s)** but contribute **zero** eligible seconds. Their visible `CameraAlberta.com` marking is a rights-clearance signal, not proof that the depositor lacked permission; an authoritative upstream grant or evidence of depositor rights would be needed to reconsider them. The five clips also share one visible intersection, so five filenames would not count as five source families. A 655 MB Lisbon download was interrupted when this issue emerged; its incomplete `.part` file was removed, with no original admitted from it.

## Existing CADP

Unresolved clips: **24**. Classifier-overlapping clip: **1** (`CADP-3VTdPoH5eGE`). Reclassified clips: **0**. No new CADP author/owner grant or source-family evidence was found in this acquisition; the [prior per-clip audit](../backend/validation/tapo_replay_detector_phase4/source_audit.json) remains authoritative. None was downloaded anew or admitted. The local [license and lineage assessment](../backend/validation/cctv_detector_pilot/cadp_provenance_lineage_report.md) still records the unresolved training-use and existing-model relationships.

## Eligible Source Pool

Acquired and admitted source families: **1**, `ZILINA_UHD_2024_ROUNDABOUT`. Videos/sequences: **1**, `ZILINA-SC10`. Total duration: **10.0 seconds** at 3840×2160, nominal 50 FPS. Its source SHA-256 and original metadata are recorded in the manifest; the file remains unchanged under `backend/data/tapo_replay_pilot/source_videos/zilina/`. Admission means its authorization and currently known provenance permit considering it for a future replay pilot with proper attribution. It does **not** mean the pilot source pool is sufficient or frozen for Tapo capture.

## Traffic Coverage

Within the admitted 10-second clip, cars: **visually observed**. Small/distant vehicles: **visually observed**. Motorcycles, trucks, buses, bicycles, and substantial occlusion: **not verified** from the limited review. Congestion: **not established**. These are evidence limits, not claims that the classes are absent throughout the original. The quarantined Lisbon footage cannot be counted toward coverage or duration. Motorcycle support, especially important for the protected Source B participant, remains unestablished.

## Authorization Summary

Across the **nine new manifest entries** (six acquired originals and three researched prospects): `TRAINING_ELIGIBLE`: **0**; `TRAINING_ELIGIBLE_WITH_CONDITIONS`: **3** (**one** acquired/admitted, **two** unacquired prospects); `AUTHORIZATION_UNRESOLVED`: **5**; `TRAINING_INELIGIBLE`: **1**; `PROTECTED_OR_OVERLAPPING`: **0** newly admitted. The prior 24 unresolved CADP clips and one training-seen CADP clip are **outside** these nine and retain their old classifications. CC BY 4.0 has no noncommercial restriction, but requires attribution and change indication; it does not itself resolve third-party rights visible within a clip. No downloaded original or derivative was redistributed.

## Independence

Source B included: **NO**. Source B derivatives included: **NO**. Phase 8C included: **NO**. Protected regression imagery included: **NO**. Known classifier-training overlap included: **NO**. The one admitted aerial roundabout original has a SHA-256 absent from the old 145-video inventory and a visibly distinct scene from the documented Source B collision replay. Classification: **NO_KNOWN_OVERLAP**, not `PROVEN_INDEPENDENT` from all possible upstream corpora. All unacquired prospects retain `LINEAGE_UNRESOLVED`; the five Lisbon files remain quarantined even though their file hashes differ from the old inventory. No Source B playback or recapture was performed.

## Manifest

Path: [source_manifest.json](../backend/data/tapo_replay_pilot/source_manifest.json). SHA-256: `e0ed337783b12ad759171dee4dfd0ab8fde47bf884850743e9beaa4172fe14fb`. The [hash sidecar](../backend/validation/tapo_replay_source_acquisition_20261001/source_manifest.sha256) records the same value. `manifest_frozen_for_capture=false` because the pool is insufficient; a later source-clearance phase must rebuild, review, then freeze a new manifest before Tapo playback.

## Pilot Sufficiency

Independent admitted sequences: **1** versus the approximate target of **at least 5**. Independent admitted source families: **1**, with more than one preferred. Admitted duration: **10 seconds** versus roughly **30–60 minutes** useful traffic. Motorcycle coverage: **NOT VERIFIED**. Verdict: **INSUFFICIENT**. The exact missing amount relative to the lower target is **at least four additional independent sequences and about 29 min 50 s of cleared useful traffic**, ideally spanning another source family and including verifiable motorcycles. Targets remain development guides, not permission to weaken rights or lineage checks. Nevsky and MAVD are leads only until individual originals are obtained, inspected, and cleared.

## Tapo Capture

**NOT STARTED.** No new video was played to the display or physical Tapo, and no RTSP training recording was made.

## Annotation

**NOT STARTED.** No training frames, crops, prelabels, or human annotations were created. Video inspection used transient in-memory views only; no frame files were saved.

## Training

**NOT RUN.** No model, weights, or training configuration changed.

## Production Changes

Detector: **UNCHANGED**. Thresholds: **UNCHANGED**. Collision logic: **UNCHANGED**. Pair integration: **NONE**. Alarm: **UNCHANGED**. Incident pipeline: **UNCHANGED**.

## Protected Asset Check

The [before snapshot](../backend/validation/tapo_replay_source_acquisition_20261001/protected_before.json) extends the prior protection set to **291 paths**, including Source B, Phase 8C, Phases 1–3, all earlier Phase 4 stages, production model/configuration/collision/threshold/pair/alarm/incident files, and prior reports. The [final rehash](../backend/validation/tapo_replay_source_acquisition_20261001/protection_audit.json) reports **zero changed protected paths**. New originals, quarantine, acquisition scripts, and manifests are isolated additions.

## Phase 4 Source Verdict

**MORE_CLEARED_REPLAY_SOURCES_REQUIRED**

Stop before physical Tapo capture. Acquire and clear more independent ordinary-traffic originals with traceable upstream rights, useful duration, source-family separation, and motorcycle coverage. Keep the quarantined Lisbon files and all protected CrashGuard evidence out of replay training.
