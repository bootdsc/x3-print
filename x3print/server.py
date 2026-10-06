import base64
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import library, link

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")
MAX_ROWS = 40000


class Worker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.p = None
        self.model = None
        self.job = None
        self.cancel = threading.Event()

    def snapshot(self):
        with self.lock:
            st = dict(self.p.last_status or {}) if self.p else {}
            st["connected"] = self.p is not None
            st["model"] = self.model
            j = self.job
            st["job"] = j and {"rows": j["rows"] * j["copies"], "sent": j["sent"] + j["rows"] * j["copy"]}
            return st

    def submit(self, data, rows, params):
        with self.lock:
            if self.job:
                return "busy"
            if not self.p:
                return "printer not connected"
            self.cancel.clear()
            self.job = {"data": data, "rows": rows, "sent": 0, "copy": 0, "copies": params.pop("copies"),
                        "params": params}
            return None

    def run(self):
        while True:
            if not self.p:
                try:
                    p = link.Printer()
                    m = p.model()
                    with self.lock:
                        self.p, self.model = p, m
                except OSError:
                    time.sleep(1.0)
                    continue
            try:
                if self.job:
                    self._print()
                else:
                    self.p.poll()
                    time.sleep(0.05)
            except (OSError, ValueError):
                with self.lock:
                    try:
                        self.p.close()
                    except Exception:
                        pass
                    self.p, self.model, self.job = None, None, None

    def _print(self):
        j = self.job

        def progress(r):
            j["sent"] = min(r, j["rows"])

        for c in range(j["copies"]):
            if self.cancel.is_set():
                break
            j["copy"], j["sent"] = c, 0
            self.p.print_rows(j["data"], cancel=self.cancel, progress=progress, **j["params"])
        with self.lock:
            self.job = None


WORKER = Worker()


def _int(q, k, default, lo, hi):
    try:
        v = int(float(q.get(k, [default])[0]))
    except ValueError:
        v = default
    return max(lo, min(hi, v))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, code, body, ctype="text/plain; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _parts(self):
        u = urlparse(self.path)
        return u, u.path.strip("/").split("/")

    def do_GET(self):
        u, parts = self._parts()
        try:
            if u.path in ("/", "/index.html"):
                with open(PAGE, "rb") as f:
                    self._reply(200, f.read(), "text/html; charset=utf-8")
            elif u.path == "/status":
                self._reply(200, json.dumps(WORKER.snapshot()), "application/json")
            elif u.path == "/library":
                self._reply(200, json.dumps(library.list_items()), "application/json")
            elif u.path == "/presets":
                self._reply(200, json.dumps(library.presets()), "application/json")
            elif len(parts) == 3 and parts[0] == "library" and parts[2] == "source":
                self._reply(200, *library.source(parts[1]))
            elif len(parts) == 3 and parts[0] == "library" and parts[2] == "thumb.png":
                self._reply(200, library.thumb(parts[1]), "image/png")
            else:
                self._reply(404, "not found")
        except KeyError:
            self._reply(404, "no such item")

    def do_DELETE(self):
        _, parts = self._parts()
        if len(parts) == 2 and parts[0] == "presets":
            try:
                library.delete_preset(unquote(parts[1]))
                return self._reply(200, "deleted")
            except KeyError:
                return self._reply(404, "no such preset")
        if len(parts) != 2 or parts[0] != "library":
            return self._reply(404, "not found")
        try:
            library.delete(parts[1])
            self._reply(200, "deleted")
        except KeyError:
            self._reply(404, "no such item")

    def do_POST(self):
        u, parts = self._parts()
        n = int(self.headers.get("Content-Length", 0))
        if u.path == "/library":
            if n > 64 << 20:
                return self._reply(413, "too large")
            try:
                j = json.loads(self.rfile.read(n))
                item_id = library.save(str(j.get("name") or "untitled"), j["settings"],
                                       base64.b64decode(j["source"]), j["source_type"],
                                       base64.b64decode(j["thumb"]), bool(j.get("printed")))
            except (ValueError, KeyError, TypeError) as e:
                return self._reply(400, f"bad save: {e}")
            return self._reply(200, json.dumps({"id": item_id}), "application/json")
        if u.path == "/presets":
            try:
                j = json.loads(self.rfile.read(n))
                library.save_preset(str(j["name"]), j["settings"])
            except (ValueError, KeyError, TypeError) as e:
                return self._reply(400, f"bad preset: {e}")
            return self._reply(200, "saved")
        if len(parts) == 3 and parts[0] == "library" and parts[2] == "printed":
            try:
                library.mark_printed(parts[1])
                return self._reply(200, "ok")
            except KeyError:
                return self._reply(404, "no such item")
        if u.path == "/stop":
            WORKER.cancel.set()
            return self._reply(200, "stopping")
        if u.path != "/print":
            return self._reply(404, "not found")
        q = parse_qs(u.query)
        rows = _int(q, "rows", 0, 0, MAX_ROWS)
        if rows <= 0 or n != rows * link.ROW_BYTES:
            return self._reply(400, f"body must be rows x 108 bytes (rows={rows}, got {n})")
        data = self.rfile.read(n)
        params = {"density": _int(q, "density", 9, 1, 15), "speed": _int(q, "speed", 100, 1, 255),
                  "feed_mm": _int(q, "feed", 8, 0, 100),
                  "copies": _int(q, "copies", 1, 1, 20)}
        err = WORKER.submit(data, rows, params)
        self._reply(409 if err else 200, err or "queued")


def start(port=0):
    library.sweep()
    WORKER.start()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"
