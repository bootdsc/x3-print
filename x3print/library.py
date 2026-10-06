import json
import os
import secrets
import shutil
import sys
import time

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "library")
EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp"}
TYPES = {v: k for k, v in EXT.items()}


def _dir(item_id):
    if not item_id or not all(c in "0123456789abcdef" for c in item_id):
        raise KeyError(item_id)
    d = os.path.join(ROOT, item_id)
    if not os.path.isdir(d):
        raise KeyError(item_id)
    return d


def _meta(d):
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def _write(path, data):
    tmp = path + ".part"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def sweep():
    if not os.path.isdir(ROOT):
        return
    for name in os.listdir(ROOT):
        d = os.path.join(ROOT, name)
        if os.path.isdir(d) and not os.path.exists(os.path.join(d, "meta.json")):
            shutil.rmtree(d, ignore_errors=True)
            continue
        for f in os.listdir(d) if os.path.isdir(d) else ():
            if f.endswith(".part"):
                os.remove(os.path.join(d, f))


def list_items():
    if not os.path.isdir(ROOT):
        return []
    out = []
    for name in os.listdir(ROOT):
        try:
            m = _meta(_dir(name))
        except (KeyError, OSError, ValueError):
            continue
        m["id"] = name
        out.append(m)
    out.sort(key=lambda m: m.get("updated", 0), reverse=True)
    return out


def save(name, settings, source, source_type, thumb, printed=False):
    ext = EXT.get(source_type)
    if not ext:
        raise ValueError(f"unsupported image type {source_type!r}")
    os.makedirs(ROOT, exist_ok=True)
    item_id = secrets.token_hex(6)
    d = os.path.join(ROOT, item_id)
    os.makedirs(d)
    now = time.time()
    try:
        _write(os.path.join(d, "source" + ext), source)
        _write(os.path.join(d, "thumb.png"), thumb)
        meta = {"name": name[:120], "settings": settings, "source": "source" + ext,
                "created": now, "updated": now, "printed": 1 if printed else 0}
        _write(os.path.join(d, "meta.json"), json.dumps(meta).encode())
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return item_id


def mark_printed(item_id):
    d = _dir(item_id)
    m = _meta(d)
    m["printed"] = m.get("printed", 0) + 1
    m["updated"] = time.time()
    _write(os.path.join(d, "meta.json"), json.dumps(m).encode())


def source(item_id):
    d = _dir(item_id)
    m = _meta(d)
    p = os.path.join(d, m["source"])
    with open(p, "rb") as f:
        return f.read(), TYPES.get(os.path.splitext(p)[1], "application/octet-stream")


def thumb(item_id):
    with open(os.path.join(_dir(item_id), "thumb.png"), "rb") as f:
        return f.read()


def delete(item_id):
    shutil.rmtree(_dir(item_id))


PRESETS = os.path.join(ROOT, "presets.json")


def presets():
    try:
        with open(PRESETS, encoding="utf-8") as f:
            p = json.load(f)
        return p if isinstance(p, dict) else {}
    except (OSError, ValueError):
        return {}


def save_preset(name, settings):
    name = name.strip()[:60]
    if not name or not isinstance(settings, dict):
        raise ValueError("preset needs a name and settings")
    p = presets()
    p[name] = settings
    os.makedirs(ROOT, exist_ok=True)
    _write(PRESETS, json.dumps(p, indent=1).encode())


def delete_preset(name):
    p = presets()
    if name not in p:
        raise KeyError(name)
    del p[name]
    _write(PRESETS, json.dumps(p, indent=1).encode())
