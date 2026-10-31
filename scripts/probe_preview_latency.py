"""Read-only comparison of camera OSD in direct RTSP and the running HTTP preview.

Saves only timestamp strips, never scene video. Does not import the AI app or write databases.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import urllib.request

import cv2
import numpy as np
import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=35)
    parser.add_argument('--threads', type=int)
    parser.add_argument('--transport', default='tcp', choices=['tcp', 'udp'])
    parser.add_argument('--low-delay', action='store_true')
    parser.add_argument('--name', required=True)
    parser.add_argument('--pid', type=int, default=3556)
    args = parser.parse_args()
    output = Path('docs/preview-latency') / args.name
    output.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(Path('data/crashguard.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as conn:
        cid, url = conn.execute("SELECT cameraId,streamUrl FROM cameras WHERE streamUrl LIKE '%192.168.1.17%/stream2' LIMIT 1").fetchone()
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
        f'rtsp_transport;{args.transport}|fflags;nobuffer|max_delay;500000' + ('|flags;low_delay' if args.low_delay else ''))
    cap = cv2.VideoCapture()
    params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]
    if args.threads is not None:
        params += [cv2.CAP_PROP_N_THREADS, args.threads]
    if not cap.open(url, cv2.CAP_FFMPEG, params):
        raise SystemExit('Direct RTSP could not be opened.')
    settings = dict(threads=cap.get(cv2.CAP_PROP_N_THREADS), fps=cap.get(cv2.CAP_PROP_FPS),
        bufferAccepted=cap.set(cv2.CAP_PROP_BUFFERSIZE, 1), transport=args.transport, lowDelay=args.low_delay)
    lock, stop = threading.Lock(), threading.Event()
    latest = None
    reads, rows, errors = [], [], []
    started = time.perf_counter()
    proc = psutil.Process(args.pid)
    cpu_start = sum(proc.cpu_times()[:2])
    def strip(frame, source, stamp, extra=None):
        filename = f'{source}-{stamp:.6f}.png'
        cv2.imwrite(str(output / filename), frame[:34, :510])
        rows.append(dict(file=filename, source=source, hostTime=stamp,
            hostIso=datetime.fromtimestamp(stamp).isoformat(), **(extra or {})))
    def capture():
        nonlocal latest
        while not stop.is_set():
            before = time.time()
            ok, frame = cap.read()
            received = time.time()
            if not ok:
                errors.append('direct_read_failed')
                break
            pts = cap.get(cv2.CAP_PROP_PTS)
            reads.append(dict(start=before, received=received, durationMs=(received-before)*1000, pts=pts))
            with lock:
                latest = frame, received, pts
    def mjpeg():
        last_saved, count = 0, 0
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:8010/api/cameras/{cid}/preview.mjpeg', timeout=5) as response:
                settings['mjpegHeaders'] = dict(response.headers)
                buf = b''
                while not stop.is_set():
                    chunk = response.read1(16384)
                    if not chunk: break
                    buf += chunk
                    while True:
                        start, end = buf.find(b'\xff\xd8'), buf.find(b'\xff\xd9')
                        if start < 0 or end < start: break
                        jpeg, buf = buf[start:end+2], buf[end+2:]
                        stamp = time.time()
                        count += 1
                        if stamp-last_saved >= 1:
                            frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                            if frame is not None: strip(frame, 'mjpeg', stamp)
                            last_saved = stamp
                    if len(buf) > 2_000_000:
                        raise ValueError('Unexpected oversized multipart frame')
        except Exception as e:
            errors.append('mjpeg_'+type(e).__name__)
        settings['mjpegFrames'] = count
    capture_thread = threading.Thread(target=capture, daemon=True)
    http_thread = threading.Thread(target=mjpeg, daemon=True)
    capture_thread.start()
    http_thread.start()
    try:
        while time.perf_counter()-started < args.seconds:
            stamp = time.time()
            with lock:
                item = latest
            if item:
                frame, received, pts = item
                strip(frame, 'direct', stamp, dict(received=received, pts=pts, decodedAgeMs=(stamp-received)*1000))
            before = time.time()
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:8010/api/cameras/{cid}/latest-frame.jpg?t={before}',timeout=3) as r:
                    jpeg = r.read()
                stamp = time.time()
                frame = cv2.imdecode(np.frombuffer(jpeg,np.uint8),cv2.IMREAD_COLOR)
                strip(frame,'snapshot',stamp,dict(requestMs=(stamp-before)*1000))
            except Exception as e:
                errors.append('snapshot_'+type(e).__name__)
            time.sleep(max(0,1-(time.time()-before)))
    finally:
        stop.set()
        capture_thread.join(6)
        http_thread.join(6)
        cap.release()
    elapsed = time.perf_counter()-started
    settings.update(duration=elapsed, captureFps=len(reads)/elapsed,
        previewFps=settings.get('mjpegFrames',0)/elapsed,
        runningBackendCpuPercent=(sum(proc.cpu_times()[:2])-cpu_start)/elapsed*100,
        cameraId=cid, errors=errors)
    (output/'samples.json').write_text(json.dumps(dict(settings=settings, reads=reads, samples=rows),indent=2))
    print(json.dumps(settings))


if __name__ == '__main__':
    main()
