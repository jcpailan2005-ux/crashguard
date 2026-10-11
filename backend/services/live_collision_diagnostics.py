"""Opt-in, best-effort telemetry. Never supplies inputs to collision decisions.

Only the decorated RTSP worker activates the context; shared detector helpers
remain silent for uploads/offline callers. No pixels, URLs, exception text or
arbitrary payload dictionaries cross this module's output boundary.
"""
from contextvars import ContextVar
from functools import wraps
import json
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid

import numpy as np


DIRECTORY = Path(__file__).resolve().parents[1] / 'validation' / 'live_collision_diagnostics'
MAX_BYTES = 16 * 1024 * 1024
BACKUPS = 2
_current = ContextVar('live_collision_diagnostic', default=None)
_sink = None
_sink_lock = threading.Lock()
_run_id = uuid.uuid4().hex
_frame_sink = None
_frame_sink_lock = threading.Lock()


def _identifier(value):
    # Do not fall back to a monitor key, URL, label, or IP address.
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value) else None


def _label(value):
    return value if value in {
        'car', 'motorcycle', 'bus', 'truck', 'bicycle', 'vehicle', 'van',
        'suv', 'automobile', 'auto', 'person',
    } else 'other_class'


def _box(box):
    return [float(box[k]) for k in ('x', 'y', 'width', 'height')]


def _streak(window):
    count = 0
    for _, hit in reversed(window):
        if not hit:
            break
        count += 1
    return count


class RotatingSink:
    """Bound disk and queue; the inference thread never writes or waits on disk."""

    def __init__(self, directory=DIRECTORY, max_bytes=MAX_BYTES, backups=BACKUPS):
        self.directory = Path(directory)
        self.max_bytes = max_bytes
        self.backups = backups
        self.pending = queue.Queue(maxsize=8)
        self.dropped = 0
        self.write_errors = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name='collision-diagnostics')
        self.thread.start()

    def submit(self, record):
        try:
            self.pending.put_nowait(record)
        except queue.Full:
            self.dropped += 1

    def _run(self):
        handler = None
        while True:
            record = self.pending.get()
            try:
                if record is None:
                    return
                record['diagnostic_records_dropped'] = self.dropped
                record['diagnostic_write_errors'] = self.write_errors
                line = json.dumps(record, separators=(',', ':'), allow_nan=False)
                if len(line.encode('utf-8')) + 1 > self.max_bytes:
                    self.dropped += 1
                    continue
                if handler is None:
                    self.directory.mkdir(parents=True, exist_ok=True)
                    handler = RotatingFileHandler(
                        self.directory / 'observations.jsonl', maxBytes=self.max_bytes,
                        backupCount=self.backups, encoding='utf-8', delay=True,
                    )
                    # Avoid logging framework stderr messages containing a record.
                    handler.handleError = lambda _: self._write_error()
                handler.emit(logging.LogRecord('collision-diagnostic', logging.INFO, '', 0, line, (), None))
            except Exception:
                self._write_error()
            finally:
                self.pending.task_done()
                if record is None and handler is not None:
                    handler.close()

    def _write_error(self):
        self.write_errors += 1


def _get_sink():
    global _sink
    if _sink is None:
        with _sink_lock:
            if _sink is None:
                _sink = RotatingSink()
    return _sink


class SynchronizedFrameSink:
    """Bounded, lossless decision-frame archive; never feeds production decisions."""

    MAX_FRAMES = 1200
    MAX_BYTES = 3 * 1024 * 1024 * 1024
    MAX_SECONDS = 15 * 60
    MAX_ERROR_EVENTS = 32

    def __init__(self, directory=None):
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        self.directory = Path(directory) if directory else DIRECTORY / f'physical_pair_capture_{stamp}_{_run_id[:8]}'
        self.pending = queue.Queue(maxsize=8)
        self.dropped = 0
        self.write_errors = 0
        self.saved = 0
        self.bytes_saved = 0
        self.first_decision_time = None
        self.first_observation_sequence = None
        self.camera_id = None
        self.last_sequence = None
        self._stage = 'idle'
        self.thread = threading.Thread(target=self._run, daemon=True, name='synchronized-collision-frames')
        self.thread.start()

    def submit(self, record, frame):
        try:
            self.pending.put_nowait((record.copy(), frame))
        except queue.Full:
            self.dropped += 1

    def _manifest(self):
        return {
            'schema_version': 1, 'run_id': _run_id,
            'capture_kind': 'native_decision_frame_lossless_npy',
            'saved_frames': self.saved, 'saved_bytes': self.bytes_saved,
            'camera_id': self.camera_id,
            'first_decision_time': self.first_decision_time,
            'first_observation_sequence': self.first_observation_sequence,
            'diagnostic_records_dropped': self.dropped,
            'diagnostic_write_errors': self.write_errors,
            'last_observation_sequence': self.last_sequence,
            'max_frames': self.MAX_FRAMES, 'max_bytes': self.MAX_BYTES,
            'max_seconds': self.MAX_SECONDS,
        }

    def _write_manifest(self):
        temporary = self.directory / 'manifest.json.tmp'
        self._stage = 'manifest_temp_write'
        temporary.write_text(json.dumps(self._manifest(), separators=(',', ':')), encoding='utf-8')
        self._stage = 'manifest_replace'
        temporary.replace(self.directory / 'manifest.json')

    def _record_write_error(self, error, sequence):
        """Record only fixed diagnostic fields; never serialize exception paths or payloads."""
        self.write_errors += 1
        if self.write_errors > self.MAX_ERROR_EVENTS:
            return
        errno = getattr(error, 'errno', None)
        winerror = getattr(error, 'winerror', None)
        message = os.strerror(errno) if isinstance(errno, int) and errno > 0 else 'diagnostic writer operation failed'
        event = {
            'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'observation_sequence': sequence,
            'stage': self._stage,
            'exception_type': type(error).__name__,
            'message': message,
            'errno': errno if isinstance(errno, int) else None,
            'winerror': winerror if isinstance(winerror, int) else None,
        }
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / 'writer_errors.jsonl').open('a', encoding='utf-8') as output:
                output.write(json.dumps(event, separators=(',', ':')) + '\n')
        except OSError:
            pass  # Error visibility must never affect production decisions.

    def _run(self):
        while True:
            item = self.pending.get()
            sequence = None
            try:
                if item is None:
                    return
                record, frame = item
                self._stage = 'record_metadata'
                sequence = int(record['observation_sequence'])
                timestamp = float(record['decision_time'])
                if self.first_decision_time is None:
                    self.first_decision_time = timestamp
                    self.first_observation_sequence = int(record['observation_sequence'])
                    self.camera_id = record.get('camera_id')
                if (self.saved >= self.MAX_FRAMES or
                        timestamp - self.first_decision_time > self.MAX_SECONDS or
                        self.bytes_saved + frame.nbytes + 1024 > self.MAX_BYTES):
                    self.dropped += 1
                    continue
                self._stage = 'directory_create'
                self.directory.mkdir(parents=True, exist_ok=True)
                frames_dir = self.directory / 'frames'
                frames_dir.mkdir(exist_ok=True)
                save_started = time.perf_counter()
                camera = record.get('camera_id') or 'unknown'
                name = f'obs_{camera}_{sequence:08d}_{int(timestamp * 1_000_000)}.npy'
                destination = frames_dir / name
                temporary = frames_dir / (name + '.tmp')
                self._stage = 'frame_write'
                with temporary.open('wb') as output:
                    np.save(output, frame, allow_pickle=False)
                self._stage = 'frame_stat'
                size = temporary.stat().st_size
                if self.bytes_saved + size > self.MAX_BYTES:
                    temporary.unlink()
                    self.dropped += 1
                    continue
                self._stage = 'frame_hash'
                digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
                self._stage = 'frame_replace'
                temporary.replace(destination)
                self._stage = 'record_serialize'
                record.update(frame_file=f'frames/{name}', frame_sha256=digest,
                              frame_shape=list(frame.shape), frame_dtype=str(frame.dtype),
                              frame_bytes=size, frame_capture_status='saved',
                              frame_save_duration_ms=(time.perf_counter() - save_started) * 1000,
                              frame_writer_dropped=self.dropped,
                              frame_writer_errors=self.write_errors)
                line = json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n'
                self._stage = 'jsonl_append'
                with (self.directory / 'observations.jsonl').open('a', encoding='utf-8') as output:
                    output.write(line)
                self.saved += 1
                self.bytes_saved += size
                self.last_sequence = sequence
                self._write_manifest()
            except Exception as error:
                self._record_write_error(error, sequence)
                # Never let diagnostic disk failures reach the live worker.
            finally:
                self.pending.task_done()


def _get_frame_sink():
    global _frame_sink
    if _frame_sink is None:
        with _frame_sink_lock:
            if _frame_sink is None:
                _frame_sink = SynchronizedFrameSink()
    return _frame_sink


class Observation:
    def __init__(self, monitor):
        self.monitor = monitor
        self.proposal_ids = {}
        self.current_pass = None
        self.frame = None
        self.record = {
            'schema_version': 1, 'run_id': _run_id,
            'camera_id': _identifier(monitor.camera_id),
            'vehicles': [], 'detector_passes': [], 'evaluated_pairs': [],
            'ids_are_observation_local': True, 'telemetry_complete': True,
        }

    def begin(self, sequence, received_at):
        now = time.time()
        previous = getattr(self.monitor, '_diagnostic_previous_start', None)
        self.monitor._diagnostic_previous_start = now
        self.record.update(observation_sequence=sequence, frame_receive_time=received_at,
                           inference_start=now,
                           seconds_since_previous_analyzed_observation=None if previous is None else now - previous)
        self.started = time.perf_counter()

    def frame_snapshot(self, frame):
        if os.getenv('LIVE_COLLISION_FRAME_CAPTURE', '0') != '1':
            return
        started = time.perf_counter()
        # The worker already copied this native BGR image outside its capture
        # lock. This second copy freezes the exact inference input before any
        # downstream library has a chance to mutate it.
        self.frame = frame.copy()
        self.record['frame_snapshot_copy_ms'] = (time.perf_counter() - started) * 1000

    def inference_end(self):
        self.record.update(inference_end=time.time(),
                           inference_duration_ms=(time.perf_counter() - self.started) * 1000)

    def detector(self, source):
        self.current_pass = len(self.record['detector_passes'])
        self.record['detector_passes'].append({'pass': self.current_pass, 'source': source})

    def vehicle(self, raw_box, label, threshold, reason, accepted_box=None):
        # Values come from the actual branch taken by the production extractor.
        index = len(self.record['vehicles'])
        item = dict(id=index, detector_pass=self.current_pass, class_name=_label(label),
                    confidence=float(raw_box.conf[0].item()),
                    raw_bbox_xyxy=[float(v) for v in raw_box.xyxy[0].tolist()],
                    acceptance_threshold=threshold, accepted=reason is None,
                    rejection_reason=reason)
        if accepted_box is not None:
            item['bbox_xywh'] = _box(accepted_box)
            self.proposal_ids[id(accepted_box)] = index
        self.record['vehicles'].append(item)

    def roi(self, before, after):
        kept = {id(box) for box in after}
        for box in before:
            index = self.proposal_ids.get(id(box))
            if index is not None and id(box) not in kept:
                self.record['vehicles'][index].update(accepted=False, rejection_reason='vehicle_outside_roi')
        # Pair indices refer to this exact final list, not stable track identities.
        self.record['accepted_vehicles'] = [dict(index=i, proposal_id=self.proposal_ids.get(id(box)),
            class_name=_label(box['label']), confidence=float(box['confidence']), bbox_xywh=_box(box))
            for i, box in enumerate(after)]

    def pair(self, index_a, index_b, iou, distance, scale):
        vehicles = self.record['accepted_vehicles']
        self.record['evaluated_pairs'].append(dict(
            vehicle_indices=[index_a, index_b], iou=iou, edge_distance=distance,
            classes=[vehicles[index_a]['class_name'], vehicles[index_b]['class_name']],
            boxes_xywh=[vehicles[index_a]['bbox_xywh'], vehicles[index_b]['bbox_xywh']],
            scale=scale, normalized_edge_distance=distance / scale,
            required_iou=0.08, maximum_normalized_edge_distance=0.05,
            qualifies=iou >= 0.08 or distance / scale <= 0.05,
        ))

    def before(self, window):
        self.record['window_before'] = list(window)
        self.record['streak_before'] = _streak(window)

    def decision(self, payload, window, observation_qualified, window_seconds, window_time):
        r = self.record
        before = r['streak_before']
        after = payload['consecutiveCrashHits']
        failures = []
        if payload['frameQualityStatus'] != 'good':
            failures.append(payload['qualityRejectionReason'] or 'low_quality_frame')
        if not payload['passedThreshold']:
            failures.append('below_case_threshold')
        if payload['vehicleCount'] <= 0:
            failures.append('no_vehicle_detected')
        if not payload['sceneValid']:
            failures.append('vehicle_outside_roi')
        expired = sum(window_time - t > window_seconds for t, _ in r['window_before'])
        # State expiry can prevent a qualified observation from incrementing.
        reset_reasons = failures if before and not observation_qualified else []
        if before and after < before + int(observation_qualified) and expired:
            reset_reasons = [*reset_reasons, 'temporal_window_expired']
        if payload['finalDecision'] == 'confirmed_crash':
            action = 'CONFIRM'
        elif reset_reasons:
            action = 'RESET'
        elif after > before:
            action = 'START' if before == 0 else 'INCREMENT'
        else:
            action = 'UNCHANGED'
        r.update(timestamp=payload['timestamp'], decision_time=time.time(),
                 candidate_analyzing=payload['finalDecision'] in {'candidate', 'verifying'},
                 final_decision=payload['finalDecision'], rejection_reason=payload['rejectionReason'],
                 accident_detected=payload['temporalCrashVerified'],
                 temporal_verified=payload['temporalCrashVerified'],
                 motion_valid=payload['motionValid'], scene_valid=payload['sceneValid'],
                 vehicle_count=payload['vehicleCount'], frame_quality_status=payload['frameQualityStatus'],
                 blur_score=payload['blurScore'], brightness_score=payload['brightnessScore'],
                 contrast_score=payload['contrastScore'],
                 quality_rejection_reason=payload['qualityRejectionReason'],
                 classifier_score=payload['accidentProbability'],
                 classifier_case_threshold=payload['caseThreshold'], classifier_passed=payload['passedThreshold'],
                 classifier_ui_threshold=payload['uiThreshold'],
                 observation_qualified=bool(observation_qualified), qualification_failures=failures,
                 streak_after=after, required_consecutive_hits=payload['requiredConsecutiveCrashHits'],
                 streak_action=action, reset_reasons=reset_reasons,
                 temporal_window_seconds=window_seconds, window_evaluated_at=window_time,
                 window_after=list(window), expired_observations=expired)


def emit(method, *args):
    observation = _current.get()
    if observation is None:
        return
    try:
        if method == 'decision':
            observation.record['decision_boundary_reached'] = True
        getattr(observation, method)(*args)
    except Exception:
        observation.record['telemetry_complete'] = False


def observe(function):
    @wraps(function)
    def wrapped(monitor, *args, **kwargs):
        if os.getenv('LIVE_COLLISION_DIAGNOSTICS', '0') != '1':
            return function(monitor, *args, **kwargs)
        try:
            sink = _get_sink()
            observation = Observation(monitor)
            token = _current.set(observation)
        except Exception:
            return function(monitor, *args, **kwargs)
        try:
            return function(monitor, *args, **kwargs)
        finally:
            _current.reset(token)
            # Stale/busy/repeated frames are not decision observations.
            if observation.record.get('decision_boundary_reached'):
                try:
                    sink.submit(observation.record)
                except Exception:
                    pass  # Diagnostic failure never changes the operational result.
                if observation.frame is not None:
                    try:
                        _get_frame_sink().submit(observation.record, observation.frame)
                    except Exception:
                        pass
    return wrapped
