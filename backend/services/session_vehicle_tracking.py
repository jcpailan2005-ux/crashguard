"""Bounded session-owned association of already accepted detector observations.

No inference, classifier, collision decisions, or preview propagation occurs here.
Uncertain associations start new identities rather than assert a physical handoff.
"""
from __future__ import annotations

import math
import re
from statistics import median
import time
from collections import deque
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import cv2
from scipy.optimize import linear_sum_assignment

from backend.services.vehicle_tracking import TrackState, VehicleTrackingService


@dataclass(frozen=True)
class SessionTrackingConfig:
    max_tracks: int = 256
    history_size: int = 16
    max_missed_frames: int = 4
    max_age_seconds: float = 1.5
    prediction_seconds: float = 0.75
    max_center_distance: float = 0.30  # Prediction residual / smaller box diagonal.
    max_size_ratio: float = 1.35
    max_aspect_ratio: float = 1.25
    min_predicted_iou: float = 0.25
    max_association_seconds: float = 0.65
    bootstrap_seconds: float = 0.40
    missed_association_seconds: float = 0.60
    bootstrap_center_distance: float = 0.20
    max_appearance_distance: float = 0.08
    max_anchor_distance: float = 0.10
    duplicate_iou: float = 0.75
    missed_observed_iou: float = 0.25
    ambiguity_margin: float = 0.10
    continuity_seconds: float = 1.25
    continuity_missed_seconds: float = 2.25
    continuity_speed: float = 1.25  # Observed displacement / smaller diagonal / second.
    continuity_max_displacement: float = 2.5
    continuity_appearance: float = 0.05
    continuity_appearance_margin: float = 0.025

    def __post_init__(self):
        if self.max_tracks < 1 or self.history_size < 2 or self.max_missed_frames < 1:
            raise ValueError("Tracking state bounds must be positive; history needs two entries")
        values = (self.max_age_seconds, self.prediction_seconds,
                  self.max_center_distance, self.max_size_ratio, self.ambiguity_margin,
                  self.max_aspect_ratio, self.max_association_seconds,
                  self.bootstrap_seconds, self.missed_association_seconds,
                  self.bootstrap_center_distance, self.max_appearance_distance,
                  self.max_anchor_distance, self.continuity_seconds,
                  self.continuity_missed_seconds, self.continuity_speed,
                  self.continuity_max_displacement, self.continuity_appearance,
                  self.continuity_appearance_margin)
        if not all(math.isfinite(x) and x > 0 for x in values) or self.max_size_ratio <= 1:
            raise ValueError("Tracking association bounds must be finite and positive")
        if not 0 < self.missed_observed_iou <= 1:
            raise ValueError("Miss recovery needs a positive observed-box overlap gate")
        if not 0 < self.min_predicted_iou <= 1 or not 0 < self.duplicate_iou <= 1:
            raise ValueError("Overlap gates must be in (0, 1]")


@dataclass(frozen=True)
class TrajectoryPoint:
    timestamp: float
    sequence: int
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    width: float
    height: float
    detected: bool
    velocity: tuple[float, float]


@dataclass
class SessionTrack:
    state: TrackState
    history: deque[TrajectoryPoint]
    lifecycle: str = "NEW"
    missed_frames: int = 0
    velocity: tuple[float, float] = (0.0, 0.0)
    last_detected_sequence: int = -1
    appearance: np.ndarray | None = None
    appearance_anchor: np.ndarray | None = None
    unresolved_origin: bool = False


@dataclass(frozen=True)
class SessionTrackingResult:
    boxes: tuple[dict, ...]
    predicted_tracks: tuple[dict, ...]
    retired_track_ids: tuple[int, ...]
    tracking_ms: float
    association_diagnostics: tuple[dict, ...] = ()


class SessionVehicleTracker:
    """Owned/serialized by one live worker's lock; never a global ID registry.

    reset is a lifecycle operation, never triggered by an arriving frame. A late
    session therefore cannot roll a current tracker back to a retired session.
    Integer IDs are local and meaningful only with camera_id and session_id.
    """

    def __init__(self, camera_id: str, session_id: str,
                 config: SessionTrackingConfig | None = None, *, diagnostics: bool = False):
        self.camera_id = camera_id
        self.config = config or SessionTrackingConfig()
        self.diagnostics = diagnostics
        self.reset(session_id)

    def reset(self, session_id: str | None):
        self.session_id = session_id
        self.tracks: dict[int, SessionTrack] = {}
        self.next_id = 1
        self.last_sequence = -1
        self.last_timestamp: float | None = None
        self.frame_shape: tuple[int, int] | None = None
        self.previous_gray: np.ndarray | None = None
        self.gray_scale: float = 1.0

    def _pixel_motion(self, candidates, boxes, gray, scale, eligible):
        """Bounded forward/backward sparse flow; no model or extra inference.

        At most 512 feature points, eight per candidate hypothesis. A single
        grayscale analyzed frame (longest side 640) is retained per session.
        Missing, weak, or inconsistent feature motion supplies no identity proof.
        """
        offsets = np.full((len(candidates), len(boxes), 2), np.nan)
        if (gray is None or self.previous_gray is None or gray.shape != self.previous_gray.shape
                or scale != self.gray_scale):
            return offsets
        points, initial, owners = [], [], []
        for index, track in enumerate(candidates):
            if len(points) >= 512:
                break
            if (track.last_detected_sequence != self.last_sequence or track.appearance is None
                    or not np.any(eligible[index])):
                continue
            x1,y1,x2,y2 = track.state.bbox
            x1,y1,x2,y2 = (int(v*scale) for v in (x1+(x2-x1)*.2,y1+(y2-y1)*.2,
                                                x2-(x2-x1)*.2,y2-(y2-y1)*.2))
            if x1 < 0 or y1 < 0 or x2 > gray.shape[1] or y2 > gray.shape[0] or min(x2-x1,y2-y1) < 8:
                continue
            corners = cv2.goodFeaturesToTrack(self.previous_gray[y1:y2,x1:x2],
                maxCorners=8, qualityLevel=.03, minDistance=3, blockSize=3)
            if corners is not None and len(corners) >= 3:
                corners = corners.reshape(-1,2)+np.asarray([x1,y1])
                for column in np.flatnonzero(eligible[index]):
                    if len(points)+len(corners) > 512:
                        break
                    old = np.asarray(track.state.bbox)*scale
                    new = np.asarray(boxes[column])*scale
                    # Boxes seed a hypothesis; bidirectional features verify it.
                    seeded = (corners-old[:2])/(old[2:]-old[:2])*(new[2:]-new[:2])+new[:2]
                    points.extend(corners)
                    initial.extend(seeded)
                    owners.extend([(index,column)]*len(corners))
        if not points:
            return offsets
        points = np.asarray(points,dtype=np.float32).reshape(-1,1,2)
        initial = np.asarray(initial,dtype=np.float32).reshape(-1,1,2)
        options = dict(winSize=(21,21),maxLevel=4,
                       criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01),
                       flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
        following, forward, forward_error = cv2.calcOpticalFlowPyrLK(self.previous_gray,gray,points,initial,**options)
        if following is None:
            return offsets
        back, backward, backward_error = cv2.calcOpticalFlowPyrLK(gray,self.previous_gray,following,points.copy(),**options)
        if back is None:
            return offsets
        following, back, points = (p.reshape(-1,2) for p in (following,back,points))
        valid = ((forward[:,0] == 1) & (backward[:,0] == 1)
                 & np.all(np.isfinite(following),axis=1)
                 & (np.linalg.norm(back-points,axis=1) <= 1.5)
                 & (forward_error[:,0] <= 14) & (backward_error[:,0] <= 14)
                 & (following[:,0]>=0) & (following[:,0]<gray.shape[1])
                 & (following[:,1]>=0) & (following[:,1]<gray.shape[0]))
        owners = np.asarray(owners)
        for index,column in sorted(set(map(tuple,owners))):
            track = candidates[index]
            selected = (owners[:,0] == index) & (owners[:,1] == column)
            accepted = selected & valid
            if accepted.sum() < max(3, math.ceil(selected.sum()*.6)):
                continue
            movements = (following[accepted]-points[accepted])/scale
            motion = np.median(movements,axis=0)
            x1,y1,x2,y2 = track.state.bbox
            spread = np.median(np.linalg.norm(movements-motion,axis=1)) / max(1,math.hypot(x2-x1,y2-y1))
            if spread <= .10:
                offsets[index,column] = motion
        return offsets

    def _prediction(self, track: SessionTrack, timestamp: float):
        dt = min(max(0.0, timestamp - track.state.last_seen_at), self.config.prediction_seconds)
        dx, dy = (v * dt for v in track.velocity)
        x1, y1, x2, y2 = track.state.bbox
        # An extrapolation cannot authorize a distant jump after lost observations.
        limit = math.hypot(x2-x1, y2-y1) * 0.5
        length = math.hypot(dx, dy)
        if length > limit:
            dx, dy = dx*limit/length, dy*limit/length
        return x1 + dx, y1 + dy, x2 + dx, y2 + dy

    @staticmethod
    def _geometry(a, b):
        aw, ah = a[..., 2]-a[..., 0], a[..., 3]-a[..., 1]
        bw, bh = b[..., 2]-b[..., 0], b[..., 3]-b[..., 1]
        intersection = np.maximum(0, np.minimum(a[..., 2], b[..., 2])-np.maximum(a[..., 0], b[..., 0])) * np.maximum(
            0, np.minimum(a[..., 3], b[..., 3])-np.maximum(a[..., 1], b[..., 1]))
        iou = intersection / np.maximum(1.0, aw*ah+bw*bh-intersection)
        displacement = np.hypot((a[..., 0]+a[..., 2]-b[..., 0]-b[..., 2])/2,
                                (a[..., 1]+a[..., 3]-b[..., 1]-b[..., 3])/2)
        distance = displacement / np.maximum(1.0, np.minimum(np.hypot(aw, ah), np.hypot(bw, bh)))
        size = np.maximum.reduce([aw/bw, bw/aw, ah/bh, bh/ah])
        aspect = np.maximum((aw/ah)/(bw/bh), (bw/bh)/(aw/ah))
        return iou, distance, size, aspect, displacement

    @staticmethod
    def _appearances(frame, boxes):
        """Batch nine bounded Lab statistics; no learned model or crops retained."""
        result = [None] * len(boxes)
        if frame is None:
            return result
        crops, indices = [], []
        for index, bbox in enumerate(boxes):
            x1, y1, x2, y2 = bbox
            width, height = x2-x1, y2-y1
            # Border truncation or tiny crops cannot supply reliable evidence.
            if x1 < 0 or y1 < 0 or x2 > frame.shape[1] or y2 > frame.shape[0]:
                continue
            x1, y1 = int(x1+width*.20), int(y1+height*.20)
            x2, y2 = int(x2-width*.20), int(y2-height*.20)
            if x2-x1 < 6 or y2-y1 < 6:
                continue
            crops.append(cv2.resize(frame[y1:y2, x1:x2], (12, 12), interpolation=cv2.INTER_AREA))
            indices.append(index)
        if crops:
            # One color conversion and percentile pass for all small crops.
            lab = cv2.cvtColor(np.concatenate(crops, axis=0), cv2.COLOR_BGR2LAB).reshape(len(crops), 144, 3)
            signatures = np.quantile(lab, [.25, .50, .75], axis=1).transpose(1, 0, 2).reshape(-1, 9)
            for index, signature in zip(indices, (signatures/255).astype(np.float32)):
                result[index] = signature
        return result

    def _association(self, candidates, boxes, labels, appearances, timestamp, pixels_required, gray, gray_scale):
        a = np.asarray([self._prediction(t, timestamp) for t in candidates])[:, None, :]
        b = np.asarray(boxes)[None, :, :]
        iou, distance, size, aspect, displacement = self._geometry(a, b)
        observed = np.asarray([t.state.bbox for t in candidates])[:, None, :]
        old_iou, old_distance, _, _, _ = self._geometry(observed, b)
        elapsed = np.asarray([timestamp-t.state.last_seen_at for t in candidates])[:, None]
        misses = np.asarray([t.missed_frames for t in candidates])[:, None]
        bootstrap = np.asarray([len(t.state.history) < 2 for t in candidates])[:, None]
        # Missing observations narrow the residual gate, never expand it.
        center_limit = np.where(bootstrap, self.config.bootstrap_center_distance,
                                self.config.max_center_distance) / (1+misses*.5)
        gates = {
            "class": np.asarray([t.state.class_name for t in candidates])[:, None] == np.asarray(labels)[None, :],
            "elapsed": elapsed <= self.config.max_association_seconds+1e-9,
            "bootstrap_gap": ~bootstrap | (elapsed <= self.config.bootstrap_seconds+1e-9),
            "missed_gap": (misses == 0) | (elapsed <= self.config.missed_association_seconds+1e-9),
            "size": size <= self.config.max_size_ratio,
            "aspect": aspect <= self.config.max_aspect_ratio,
            "motion": distance <= center_limit,
            "overlap": iou >= self.config.min_predicted_iou,
            "missed_overlap": (misses == 0) | (old_iou >= self.config.missed_observed_iou),
        }
        appearance_distance = np.zeros_like(iou)
        anchor_distance = np.zeros_like(iou)
        available = np.zeros_like(iou, dtype=bool)
        old_indices = [i for i, t in enumerate(candidates) if t.appearance is not None]
        new_indices = [i for i, appearance in enumerate(appearances) if appearance is not None]
        if old_indices and new_indices:
            old = np.asarray([candidates[i].appearance for i in old_indices])
            anchor = np.asarray([candidates[i].appearance_anchor for i in old_indices])
            new = np.asarray([appearances[i] for i in new_indices])
            at = np.ix_(old_indices, new_indices)
            # A strong change in any median channel rejects a color/brightness
            # replacement; the average also rejects changes in color distribution.
            delta = np.abs(old[:, None, :]-new[None, :, :])
            appearance_distance[at] = np.maximum(delta.mean(axis=2), delta[:, :, 3:6].max(axis=2))
            delta = np.abs(anchor[:, None, :]-new[None, :, :])
            anchor_distance[at] = np.maximum(delta.mean(axis=2), delta[:, :, 3:6].max(axis=2))
            available[at] = True
        need = pixels_required or any(t.appearance is not None for t in candidates)
        gates["appearance_available"] = available if need else np.ones_like(available)
        gates["appearance"] = appearance_distance <= self.config.max_appearance_distance
        gates["appearance_anchor"] = anchor_distance <= self.config.max_anchor_distance
        valid = np.ones_like(iou, dtype=bool)
        for gate in gates.values():
            valid &= gate
        score = .55*(1-iou)+.30*distance/self.config.max_center_distance
        score += .15*appearance_distance/self.config.max_appearance_distance
        cadence = (elapsed > self.config.bootstrap_seconds) & (elapsed <= self.config.continuity_missed_seconds)
        moving_bootstrap = bootstrap & available & (old_distance > .10)
        if (not np.any(cadence) and not np.any(moving_bootstrap)) or not np.any(available):
            # High-cadence/geometry-only observations cannot use the stronger
            # path. Avoid its extra pair matrices and ownership comparisons.
            empty = np.zeros_like(valid)
            return np.where(valid,score,1e6), dict(iou=iou,old_iou=old_iou,
                distance=displacement,predicted=a[:,0,:],elapsed=elapsed,
                appearance=appearance_distance,anchor=anchor_distance,gates=gates,
                old_distance=old_distance,scale=size,aspect=aspect,slow_error=distance,
                slow_distance=displacement,slow_prediction=a,use_slow=empty,
                slow_gates=dict(cadence=cadence,pixels=available),
                continuity_ambiguous=empty,flow_available=empty,flow_error=old_distance,slow_iou=iou)
        # A longer cadence never authorizes geometry-only continuation. Bootstrap
        # needs verified pixel motion; established motion can support lost overlap.
        # Verified bootstrap motion also supports a fast but significant jump;
        # evidence strength must not disappear just below the cadence boundary.
        trained = ~bootstrap
        gap_limit = np.where((misses == 1) & trained, self.config.continuity_missed_seconds,
                             self.config.continuity_seconds)
        velocity = np.asarray([t.velocity for t in candidates])[:, None, :]
        displacement_limit = np.minimum(self.config.continuity_max_displacement,
                                        .10+self.config.continuity_speed*elapsed)
        eligible = (gates['class'] & gates['size'] & gates['aspect'] & available
                    & (appearance_distance <= np.where(moving_bootstrap & (elapsed <= self.config.bootstrap_seconds),
                                                       self.config.max_appearance_distance,self.config.continuity_appearance))
                    & (old_distance <= displacement_limit)
                    & ((elapsed > self.config.bootstrap_seconds) | moving_bootstrap)
                    & (elapsed <= self.config.continuity_seconds) & (misses == 0))
        flow = self._pixel_motion(candidates,boxes,gray,gray_scale,eligible) if np.any(eligible) else np.full((*iou.shape,2),np.nan)
        flow_available = np.all(np.isfinite(flow),axis=2)
        shift = np.where(bootstrap[...,None], np.nan_to_num(flow), velocity*elapsed[...,None])
        slow_prediction = observed + np.concatenate([shift, shift], axis=2)
        slow_iou, slow_error, _, _, slow_pixels = self._geometry(slow_prediction, b)
        flow_prediction = observed + np.tile(np.nan_to_num(flow),(1,1,2))
        _, flow_error, _, _, _ = self._geometry(flow_prediction,b)
        residual_limit = np.minimum(.35, .15+.15*elapsed) / (1+misses*.5)
        slow_gates = {
            "cadence": (cadence | moving_bootstrap) & (elapsed <= gap_limit+1e-9),
            "observed_motion": old_distance <= displacement_limit,
            "prediction": np.where(bootstrap, slow_error <= .20, slow_error <= residual_limit),
            "pixel_motion": np.where(bootstrap, flow_available,
                                      ~flow_available | (flow_error <= .25)),
            "miss_budget": (misses == 0) | ((misses == 1) & trained),
            "class": gates["class"], "size": gates["size"], "aspect": gates["aspect"],
            "pixels": available,
            "appearance": appearance_distance <= self.config.continuity_appearance,
            "anchor": anchor_distance <= self.config.max_anchor_distance,
        }
        plausible = np.ones_like(valid)
        for name, gate in slow_gates.items():
            if name not in ("appearance", "anchor", "pixel_motion"):
                # Without an established trajectory, even a nonoverlapping
                # neighboring track/detection can be a plausible ownership rival.
                if name == "prediction":
                    plausible &= np.where(bootstrap, ~flow_available | (slow_error <= .30),
                                          slow_error <= residual_limit*1.5)
                else:
                    plausible &= gate
        plausible &= gates["appearance"] & gates["appearance_anchor"]
        # Consider weaker but plausible rivals too: falling just outside a strict
        # appearance threshold must not manufacture unique ownership. Motion gates
        # may exclude a rival only if its actual learned trajectory disagrees.
        rivals = np.where(plausible, appearance_distance, np.inf)
        row_second = np.full((len(candidates), 1), np.inf)
        col_second = np.full((1, len(boxes)), np.inf)
        if len(boxes) > 1:
            row_second[:, 0] = np.partition(rivals, 1, axis=1)[:, 1]
        if len(candidates) > 1:
            col_second[0] = np.partition(rivals, 1, axis=0)[1]
        slow_gates["unique_appearance"] = (
            (appearance_distance < rivals.min(axis=1)[:, None]+1e-9)
            & (appearance_distance < rivals.min(axis=0)[None, :]+1e-9)
            & (row_second-appearance_distance >= self.config.continuity_appearance_margin)
            & (col_second-appearance_distance >= self.config.continuity_appearance_margin))
        # Broad geometry is ONLY a rejection shadow, never a continuation gate.
        # Bootstrap direction is unknown, so tighter thresholds must not hide
        # another nearby physical owner just outside those acceptance bounds.
        shadow = (gates['class'] & (size <= 1.8) & (aspect <= 1.5)
                  & (old_distance <= np.minimum(2.5,.10+2.1*elapsed))
                  & (elapsed <= self.config.continuity_seconds) & (misses <= 1)
                  & (~available | (appearance_distance <= .25)))
        slow_gates['bootstrap_ownership'] = ~bootstrap | ((np.sum(shadow,axis=1)[:,None] == 1)
                                                         & (np.sum(shadow,axis=0)[None,:] == 1))
        # Live review also found a silver-to-silver transfer inside the original
        # 0.40 s bootstrap window. Moving pixel-backed bootstraps need verified
        # motion and unambiguous wider ownership at short gaps as well.
        fast_bootstrap_safe = (~moving_bootstrap | (flow_available & (flow_error <= .20)
                                                    & slow_gates['bootstrap_ownership']))
        gates['bootstrap_pixel_motion'] = fast_bootstrap_safe
        fast_ambiguous = valid & moving_bootstrap & flow_available & ~slow_gates['bootstrap_ownership']
        valid &= fast_bootstrap_safe
        slow_valid = np.ones_like(valid)
        for name, gate in slow_gates.items():
            if name not in ("unique_appearance", "bootstrap_ownership"):
                slow_valid &= gate
        ownership_unique = slow_gates["unique_appearance"] & slow_gates["bootstrap_ownership"]
        slow_ambiguous = (slow_valid & ~ownership_unique & ~np.any(valid, axis=1)[:, None]) | fast_ambiguous
        slow_valid &= ownership_unique
        slow_score = (.25*(1-slow_iou)+.30*np.where(bootstrap, slow_error/.20,
                                                  slow_error/residual_limit)
                      + .35*appearance_distance/self.config.continuity_appearance
                      + .10*(size-1)/(self.config.max_size_ratio-1))
        use_slow = slow_valid & ~valid
        # Diagnostics report the accepted path; failed edges retain both paths'
        # reasons. Ownership ambiguity/duplicate rejection still happens globally.
        effective_gates = {key: value | use_slow for key, value in gates.items()}
        return np.where(valid | slow_valid, np.where(use_slow, slow_score, score), 1e6), dict(iou=iou, old_iou=old_iou,
            distance=displacement, predicted=a[:, 0, :], elapsed=elapsed,
            appearance=appearance_distance, anchor=anchor_distance, gates=effective_gates,
            old_distance=old_distance, scale=size, aspect=aspect, slow_error=slow_error,
            slow_distance=slow_pixels, slow_prediction=slow_prediction,
            use_slow=use_slow, slow_gates=slow_gates, continuity_ambiguous=slow_ambiguous,
            flow_available=flow_available, flow_error=flow_error, slow_iou=slow_iou)

    def _diagnostic_rows(self, candidates, boxes, costs, metrics, matches, timestamp, sequence):
        # Opt-in, at most 64 nearest edges. Never serializes source detections,
        # frames, URLs, exception text, credentials, or arbitrary caller fields.
        if not self.diagnostics:
            return ()
        safe = lambda value: value if isinstance(value, str) and re.fullmatch(r"[\w-]{1,80}", value) else "redacted"
        rows = []
        for r, track in enumerate(candidates):
            for c in np.argsort(metrics["distance"][r], kind="stable")[:2]:
                if len(rows) >= 64:
                    return tuple(rows)
                box = boxes[c]
                use_slow = bool(metrics['use_slow'][r,c])
                predicted = metrics["slow_prediction"][r,c] if use_slow else metrics["predicted"][r]
                rejected = [key for key, values in metrics["gates"].items()
                            if not np.broadcast_to(values, costs.shape)[r, c]]
                rows.append(dict(camera_id=safe(self.camera_id), session_id=safe(self.session_id),
                    sequence=int(sequence), track_id=track.state.track_id,
                    previous_bbox=list(track.state.bbox), candidate_bbox=list(box),
                    iou=float(metrics["slow_iou" if use_slow else "iou"][r, c]),
                    observed_iou=float(metrics['old_iou'][r,c]),
                    center_distance=float(metrics["slow_distance" if use_slow else "distance"][r, c]),
                    predicted_center=[float((predicted[0]+predicted[2])/2), float((predicted[1]+predicted[3])/2)],
                    actual_center=[(box[0]+box[2])/2, (box[1]+box[3])/2],
                    elapsed_seconds=float(timestamp-track.state.last_seen_at),
                    track_age_seconds=float(timestamp-track.state.first_seen_at), miss_count=track.missed_frames,
                    vehicle_class=safe(track.state.class_name), competing_tracks=int(np.sum(costs[:, c] < 1e6)),
                    competing_detections=int(np.sum(costs[r] < 1e6)), association_cost=float(costs[r, c]),
                    appearance_distance=float(metrics["appearance"][r, c]),
                    normalized_displacement=float(metrics["old_distance"][r, c]),
                    normalized_prediction_error=float(metrics["slow_error"][r, c]),
                    size_ratio=float(metrics["scale"][r, c]), aspect_ratio=float(metrics["aspect"][r, c]),
                    ambiguity_margin=self.config.ambiguity_margin,
                    pixel_motion_available=bool(metrics['flow_available'][r,c]),
                    pixel_motion_error=float(metrics['flow_error'][r,c]),
                    continuation_path="pixel_motion" if metrics["use_slow"][r, c] else "short_gap",
                    ownership_ambiguous=bool(metrics['continuity_ambiguous'][r, c]),
                    slow_rejected_gates=[key for key, values in metrics["slow_gates"].items()
                        if not np.broadcast_to(values, costs.shape)[r, c]],
                    rejected_gates=rejected, matched=matches.get(int(c)) is track))
        return tuple(rows)

    def _packet(self, track: SessionTrack, bbox, *, detected: bool, sequence: int, timestamp: float):
        x1, y1, x2, y2 = bbox
        return dict(cameraId=self.camera_id, sessionId=self.session_id,
                    trackId=track.state.track_id, label=track.state.class_name,
                    confidence=track.state.confidence, x=x1, y=y1, width=x2-x1, height=y2-y1,
                    sequence=sequence, capturedMonotonic=timestamp,
                    lastDetectedSequence=track.last_detected_sequence,
                    observationKind="DETECTED" if detected else "PREDICTED",
                    detected=detected, collisionObservation=detected, trackLifecycle=track.lifecycle)

    def update(self, session_id: str, sequence: int, timestamp: float,
               detections: Sequence[Mapping], *, frame_width: int, frame_height: int,
               source_frame: np.ndarray | None = None):
        started = time.perf_counter()
        if session_id != self.session_id or self.session_id is None:
            raise ValueError("Discarded tracker observation from retired camera session")
        if (sequence <= self.last_sequence or not math.isfinite(timestamp)
                or (self.last_timestamp is not None and timestamp < self.last_timestamp)):
            raise ValueError("Duplicate or late tracker observation")
        if frame_width <= 0 or frame_height <= 0 or len(detections) > self.config.max_tracks:
            raise ValueError("Tracking frame exceeds bounded capacity or has invalid dimensions")
        if source_frame is not None and (source_frame.shape != (frame_height, frame_width, 3)
                                        or source_frame.dtype != np.uint8):
            raise ValueError("Tracking appearance needs the exact uint8 BGR source frame")
        # Reuse the existing tested detector-coordinate parser and TrackState.
        boxes = [VehicleTrackingService._xyxy(d) for d in detections]
        if any(not all(math.isfinite(v) for v in b) or b[2] <= b[0] or b[3] <= b[1] for b in boxes):
            raise ValueError("Invalid accepted vehicle box")
        labels = [str(d.get("label") or "vehicle").lower() for d in detections]
        appearances = self._appearances(source_frame, boxes)
        # Duplicate/near-identical boxes remain detector observations. Their
        # unresolved ownership must never seed or inherit continued identities.
        duplicates = np.zeros(len(boxes), dtype=bool)
        if len(boxes) > 1:
            arr = np.asarray(boxes)
            overlap, _, _, _, _ = self._geometry(arr[:, None, :], arr[None, :, :])
            np.fill_diagonal(overlap, 0)
            duplicates = np.any(overlap >= self.config.duplicate_iou, axis=1)
        retired = []
        shape = (frame_width, frame_height)
        for tid, track in list(self.tracks.items()):
            # One missed observation at a slow cadence may survive longer only
            # with established real motion and pixels. Recovery still needs the
            # strict continuation gates; no old bootstrap identity gets this grace.
            age_limit = self.config.max_age_seconds
            if (track.missed_frames <= 1 and len(track.state.history) >= 2
                    and track.appearance is not None):
                age_limit = max(age_limit, self.config.continuity_missed_seconds)
            if (timestamp-track.state.last_seen_at > age_limit
                    or track.missed_frames >= self.config.max_missed_frames
                    or track.unresolved_origin
                    or (self.frame_shape is not None and self.frame_shape != shape)):
                track.lifecycle = "RETIRED"
                retired.append(tid)
                del self.tracks[tid]
        candidates = sorted(self.tracks.values(), key=lambda t: t.state.track_id)
        gray, gray_scale = None, 1.0
        if source_frame is not None:
            gray_scale = min(1.0,640/max(frame_width,frame_height))
            gray = cv2.cvtColor(cv2.resize(source_frame,(max(1,round(frame_width*gray_scale)),
                                                        max(1,round(frame_height*gray_scale)))),cv2.COLOR_BGR2GRAY)
        matches = {}
        diagnostics = ()
        ambiguous_tracks = set()
        if candidates and boxes:
            # Feature work supports lower cadence and significant bootstrap
            # motion. Display extrapolation remains separate from identity proof.
            costs, metrics = self._association(candidates, boxes, labels, appearances,
                                                timestamp, source_frame is not None, gray, gray_scale)
            valid = costs < 1e6
            row_ties = np.sum(valid & (costs <= costs.min(axis=1)[:, None]+self.config.ambiguity_margin), axis=1) > 1
            col_ties = np.sum(valid & (costs <= costs.min(axis=0)[None, :]+self.config.ambiguity_margin), axis=0) > 1
            blocked_rows = row_ties | np.any(valid & (col_ties | duplicates)[None, :], axis=1)
            blocked_rows |= np.any(metrics["continuity_ambiguous"], axis=1)
            ambiguous_tracks = {t.state.track_id for t, blocked in zip(candidates, blocked_rows) if blocked}
            # Reject ambiguous ownership BEFORE assignment; do not force a match.
            # Canonical geometric ordering makes both assignment and ID allocation
            # independent of the detector's incidental array order.
            order = sorted(range(len(boxes)), key=lambda i: (labels[i], *boxes[i]))
            safe_costs = np.where(valid & ~blocked_rows[:, None] & ~(col_ties | duplicates)[None, :], costs, 1e6)
            # One dummy column per track explicitly permits unmatched ownership.
            matrix = np.concatenate([safe_costs[:, order], np.full((len(candidates), len(candidates)), .95)], axis=1)
            rows, cols = linear_sum_assignment(matrix)
            for r, c in zip(rows, cols):
                if c < len(order) and matrix[r, c] < .95:
                    matches[order[c]] = candidates[r]
            diagnostics = self._diagnostic_rows(candidates, boxes, costs, metrics,
                                                matches, timestamp, sequence)
        # Once ownership becomes ambiguous, no future frame may resurrect it.
        for tid in sorted(ambiguous_tracks):
            self.tracks[tid].lifecycle = "RETIRED"
            retired.append(tid)
            del self.tracks[tid]
        matched_ids = {t.state.track_id for t in matches.values()}
        unmatched = [t for t in candidates if t.state.track_id not in matched_ids and t.state.track_id in self.tracks]
        # Preserve all accepted detections; evict missed continuity first at capacity.
        needed = len(boxes)-len(matches)
        for track in sorted(unmatched, key=lambda t: (t.state.last_seen_at, t.state.track_id)):
            if len(self.tracks)+needed <= self.config.max_tracks:
                break
            tid = track.state.track_id
            track.lifecycle = "RETIRED"
            retired.append(tid)
            del self.tracks[tid]
        output = [None] * len(boxes)
        for index in sorted(range(len(boxes)), key=lambda i: (labels[i], *boxes[i])):
            detection, bbox, label = detections[index], boxes[index], labels[index]
            track = matches.get(index)  # Only current-frame association, never identity.
            if track is None:
                state = TrackState.create(track_id=self.next_id, camera_id=self.camera_id,
                    class_id=VehicleTrackingService._class_id(detection), class_name=label,
                    history_size=self.config.history_size, timestamp=timestamp)
                track = SessionTrack(state, deque(maxlen=self.config.history_size))
                self.tracks[self.next_id] = track
                self.next_id += 1
            else:
                track.lifecycle = "ACTIVE"
            track.missed_frames = 0
            track.last_detected_sequence = sequence
            track.state.add_observation(timestamp=timestamp, bbox=bbox,
                confidence=float(detection.get("confidence", detection.get("score", 0.0))),
                frame_width=frame_width, frame_height=frame_height)
            real = list(track.state.history)[-4:]
            velocities = [((b.center_x-a.center_x)/(b.timestamp-a.timestamp),
                           (b.center_y-a.center_y)/(b.timestamp-a.timestamp))
                          for a, b in zip(real, real[1:]) if b.timestamp > a.timestamp]
            if velocities:
                track.velocity = (median(v[0] for v in velocities), median(v[1] for v in velocities))
            if track.appearance_anchor is None and appearances[index] is not None:
                track.appearance_anchor = appearances[index].copy()
            track.appearance = appearances[index]
            track.unresolved_origin = bool(duplicates[index])
            track.history.append(TrajectoryPoint(timestamp, sequence, bbox, track.state.center,
                bbox[2]-bbox[0], bbox[3]-bbox[1], True, track.velocity))
            # Preserve exact detector coordinates/class/confidence and array order.
            packet = self._packet(track, bbox, detected=True, sequence=sequence, timestamp=timestamp)
            output[index] = {**packet, **dict(detection), "trackId": track.state.track_id}
        predicted = []
        for track in unmatched:
            if track.state.track_id not in self.tracks:
                continue
            track.missed_frames += 1
            if track.missed_frames >= self.config.max_missed_frames:
                track.lifecycle = "RETIRED"
                retired.append(track.state.track_id)
                del self.tracks[track.state.track_id]
                continue
            track.lifecycle = "TEMPORARILY_MISSED"
            bbox = self._prediction(track, timestamp)
            center = ((bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2)
            track.history.append(TrajectoryPoint(timestamp, sequence, bbox, center,
                bbox[2]-bbox[0], bbox[3]-bbox[1], False, track.velocity))
            predicted.append(self._packet(track, bbox, detected=False, sequence=sequence, timestamp=timestamp))
        self.last_sequence, self.last_timestamp, self.frame_shape = sequence, timestamp, shape
        self.previous_gray, self.gray_scale = gray, gray_scale
        return SessionTrackingResult(tuple(output), tuple(predicted), tuple(retired),
                                     (time.perf_counter()-started)*1000, diagnostics)
