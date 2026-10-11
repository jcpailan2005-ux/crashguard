"""Detection-to-dispatch boundary; PostgreSQL owns operational incidents.

Decision evaluation remains with the detector. This service never turns a
candidate into a confirmed crash or synthesizes verifier measurements.
"""
from typing import TypedDict

from backend.phase3 import service
from backend.repositories.crash_cases import crash_case_creation_enabled


class PersistenceResult(TypedDict):
    caseId: str
    incidentId: str
    incidentCreated: bool
    casePersistenceStatus: str
    status: str
    notificationCount: int
    createdNotificationId: None
    operational: bool
    detectionMode: str
    detectorEventId: str
    reviewCaseId: str | None


def persist_operational_detection(data: dict) -> PersistenceResult | None:
    decision = data.get('finalDecision')
    if decision not in {'confirmed_crash', 'possible_crash_aftermath'}:
        return None
    if not crash_case_creation_enabled():
        return None
    payload = dict(data)
    payload['detectionMode'] = 'temporal_collision' if decision == 'confirmed_crash' else 'aftermath_review'
    # The initial operational state is AWAITING_REVIEW in both cases. Only a
    # dispatcher can confirm the incident for dispatch.
    result = service.create_ai_incident(payload)
    created = result['incidentCreated']
    return {
        'caseId': result['incidentId'], 'incidentId': result['incidentId'],
        'incidentCreated': created, 'casePersistenceStatus': 'created' if created else 'blocked_existing_case',
        'status': 'pending_review', 'notificationCount': result.get('notificationCount', 0),
        'createdNotificationId': None, 'operational': True,
        'detectionMode': payload['detectionMode'],
        'detectorEventId': payload['detectorEventId'],
        'reviewCaseId': result.get('reviewCaseId'),
        **payload.get('media', {}),
    }


def find_pending_camera_incident(camera_ip=None, camera_id=None, source_camera=None, **_):
    key = camera_id or camera_ip or source_camera
    if not key:
        return None
    row = service.find_pending_detection(str(key))
    if not row:
        return None
    return {'caseId': str(row['id']), 'incidentId': str(row['id']),
            'status': 'pending_review' if row['review_status'] == 'PENDING_REVIEW' else 'under_review',
            'operational': True, 'detectorEventId': row['detector_event_id'],
            **(row.get('media') or {})}
