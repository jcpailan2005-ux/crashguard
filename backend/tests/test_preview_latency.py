import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from fastapi.testclient import TestClient
import backend.main as app
from backend.tests.test_live_monitor_restoration import monitor


class PreviewLatencyTests(unittest.TestCase):
    def test_decoder_uses_measured_single_thread_open_parameters(self):
        m=monitor()
        m.running=True
        cap=MagicMock()
        cap.get.return_value=1
        def read():
            m.stop()
            return True,np.zeros((48,64,3),np.uint8)
        cap.read.side_effect=read
        with patch.object(app.cv2,'VideoCapture',return_value=cap),patch.object(app.time,'sleep'):
            m._capture_loop()
        cap.open.assert_called_once_with(m.stream_url,app.cv2.CAP_FFMPEG,[
            app.cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,app.cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000,
            app.cv2.CAP_PROP_N_THREADS,1])
        self.assertGreaterEqual(m.frame_published_at,m.last_frame_at)
        self.assertIsNotNone(m.capture_read_ms)

    def test_preview_packet_pins_metadata_to_cached_frame(self):
        m=monitor()
        m.seed_first_frame(np.zeros((48,64,3),np.uint8))
        first,headers=m.latest_preview_packet()
        self.assertEqual(headers['X-Frame-Sequence'],'1')
        self.assertEqual(float(headers['X-Frame-Decoded-At']),m.last_frame_at)
        m.seed_first_frame(np.ones((48,64,3),np.uint8)*180)
        second,next_headers=m.latest_preview_packet()
        self.assertNotEqual(first,second)
        self.assertEqual(next_headers['X-Frame-Sequence'],'2')
        self.assertEqual(headers['X-Frame-Sequence'],'1')

    def test_slow_mjpeg_consumer_resumes_with_latest_frame_not_queue(self):
        m=monitor()
        m.running=True
        m.seed_first_frame(np.zeros((48,64,3),np.uint8))
        stream=m.mjpeg_stream()
        first=next(stream)
        self.assertIn(b'X-Frame-Sequence: 1',first)
        for i in range(5): m.seed_first_frame(np.ones((48,64,3),np.uint8)*i)
        second=next(stream)
        self.assertIn(b'X-Frame-Sequence: 6',second)
        self.assertIn(b'Content-Length:',second)
        m.stop()
        stream.close()

    def test_snapshot_no_cache_headers_and_frame_metadata(self):
        m=monitor()
        m.seed_first_frame(np.zeros((48,64,3),np.uint8))
        with patch.object(app,'resolve_camera_identifier',return_value={'cameraId':'TEST'}), \
             patch.object(app,'require_camera_stream_access'),patch.object(app,'monitor_for_camera',return_value=m):
            response=TestClient(app.app).get('/api/cameras/TEST/latest-frame.jpg')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['pragma'],'no-cache')
        self.assertIn('max-age=0',response.headers['cache-control'])
        self.assertEqual(response.headers['x-frame-sequence'],'1')
