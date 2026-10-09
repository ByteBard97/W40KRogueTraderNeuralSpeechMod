from __future__ import annotations

import base64
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .errors import ApiError

HEALTH_TIMEOUT_S = 3
CALL_TIMEOUT_S = 240
DOWN_MESSAGE = "model backend is not running (start tools/voice_design/live_backend.py when the GPU is free)"


LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class ModelClient:
    """Talks to live_backend.py. A backend on another machine has none of our files and we have none of its: in that
    (remote) mode the reference clip is sent with the request and the generated wav comes back in the reply and is
    written under <voice_design>/live_tmp, so the rest of the studio sees the same shape as a local backend."""

    def __init__(self, url: str, timeout: int = CALL_TIMEOUT_S, root: Path | None = None,
                 live_dir: Path | None = None, remote: bool | None = None):
        self.url, self.timeout, self.root, self.live_dir = url, timeout, root, live_dir
        self.remote = (urlparse(url).hostname not in LOCAL_HOSTS) if remote is None else remote

    def health(self) -> str:
        try:
            with urllib.request.urlopen(self.url + "/health", timeout=HEALTH_TIMEOUT_S) as r:
                h = json.loads(r.read())
        except (OSError, ValueError):
            return "down"
        if not h.get("ok"):
            return "down"
        return "busy" if h.get("busy") else "ready"

    def _sends_files(self) -> bool:
        return self.remote and self.root is not None and self.live_dir is not None

    def _to_remote(self, body: dict) -> dict:
        body = {**body, "return_audio": True}
        ref = body.pop("reference_wav", None)
        if ref:
            body["reference_b64"] = base64.b64encode((self.root / ref).read_bytes()).decode()
        return body

    def _save_audio(self, out: dict) -> dict:
        audio = out.pop("audio_b64", None)
        if audio is not None:
            dest = self.live_dir / "live_tmp" / Path(out["file"]).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(base64.b64decode(audio))
            out["file"] = f"live_tmp/{dest.name}"
        return out

    def call(self, path: str, body: dict) -> dict:
        if self._sends_files():
            body = self._to_remote(body)
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                out = json.loads(e.read() or b"{}")
            except ValueError:
                out = {}
            raise ApiError(502, out.get("error", f"backend HTTP {e.code}"))
        except (TimeoutError, socket.timeout):
            raise ApiError(504, f"the model took longer than {self.timeout}s; it may still be generating, try again shortly")
        except OSError as e:
            if isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout)):
                raise ApiError(504, f"the model took longer than {self.timeout}s; it may still be generating, try again shortly")
            raise ApiError(503, DOWN_MESSAGE)
        if "error" in out:
            raise ApiError(502, out["error"])
        return self._save_audio(out) if self._sends_files() else out
