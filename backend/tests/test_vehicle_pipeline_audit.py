"""Controlled class, real-observation motion and incident-delivery regressions.

Run with run_isolated_tests so all application storage is temporary. Synthetic
participant identities test decision logic, not YOLO recall or physical truth.
"""
import itertools
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
import cv2

import backend.main as app
from backend.phase3 import service
from backend.phase3.database import connection
from backend.services.collision_observation_session import CollisionObservationSession, AnalyzedCollisionSession
from backend.services.collision_pair_classifier import select_plausible_pairs


ROAD_CLASSES = ('bicycle', 'car', 'motorcycle', 'bus', 'truck')
DISPLAY_CLASSES = ('bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat')


def observed(track_id, label, x, y=.50, width=.12):
    return dict(trackId=track_id, label=label, confidence=.95, detected=True,
                observationKind='DETECTED', detectionState='TRUSTED',
                x=(x-width/2)*1000, y=(y-.05)*1000, width=width*1000, height=100)


class VehiclePipelineTests(unittest.TestCase):
    def observation(self, session, sequence, boxes, *, score=.95, epoch='S1', quality='good', width=1000):
        return session.observe(session_id=epoch, sequence=sequence, timestamp=sequence*.5,
            boxes=boxes, frame_width=width, frame_height=1000,
            classifier_score=score, frame_quality_status=quality)

    def test_installed_model_vehicle_names_are_supported_without_fabricated_classes(self):
        names = set(app.model.names.values())
        self.assertTrue(set(DISPLAY_CLASSES).issubset(names))
        self.assertFalse({'van', 'suv', 'accident'} & names)
        self.assertTrue(set(DISPLAY_CLASSES).issubset(app.ALLOWED_DETECTION_OUTPUT_LABELS))
        self.assertTrue(set(DISPLAY_CLASSES).issubset(app.VEHICLE_BOX_LABELS))

    def test_result_owns_class_mapping_in_dict_or_list_form(self):
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        boxes = [SimpleNamespace(cls=torch.tensor([i]), conf=torch.tensor([.95]),
                    xyxy=torch.tensor([[i*25, 20, i*25+20, 70]])) for i in range(8)]
        for names in (list(DISPLAY_CLASSES), dict(enumerate(DISPLAY_CLASSES))):
            result = SimpleNamespace(boxes=boxes, names=names)
            extracted = app.extract_vehicle_boxes_from_results([result], {0:'person'}, frame)
            self.assertEqual([b['label'] for b in extracted], list(DISPLAY_CLASSES))
            with patch.object(app, 'model', SimpleNamespace(names={0:'person'})):
                detections, _, _ = app.extract_detections([result])
                rendered = app.draw_filtered_detection_overlay(frame, [result])
            self.assertEqual([d['label'] for d in detections], list(DISPLAY_CLASSES))
            for i in range(8):
                self.assertTrue(rendered[20:72, i*25:i*25+22].any())

    def test_nonroad_model_vehicles_have_correct_ids_and_cannot_confirm_road_crashes(self):
        from backend.services.vehicle_tracking import COCO_VEHICLE_CLASS_IDS
        self.assertEqual({k:COCO_VEHICLE_CLASS_IDS[k] for k in ('airplane','train','boat')},
                         {'airplane':4,'train':6,'boat':8})
        session=CollisionObservationSession('TEST')
        for i,x in enumerate([.18,.28,.38,.47,.535,.55,.55,.55,.55],1):
            boxes=[observed(1,'airplane',x),observed(2,'boat',.62)]
            self.assertEqual(app.collision_vehicle_boxes(boxes),[])
            self.assertFalse(self.observation(session,i,boxes)['temporalCrashVerified'])

    def test_invalid_boxes_and_nonvehicle_classes_do_not_leak(self):
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        result = SimpleNamespace(names={0:'car',1:'person'}, boxes=[
            SimpleNamespace(cls=torch.tensor([0]), conf=torch.tensor([.95]), xyxy=torch.tensor([[float('nan'),0,20,20]])),
            SimpleNamespace(cls=torch.tensor([1]), conf=torch.tensor([.99]), xyxy=torch.tensor([[0,0,20,20]])),
            SimpleNamespace(cls=torch.tensor([0]), conf=torch.tensor([.2]), xyxy=torch.tensor([[0,0,20,20]]))])
        self.assertEqual(app.extract_vehicle_boxes_from_results([result], {}, frame), [])

    def test_each_mixed_pair_is_selected_and_motion_verified(self):
        for a,b in itertools.combinations_with_replacement(ROAD_CLASSES, 2):
            with self.subTest(a=a,b=b):
                session = CollisionObservationSession('TEST')
                results = []
                for i,x in enumerate([.18,.28,.38,.47,.535,.55,.55,.55,.55],1):
                    boxes = [observed(1,a,x),observed(2,b,.62)]
                    results.append(self.observation(session,i,boxes))
                selected = select_plausible_pairs(boxes,frame_width=1000,frame_height=1000)
                self.assertEqual(len(selected),1)
                self.assertTrue(any(r['temporalCrashVerified'] for r in results))
                self.assertEqual(results[-1]['involvedTrackIds'],[1,2])
                self.assertTrue(results[-1]['temporalEvidence']['post_contact_disruption'])
                self.assertEqual(results[-1]['detectorEventId'],results[-2]['detectorEventId'])

    def test_overlap_close_following_and_near_miss_are_not_verified(self):
        scenes = [lambda i:[observed(1,'car',.50),observed(2,'bus',.54)],
                  lambda i:[observed(1,'motorcycle',.18+i*.035),observed(2,'truck',.29+i*.035)],
                  lambda i:[observed(1,'car',.18+i*.065,.47),observed(2,'bicycle',.50,.18+i*.065)]]
        for scene in scenes:
            session = CollisionObservationSession('TEST')
            results = [self.observation(session,i+1,scene(i),score=.999) for i in range(10)]
            self.assertFalse(any(r['temporalCrashVerified'] for r in results))

    def test_different_pairs_predictions_and_empty_frames_cannot_supply_proof(self):
        session = CollisionObservationSession('TEST')
        for i in range(1,10):
            boxes = [observed(i*2,'car',.50),observed(i*2+1,'motorcycle',.54)]
            result = self.observation(session,i,boxes)
            self.assertFalse(result['temporalCrashVerified'])
            self.assertLessEqual(result['pairQualifiedHits'],1)
        predicted = [dict(observed(20,'car',.55),detected=False,observationKind='PREDICTED')]
        self.assertFalse(self.observation(session,10,predicted)['temporalCrashVerified'])
        self.assertFalse(self.observation(session,11,[])['temporalCrashVerified'])

    def test_bad_frames_epoch_and_resolution_reset_collision_history(self):
        session = CollisionObservationSession('TEST')
        for i in range(1,4):
            self.observation(session,i,[observed(1,'car',.2+i*.08),observed(2,'car',.62)])
        self.observation(session,4,[],quality='bad')
        self.assertEqual(session.tracks,{})
        result = self.observation(session,5,[observed(1,'car',.55),observed(2,'car',.62)])
        self.assertFalse(result['temporalCrashVerified'])
        result = self.observation(session,1,[observed(1,'car',.55),observed(2,'car',.62)],epoch='S2')
        self.assertFalse(result['temporalCrashVerified'])
        result = self.observation(session,2,[observed(1,'car',.55),observed(2,'car',.62)],epoch='S2',width=1200)
        self.assertLessEqual(result['pairQualifiedHits'],1)
        with self.assertRaises(ValueError):
            self.observation(session,2,[],epoch='S2',width=1200)

    def test_short_occlusion_uses_only_returned_real_observations(self):
        session = AnalyzedCollisionSession()
        frame = np.full((100,200,3),120,np.uint8)
        detection = dict(label='truck',confidence=.95,x=30,y=30,width=40,height=30)
        session.observe(frame,[detection],timestamp=0,classifier_score=.1)
        session.observe(frame,[],timestamp=.1,classifier_score=.99)
        result = session.observe(frame,[detection],timestamp=.2,classifier_score=.1)
        self.assertFalse(result['temporalCrashVerified'])
        self.assertEqual(len(session.verifier.tracks),1)
        self.assertEqual(len(next(iter(session.verifier.tracks.values())).history),2)

    def test_video_sampling_honors_target_fps_for_low_fps_and_long_clips(self):
        with patch.dict(os.environ, {'VIDEO_FRAME_SKIP':'0','VIDEO_ANALYSIS_FPS':'3'}):
            self.assertEqual(app.get_video_frame_skip(5000,30),10)
            self.assertEqual(app.get_video_frame_skip(50,5),2)
        with patch.dict(os.environ, {'VIDEO_FRAME_SKIP':'1'}):
            self.assertEqual(app.get_video_frame_skip(5000,30),1)

    def test_equal_capture_timestamp_is_not_new_motion_proof(self):
        session=CollisionObservationSession('TEST')
        self.observation(session,1,[observed(1,'car',.30),observed(2,'car',.60)])
        result=session.observe(session_id='S1',sequence=2,timestamp=.5,
            boxes=[observed(1,'car',.40),observed(2,'car',.60)],frame_width=1000,
            frame_height=1000,classifier_score=.99)
        self.assertFalse(result['temporalCrashVerified'])
        self.assertEqual(result['pairQualifiedHits'],0)
        self.assertEqual(len(session.tracks[1].history),1)

    def test_related_multivehicle_contacts_share_one_event_identity(self):
        session=CollisionObservationSession('TEST')
        first=None
        for i,x in enumerate([.18,.28,.38,.47,.535,.55,.55,.55,.55],1):
            result=self.observation(session,i,[observed(1,'car',x),observed(2,'truck',.62),observed(3,'bus',.66)])
            if result['temporalCrashVerified'] and first is None:first=result['detectorEventId']
        self.assertIsNotNone(first)
        result=self.observation(session,10,[observed(1,'car',.55),observed(3,'bus',.66)])
        self.assertTrue(result['temporalCrashVerified'])
        self.assertEqual(result['detectorEventId'],first)
        self.assertEqual(result['involvedTrackIds'],[1,2,3])

    def test_separation_clears_live_confirmation_and_later_contact_has_new_identity(self):
        session=CollisionObservationSession('TEST')
        positions=[.18,.28,.38,.47,.535,.55,.55,.55,.55]
        for i,x in enumerate(positions,1):
            first=self.observation(session,i,[observed(1,'car',x),observed(2,'truck',.62)])
        self.assertTrue(first['temporalCrashVerified'])
        for i in range(10,14):
            clear=self.observation(session,i,[observed(1,'car',.15),observed(2,'truck',.85)])
        self.assertFalse(clear['temporalCrashVerified'])
        for i,x in enumerate(positions,14):
            second=self.observation(session,i,[observed(1,'car',x),observed(2,'truck',.62)])
        self.assertTrue(second['temporalCrashVerified'])
        self.assertNotEqual(first['detectorEventId'],second['detectorEventId'])

    def test_new_independent_crash_is_selected_while_old_pair_remains_visible(self):
        session=CollisionObservationSession('TEST')
        positions=[.18,.28,.38,.47,.535,.55,.55,.55,.55]
        for i,x in enumerate(positions,1):
            first=self.observation(session,i,[observed(1,'car',x),observed(2,'truck',.62)])
        self.assertTrue(first['temporalCrashVerified'])
        fresh=[]
        for i,x in enumerate(positions,10):
            result=self.observation(session,i,[observed(1,'car',.55),observed(2,'truck',.62),
                observed(3,'motorcycle',x,.90),observed(4,'bus',.62,.90)])
            if result['temporalCrashVerified'] and result['detectorEventId']!=first['detectorEventId']:
                fresh.append(result)
        self.assertTrue(fresh)
        self.assertEqual(fresh[-1]['involvedTrackIds'],[3,4])

    def test_live_display_keeps_vehicles_outside_collision_roi(self):
        from unittest.mock import Mock
        frame=np.full((100,200,3),120,np.uint8)
        detector=SimpleNamespace(names={0:'car',1:'motorcycle'},predict=Mock(return_value=[
            SimpleNamespace(names={0:'car',1:'motorcycle'},boxes=[
                SimpleNamespace(cls=torch.tensor([0]),conf=torch.tensor([.95]),xyxy=torch.tensor([[20,20,50,60]])),
                SimpleNamespace(cls=torch.tensor([1]),conf=torch.tensor([.95]),xyxy=torch.tensor([[150,20,180,60]]))])]))
        monitor=app.LiveCameraMonitor(monitor_key='TEST',camera_id='TEST',camera_ip=None,
            stream_url='webcam://controlled-test',label='Controlled',area_id='TEST',barangay=None,
            road_name=None,latitude=None,longitude=None,location='TEST',redacted_stream_url='controlled',output_base='http://test')
        with patch.dict(os.environ,{'CRASH_ROI_NORMALIZED':'0,0,0.5,1'}), \
             patch.object(app,'model',detector),patch.object(app,'vehicle_model',detector), \
             patch.object(app,'analyze_frame_quality',return_value=dict(frameQualityStatus='good',qualityRejectionReason=None,blurScore=100,brightnessScore=100,contrastScore=100)), \
             patch.object(app,'classify_crash_frame',return_value={'accidentProbability':.1}), \
             patch.object(app,'persist_sqlite_crash_case') as persist:
            monitor.seed_first_frame(frame)
            result=monitor.analyze_current_frame()
        self.assertEqual(result['vehicleCount'],1)
        self.assertEqual([b['label'] for b in result['boxes']],['car','motorcycle'])
        self.assertEqual(len(monitor.latest_box_packet()['boxes']),2)
        persist.assert_not_called()


class VideoRouteTests(unittest.TestCase):
    def run_clip(self, moving=True, skip=1, write_fails=False):
        positions = [.30,.32,.34,.36,.38,.40,.415,.42,.42,.42,.42,.42,.42,.42,.42,.42]
        if not moving:
            positions = [.42]*len(positions)
        frames, results = [], []
        for x in positions:
            frame = np.zeros((1000,1000,3),np.uint8)
            boxes=[]
            for i,(center,label,color) in enumerate([(x,'car',(10,20,230)),(.60,'motorcycle',(230,30,10))]):
                bbox=[int((center-.10)*1000),450,int((center+.10)*1000),550]
                cv2.rectangle(frame,tuple(bbox[:2]),tuple(bbox[2:]),color,-1)
                boxes.append(SimpleNamespace(cls=torch.tensor([i]),conf=torch.tensor([.95]),xyxy=torch.tensor([bbox])))
            frames.append(frame)
            results.append([SimpleNamespace(boxes=boxes,names={0:'car',1:'motorcycle'})])
        current={'i':-1}
        def read():
            current['i']+=1
            return (True,frames[current['i']]) if current['i']<len(frames) else (False,None)
        def get(prop):
            return {cv2.CAP_PROP_FPS:5,cv2.CAP_PROP_FRAME_WIDTH:1000,cv2.CAP_PROP_FRAME_HEIGHT:1000,
                    cv2.CAP_PROP_FRAME_COUNT:len(frames),cv2.CAP_PROP_POS_MSEC:(current['i']+1)*200}.get(prop,0)
        from unittest.mock import Mock
        cap=Mock();cap.isOpened.return_value=True;cap.read.side_effect=read;cap.get.side_effect=get
        detector=SimpleNamespace(names={0:'car',1:'motorcycle'},predict=Mock(side_effect=lambda *a,**kw:results[current['i']]))
        saved=[]
        writer=Mock();writer.write.side_effect=lambda frame:saved.append(frame.copy())
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'out.mp4'
            output.write_bytes(b'controlled-output')
            source=Path(directory)/'source.mp4';source.write_bytes(b'controlled-source')
            with patch.dict(os.environ, {'VIDEO_FRAME_SKIP':str(skip),'CRASH_ROI_NORMALIZED':'','ENABLE_CRASH_CASE_CREATION':'true'}), \
                 patch.object(app,'require_legacy_permission'),patch.object(app,'save_upload_file',return_value=source), \
                 patch.object(app.cv2,'VideoCapture',return_value=cap),patch.object(app,'model',detector), \
                 patch.object(app,'vehicle_model',detector),patch.object(app,'OUTPUTS',Path(directory)), \
                 patch.object(app,'create_video_writer',return_value={'writer':writer,'output_path':output,'output_name':'out.mp4','browser_preview_safe':True,'codec':'controlled'}), \
                 patch.object(app,'analyze_frame_quality',return_value=dict(frameQualityStatus='good',qualityRejectionReason=None,blurScore=100,brightnessScore=100,contrastScore=100)), \
                 patch.object(app,'classify_crash_frame',return_value={'accidentProbability':.95}),patch.object(app,'log_video'),patch.object(app,'log_crash_decision'):
                if write_fails:
                    with patch.object(app.cv2,'imwrite',side_effect=OSError('controlled evidence failure')):
                        result=app.detect_video(SimpleNamespace(base_url='http://test/'),SimpleNamespace(filename='controlled.mp4',content_type='video/mp4'))
                else:
                    result=app.detect_video(SimpleNamespace(base_url='http://test/'),SimpleNamespace(filename='controlled.mp4',content_type='video/mp4'))
        return result,saved,frames,detector.predict.call_count

    def test_actual_video_route_uses_classifier_tracking_motion_and_sqlite(self):
        result,_,_,calls=self.run_clip()
        self.assertEqual(calls,16)
        self.assertTrue(result['temporalCrashVerified'])
        self.assertEqual(result['finalDecision'],'confirmed_crash')
        self.assertTrue(result['incidentCreated'])
        self.assertEqual(result['persistenceStatus'],'created')
        self.assertEqual([b['label'] for b in result['boxes']],['car','motorcycle'])

    def test_static_overlap_does_not_create_temporal_collision(self):
        result,_,_,_=self.run_clip(moving=False)
        self.assertFalse(result['temporalCrashVerified'])
        self.assertFalse(result['accident_detected'])
        self.assertNotEqual(result['finalDecision'],'confirmed_crash')

    def test_skipped_frames_are_current_pixels_without_invented_boxes(self):
        _,saved,frames,calls=self.run_clip(skip=2)
        self.assertEqual(len(saved),len(frames))
        self.assertEqual(calls,8)
        for i in range(1,len(frames),2):
            np.testing.assert_array_equal(saved[i],frames[i])

    def test_snapshot_failure_does_not_discard_verified_incident(self):
        result,_,_,_=self.run_clip(write_fails=True)
        self.assertTrue(result['incidentCreated'])
        self.assertTrue(result['temporalCrashVerified'])
        self.assertIsNone(result['annotated_key_frame_url'])
        self.assertIn('could not be saved',result['evidenceWarning'])


class IncidentDeliveryTests(unittest.TestCase):
    def setUp(self):
        import uuid
        with connection() as conn, conn.transaction():
            user = conn.execute('INSERT INTO users(email,full_name,password_hash,must_change_password) VALUES (%s,%s,%s,FALSE) RETURNING id',
                (f'audit-{uuid.uuid4().hex}@example.invalid','Synthetic Dispatcher','unused-test-only-hash')).fetchone()
            conn.execute("INSERT INTO user_roles(user_id,role_id) SELECT %s,id FROM roles WHERE name='DISPATCHER'",(user['id'],))

    def payload(self):
        import uuid
        return dict(detectorEventId=str(uuid.uuid4()),cameraKey='CONTROLLED-AUDIT',
            detectedAt='2026-10-13T00:00:00+00:00',crashScore=.95,
            evidenceSummary={'temporalCrashVerified':True,'trackingSessionId':'S1','involvedTrackIds':[1,2]})

    def test_delivery_failure_preserves_incident_and_retries_without_duplicates(self):
        payload = self.payload()
        original = service._create_dispatcher_notifications
        def partial_failure(conn, incident_id):
            original(conn,incident_id)
            raise sqlite3.IntegrityError('controlled delivery failure')
        with patch.object(service,'_create_dispatcher_notifications',side_effect=partial_failure):
            result = service.create_ai_incident(payload)
        self.assertTrue(result['incidentCreated'])
        self.assertEqual(result['notificationStatus'],'failed')
        with connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM incidents WHERE id=%s',(result['incidentId'],)).fetchone()['n'],1)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM review_cases WHERE incident_id=%s',(result['incidentId'],)).fetchone()['n'],1)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM notifications WHERE incident_id=%s',(result['incidentId'],)).fetchone()['n'],0)
        retry = service.create_ai_incident(payload)
        self.assertFalse(retry['incidentCreated'])
        self.assertEqual(retry['incidentId'],result['incidentId'])
        self.assertEqual(retry['notificationStatus'],'delivered')
        self.assertGreaterEqual(retry['notificationCount'],1)
        again = service.create_ai_incident(payload)
        self.assertFalse(again['incidentCreated'])
        self.assertEqual(again['notificationCount'],0)

    def test_distinct_pair_event_is_not_blocked_by_unresolved_camera_review(self):
        first = self.payload()
        second = self.payload()
        second['evidenceSummary']['involvedTrackIds']=[3,4]
        one = service.create_ai_incident(first)
        two = service.create_ai_incident(second)
        self.assertTrue(one['incidentCreated'])
        self.assertTrue(two['incidentCreated'])
        self.assertNotEqual(one['incidentId'],two['incidentId'])

    def test_retry_of_deleted_or_unknown_event_cannot_create_an_incident(self):
        self.assertIsNone(service.retry_ai_incident_notifications('NONEXISTENT-SYNTHETIC-EVENT'))

    def test_compound_contact_adds_participants_without_replacing_original_evidence(self):
        payload=self.payload()
        payload['evidenceSummary']['boxes']=[{'label':'car','x':12}]
        result=service.create_ai_incident(payload)
        payload['evidenceSummary']['involvedTrackIds']=[1,2,3]
        repeated=service.create_ai_incident(payload)
        self.assertFalse(repeated['incidentCreated'])
        with connection() as conn:
            summary=conn.execute('SELECT evidence_summary FROM incidents WHERE id=%s',(result['incidentId'],)).fetchone()['evidence_summary']
        self.assertEqual(summary['involvedTrackIds'],[1,2,3])
        self.assertEqual(summary['boxes'],[{'label':'car','x':12}])


if __name__=='__main__':
    unittest.main()
