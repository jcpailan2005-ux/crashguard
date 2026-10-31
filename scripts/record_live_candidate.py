"""External, bounded observer of the running backend. Never changes its decisions."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import threading
import time
import urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seconds', type=int, default=90)
    p.add_argument('--camera', default='CAM-30960048ED')
    p.add_argument('--output', default='docs/live-candidate-audit/observation-1')
    args = p.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    base = f'http://127.0.0.1:8010/api/cameras/{args.camera}'
    start = time.time()
    stop = threading.Event()
    previews = []
    # JPEG snapshots have their own receive time; never label these exact AI inputs.
    def preview():
        seq = 0
        while not stop.is_set():
            before = time.time()
            try:
                with urllib.request.urlopen(base+'/latest-frame.jpg?t='+str(before),timeout=3) as response:
                    jpeg = response.read()
                received = time.time()
                name = f'preview-{seq:05d}.jpg'
                (output/name).write_bytes(jpeg)
                previews.append(dict(file=name, requestedAt=before, receivedAt=received))
                seq += 1
            except Exception:
                pass
            stop.wait(max(0,.25-(time.time()-before)))
    thread = threading.Thread(target=preview,daemon=True)
    thread.start()
    count, previous, errors = 0, None, []
    print('Recording live status transitions and timestamped preview frames.',flush=True)
    with (output/'observations.jsonl').open('w',encoding='utf-8') as log:
        while time.time()-start < args.seconds:
            before = time.time()
            try:
                with urllib.request.urlopen(base+'/status',timeout=3) as response:
                    status = json.load(response)
                received = time.time()
                result = status.get('latestResult') or {}
                key = result.get('timestamp')
                if key and key != previous:
                    previous = key
                    row = dict(observation=count,hostReceivedAt=received,hostIso=datetime.fromtimestamp(received).isoformat(),
                        requestMs=(received-before)*1000,lastFrameAt=status.get('lastFrameAt'),
                        status=status.get('status'),result=result)
                    log.write(json.dumps(row)+'\n')
                    log.flush()
                    if result.get('finalDecision') in {'candidate','verifying','confirmed_crash','possible_crash_aftermath'}:
                        print(json.dumps({k:result.get(k) for k in ['timestamp','finalDecision','rejectionReason','consecutiveCrashHits','crashScore','vehicleCount','motionValid']}),flush=True)
                    count += 1
            except Exception as error:
                errors.append(type(error).__name__)
            stop.wait(.05)
    stop.set()
    thread.join(4)
    (output/'preview-index.json').write_text(json.dumps(previews,indent=2))
    (output/'summary.json').write_text(json.dumps(dict(start=start,end=time.time(),observations=count,previews=len(previews),errors=errors),indent=2))
    print(f'Recorded {count} distinct inference results and {len(previews)} preview frames.')


if __name__ == '__main__':
    main()
