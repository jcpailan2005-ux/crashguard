# Phase 4 — Replay Source Acquisition Round 3

## Starting Pool

The Round 2 [manifest](../backend/data/tapo_replay_pilot/source_manifest.json) was verified at SHA-256 `e85cc7b1121f468be2651fb44a82518e54552f459fdf4f48556e648ded7dcb3c` before editing. It contained **8** eligible original sequences from **3** source families, **~00:12:40** useful traffic, and a **~00:17:20** shortfall against the approximate 30-minute gate. Motorcycle presence was verified, but sustained moving-motorcycle coverage was **LOW**. Manifest state: **UNFROZEN**. The [Round 1](tapo-replay-source-acquisition-phase4-2026-10-01.md) and [Round 2](tapo-replay-source-acquisition-round2-phase4-2026-10-01.md) reports and their source classifications were preserved.

## Existing License Conditions

- **Ficosa FNTVD, six originals:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode) under the [Ficosa/UPM source page](https://mx.gti.ssr.upm.es/data/ficosa). The current noncommercial research/capstone use may download, analyze, train experimentally, and screen-replay under the published grant, with credit to Ficosa International and FNTVD, source and license links, a change notice, and ShareAlike when adapted source media is shared. NonCommercial remains binding. This finding **does not clear commercial deployment** of the footage or any downstream product; that requires separate rights resolution. Do not imply Ficosa endorsement.
- **Aveiro UrbanEgo run 2:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) on the [author record](https://zenodo.org/records/23062929). Credit the creators, title/source and license, and indicate modifications or physical screen recapture. The admitted useful interval remains only the ~390-second roadside span. Residual identifiable content may remain despite automatic blur, so public display needs review.
- **Žilina Sc10:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) on the [University of Žilina creator record](https://zenodo.org/records/10663664). Credit Lukáš Ševčík and the university/source, link the license, and indicate modifications or physical screen recapture.

No prior eligible file, hash, family, recording ID, license, condition, quarantine, or overlap classification was removed or relaxed. The five `CameraAlberta.com`-branded Lisbon originals, 24 unresolved CADP clips, one classifier-overlapping CADP clip, and Round 2 rejected prospects remain excluded.

## Newly Investigated Candidates

The two admitted recordings are separately packaged **original MP4 members** of two MiTra flight campaigns. The [TU Dresden institutional record](https://opara.zih.tu-dresden.de/items/68482417-ddc5-40ac-885a-83124bd459e8) names Ankit Anil Chaudhari, Martin Treiber, and Ostap Okhrin and publishes the item as *Attribution 4.0 International*. Its README describes author drone acquisition, 135 minutes across nine flight campaigns, original videos, and corresponding creator trajectories. The [CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/) grant reproduction and adaptation with attribution and change notice; applying those grants to local noncommercial school-pilot model training and experimental screen replay is this audit's interpretation, rather than a separate ML-specific permission statement. The record has no NonCommercial or ShareAlike term. No extra repository redistribution ban was identified; incidental rights still need review before public redistribution.

| Source | Publisher | Useful duration | License | ML training | Replay permission | Rights chain | Lineage | Moving motorcycle coverage | Classification |
|---|---|---:|---|---|---|---|---|---|---|
| [MiTra T1_D6](https://opara.zih.tu-dresden.de/items/68482417-ddc5-40ac-885a-83124bd459e8) | TU Dresden / dataset authors | 07:19.206 | CC BY 4.0 | YES under grant interpretation, with attribution | YES under grant interpretation, with attribution | `RIGHTS_CHAIN_CLEAR` | `NO_KNOWN_OVERLAP` | `STRONG_MOVING_COVERAGE`; 22 creator tracks across all 7 minute bins, native-frame motion checked | Admitted |
| [MiTra T2_D1](https://opara.zih.tu-dresden.de/items/68482417-ddc5-40ac-885a-83124bd459e8) | TU Dresden / dataset authors | 15:41.541 | CC BY 4.0 | YES under grant interpretation, with attribution | YES under grant interpretation, with attribution | `RIGHTS_CHAIN_CLEAR` | `NO_KNOWN_OVERLAP` | `STRONG_MOVING_COVERAGE`; 33 creator tracks across 13 minute bins, group motion checked | Admitted |
| [AMIT-SI](https://dataverse.lib.nycu.edu.tw/dataset.xhtml?persistentId=doi:10.57770/2SFJ2G) | NYCU Dataverse authors | 0 for this video gate | CC BY-NC 4.0 on public record | Raw-video grant/access not established | Original replay video not found in public files | Video unreviewed | Unreviewed | Creator describes motorcycle-dominant intersections; footage not checked | Not acquired: no cleared original video |
| [MOTOR](https://huggingface.co/datasets/varunpaturkar/MOTOR) | Dataset author | 0 for this longer-original gate | CC BY-NC 4.0 on author page | Conditional license; individual source chain not audited here | Long uncut rides described as future release | Unreviewed | Unreviewed | Short clips exist; no 5–20-minute original reviewed | Not acquired |

Other prospects considered during the bounded search did not displace the smaller, cleared MiTra pair: SinD requires author-mediated access to full data, while the ETH cycling experiment centers on bicycles and required additional footage-rights review. They contribute zero pilot seconds. No prospect was treated as eligible merely because it was public or downloadable.

## Newly Eligible Sources

| Field | MiTra T1_D6 | MiTra T2_D1 |
|---|---|---|
| Source ID / family | `MITRA-T1-D6` / `MITRA_TU_DRESDEN_A50_MILAN_DRONE` | `MITRA-T2-D1` / same family |
| Original / official archive | `T1_D6.mp4` in `Tracking_Logs_Videos_T1.zip` | `T2_D1.mp4` in `Tracking_Logs_Videos_T2.zip` |
| Local original | `backend/data/tapo_replay_pilot/source_videos/mitra/T1_D6.mp4` | `backend/data/tapo_replay_pilot/source_videos/mitra/T2_D1.mp4` |
| SHA-256 | `7a1b1e4c18b808c74498ee596d2858a7305f82c5adaf279f35f285ed2eaef95e` | `3ea225c192574330dcb9b639df7be6cb8aa54c1459b2140e7b795c4cefdd2c75` |
| Original bytes / ZIP CRC32 | 5,485,468,688 / `b39b4f7e` | 11,759,100,639 / `1d943556` |
| Raw and useful duration | 439.206 s / 439.206 s | 941.541 s / 941.541 s |
| Resolution / FPS / codec | 3840×2160 / 29.970 / H.264 MP4 | 3840×2160 / 29.970 / H.264 MP4 |
| Download completed UTC | 2026-10-01 00:50:41 | 2026-10-01 01:18:22 |
| Traffic / motorcycles | Daylight divided motorway, cars, vans, heavy trucks; 22 source-labeled moving-motorcycle tracks in all 7 minute bins | Second flight campaign and motorway segment, daylight mixed traffic; 33 source-labeled moving-motorcycle tracks in 13 minute bins through minute 14 |

Each MP4 was extracted byte-for-byte from a stored ZIP member through publisher-hosted HTTP ranges. The local member size and source ZIP CRC32 passed, then an independent disk SHA-256 rehash matched its acquisition record. No transcoding or derivative source video was admitted. Creator CSV trajectories were read only to select bounded content-review times; no annotations, prelabels, or training samples were created.

For **T1_D6**, 17 separated video frames decoded to continuous traffic from the opening through ~437 seconds. Native frames at 147.2 and 149.0 seconds showed multiple motorcycles moving along the near carriageway among cars and trucks; another was visible at ~389 seconds. For **T2_D1**, 17 separated frames decoded to continuous traffic from the opening through ~939 seconds. Native frames at 666.9 and 668.7 seconds showed several separate motorcycles traveling together, and a late motorcycle near ~891 seconds had partial foliage occlusion. The video itself confirms repeated motion, while the creator's track counts establish distinct IDs and temporal spread. Fixed aerial viewpoints and generally small motorcycle image sizes are explicit limitations. No source-footage operator, broadcaster, platform, municipal, or third-party camera watermark was found. Truck branding and other incidental scene marks are not presented as an upstream footage grant.

## Rejected / Quarantined Sources

No new video was quarantined in Round 3. AMIT-SI and MOTOR remain unacquired prospects with zero admitted seconds. The five CameraAlberta originals remain `AUTHORIZATION_UNRESOLVED` / `RIGHTS_CHAIN_UNRESOLVED`; 24 CADP clips remain unresolved and one CADP clip has known classifier overlap. `URBANEGO-RUN4` remains ineligible for insufficient moving traffic. Source B, Phase 8C, protected regression scenes, and their derivatives remain excluded. No old unsafe source was reopened to close the duration gap.

## Final Eligible Pool

In this table, **Y** means prior bounded visual or creator annotation evidence, **?** means unverified, and **source-labeled** means the publisher's own trajectory/annotation file supplies that class. A parked motorcycle does not count as a moving one. All ten rows are source-packaged original recordings, not cuts created by this audit.

| Source ID | Family | Recording | Useful duration | Cars | Moving motorcycles | Trucks | Buses | Bicycles | License | Rights chain | Lineage | Eligible |
|---|---|---|---:|---|---|---|---|---|---|---|---|---|
| `ZILINA-SC10` | Žilina UHD | Sc10 | 00:10 | Y | ? | ? | ? | ? | CC BY 4.0 | No third-party indicator found | No known overlap | YES, conditions |
| `URBANEGO-RUN2` | Aveiro UrbanEgo | 20260506_163935 | ~06:30 | Y | No; parked only | ? | ? | ? | CC BY 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_182008` | FNTVD | 20221010_182008 | 01:00 | Y | No in creator labels | ? | ? | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_185218` | FNTVD | 20221010_185218 | 01:00 | Y | Y, low | Y | Y | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_191849` | FNTVD | 20221010_191849 | 01:00 | Y | Y, legacy moderate within clip | ? | Y | Y, creator label | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20221010_194855` | FNTVD | 20221010_194855 | 01:00 | Y | No in creator labels | ? | ? | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20230220_202721` | FNTVD | 20230220_202721 | 01:00 | Y | Y, low | ? | ? | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `FICOSA-20230220_203150` | FNTVD | 20230220_203150 | 01:00 | Y | Y, low | ? | Y | ? | CC BY-NC-SA 4.0 | Clear | No known overlap | YES, conditions |
| `MITRA-T1-D6` | TU Dresden MiTra | T1_D6 | 07:19.206 | Y | Y, strong | Y | source-labeled | Not labeled/observed | CC BY 4.0 | Clear | No known overlap | YES, conditions |
| `MITRA-T2-D1` | TU Dresden MiTra | T2_D1 | 15:41.541 | Y | Y, strong | Y | source-labeled | Not labeled/observed | CC BY 4.0 | Clear | No known overlap | YES, conditions |

Eligible sequences: **10**. Eligible families: **4**. Raw eligible duration: **00:40:14.397** (2,414.397 seconds). Useful eligible traffic: **~00:35:40.747** (2,140.747 seconds). Useful duration exceeds the 30-minute gate by **~00:05:40.747**. Round 3 added **00:23:00.747** useful seconds; no title card, blank, corrupted, or nontraffic interval was found in the representative MiTra review. The Round 2 UrbanEgo nontraffic interval remains excluded rather than counted by container length.

## Vehicle Coverage

Cars: verified in every eligible recording. Motorcycles: verified in seven recordings overall, of which six have moving-traffic evidence and one Aveiro run has only a parked motorcycle in the inspected span. Trucks: verified in Ficosa `185218` and both MiTra originals. Buses: verified in three Ficosa clips and source-labeled in both MiTra creator trajectory files. Bicycles: one Ficosa creator cyclist label; neither motorway video supplies meaningful bicycle coverage. Variation includes an aerial roundabout, daylight pedestrian roadside view, six nighttime fisheye driving recordings, and two 4K daylight drone motorway campaigns.

## Motorcycle Coverage

Overall classification: **STRONG_MOVING_COVERAGE** for this pilot pool. Motorcycle-containing recordings: **7**. Exact new-taxonomy `MODERATE_MOVING_COVERAGE` recordings: **0**; the unchanged Ficosa `20221010_191849` record retains its older `MODERATE` label limited to one minute. Exact `STRONG_MOVING_COVERAGE` recordings: **2** (MiTra T1_D6 and T2_D1). The MiTra creator trajectories contain **22 + 33 = 55** distinct per-recording moving-motorcycle track IDs. They are separate flight campaigns, so this is a sum of IDs within each original, not a claim of 55 globally unique riders. Native-video paired-frame review found separate moving motorcycles in both; T2 also provides group traffic and partial tree occlusion. This materially exceeds the previous short, mostly nighttime or parked-motorcycle evidence. The fixed overhead viewpoints and small motorcycle pixels limit transfer to near-ground Tapo views and must remain visible in later training evaluation.

## Rights and Authorization

Rights-chain audit: **PASS for the ten admitted originals**, based on creator/institutional self-capture claims and bounded no-watermark inspection. Training authorization: **PASS for the stated noncommercial school pilot**, with source-specific conditions. For MiTra, research use, local download, derivative processing, experimental screen replay, and pilot ML training are **YES under the CC BY 4.0 reproduction/adaptation grant interpretation**; attribution, source/license links, and change notice are required. MiTra has no CC NonCommercial or ShareAlike restriction. This source-level determination does not clear incidental people, vehicle liveries, or other rights for unrestricted public distribution.

Ficosa remains **NonCommercial** and requires attribution plus **ShareAlike for shared adaptations**. Aveiro and Žilina remain CC BY 4.0 with attribution and change notices; Aveiro's residual identifiable-content warning remains. No condition was silently converted into an unrestricted commercial product grant. The unreviewed and upstream-rights-unresolved candidates are outside this pass.

## Protected Independence

Source B: **EXCLUDED**. Phase 8C: **EXCLUDED**. Known protected regressions: **EXCLUDED**. Known classifier overlap: **EXCLUDED**. The two new SHA-256 values differ from the protected 145-video source inventory and all earlier manifest video hashes; the author UAV flight-campaign origin and bounded freeway views show no known overlap with documented protected scenes. Their status is **NO_KNOWN_OVERLAP**, not a claim of mathematically proven independence from every unknown upstream corpus. No Source B or Phase 8C material was replayed, sampled, annotated, or trained.

## Manifest

Path: [source_manifest.json](../backend/data/tapo_replay_pilot/source_manifest.json). Starting SHA-256: `e85cc7b1121f468be2651fb44a82518e54552f459fdf4f48556e648ded7dcb3c`. Final SHA-256: **`9e5eb867d746f292ab3e369e41f35e45997947f6c462f7386bdce47d69c2c578`**. State: **FROZEN_FOR_TAPO_REPLAY_CAPTURE**. The [Round 3 hash sidecar](../backend/validation/tapo_replay_source_acquisition_round3_20261001/source_manifest_round3.sha256) records the same value. All 17 old source records were compared as JSON values before writing the two appended entries; the 8 earlier eligible IDs and 3 earlier family IDs remain present. The frozen state authorizes the *next separately instructed stage* to consider capture; this round did not access the camera.

## Pilot Sufficiency

Sequence diversity: **PASS**, 10 originals. Source-family diversity: **PASS**, 4 families. Useful duration: **PASS**, ~35:40.747 versus ~30:00. Moving-motorcycle coverage: **PASS**, two sustained strong recordings. Rights: **PASS for admitted sources with conditions**. Lineage: **PASS at NO_KNOWN_OVERLAP**, with the prior quarantines retained. Overall: **SUFFICIENT**. The two-recording Round 3 addition is the smallest inspected pair used to close the duration gap; search and acquisition stopped here.

## Tapo Camera

**NOT ACCESSED.** No RTSP, Bago CCTV, stream1, or stream2 connection.

## Tapo Capture

**NOT STARTED.** No replay display or physical-camera capture.

## Annotation

**NOT STARTED.** No training frames, labels, or prelabels were generated. Temporary bounded visual-inspection images were deleted after review.

## Training

**NOT RUN.** No YOLO weights or training settings changed.

## Production

Detector: **UNCHANGED**. Thresholds: **UNCHANGED**. Collision logic: **UNCHANGED**. Pair integration: **NONE**. Alarm: **UNCHANGED**. Incident pipeline: **UNCHANGED**.

## Protected Rehash

**PASS.** The [Round 3 protected rehash](../backend/validation/tapo_replay_source_acquisition_round3_20261001/protected_rehash.json) found **zero changed and zero missing** among 291 older protected snapshot paths, 19 additional Round 1 evidence paths, and 7 Round 2 eligible-media paths, each compared with a recorded earlier SHA-256. Six Round 2 report/code/evidence files were hashed into a current inventory; their file modification times all predate Round 3, but no prior SHA-256 baseline exists for that six-file group, so the audit does not claim a cryptographic before/after comparison for it. The newly acquired MP4s separately passed official ZIP member CRC32, byte size, streaming SHA-256, and independent disk SHA-256 checks. Earlier Phase 4 evidence, Source B, Phase 8C, Phases 1–3, production model/configuration, thresholds, collision/pair logic, alarm, and incident files were not changed by this round.

## Phase 4 Source Verdict

**CLEARED_REPLAY_SOURCES_READY_FOR_TAPO_CAPTURE**

Stop at the frozen source gate. The next prompt may handle physical Tapo replay capture under the recorded source license conditions; this round performed no camera access, capture, annotation, training, collision replay, or production change.
