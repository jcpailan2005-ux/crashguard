"""Bounded, read-only camera benchmark. Never creates cases or updates camera records."""
import argparse
import contextlib
import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import threading
import time
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import backend.db as db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--output', required=True)
    parser.add_argument('--wait-ms', type=int)
    args = parser.parse_args()
    with sqlite3.connect(db.DATABASE_PATH.resolve().as_uri() + '?mode=ro', uri=True) as conn:
        row = conn.execute("SELECT cameraId,streamUrl FROM cameras WHERE streamUrl LIKE 'rtsp://%' LIMIT 1").fetchone()
    if not row:
        raise SystemExit('No configured RTSP feed.')
    # main imports initialize the legacy database; redirect those to disposable storage.
    with tempfile.TemporaryDirectory(prefix='crashguard-benchmark-') as temp:
        db.DATABASE_PATH = pathlib.Path(temp) / 'test.sqlite'
        with contextlib.redirect_stdout(io.StringIO()):
            import backend.main as app
        import cv2
        import psutil
        monitor = app.LiveCameraMonitor(monitor_key='benchmark', camera_id=row[0], camera_ip=None,
            stream_url=row[1], label='Read-only benchmark', area_id='test', barangay=None,
            road_name=None, latitude=None, longitude=None, location='Benchmark',
            redacted_stream_url='rtsp://redacted', output_base='http://testserver')
        encodes, inference_ms, inference_age, preview_age = [], [], [], []
        capture_stamps = set()
        original_encode = cv2.imencode
        def encode(*a, **kw):
            t = time.perf_counter()
            result = original_encode(*a, **kw)
            encodes.append((time.perf_counter()-t)*1000)
            return result
        original_decide = app.evaluate_crash_case_decision
        def no_persistence(**kw):
            kw['cooldown_ready'] = False
            return original_decide(**kw)
        monitor.running = True
        capture = threading.Thread(target=monitor._capture_loop, daemon=True)
        def preview():
            while monitor.running:
                monitor.latest_jpeg()
                with monitor.lock:
                    if monitor.last_frame_at:
                        capture_stamps.add(monitor.last_frame_at)
                        stamp = getattr(monitor, 'preview_frame_at', monitor.last_frame_at)
                        if stamp:
                            preview_age.append((time.time()-stamp)*1000)
                time.sleep(1/30)
        consumer = threading.Thread(target=preview, daemon=True)
        process = psutil.Process()
        cpu_start = sum(process.cpu_times()[:2])
        start = time.perf_counter()
        with patch.object(cv2, 'imencode', side_effect=encode), patch.object(app, 'evaluate_crash_case_decision', side_effect=no_persistence), patch.object(app, 'find_unresolved_camera_case', return_value=None), contextlib.redirect_stdout(io.StringIO()):
            capture.start()
            consumer.start()
            try:
                while time.perf_counter()-start < args.seconds:
                    wait_ms = app.LIVE_CAMERA_DETECTION_INTERVAL_MS if args.wait_ms is None else args.wait_ms
                    time.sleep(wait_ms/1000)
                    with monitor.lock:
                        stamp = monitor.last_frame_at
                    if stamp is None:
                        time.sleep(.01)
                        continue
                    t = time.perf_counter()
                    try:
                        monitor.analyze_current_frame(manual=False)
                    except ValueError:
                        continue
                    inference_ms.append((time.perf_counter()-t)*1000)
                    inference_age.append((time.time()-stamp)*1000-inference_ms[-1])
            finally:
                monitor.stop()
                consumer.join(timeout=3)
                capture.join(timeout=6)
        elapsed = time.perf_counter()-start
        avg = lambda xs: round(sum(xs)/len(xs), 2) if xs else None
        result = dict(durationSeconds=round(elapsed,2), framesObserved=len(capture_stamps),
            captureFps=round(getattr(monitor,'frame_seq',len(capture_stamps))/elapsed,2),
            captureFpsMethod='sequence count' if hasattr(monitor,'frame_seq') else '30 Hz timestamp sampling',
            inferenceCyclesPerSec=round(len(inference_ms)/elapsed,2), inferenceMs=avg(inference_ms),
            jpegEncodesPerSec=round(len(encodes)/elapsed,2), jpegEncodeMs=avg(encodes),
            previewFrameAgeMs=avg(preview_age), inferenceFrameAgeMs=avg(inference_age),
            processCpuPercent=round((sum(process.cpu_times()[:2])-cpu_start)/elapsed*100,2),
            sensorToBrowserLatency='unmeasured: timestamps begin after decode, no browser consumer',
            artificialWaitMs=args.wait_ms if args.wait_ms is not None else app.LIVE_CAMERA_DETECTION_INTERVAL_MS)
        pathlib.Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
