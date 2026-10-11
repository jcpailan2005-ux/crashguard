"""Configured camera sources. No application/model/database imports or discovery.

Windows capture runs in a supervised child: native open/read can block without
honoring OpenCV timeouts. One shared native BGR slot replaces frames, never queues.
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import time

import cv2
import numpy as np

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'local_webcam_sources.json'
RTSP_NETWORK_SOURCE = 'network'
LOCAL_WEBCAM_SOURCE = 'webcam'
BACKENDS = {'dshow': cv2.CAP_DSHOW, 'msmf': cv2.CAP_MSMF}
ALIAS_PATTERN = re.compile(r'webcam://([a-z][a-z0-9-]{0,63})\Z')
MAX_BYTES = 4096 * 2160 * 3
OPEN_SECONDS = 15.0
READ_SECONDS = 2.0
MAX_ATTEMPTS = 5

@dataclass(frozen=True)
class CameraSourceSpec:
    source_type: str
    reference: str
    device_index: int | None = None
    backend: str | None = None
    friendly_name: str = 'Local Webcam'
    width: int | None = None
    height: int | None = None
    fps: float | None = None

def is_webcam_reference(value: str | None) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith('webcam:')

def _integer(value, low, high):
    return type(value) is int and low <= value <= high

def load_webcam_registry(path: Path | None = None) -> dict[str, CameraSourceSpec]:
    path = path or CONFIG_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or set(data) != {'sources'} or not isinstance(data['sources'], dict):
            raise ValueError
        sources = {}
        indices = set()
        for alias, entry in data['sources'].items():
            reference = 'webcam://' + alias
            if not ALIAS_PATTERN.fullmatch(reference) or not isinstance(entry, dict):
                raise ValueError
            if set(entry) - {'source_type', 'device_index', 'backend', 'friendly_name', 'width', 'height', 'fps'}:
                raise ValueError
            index = entry.get('device_index')
            if entry.get('source_type') != LOCAL_WEBCAM_SOURCE or not _integer(index, 0, 31) or index in indices:
                raise ValueError
            if entry.get('backend') not in BACKENDS:
                raise ValueError
            name = entry.get('friendly_name', 'Local Webcam')
            if not isinstance(name, str) or not 1 <= len(name) <= 80 or any(ord(c) < 32 for c in name):
                raise ValueError
            width, height, fps = entry.get('width'), entry.get('height'), entry.get('fps')
            if width is not None and not _integer(width, 1, 4096):
                raise ValueError
            if height is not None and not _integer(height, 1, 2160):
                raise ValueError
            if fps is not None and (type(fps) not in (int, float) or not math.isfinite(fps) or not 0 < fps <= 120):
                raise ValueError
            sources[reference] = CameraSourceSpec(LOCAL_WEBCAM_SOURCE, reference, index,
                                                  entry['backend'], name, width, height, fps)
            indices.add(index)
        return sources
    except (ValueError, TypeError, OSError, KeyError):
        raise ValueError('Local webcam configuration is invalid.') from None

def resolve_source(reference: str, network_validator=None, path: Path | None = None) -> CameraSourceSpec:
    if is_webcam_reference(reference):
        if not ALIAS_PATTERN.fullmatch(reference):
            raise ValueError('Invalid configured webcam reference.')
        source = load_webcam_registry(path).get(reference)
        if source is None:
            raise ValueError('Local webcam source is not configured.')
        return source
    if network_validator is None:
        raise ValueError('Only configured local webcam references are accepted.')
    network_validator(reference)
    return CameraSourceSpec('demo' if reference.startswith('demo://') else RTSP_NETWORK_SOURCE, reference)

class DeviceLease:
    """Machine-local device exclusion, including independent backend processes.

    Index is deliberately conservative across Windows APIs. Registry disallows
    aliases sharing an index. This does not identify hardware after reordering.
    """
    def __init__(self, index: int):
        self.handle = None
        self.file = None
        if os.name == 'nt':
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle.restype = wintypes.BOOL
            self.kernel = kernel
            handle = kernel.CreateMutexW(None, False, f'Local\\CrashGuard-Webcam-{index}')
            if not handle:
                raise ValueError('Local webcam is unavailable.')
            if ctypes.get_last_error() == 183:
                kernel.CloseHandle(handle)
                raise ValueError('Local webcam is unavailable or busy.')
            self.handle = handle
        else:
            import fcntl
            import tempfile
            self.file = open(Path(tempfile.gettempdir()) / f'crashguard-webcam-{index}.lock', 'a+b')
            try:
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.file.close()
                self.file = None
                raise ValueError('Local webcam is unavailable or busy.') from None

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        if self.file is not None:
            self.file.close()
            self.file = None

def _capture_child(spec, pixels, info, lock, available, stopped):
    cap = None
    lease = None
    try:
        lease = DeviceLease(spec.device_index)
        cap = cv2.VideoCapture(spec.device_index, BACKENDS[spec.backend])
        if not cap.isOpened():
            return
        for prop, value in [(cv2.CAP_PROP_FRAME_WIDTH, spec.width),
                            (cv2.CAP_PROP_FRAME_HEIGHT, spec.height), (cv2.CAP_PROP_FPS, spec.fps)]:
            if value is not None:
                cap.set(prop, value)
        reported = cap.get(cv2.CAP_PROP_FPS)
        destination = np.frombuffer(pixels, dtype=np.uint8)
        while not stopped.is_set():
            ok, frame = cap.read()
            received, monotonic = time.time(), time.monotonic()
            if not ok or frame is None:
                break
            if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or frame.size > MAX_BYTES:
                break
            h, w = frame.shape[:2]
            if h <= 0 or w <= 0 or w > 4096 or h > 2160:
                break
            with lock:
                destination[:frame.size] = frame.reshape(-1)
                info[0] += 1
                info[1:6] = [w, h, received, monotonic, reported]
                info[6] = 1
            available.set()
    except Exception:
        # No device/driver errors or local paths cross the public boundary.
        pass
    finally:
        if cap is not None:
            cap.release()
        if lease is not None:
            lease.close()
        with lock:
            info[6] = -1
        available.set()

class WebcamCapture:
    """Bounded OpenCV-like adapter over a single shared latest-frame slot."""
    def __init__(self, spec: CameraSourceSpec, *, target=None, open_seconds=OPEN_SECONDS, read_seconds=READ_SECONDS):
        if spec.source_type != LOCAL_WEBCAM_SOURCE or spec.backend not in BACKENDS or not _integer(spec.device_index, 0, 31):
            raise ValueError('Invalid configured webcam source.')
        self.spec = spec
        ctx = mp.get_context('spawn')
        self.pixels = ctx.RawArray('B', MAX_BYTES)
        self.info = ctx.RawArray('d', 7)
        self.lock = ctx.Lock()
        self.available = ctx.Event()
        self.stopped = ctx.Event()
        self.process = ctx.Process(target=target or _capture_child,
                                   args=(spec, self.pixels, self.info, self.lock, self.available, self.stopped),
                                   daemon=True, name='configured-webcam-capture')
        self.last_sequence = 0
        self.received_at = self.received_monotonic = None
        self.read_seconds = read_seconds
        self.closed = False
        try:
            self.process.start()
            self.available.wait(open_seconds)
            self.opened = self.process.is_alive() and self.info[6] == 1
            if not self.opened:
                self.release()
        except Exception:
            self.release()
            raise ValueError('Local webcam is unavailable.') from None

    def isOpened(self):
        return not self.closed and self.opened and self.process.is_alive() and self.info[6] == 1

    def get(self, prop):
        return self.info[5] if prop == cv2.CAP_PROP_FPS else 0

    def read(self):
        deadline = time.monotonic() + self.read_seconds
        while not self.closed and time.monotonic() < deadline:
            if not self.process.is_alive() or self.info[6] < 0:
                return False, None
            if self.lock.acquire(timeout=min(.1, max(0, deadline - time.monotonic()))):
                try:
                    sequence = int(self.info[0])
                    if self.info[6] == 1 and sequence > self.last_sequence:
                        w, h = int(self.info[1]), int(self.info[2])
                        frame = np.frombuffer(self.pixels, dtype=np.uint8, count=w*h*3).reshape(h, w, 3).copy()
                        self.last_sequence = sequence
                        self.received_at, self.received_monotonic = self.info[3], self.info[4]
                        return True, frame
                finally:
                    self.lock.release()
            self.available.clear()
            self.available.wait(min(.05, max(0, deadline - time.monotonic())))
        return False, None

    def release(self):
        if self.closed:
            return
        self.closed = True
        self.stopped.set()
        if self.process.pid is not None:
            self.process.join(1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(1)
            if self.process.is_alive():
                raise ValueError('Local webcam capture could not be stopped.')

def open_webcam(spec: CameraSourceSpec) -> WebcamCapture:
    return WebcamCapture(spec)
