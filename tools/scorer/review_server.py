"""Blind A/B review page for the scorer test. Serves data/scorer_probe/best_of_n/pairs.json,
stores answers in answers.json. Run: python tools/scorer/review_server.py  (port 8906)"""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = (ROOT / "data").resolve()
BON = ROOT / "data/scorer_probe/best_of_n"
ANS = BON / "answers.json"
PAGE = """<!doctype html><meta charset=utf-8><title>Scorer check</title>
<style>body{font:16px system-ui;max-width:760px;margin:24px auto;padding:0 16px;background:#14161a;color:#e8e8e8}
button{font:inherit;padding:10px 18px;margin:6px 6px 6px 0;border-radius:6px;border:1px solid #556;background:#222833;color:inherit;cursor:pointer}
.q{background:#1e2430;padding:12px 16px;border-radius:8px;margin:12px 0}small{color:#9aa}audio{width:100%;margin:4px 0 10px}</style>
<div id=app>loading</div>
<script>
let pairs=[],ans={},i=0;
async function init(){pairs=await (await fetch('/pairs')).json();ans=await (await fetch('/answers')).json();
 i=pairs.findIndex(p=>!(p.id in ans)); if(i<0)i=pairs.length; render();}
const au=p=>`<audio controls preload=auto src="/file?p=${encodeURIComponent(p)}"></audio>`;
function render(){const a=document.getElementById('app');
 if(i>=pairs.length){a.innerHTML='<h2>All done, thank you.</h2>';return}
 const p=pairs[i];const q=p.axis=='voice'?'Which take sounds more like the SAME person as the reference and is cleaner (no gravel, whisper, garble)?':
 `Which take conveys the intended emotion ("${p.emotion}") better, at a believable intensity?`;
 a.innerHTML=`<small>${i+1} / ${pairs.length}</small><div class=q><b>${q}</b><br><small>${p.text}</small></div>
 <div>Reference (voice to match)</div>${au(p.reference_wav)}<div>A</div>${au(p.a)}<div>B</div>${au(p.b)}
 <button onclick="pick('a')">A better (1)</button><button onclick="pick('b')">B better (2)</button><button onclick="pick('tie')">Can't tell (3)</button>`;}
async function pick(v){const p=pairs[i];ans[p.id]=v;await fetch('/answer',{method:'POST',body:JSON.stringify({id:p.id,choice:v})});i++;render();}
addEventListener('keydown',e=>{if(e.key=='1')pick('a');if(e.key=='2')pick('b');if(e.key=='3')pick('tie')});
init();</script>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(PAGE.encode(), "text/html; charset=utf-8")
        if u.path == "/pairs":
            return self._send((BON / "pairs.json").read_bytes())
        if u.path == "/answers":
            return self._send(ANS.read_bytes() if ANS.exists() else b"{}")
        if u.path == "/file":
            p = Path(parse_qs(u.query)["p"][0])
            p = (ROOT / p).resolve()  # absolute p replaces ROOT; boundary enforced below
            if DATA_ROOT not in p.parents or not p.is_file():
                return self._send(b"no", "text/plain", 404)
            return self._send(p.read_bytes(), mimetypes.guess_type(p.name)[0] or "audio/wav")
        self._send(b"no", "text/plain", 404)

    def do_POST(self):
        if self.path != "/answer":
            return self._send(b"no", "text/plain", 404)
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        a = json.loads(ANS.read_text()) if ANS.exists() else {}
        a[d["id"]] = d["choice"]
        ANS.write_text(json.dumps(a, indent=1))
        self._send(b"{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("http://localhost:8906")
    ThreadingHTTPServer(("127.0.0.1", 8906), H).serve_forever()
