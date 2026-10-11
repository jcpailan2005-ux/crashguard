import asyncio
import threading
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException
import backend.main as app


class InferenceConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_video_work_does_not_block_health_and_concurrency_is_bounded(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_upload(_):
            entered.set()
            release.wait(5)
            raise HTTPException(400, 'Controlled test completed')

        principal = dict(id='USER', role='dispatcher', permissions=['cameras.monitor'])
        with patch('backend.phase3.service.authenticate_session', return_value=principal), \
             patch.object(app, 'save_upload_file', side_effect=slow_upload):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url='http://test') as client:
                client.cookies.set('crashguard_session', 'test')
                first = asyncio.create_task(client.post('/api/detect/video', files={'file':('test.mp4',b'test','video/mp4')}))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    health = await asyncio.wait_for(client.get('/api/health'), timeout=1)
                    self.assertEqual(health.status_code, 200)
                    second = await asyncio.wait_for(client.post('/api/detect/video', files={'file':('test.mp4',b'test','video/mp4')}), timeout=1)
                    self.assertEqual(second.status_code, 503)
                    self.assertFalse(first.done())
                finally:
                    release.set()
                    response = await first
                self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
