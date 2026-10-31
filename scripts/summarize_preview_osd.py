"""Read the fixed Tapo OSD font using manually verified, same-camera digit exemplars.

This is diagnostic OCR, not a detector or annotation change. Ambiguous glyphs are rejected.
Host-minus-OSD includes camera clock offset and one-second OSD quantization.
"""
from datetime import datetime
import json
from pathlib import Path
import sys
import cv2
import numpy as np

root = Path('docs/preview-latency')


def glyph(image, x):
    mask = cv2.threshold(cv2.cvtColor(image[:32,x:x+24],cv2.COLOR_BGR2GRAY),210,255,cv2.THRESH_BINARY)[1]
    mask[:3] = 0
    mask[30:] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2: return mask > 0
    return labels == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))


# Visual ground truth: 2026-09-16 12:37:23AM, 12:40:53AM, 12:40:58AM.
old = cv2.imread(str(root/'running-preview.jpg'))
first = cv2.imread(str(root/'default-threads/direct-1789490454.443041.png'))
eight = cv2.imread(str(root/'default-threads/direct-1789490459.489028.png'))
exemplars = {'0': (old,24), '1':(old,192), '2':(old,0), '3':(old,336), '4':(first,336),
             '5':(first,408), '6':(old,72), '7':(old,360), '8':(eight,432), '9':(old,144)}
templates = {digit:glyph(image,x) for digit,(image,x) in exemplars.items()}


def read_osd(image):
    digits, scores = [], []
    for x in [264,288,336,360,408,432]:
        observed = glyph(image,x)
        matches = [(np.logical_and(observed,template).sum()/max(1,np.logical_or(observed,template).sum()), digit)
                   for digit,template in templates.items()]
        score,digit = max(matches)
        if score < .70: return None, float(score)
        digits.append(digit)
        scores.append(score)
    return f'{digits[0]}{digits[1]}:{digits[2]}{digits[3]}:{digits[4]}{digits[5]}',float(min(scores))


for name in sys.argv[1:] or ['default-threads']:
    folder = root/name
    data = json.loads((folder/'samples.json').read_text())
    rows = []
    for row in data['samples']:
        text, confidence = read_osd(cv2.imread(str(folder/row['file'])))
        item = {**row,'osd':text,'glyphMatch':confidence}
        if text:
            try:
                stamp=datetime.strptime(datetime.fromtimestamp(row['hostTime']).strftime('%Y-%m-%d')+' '+text+'AM','%Y-%m-%d %I:%M:%S%p').timestamp()
                item['hostMinusOsdSeconds']=row['hostTime']-stamp
            except ValueError: item['osd']=None
        rows.append(item)
    summary={}
    for source in ['direct','snapshot','mjpeg']:
        items=sorted([r for r in rows if r['source']==source and r.get('osd')],key=lambda r:r['hostTime'])
        values=[r['hostMinusOsdSeconds'] for r in items]
        n=min(5,len(items))
        summary[source]=dict(valid=len(values),min=min(values) if values else None,
            mean=float(np.mean(values)) if values else None,max=max(values) if values else None,
            first5Mean=float(np.mean(values[:n])) if values else None,
            last5Mean=float(np.mean(values[-n:])) if values else None)
    (folder/'osd-results.json').write_text(json.dumps(dict(summary=summary,samples=rows),indent=2))
    print(name,json.dumps(summary))
