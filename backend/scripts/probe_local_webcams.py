"""Explicit, finite local-only webcam probe; discards pixels and runs no inference."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.services.camera_sources import CameraSourceSpec, WebcamCapture, LOCAL_WEBCAM_SOURCE

def probe(index, backend, seconds=2):
    spec = CameraSourceSpec(LOCAL_WEBCAM_SOURCE, 'webcam://diagnostic', index, backend)
    began = time.perf_counter()
    try:
        cap = WebcamCapture(spec)
    except ValueError:
        return dict(device_index=index, backend=backend, opened=False, decoded=False,
                    resolution=None, observed_fps=None, samples=0, stable=False,
                    error='Local webcam unavailable or busy')
    result = dict(device_index=index, backend=backend, opened=cap.isOpened(),
                  open_latency_ms=round((time.perf_counter()-began)*1000, 2), decoded=False,
                  resolution=None, observed_fps=None, samples=0, stable=True)
    try:
        if not cap.isOpened():
            result['stable'] = False
            return result
        started = time.perf_counter()
        first_sequence = None
        while time.perf_counter() - started < seconds:
            ok, frame = cap.read()
            if not ok:
                result['stable'] = False
                break
            result['decoded'] = True
            result['resolution'] = [int(frame.shape[1]), int(frame.shape[0])]
            result['samples'] += 1
            if first_sequence is None:
                first_sequence = cap.last_sequence
            result['observed_fps'] = round((cap.last_sequence-first_sequence)/max(.001, time.perf_counter()-started), 2)
            del frame
        result['reported_fps'] = cap.get(5)
    finally:
        released = time.perf_counter()
        cap.release()
        result['release_latency_ms'] = round((time.perf_counter()-released)*1000, 2)
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--indices', nargs='+', type=int, required=True)
    parser.add_argument('--seconds', type=float, default=2)
    args = parser.parse_args()
    if len(args.indices) > 4 or len(set(args.indices)) != len(args.indices) or any(not 0 <= i <= 31 for i in args.indices) or not .5 <= args.seconds <= 5:
        parser.error('Supply at most four distinct indices (0..31) and 0.5..5 seconds.')
    results = [probe(index, backend, args.seconds) for index in args.indices for backend in ('dshow', 'msmf')]
    print(json.dumps(results, indent=2))
