"""Bound shared model use without queueing unlimited inference jobs."""
import functools
import threading
from collections import OrderedDict
from collections.abc import Callable

from fastapi import HTTPException


_inference_lock = threading.RLock()


class FairLatestFrameScheduler:
    """One pending latest-frame request per camera, served round-robin.

    Re-submitting a camera replaces its pending work without moving it behind
    newer cameras. Queue size is therefore bounded by the number of cameras.
    """

    def __init__(self, *, autostart: bool = True):
        self._condition = threading.Condition()
        self._pending: OrderedDict[str, tuple[str, int, Callable[[], None]]] = OrderedDict()
        self._stopped = False
        self._thread = None
        if autostart:
            self._thread = threading.Thread(
                target=self._run,
                name="shared-camera-inference",
                daemon=True,
            )
            self._thread.start()

    def submit(self, camera_id: str, session_id: str, sequence: int, callback: Callable[[], None]) -> bool:
        if not camera_id or not session_id or sequence < 1:
            return False
        with self._condition:
            if self._stopped:
                return False
            current = self._pending.get(camera_id)
            if current and current[0] == session_id and current[1] >= sequence:
                return False
            # Assignment preserves an existing OrderedDict position, giving a
            # slower camera already waiting its turn ahead of repeat submits.
            self._pending[camera_id] = (session_id, sequence, callback)
            self._condition.notify()
        return True

    def cancel(self, camera_id: str, session_id: str | None = None) -> None:
        with self._condition:
            current = self._pending.get(camera_id)
            if current and (session_id is None or current[0] == session_id):
                self._pending.pop(camera_id, None)

    def run_next(self) -> tuple[str, str, int] | None:
        with self._condition:
            if not self._pending:
                return None
            camera_id, (session_id, sequence, callback) = self._pending.popitem(last=False)
        callback()
        return camera_id, session_id, sequence

    def pending_count(self) -> int:
        with self._condition:
            return len(self._pending)

    def _run(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._stopped or bool(self._pending))
                if self._stopped:
                    return
            try:
                self.run_next()
            except Exception:
                # A camera/model failure is isolated; the next camera still runs.
                continue


live_camera_inference_scheduler = FairLatestFrameScheduler()


def bounded_inference(function):
    @functools.wraps(function)
    def run(*args, **kwargs):
        if not _inference_lock.acquire(blocking=False):
            raise HTTPException(status_code=503, detail='Detection is busy. Please retry shortly.',
                                headers={'Retry-After': '1'})
        try:
            return function(*args, **kwargs)
        finally:
            _inference_lock.release()
    return run
