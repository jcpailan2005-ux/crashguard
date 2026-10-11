# CrashGuard Preview Latency Audit

## Result

**First measured accumulation point: FFmpeg/OpenCV H.264 frame decoding with its default 12 decoder threads.** At nearly simultaneous sampling times, changing only a separate diagnostic decoder to one thread made its camera OSD exactly one second ahead of the running CrashGuard snapshot in **34/34 paired samples**. With default decoder threading, direct RTSP and CrashGuard snapshots showed the same OSD second in **33/34 samples**.

This identifies approximately one second of avoidable decoding delay. It does **not** prove that every part of the user-observed three-second browser delay has been removed.

## Requested summary

| Field | Finding |
|---|---|
| Tapo app | User reports no noticeable delay; no instrumented mobile measurement |
| Direct RTSP | Default 12-thread decoder: mean host-minus-OSD **1.506 s**. One-thread decoder: **0.209 s** in a separate 35-second window. This measures decoded frames, not a separate player's screen |
| CrashGuard before | User reports approximately **3 s** on the browser timestamp. Running HTTP snapshot means **1.560 s** and **1.231 s** in the paired windows; running MJPEG HTTP-arrival means **1.371 s** and **1.458 s** |
| Primary accumulation point | Decoder frame-thread pipeline, before the latest-frame slot |
| Root cause | OpenCV reported **12** decoder threads; one thread substantially advanced the OSD without reducing capture throughput |
| Fix | Open the capture with `CAP_PROP_N_THREADS=1`, using the supported open-time parameter list. Add bounded capture/JPEG timing diagnostics and frame-bound HTTP metadata. Strengthen snapshot no-cache headers |
| CrashGuard after | **Revised preview-only HTTP harness**, not the restarted production service: host-minus-OSD mean **0.422 s** over five minutes; **0.385 s** after the initial five seconds. Local HTTP receipt age since decode averaged **45.5 ms**, sampled maximum **107.8 ms** |
| Latency grows over time | **NO observed growth** over the five-minute revised-path test; after-startup maximum sampled OSD offset **0.907 s**, last-30-second mean **0.390 s** |
| Active production RTSP capture workers | **1 effective source reader inferred** from one camera/source and one established connection; private Python thread objects were not remotely enumerated |
| Active production RTSP connections | **1 established TCP connection**, PID **3556**, `192.168.1.17:554`, before and after probes |
| Inference workers | **1 reported active monitor inference worker** for the sole camera; probes did not start AI workers |
| Capture FPS | Revised five-minute preview path: **14.85** |
| Preview FPS | Revised five-minute MJPEG HTTP delivery: **9.42** |
| AI pipeline changed | **NO in this task** |
| Models changed | **NO** |
| Thresholds changed | **NO** |
| Database changed | **NO edits by this audit**; configuration/camera inspection used read-only queries |

## Measurement validity

The camera OSD contains seconds and was visually checked against captured strips. Its digits were read with fixed-font matching using manually verified exemplars from the same camera. Ambiguous glyphs were rejected. Sixty-one OSD samples were successfully read in the five-minute test. Original strips and per-sample host times remain available.

**Host-minus-OSD is not absolute physical latency.** It includes camera clock offset and one-second display quantization. A slightly negative minimum (-0.096 s) illustrates this limitation. The paired same-camera comparisons cancel the clock offset and give stronger evidence of the approximately one-second decoder difference. No stopwatch synchronization was available. Tapo may use another protocol; it was not treated as proof that RTSP itself is delay-free.

There was an initial startup sample with **2.419 s** host-minus-OSD. Continuous consumption caught up; after the first five seconds all sampled offsets were between **-0.096 and 0.907 s**. The fix does not promise an immediately fresh first frame or a verified sub-second physical/browser delay.

## Trace of the preview path

### RTSP and decoder

- The source is `rtsp://<redacted>@192.168.1.17:554/stream2`; source credentials were never placed in report files.
- Current configured FFmpeg options remain TCP, `fflags=nobuffer`, and `max_delay=500000`. Transport was not changed.
- `CAP_PROP_BUFFERSIZE=1` returned **False** in every tested setup. The source now records that acceptance result instead of assuming the setting works.
- OpenCV 4.13.0 reported 12 default decoder threads. The explicit one-thread option was accepted and reported as **1**.
- The two 35-second diagnostic connections were opened serially, not as concurrent CPU-heavy benchmarks. Each intentionally added one temporary RTSP connection while the original production connection remained open. All diagnostic connections were closed afterward.
- A separate 35-second `flags=low_delay` trial retained 12 decoder threads and measured mean host-minus-OSD of **1.487 s** direct, **1.507 s** snapshot, and **1.507 s** MJPEG, with no read errors. It did not reproduce the one-thread improvement. Its settings and OSD results are retained under `low-delay-default-threads/`; this option was not selected. UDP was not tested or selected; TCP delivered continuously without observed read failures.

### Capture and latest-frame publication

The source already contains the previous restoration's continuous overwrite architecture: one native `latest_frame`, no capture FIFO, no fixed five-frame flush, and no JPEG compression in the capture loop. The still-running production process predates that restoration; its status payload lacks the new diagnostics. It was not silently treated as running the current source.

The five-minute probe extracted the current `LiveCameraMonitor` class without importing the app, models, repositories, or startup database routines. It ran only its capture thread and served its actual MJPEG generator over a loopback HTTP server. The production AI process remained running independently.

Sampled timing diagnostics:

| Timing | Mean | Maximum |
|---|---:|---:|
| Capture `read()` duration | 57.86 ms | 132.04 ms |
| Decoded-frame arrival interval | 58.25 ms | 132.25 ms |
| Decode completion to latest-slot publication | 0.32 ms | 1.03 ms |
| JPEG encode | 4.67 ms | 7.38 ms |
| Age of outgoing JPEG at send selection, measured since decode | 44.94 ms | 107.26 ms |
| Age at local HTTP receipt, measured since decode | 45.53 ms | 107.78 ms |
| Age of old cached JPEG when replaced, since its source decode | 153.61 ms | 217.92 ms |

These timings are sampled snapshots of the diagnostics, not every frame's duration. They are not substituted for the OSD comparison when assessing decoder backlog.

### JPEG cache and HTTP

- One encoded preview slot, keyed by source-frame sequence, replaces the previous JPEG. There is no JPEG queue.
- Preview consumers serialize on a preview-only lock. Encoding runs outside the capture lock. HTTP writes and generator yields occur after releasing that lock.
- `latest_preview_packet()` pins frame metadata to the JPEG bytes returned to a caller. This avoids labeling one encoded image with a different frame's time when consumers overlap.
- JPEG snapshots and MJPEG responses prevent caching. MJPEG now includes per-part `Content-Length`, frame sequence, decode time, encode time, and decode-to-send age. The existing `X-Accel-Buffering: no` is retained.
- A slow-consumer regression confirms that resuming after five new capture frames yields the newest frame sequence, rather than replaying queued images.

### Browser findings and limits

- The selected camera uses a single conditional MJPEG `<img>` keyed by its stream URL. Fallback still-image and annotated-image elements are alternate branches, not simultaneous primary streams.
- `stopDetection()` clears the MJPEG URL and preview blob; component unmount releases its DOM stream element. However, the still-image fetches lack abort/generation guards, so late results can update a preview after a source change. Overlapping polling can also complete out of order. These are source-level risks, not measured causes of this run's delay.
- Workspace camera tiles are **four-second polling snapshots**, not continuous MJPEG. A displayed tile can therefore be almost four seconds older than its most recent fetch, even when the decoder is current. This is an independent explanation for visibly stale tiles and should not be confused with selected-camera MJPEG buffering.
- The in-app browser failed to initialize with the previously observed missing `sandboxPolicy` connection error. Consequently browser display time, active DOM/network connection cleanup during a real reconnect, and the precise location of any remaining browser-side delay were not validated. No browser behavior was falsely claimed as fixed.
- Browser code was not changed during this investigation. The first measured accumulation point was addressed with the narrower decoder fix.

## Duplicate workers and CPU

A read-only SQLite query found one current source record: **CAM-30960048ED**. A read-only PostgreSQL query found one corresponding record, **ea01e0fa-f60d-43ad-b8f1-4bf370820d25**, with that legacy ID and the same host/path. The older historical camera IDs still occur in incident history but were not found as additional current camera records for this source.

The worker registry has a stream-URL key as well as camera-ID aliases and reuses a running worker for the same stream URL. Windows showed one production RTSP TCP connection throughout the unprobed periods. This does not establish anything about a separate Tapo mobile-app connection, which is outside this host's process inventory.

The production backend used roughly **119–122% process CPU** during the short comparisons (100% equals one core). The five-minute preview-only probe used **3.47% of one core** on average while the production AI process remained active. It maintained approximately 15 captured frames/sec. Thus these measurements support decoder pipeline depth, rather than sustained inability to consume the feed, as the first demonstrated delay source. No model, inference resolution, frequency, or thread settings inside YOLO were changed.

## Validation and deployment state

- **23 focused tests passed**, including single-thread decoder open parameters, pinned JPEG metadata, no-cache headers, latest-frame behavior with a slow MJPEG consumer, capture/JPEG independence, and existing camera/alarm restoration regressions.
- The test runner subsequently encountered a Windows file-lock error while removing its disposable `unit.sqlite`. All 23 assertions passed, but the overall runner did not exit cleanly; this is a cleanup limitation, not a clean command-level pass.
- The actual revised capture/JPEG/MJPEG source completed a **300-second** loopback HTTP test.
- The original backend process **has not been restarted**. The working-tree decoder change is staged in code, not silently injected into the running process. Restarting it would also activate pre-existing restoration changes, so the staged preview result and production observation are kept separate.
- Protected models, Phase 8C, existing validation datasets, credentials, PostgreSQL configuration, and camera records were not modified.

## Artifacts

- `default-threads/`: 35-second direct/default-decoder versus running HTTP comparison.
- `single-thread/`: paired comparison showing the one-second OSD advantage in 34/34 samples.
- `working-preview-5min/`: revised source class served over HTTP for five minutes, with OSD samples and timing headers.
- `low-delay-default-threads/`: isolated FFmpeg option diagnostic.
- `tests.txt`: focused regression output.
- `scripts/probe_preview_latency.py`, `scripts/probe_working_preview.py`, and `scripts/summarize_preview_osd.py`: read-only reproducible diagnostics.

**Remaining work:** activate the reviewed source in the intended deployment and measure the actual browser against the same camera OSD/stopwatch. The end-to-end three-second browser observation is not claimed fully resolved.
