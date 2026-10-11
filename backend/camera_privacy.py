"""Public camera serialization. Stored connection secrets remain server-side."""
import re


def redact_camera_text(value: str) -> str:
    return re.sub(r'((?:rtsp|rtsps|http|https)://)[^\s/]*@', r'\1<redacted>@', value,
                  flags=re.IGNORECASE)


def public_camera_data(value):
    if isinstance(value, dict):
        result = {key: public_camera_data(item) for key, item in value.items()
                  if key not in {'stream_reference', 'streamReference', 'stream_url',
                                 'cameraPassword', 'cameraUsername'}}
        if 'stream_reference' in value:
            result['streamConfigured'] = bool(value['stream_reference'])
        return result
    if isinstance(value, (list, tuple)):
        return [public_camera_data(item) for item in value]
    return redact_camera_text(value) if isinstance(value, str) else value
