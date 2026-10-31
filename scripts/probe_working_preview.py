"""Exercise the revised capture/JPEG/MJPEG code without importing AI or databases."""
import argparse
import ast
from collections import deque
from datetime import datetime
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from urllib.parse import quote, urlparse
import urllib.request
import cv2
import numpy as np
import psutil

p=argparse.ArgumentParser()
p.add_argument('--seconds',type=int,default=300)
p.add_argument('--name',default='working-preview-5min')
args=p.parse_args()
output=Path('docs/preview-latency')/args.name
output.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(Path('data/crashguard.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
    cid,url=db.execute("SELECT cameraId,streamUrl FROM cameras WHERE streamUrl LIKE '%192.168.1.17%/stream2' LIMIT 1").fetchone()
node=next(n for n in ast.parse(Path('backend/main.py').read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef) and n.name=='LiveCameraMonitor')
ns=dict(globals(),LIVE_CAMERA_REQUIRED_HITS=3,LIVE_CAMERA_JPEG_QUALITY=75,LIVE_CAMERA_PREVIEW_FPS=10,
    LIVE_CAMERA_FREEZE_TIMEOUT_SECONDS=10,log_stream=lambda *_:None)
exec(compile(ast.Module(body=[node],type_ignores=[]),'backend/main.py (capture-only extraction)','exec'),ns)
monitor=ns['LiveCameraMonitor'](monitor_key=cid,camera_id=cid,camera_ip=None,stream_url=url,label='Read-only preview probe',
    area_id='test',barangay=None,road_name=None,latitude=None,longitude=None,location='test',
    redacted_stream_url='rtsp://redacted',output_base='http://127.0.0.1')
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0')
        self.end_headers()
        try:
            for packet in monitor.mjpeg_stream():
                self.wfile.write(packet)
                self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError): pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
server.daemon_threads=True
monitor.running=True
capture=threading.Thread(target=monitor._capture_loop,daemon=True)
capture.start()
threading.Thread(target=server.serve_forever,daemon=True).start()
samples=[]
count=0
start=time.time()
proc=psutil.Process()
cpu_start=sum(proc.cpu_times()[:2])
last_saved=0
try:
    with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/',timeout=6) as response:
        buf=b''
        while time.time()-start<args.seconds:
            buf+=response.read1(16384)
            while True:
                a,b=buf.find(b'\xff\xd8'),buf.find(b'\xff\xd9')
                if a<0 or b<a: break
                headers=buf[:a].decode('ascii',errors='ignore')
                jpeg,buf=buf[a:b+2],buf[b+2:]
                received=time.time()
                count+=1
                if received-last_saved>=5 or (received-start<5 and received-last_saved>=1):
                    fields={}
                    for line in headers.splitlines():
                        if ': ' in line:
                            key,value=line.split(': ',1)
                            if key.startswith('X-'):fields[key]=value
                    image=cv2.imdecode(np.frombuffer(jpeg,np.uint8),cv2.IMREAD_COLOR)
                    filename=f'mjpeg-{received:.6f}.png'
                    cv2.imwrite(str(output/filename),image[:34,:510])
                    samples.append(dict(file=filename,source='mjpeg',hostTime=received,headers=fields,
                        captureReadMs=monitor.capture_read_ms,arrivalMs=monitor.decoded_arrival_interval_ms,
                        publishDelayMs=(monitor.frame_published_at-monitor.last_frame_at)*1000,
                        jpegEncodeMs=monitor.jpeg_encode_ms,jpegReplacedAgeMs=monitor.jpeg_replaced_age_ms))
                    last_saved=received
            if len(buf)>2_000_000: raise ValueError('Multipart frame exceeded diagnostic bound')
finally:
    elapsed=time.time()-start
    monitor.stop()
    server.shutdown()
    server.server_close()
    capture.join(6)
    settings=dict(duration=elapsed,captureFps=monitor.frame_seq/elapsed,previewFps=count/elapsed,
        decoderThreads=monitor.decoder_threads,bufferAccepted=monitor.capture_buffer_accepted,
        probeCpuPercent=(sum(proc.cpu_times()[:2])-cpu_start)/elapsed*100,
        jpegEncodes=monitor.jpeg_encode_count,productionRestarted=False,aiStartedByProbe=False)
    (output/'samples.json').write_text(json.dumps(dict(settings=settings,samples=samples),indent=2))
    print(json.dumps(settings))
