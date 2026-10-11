# Phase 4 — Replay Source Acquisition Round 2

## Starting State

Previous verdict: **MORE_CLEARED_REPLAY_SOURCES_REQUIRED**. Eligible sequences: **1**. Eligible duration: **~00:00:10**. Remaining useful-duration target: **~00:29:50**. Motorcycle coverage: **UNVERIFIED**. Manifest: **UNFROZEN**. The prior [source audit](tapo-replay-source-acquisition-phase4-2026-10-01.md) and [manifest](../backend/data/tapo_replay_pilot/source_manifest.json) were read before this round; their per-source decisions were preserved.

## Existing Eligible Source

`ZILINA-SC10`, the University of Žilina [UHD smart-transport record](https://zenodo.org/records/10663664): one unchanged aerial roundabout original, 10 seconds, 3840×2160 at 50 FPS. License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit the creator and source, link the license, and indicate changes. Cars were visually observed; motorcycles and other classes were not verified in this source. Its existing `TRAINING_ELIGIBLE_WITH_CONDITIONS` and `NO_KNOWN_OVERLAP` decisions remain intact.

## Existing Quarantine

The five `CameraAlberta.com`-branded Lisbon files remain **AUTHORIZATION_UNRESOLVED / RIGHTS_CHAIN_UNRESOLVED**, outside the eligible pool. The [depositor record](https://zenodo.org/records/14041920) labels the deposit CC BY 4.0, but no authoritative upstream camera-footage grant was found. Their original files remain in the prior quarantine directory. None was replayed, trained on, or reclassified. The earlier **24** unresolved CADP clips and **one** classifier-overlapping CADP clip also retain their previous statuses.

## Newly Investigated Candidates

| Source | Publisher | Duration and content | License / terms | ML training; replay / derivatives | Rights chain | Lineage | Motorcycles | Classification and decision |
|---|---|---|---|---|---|---|---|---|
| UrbanEgo run 2 | University of Aveiro / Instituto de Telecomunicações authors | 11:03.65 RGB; ~6:30 useful roadside span, with indoor footage at both ends | [Zenodo record](https://zenodo.org/records/23062929), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | YES; YES with attribution and change notice | `RIGHTS_CHAIN_CLEAR`: author-recorded HoloLens video; no camera/operator watermark in bounded views | `NO_KNOWN_OVERLAP` | YES, **stationary only** in inspected frames; LOW | `TRAINING_ELIGIBLE_WITH_CONDITIONS`; admitted for the roadside span only |
| UrbanEgo run 4 | Same authors | 11:04; repeated route dominated by parked cars, sidewalk, and indoor footage | Same CC BY 4.0 | License permits both, but traffic utility fails this gate | `RIGHTS_CHAIN_CLEAR` | `NO_KNOWN_OVERLAP` | UNKNOWN in bounded visual review | `TRAINING_INELIGIBLE`; quarantined for insufficient moving-traffic content |
| FNTVD six separately dated sequences | Ficosa International; distributed by Universidad Politécnica de Madrid GTI | Six **1-minute** 1344×968, 25-FPS night-driving videos, 6:00 total; cars and varying road/lighting scenes | [Official FNTVD page](https://mx.gti.ssr.upm.es/data/ficosa), [CC BY-NC-SA 4.0 legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode) and license inside archive | YES for noncommercial use; YES for noncommercial replay and derivatives, with ShareAlike for shared adapted media | `RIGHTS_CHAIN_CLEAR`: Ficosa says its recording car captured the videos and asserts copyright; no third-party camera/broadcast mark found in bounded views | `NO_KNOWN_OVERLAP`; six separately packaged timestamped recordings and distinct hashes | Four videos have creator motorcycle labels, with bounded visual support; overall LOW | `TRAINING_ELIGIBLE_WITH_CONDITIONS`; all six admitted |
| Songdo Traffic sample videos | EPFL and KAIST researchers | [29 creator-recorded 60-second drone samples](https://zenodo.org/records/13828384), 26.8-GB ZIP; dense intersections | CC BY 4.0 on official record and `LICENSE.txt` | YES under terms; replay/derivatives YES with attribution | Creator-described drone capture; individual media not checked | `LINEAGE_UNRESOLVED` for individual files | Dataset documents motorcycles; specific sample videos unverified | `TRAINING_ELIGIBLE_WITH_CONDITIONS` as an **unacquired prospect only**; zero pilot seconds until individual originals pass review |
| UTUAV B/C | UTUAV authors | [UAV imagery](https://videodatasets.org/UTUAV/) explicitly contains motorcycles, light and heavy vehicles; access by contacting author | Official page says research-only, noncommercial; no general video-replay grant shown | Research YES; model training of supplied images plausibly allowed; original-video local download, derivatives, and replay **UNCLEAR** | Creator-captured imagery, but video release not established | `LINEAGE_UNRESOLVED` | YES in dataset imagery, original video unavailable here | `AUTHORIZATION_UNRESOLVED` for this video replay gate; not acquired |
| IDOT traffic videos | UIC researchers; Illinois DOT camera footage | [13 five-minute videos](https://github.com/bitslab/IDOT_dataset), promising duration | Repository has a citation request but no footage license or upstream DOT grant | Research, ML training, download permission beyond access, derivatives, replay **UNCLEAR** | `RIGHTS_CHAIN_UNRESOLVED`: DOT is an upstream operator | `LINEAGE_UNRESOLVED` | UNKNOWN | `AUTHORIZATION_UNRESOLVED`; not acquired |
| NVD | UPM researchers using public highway cameras | [Night road cameras](https://www.gti.ssr.upm.es/data/NVD_database) from five locations | No footage license/terms found on official page | Research, ML training, local download rights, derivatives, replay **UNCLEAR** | `RIGHTS_CHAIN_UNRESOLVED`: public third-party cameras | `LINEAGE_UNRESOLVED` | UNKNOWN | `AUTHORIZATION_UNRESOLVED`; not acquired |

For the acquired CC BY source, the license permits copying and adaptation, including the intended internal model-training and experimental-display use as an interpretation of those grants. It requires attribution and a change notice; it has no commercial restriction. For FNTVD, the [creator's page](https://mx.gti.ssr.upm.es/data/ficosa) and included license file expressly apply CC BY-NC-SA 4.0: local download, noncommercial research, noncommercial ML use, derivative processing, and noncommercial experimental display are permitted under the license; give credit and source/license links, mark changes, and use the same or a compatible license when sharing adapted media. Ficosa does not grant commercial use. Neither admitted source has an extra redistribution ban beyond its license conditions. UrbanEgo warns that automatic blur may leave identifiable content; public display would require review. Public accessibility alone was not treated as authorization for IDOT, NVD, or UTUAV video.

## Newly Eligible Sources

The following table counts **officially packaged original video sequences**, never cuts made here. `Y` denotes support from bounded source-video review or creator-supplied labels; `?` means not verified. FNTVD has source-provided OpenLABEL objects, including seven motorcycle objects in `20221010_191849`, three in `20230220_202721`, and motorcycle objects in two other clips. We read those labels to verify source content; we did not create annotations.

| Source ID | Family | Original Sequence | Duration (useful estimate) | Cars | Motorcycles | Trucks | Buses | Bicycles | License | Rights Chain | Lineage | Eligible |
|---|---|---|---:|---|---|---|---|---|---|---|---|---|
| `ZILINA-SC10` | Žilina UHD | Sc10 | 00:10 (00:10) | Y | ? | ? | ? | ? | CC BY 4.0 | No third-party indicator found | No known overlap | YES, conditions |
| `URBANEGO-RUN2` | UrbanEgo Aveiro | 20260506_163935 | 11:03.65 (~06:30) | Y | Y, parked only | ? | ? | ? | CC BY 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_182008` | FNTVD | 20221010_182008 | 01:00 (01:00) | Y | NO in creator labels | ? | ? | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_185218` | FNTVD | 20221010_185218 | 01:00 (01:00) | Y | Y, low | Y | Y | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_191849` | FNTVD | 20221010_191849 | 01:00 (01:00) | Y | Y, moderate within clip | ? | Y | Y, creator cyclist label | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_194855` | FNTVD | 20221010_194855 | 01:00 (01:00) | Y | NO in creator labels | ? | ? | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20230220_202721` | FNTVD | 20230220_202721 | 01:00 (01:00) | Y | Y, low | ? | ? | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20230220_203150` | FNTVD | 20230220_203150 | 01:00 (01:00) | Y | Y, low | ? | Y | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |

Eligible sequences: **8**. Eligible source families: **3**. Total nominal original duration: **00:17:13.65**. Combined useful traffic estimate: **~00:12:40**. Additional useful duration required to reach the 30-minute lower target: **~00:17:20**. Motorcycle-containing eligible sequences: **5**, of which **four** contain creator-labeled traffic motorcycles and **one** contains only a parked motorcycle in the inspected span. The FNTVD six files are source-packaged, separately timestamped recordings (the two closest start more than four minutes apart), each with its own MP4 and source annotation JSON; no single file was split into multiple counted sequences here.

## Quarantined / Rejected Sources

- `URBANEGO-RUN4`: the extracted original is under `backend/data/tapo_replay_pilot/quarantine/urbanego/`. The license and rights chain are clear, but bounded views show mostly parked cars, pedestrian-only street scenes, and indoor footage. Its full 11:04 cannot honestly count as moving-traffic duration. Classification: `TRAINING_INELIGIBLE` for this pilot gate.
- The five CameraAlberta-branded Lisbon originals remain quarantined for **unresolved upstream camera rights**. No change to their prior decision.
- Songdo samples were not downloaded because individual 4K files are 0.7–1.0 GB inside a 26.8-GB archive and would add only one minute each; individual rights-cue, content, and lineage checks remain undone. This is an eligible-license prospect, not an eligible pilot original.
- UTUAV video access/replay terms remain unclear and the visible download describes image data. IDOT has no documented DOT footage grant or license. NVD reuses public third-party camera footage without an upstream grant shown. Each contributes zero seconds.
- The prior 24 unresolved CADP clips and one known classifier-training overlap stay excluded. Nevsky and isolated MAVD remain unacquired prior prospects; their earlier classifications were preserved.

## Eligible Pool

Sequences: **8**. Source families: **3**. Nominal duration: **00:17:13.65**. Useful traffic estimate: **~00:12:40**. Cars: **verified across all eight**. Motorcycles: **documented in four short FNTVD traffic clips**, plus a parked Aveiro motorcycle; overall coverage is **LOW** for the eventual detector domain. Trucks: **one FNTVD clip**. Buses: **three FNTVD clips**. Bicycles: **one FNTVD creator cyclist label**. Variation includes an aerial roundabout, a daylight pedestrian roadside view, and sparse to moderate fisheye night driving. All admitted sources retain their attribution or noncommercial conditions.

## Motorcycle Coverage

Verified presence: **YES**. Evidence: FNTVD creator OpenLABEL objects identify motorcycles in four dated recordings; bounded frame inspection saw motorcycles in the FNTVD night-road views. `20221010_191849` has seven separately named source motorcycle objects, but all six FNTVD videos last just one minute and night/fisheye imagery often renders the subjects small. The UrbanEgo run 2 detections at approximately 565–573 seconds correspond to a **parked** motorcycle and do not strengthen moving-traffic coverage. Meaningful motorcycle diversity and sustained observations: **INSUFFICIENT / LOW**. No source was marked motorcycle-present merely because it described generic vehicles.

## Rights-Chain Audit

Admitted pool: **PASS** for the evidence reviewed. Ficosa asserts copyright and own-car capture on its [official page](https://mx.gti.ssr.upm.es/data/ficosa); the UrbanEgo [record](https://zenodo.org/records/23062929) says a researcher wore the capture headset; Žilina's prior paper described creator drone capture. Bounded media inspection found no third-party camera, broadcaster, municipal/operator, or platform overlay in the newly admitted clips. This is a source-level rights conclusion, not a guarantee about unrelated incidental rights in filmed people or surroundings. Unresolved, excluded sources: **five CameraAlberta files; IDOT; NVD**. Songdo individual video inspection is pending and it is excluded from the pool.

## Protected Independence

Source B included: **NO**. Phase 8C included: **NO**. Known classifier overlap included: **NO**. Protected regression material included: **NO**. All eight new acquired MP4 SHA-256 values differ from the old 145-video inventory. The newly admitted locations, viewpoints, dates, and scenes differ from documented protected material in bounded review. The appropriate claim is **NO_KNOWN_OVERLAP**, not proof against every unknown upstream corpus. No Source B or Phase 8C media was replayed or used for training.

## Manifest

Path: [source_manifest.json](../backend/data/tapo_replay_pilot/source_manifest.json). Previous SHA-256: `e0ed337783b12ad759171dee4dfd0ab8fde47bf884850743e9beaa4172fe14fb`. New SHA-256: `e85cc7b1121f468be2651fb44a82518e54552f459fdf4f48556e648ded7dcb3c`. State: **UNFROZEN**. The new [hash sidecar](../backend/validation/tapo_replay_source_acquisition_round2_20261001/source_manifest_round2.sha256) records this value. The original FNTVD outer RAR SHA-256 is `f927d9c65f11c1a46ad0b2b39db78131cedd2898b36623e876d4f61bf9c4f273`; individual video and nested-ZIP hashes, file sizes, duration, resolution, FPS, codec, source and license are in the manifest. FNTVD media was extracted byte-for-byte from the source archive; no source was transcoded.

## Pilot Sufficiency

Independent source-packaged sequences: **8 / approximately 5+**. Source families: **3 / preferably 2+**. Useful duration: **~00:12:40 / approximately 00:30:00+**. Motorcycle coverage: **verified but low and brief**. License, rights chain, and known lineage: **acceptable only for the admitted sources and subject to stated conditions**. Verdict: **INSUFFICIENT**. Sequence deficit: **0**. Useful-duration deficit: **~00:17:20**. Class deficit: **sustained moving-motorcycle variation**, with trucks, buses, and bicycles represented only sparsely. The full runtime of mixed-content UrbanEgo video was not substituted for useful traffic time.

## Tapo Camera

**NOT REQUIRED / NOT OPENED.** No RTSP connection, Bago CCTV view, camera check, replay display, or capture was performed.

## Tapo Capture

**NOT STARTED.**

## Annotation

**NOT STARTED.** Creator-provided FNTVD annotations were read for source-content verification only. Transient bounded inspection images were removed after review; no training frames, labels, or prelabels were created.

## Training

**NOT RUN.** No YOLO weights or training configuration changed.

## Production

**UNCHANGED.** No detector threshold, collision logic, pair integration, alarm, or incident-pipeline change.

## Protected Rehash

**PASS.** The previous 291-path [protected snapshot](../backend/validation/tapo_replay_source_acquisition_20261001/protected_before.json) has **zero changed or missing paths**. The [Round 2 rehash](../backend/validation/tapo_replay_source_acquisition_round2_20261001/protected_rehash.json) also records current hashes for 19 prior Phase 4 evidence files, including the old report and original eligible media. Earlier Phase 4 evidence, Source B, Phase 8C, Phases 1–3, production model/configuration, thresholds, collision/pair logic, alarm, and incident files were not modified by this round.

## Phase 4 Source Verdict

**MORE_CLEARED_REPLAY_SOURCES_REQUIRED**

Keep the manifest unfrozen. Seek at least ~17:20 more useful, clearly licensed, source-owned traffic footage with sustained moving-motorcycle observations. Stop before physical Tapo capture, annotation, or training.
