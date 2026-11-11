"""Small ElevenLabs REST client shared by the engine scripts (no SDK needed).

Reads ELEVENLABS_API_KEY from kanz-motion/.env. json_call() for JSON endpoints, upload() for
multipart endpoints (speech to text, forced alignment, audio isolation); both return the raw
response bytes or parsed JSON and raise with ElevenLabs' own error message.
"""
import json
import mimetypes
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.elevenlabs.io/v1"


def env():
    vals = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def has_key():
    return bool(env().get("ELEVENLABS_API_KEY"))


def key():
    k = env().get("ELEVENLABS_API_KEY")
    if not k:
        sys.exit("Add ELEVENLABS_API_KEY=... to kanz-motion/.env (see .env.example)")
    return k


def _send(req, raw):
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ElevenLabs {e.code} on {req.full_url}: {e.read().decode(errors='replace')[:400]}")
    return body if raw else json.loads(body)


def json_call(path, body=None, raw=False):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"xi-api-key": key(), "Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    return _send(req, raw)


def upload(path, fields, files, raw=False):
    """fields: {name: str}; files: {name: Path}."""
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, p in files.items():
        p = Path(p)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{p.name}"\r\n'
                     f'Content-Type: {ctype}\r\n\r\n'.encode() + p.read_bytes() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request(API + path, data=b"".join(parts), method="POST",
                                 headers={"xi-api-key": key(), "Content-Type": f"multipart/form-data; boundary={b}"})
    return _send(req, raw)
