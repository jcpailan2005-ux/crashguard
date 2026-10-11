"""Deterministic source/security/driver-lifecycle tests; no app or devices opened."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from backend.services import camera_sources as sources

def synthetic_child(spec, pixels, info, lock, available, stopped):
    lease = sources.DeviceLease(spec.device_index)
    try:
        array = np.frombuffer(pixels, dtype=np.uint8)
        while not stopped.is_set():
            with lock:
                info[0] += 1
                array[:64*48*3] = int(info[0]) % 255
                info[1:7] = [64, 48, time.time(), time.monotonic(), 100, 1]
            available.set()
            stopped.wait(.01)
    finally:
        lease.close()

def failed_child(spec, pixels, info, lock, available, stopped):
    info[6] = -1
    available.set()

def blocked_child(spec, pixels, info, lock, available, stopped):
    time.sleep(60)

def blocked_read_child(spec, pixels, info, lock, available, stopped):
    synthetic = np.frombuffer(pixels, dtype=np.uint8)
    synthetic[:64*48*3] = 10
    info[:] = [1, 64, 48, time.time(), time.monotonic(), 30, 1]
    available.set()
    time.sleep(60)

def spec(index=31):
    return sources.CameraSourceSpec(sources.LOCAL_WEBCAM_SOURCE, 'webcam://test', index, 'dshow')

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'sources.json'
        self.entry = dict(source_type='webcam', device_index=2, backend='dshow', friendly_name='Test camera')
        self.write()

    def write(self):
        self.path.write_text(json.dumps({'sources': {'test': self.entry}}))

    def test_resolves_explicit_nonzero_index(self):
        result = sources.resolve_source('webcam://test', path=self.path)
        self.assertEqual((result.device_index, result.backend, result.friendly_name), (2, 'dshow', 'Test camera'))

    def test_integer_bounds_and_metadata(self):
        for index in (0, 31):
            self.entry['device_index'] = index
            self.write()
            self.assertEqual(sources.resolve_source('webcam://test', path=self.path).device_index, index)
        for index in (-1, 32, '0', True, 1.5, None):
            self.entry['device_index'] = index
            self.write()
            with self.assertRaises(ValueError):
                sources.resolve_source('webcam://test', path=self.path)

    def test_rejects_arbitrary_sources_and_decorated_aliases(self):
        for reference in ['0', '-1', 'C:\\private\\video.mp4', '/dev/video0', 'http://evil/camera',
                          'rtsp://evil/camera', 'powershell.exe', 'webcam://0', 'webcam://unknown',
                          'webcam://test/path', 'webcam://test?index=0', 'webcam://test#x',
                          'webcam://user:pass@test', 'webcam://test:1', 'WEBCAM://test', ' webcam://test']:
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                sources.resolve_source(reference, path=self.path)

    def test_rejects_unsafe_config_backend_paths_and_credentials(self):
        for key, value in [('backend', 'ffmpeg'), ('backend', 'CAP_DSHOW'), ('device_index', 'http://evil'),
                           ('path', 'C:\\secret'), ('cameraPassword', 'secret'), ('fps', float('nan')),
                           ('width', 4097), ('height', -1), ('friendly_name', 'name\nsecret')]:
            with self.subTest(key=key):
                entry = dict(self.entry, **{key: value})
                self.path.write_text(json.dumps({'sources': {'test': entry}}))
                with self.assertRaises(ValueError):
                    sources.load_webcam_registry(self.path)

    def test_duplicate_device_aliases_rejected(self):
        self.path.write_text(json.dumps({'sources': {'test': self.entry, 'other': self.entry}}))
        with self.assertRaises(ValueError):
            sources.load_webcam_registry(self.path)

    def test_network_source_uses_original_validator(self):
        validator = Mock()
        url = 'rtsp://operator:secret@192.168.1.2/stream2'
        result = sources.resolve_source(url, validator)
        validator.assert_called_once_with(url)
        self.assertEqual((result.reference, result.source_type), (url, sources.RTSP_NETWORK_SOURCE))
        validator.side_effect = ValueError('rejected')
        with self.assertRaises(ValueError):
            sources.resolve_source('/secret.mp4', validator)

    def test_child_opener_receives_integer_and_explicit_backend(self):
        cap = Mock()
        cap.read.return_value = (False, None)
        cap.get.return_value = 30
        from multiprocessing import get_context
        ctx = get_context('spawn')
        with patch.object(sources, 'DeviceLease') as lease, patch.object(sources.cv2, 'VideoCapture', return_value=cap) as open_device:
            sources._capture_child(spec(2), ctx.RawArray('B', sources.MAX_BYTES), ctx.RawArray('d', 7),
                                   ctx.Lock(), ctx.Event(), ctx.Event())
            open_device.assert_called_once_with(2, cv2.CAP_DSHOW)
            cap.release.assert_called_once()
            lease.return_value.close.assert_called_once()

    def test_device_lease_rejects_second_owner_then_releases(self):
        first = sources.DeviceLease(31)
        try:
            with self.assertRaises(ValueError):
                sources.DeviceLease(31)
        finally:
            first.close()
        second = sources.DeviceLease(31)
        second.close()

    def test_latest_shared_slot_no_backlog_and_release(self):
        cap = sources.WebcamCapture(spec(), target=synthetic_child)
        try:
            self.assertTrue(cap.isOpened())
            ok, first = cap.read()
            self.assertTrue(ok)
            sequence = cap.last_sequence
            time.sleep(.1)
            ok, latest = cap.read()
            self.assertTrue(ok)
            self.assertGreater(cap.last_sequence, sequence + 1)
            self.assertEqual(latest.shape, (48, 64, 3))
            self.assertFalse(np.shares_memory(first, latest))
            self.assertAlmostEqual(cap.received_at, time.time(), delta=.3)
        finally:
            cap.release()
        self.assertFalse(cap.process.is_alive())

    def test_open_failure_is_unavailable_and_released(self):
        cap = sources.WebcamCapture(spec(), target=failed_child)
        self.assertFalse(cap.isOpened())
        self.assertEqual(cap.read(), (False, None))
        self.assertFalse(cap.process.is_alive())

    def test_blocked_driver_open_has_deadline(self):
        began = time.monotonic()
        cap = sources.WebcamCapture(spec(), target=blocked_child, open_seconds=.1)
        self.assertFalse(cap.isOpened())
        self.assertFalse(cap.process.is_alive())
        self.assertLess(time.monotonic() - began, 3)

    def test_blocked_driver_read_does_not_return_stale_pixels(self):
        cap = sources.WebcamCapture(spec(), target=blocked_read_child, read_seconds=.1)
        try:
            self.assertTrue(cap.read()[0])
            self.assertEqual(cap.read(), (False, None))
        finally:
            cap.release()
        self.assertFalse(cap.process.is_alive())

if __name__ == '__main__':
    unittest.main()
