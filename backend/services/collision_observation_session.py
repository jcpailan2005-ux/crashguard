"""Connect real tracked observations to the existing collision verifiers.

Predictions, stale display packets and classifier-only streaks supply no motion
proof. Histories belong to one capture epoch and one frame geometry.
"""
from __future__ import annotations

import uuid
from collections import deque

from backend.services.crash_aftermath_detector import CrashAftermathDetector, estimate_scene_abnormality
from backend.services.collision_pair_classifier import VEHICLE_LABELS as ROAD_COLLISION_LABELS
from backend.services.pair_hit_ledger import PairHitLedger
from backend.services.temporal_crash_verifier import TemporalCrashVerifier
from backend.services.vehicle_tracking import TrackState


class CollisionObservationSession:
    def __init__(self, camera_id: str, *, required_hits=3, window_seconds=5.0, classifier_threshold=.90):
        self.camera_id = camera_id
        self.required_hits = required_hits
        self.window_seconds = window_seconds
        self.classifier_threshold = classifier_threshold
        self.identity = None
        self.reset()

    def reset(self):
        self.temporal = TemporalCrashVerifier()
        self.aftermath = CrashAftermathDetector()
        self.ledger = PairHitLedger(required_hits=self.required_hits, window_seconds=self.window_seconds)
        self.tracks = {}
        self.last_sequence = -1
        self.last_timestamp = None
        self.events = []
        self.reported_interactions = deque(maxlen=64)

    def observe(self, *, session_id, sequence, timestamp, boxes, frame_width,
                frame_height, classifier_score, frame_quality_status="good", scene_valid=True):
        identity = (session_id, frame_width, frame_height)
        if identity != self.identity:
            self.reset()
            self.identity = identity
        if sequence <= self.last_sequence or (
            self.last_timestamp is not None and timestamp < self.last_timestamp
        ):
            raise ValueError("Collision observations must be ordered and unique")
        if self.last_timestamp is not None and timestamp == self.last_timestamp:
            self.last_sequence = sequence
            # Distinct frame packets can share a coarse capture timestamp.
            # Display remains valid, but zero elapsed time cannot prove motion.
            return {
                "temporalCrashVerified": False, "temporalCrashCandidate": False,
                "temporalCrashScore": 0.0, "temporalEvidence": {},
                "temporalRejectionReason": "non_advancing_capture_timestamp",
                "involvedTrackIds": [], "trackingSessionId": session_id,
                "pairQualifiedHits": 0, "aftermathCandidate": False,
                "aftermathReason": "non_advancing_capture_timestamp",
                "detectorEventId": str(uuid.uuid5(uuid.NAMESPACE_OID, repr(self.identity))),
            }
        self.last_sequence, self.last_timestamp = sequence, timestamp
        usable = frame_quality_status == "good" and scene_valid
        if not usable:
            # Poor frames cannot contaminate approach/stop histories on recovery.
            self.tracks.clear()
            self.temporal.reset_all()
            self.aftermath.reset_all()
            self.ledger.reset()
        expired = [key for key, track in self.tracks.items() if timestamp-track.last_seen_at > 1.5]
        for key in expired:
            self.tracks.pop(key)
            self.ledger.expire_track(key)
        self.temporal.expire_track_ids(self.camera_id, expired)
        active = []
        for box in boxes if usable else ():
            if box.get('label') not in ROAD_COLLISION_LABELS:
                continue
            if not box.get("detected", False) or box.get("observationKind") != "DETECTED":
                continue
            track_id = int(box["trackId"])
            track = self.tracks.get(track_id)
            if track is None:
                track = TrackState.create(track_id=track_id, camera_id=self.camera_id,
                    class_id=-1, class_name=box["label"], history_size=16, timestamp=timestamp)
                self.tracks[track_id] = track
            track.add_observation(timestamp=timestamp,
                bbox=(box["x"], box["y"], box["x"]+box["width"], box["y"]+box["height"]),
                confidence=box["confidence"], frame_width=frame_width, frame_height=frame_height)
            active.append(track)
        temporal = self.temporal.analyze(self.camera_id, active,
            classifier_score=classifier_score, frame_width=frame_width,
            frame_height=frame_height, timestamp=timestamp,
            reported_interactions=frozenset(self.reported_interactions))
        self.ledger.expire(timestamp)
        pair_states = {}
        for interaction in self.temporal.get_interactions(self.camera_id):
            if interaction.last_observed_at != timestamp:
                continue
            pair = (interaction.track_a, interaction.track_b)
            pair_states[pair] = self.ledger.observe(pair, sequence=sequence, timestamp=timestamp,
                qualified=bool(classifier_score >= self.classifier_threshold or (
                    temporal.is_verified and pair == temporal.involved_track_ids)),
                classifier_score=classifier_score,
                geometry=interaction.possible_contact_at is not None,
                interaction=interaction.approach_detected)
        pair = temporal.involved_track_ids
        verified = bool(usable and temporal.is_verified and self.ledger.ready(pair)) if len(pair)==2 else False
        aftermath = self.aftermath.observe(self.camera_id, classifier_score=classifier_score,
            vehicle_count=len(active), active_tracks=active, scene_valid=scene_valid,
            frame_quality_status=frame_quality_status, scene_abnormality_score=estimate_scene_abnormality(active),
            temporal_collision_active=temporal.is_verified, timestamp=timestamp)
        event_pair = pair if verified else aftermath.track_ids
        event_time = temporal.contact_timestamp if verified else round(timestamp-aftermath.persistence_seconds, 6)
        # Stable through repeated reads and save retries; separate observed events
        # receive separate keys even while another dispatcher review is pending.
        event_id = str(uuid.uuid5(uuid.NAMESPACE_OID,
            repr((self.camera_id, session_id, event_pair, event_time))))
        involved = list(pair)
        if verified:
            signature = (pair, temporal.contact_timestamp)
            if signature not in self.reported_interactions:
                self.reported_interactions.append(signature)
            self.events = [event for event in self.events if timestamp-event['last_at'] <= self.window_seconds]
            related = next((event for event in self.events
                if event['tracks'].intersection(pair)
                and abs(event['contact_at']-event_time) <= self.temporal.config.post_contact_window_seconds), None)
            if related is None:
                related = {'id':event_id, 'tracks':set(pair), 'contact_at':event_time, 'last_at':timestamp}
                self.events.append(related)
                self.events = self.events[-64:]
            else:
                related['tracks'].update(pair)
                related['last_at'] = timestamp
            event_id = related['id']
            involved = sorted(related['tracks'])
        return {
            "temporalCrashVerified": verified, "temporalCrashCandidate": temporal.is_candidate,
            "temporalCrashScore": temporal.score, "temporalEvidence": temporal.evidence,
            "temporalRejectionReason": temporal.reason,
            "involvedTrackIds": involved, "verifiedPairTrackIds": list(pair), "trackingSessionId": session_id,
            "pairQualifiedHits": pair_states[pair].streak if pair in pair_states else 0,
            "aftermathCandidate": bool(usable and aftermath.review_candidate),
            "aftermathReason": aftermath.reason, "detectorEventId": event_id,
        }


class AnalyzedCollisionSession:
    """Isolated tracker/verifier for uploaded clips and browser camera frames."""
    def __init__(self, *, required_hits=3, window_seconds=5.0, classifier_threshold=.90):
        from backend.services.session_vehicle_tracking import SessionVehicleTracker
        self.camera_id, self.session_id = uuid.uuid4().hex, uuid.uuid4().hex
        self.tracker = SessionVehicleTracker(self.camera_id, self.session_id)
        self.verifier = CollisionObservationSession(self.camera_id,
            required_hits=required_hits, window_seconds=window_seconds, classifier_threshold=classifier_threshold)
        self.sequence = 0

    def observe(self, frame, boxes, *, timestamp, classifier_score,
                frame_quality_status="good", scene_valid=True):
        self.sequence += 1
        height, width = frame.shape[:2]
        tracking = self.tracker.update(self.session_id, self.sequence, timestamp, boxes,
            frame_width=width, frame_height=height, source_frame=frame)
        return self.verifier.observe(session_id=self.session_id, sequence=self.sequence,
            timestamp=timestamp, boxes=tracking.boxes, frame_width=width, frame_height=height,
            classifier_score=classifier_score, frame_quality_status=frame_quality_status,
            scene_valid=scene_valid)
