from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import DEFAULT_BACKEND_URL, Config
from .errors import ApiError
from .model import ModelClient
from . import fx, qa, vendor_files
from .routes import build_router

DEFAULT_PORT = 8930
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def parse_range(header: str | None, total: int):
    """(first, last) for a single `bytes=a-b` / `bytes=a-` / `bytes=-n` range; None when absent or not understood; "bad" when unsatisfiable."""
    if not header or not header.startswith("bytes=") or "," in header:
        return None
    a, _, z = header[6:].strip().partition("-")
    try:
        if a == "":
            n = int(z)
            return (max(total - n, 0), total - 1) if n > 0 and total else "bad"
        first, last = int(a), int(z) if z else total - 1
    except ValueError:
        return None
    if first >= total or first > last:
        return "bad"
    return first, min(last, total - 1)


def make_server(cfg: Config, model: ModelClient, port: int = DEFAULT_PORT, web_dist: Path | None = None):
    router, dist = build_router(), web_dist or DEFAULT_DIST

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str, headers: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _send_media(self, body: bytes, ctype: str) -> None:
            """200 or 206: browsers can only seek an audio source when Range requests are answered."""
            total, rng = len(body), parse_range(self.headers.get("Range"), len(body))
            if rng is None:
                return self._send(200, body, ctype, {"Accept-Ranges": "bytes"})
            if rng == "bad":
                return self._send(416, b"", ctype, {"Content-Range": f"bytes */{total}"})
            a, z = rng
            self._send(206, body[a:z + 1], ctype, {"Accept-Ranges": "bytes", "Content-Range": f"bytes {a}-{z}/{total}"})

        def _api(self, method: str, body: dict) -> None:
            u = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(u.query).items()}
            status, obj = router.dispatch(method, u.path, query, body, cfg, model)
            self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path.startswith("/api/"):
                return self._api("GET", {})
            if u.path == "/file":
                p = cfg.resolve_file(parse_qs(u.query).get("p", [""])[0])
                if p is None:
                    return self._send(404, b"not found", "text/plain")
                try:
                    return self._send_media(p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream")
                except Exception as e:
                    return self._send(500, f"{type(e).__name__}: {e}".encode(), "text/plain")
            if u.path == "/fx-file":
                args = {k: v[0] for k, v in parse_qs(u.query).items()}
                p = cfg.resolve_file(args.get("p", ""))
                if p is None or p.suffix != ".wav":
                    return self._send(404, b"not found", "text/plain")
                try:
                    return self._send_media(qa.compressed(p, args.get("fx", "")), "audio/wav")
                except ApiError as e:
                    return self._send(e.status, e.message.encode(), "text/plain")
                except Exception as e:
                    return self._send(500, f"{type(e).__name__}: {e}".encode(), "text/plain")
            if u.path == "/fx-render":
                args = {k: v[0] for k, v in parse_qs(u.query).items()}
                names = [n for n in (args.get("presets") or args.get("preset") or "").split(fx.PREVIEW_SEP) if n]
                try:
                    return self._send_media(fx.render_preview(cfg, names, args.get("p", "")), "audio/wav")
                except ApiError as e:
                    return self._send(e.status, e.message.encode(), "text/plain")
                except Exception as e:
                    return self._send(500, f"{type(e).__name__}: {e}".encode(), "text/plain")
            vendor = vendor_files.resolve(REPO_ROOT, u.path)
            if vendor:
                return self._send(200, vendor[0].read_bytes(), vendor[1], {"Cache-Control": "no-store"})
            rel = u.path.lstrip("/")
            f = (dist / rel).resolve() if rel else None
            if f and f.is_file() and dist.resolve() in f.parents:
                return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            index = dist / "index.html"
            if index.is_file():
                return self._send(200, index.read_bytes(), "text/html; charset=utf-8")
            self._send(503, b"web app not built: cd tools/studio/web && npm run build", "text/plain")

        def do_POST(self) -> None:
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError:
                return self._send(400, b'{"error":"body is not JSON"}', "application/json")
            self._api("POST", body)

        def log_message(self, *a) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--backend", default=DEFAULT_BACKEND_URL)
    ap.add_argument("--remote-backend", action="store_true",
                    help="the backend is on another machine (even if reached through an ssh tunnel on localhost): "
                         "send reference clips with each request and save the returned audio")
    a = ap.parse_args()
    cfg = Config(backend_url=a.backend)
    print(f"Voice Studio on http://127.0.0.1:{a.port}  (model backend {a.backend})", flush=True)
    make_server(cfg, ModelClient(a.backend, root=cfg.root, live_dir=cfg.voice_design, remote=a.remote_backend or None), a.port).serve_forever()
