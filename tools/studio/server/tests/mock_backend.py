import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from conftest import write_wav


class MockBackend:
    """Stands in for tools/voice_design/live_backend.py. Writes a short wav under <voice_design>/live_tmp."""

    def __init__(self, voice_design: Path, busy: bool = False, fail: bool = False):
        self.voice_design, self.busy, self.fail, self.calls = voice_design, busy, fail, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def _send(self, obj, code=200):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                self._send({"ok": True, "busy": outer.busy})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append(body)
                if outer.fail:
                    return self._send({"error": "ValueError: boom"}, 500)
                n = len(outer.calls)
                write_wav(outer.voice_design / f"live_tmp/mock{n}.wav")
                out = {"file": f"live_tmp/mock{n}.wav", "seed": int(body.get("seed") or 99),
                       "cfg": body.get("cfg", 2.0), "timesteps": body.get("timesteps", 10),
                       "seconds": 0.1, "audio_s": 0.1}
                if body.get("return_audio"):
                    out["audio_b64"] = base64.b64encode((outer.voice_design / out["file"]).read_bytes()).decode()
                self._send(out)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
