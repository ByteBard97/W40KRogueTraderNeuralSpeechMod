import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import run_pilot
from backends import ChatBackend

requests_seen = []


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests_seen.append(body)
        text = body["messages"][0]["content"][-1]["text"]
        if "closer" in text:
            ans = '{"closer": "A"}'          # always slot A: consistent verdict must be None
            lp = None
        else:
            ans = '{"family": "warm"}'
            toks = [{"token": '{"', "logprob": 0, "top_logprobs": []}, {"token": "family", "logprob": 0, "top_logprobs": []},
                    {"token": '": "', "logprob": 0, "top_logprobs": []},
                    {"token": "w", "logprob": -0.1, "top_logprobs": [{"token": "w", "logprob": -0.1}] + [
                        {"token": t, "logprob": -3.0} for t in ("st", "an", "ang", "sa", "su", "sar", "o")]}]
            lp = {"content": toks}
        out = json.dumps({"choices": [{"message": {"content": ans}, "logprobs": lp}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    (tmp_path / "data").mkdir()
    (tmp_path / "clips").mkdir()
    for n in ("r.wav", "a.wav", "b.wav"):
        (tmp_path / "clips" / n).write_bytes(b"RIFFxxxx")
    gt = [{"event": f"e{i}", "family": "warm" if i % 2 else "stern", "wav": "clips/r.wav", "text": "t", "word": "x"}
          for i in range(4)]
    pairs = [{"id": "p1", "axis": "emotion", "emotion": "relieved", "instruct": "warm", "reference_wav": "clips/r.wav",
              "a": "clips/a.wav", "b": "clips/b.wav"}]
    (tmp_path / "data/gt.json").write_text(json.dumps(gt))
    (tmp_path / "data/pairs.json").write_text(json.dumps(pairs))
    (tmp_path / "data/answers.json").write_text(json.dumps({"p1": "a"}))
    monkeypatch.setattr(run_pilot, "HERE", tmp_path)
    monkeypatch.setattr(run_pilot, "DATA", tmp_path / "data")
    monkeypatch.setattr(run_pilot, "RES", tmp_path / "results")
    requests_seen.clear()
    yield ChatBackend(f"http://127.0.0.1:{srv.server_port}")
    srv.shutdown()


class A:
    transcript = False


def test_single_is_resumable_and_reports_prior_correction(server, tmp_path):
    run_pilot.cmd_single(server, A())
    n = len(requests_seen)
    assert n == 4
    audio = requests_seen[0]["messages"][0]["content"][0]
    assert audio["type"] == "input_audio" and audio["input_audio"]["format"] == "wav"
    run_pilot.cmd_single(server, A())          # resume: nothing new
    assert len(requests_seen) == n
    rep = run_pilot.single_report(tmp_path / "results/single_audio.jsonl")
    assert rep["raw"]["top1"] == 0.5 and "prior_corrected" in rep


def test_pair_position_biased_model_gets_no_verdict(server, tmp_path, capsys):
    run_pilot.cmd_pair(server, A())
    assert len(requests_seen) == 2 and len(requests_seen[0]["messages"][0]["content"]) == 4   # 3 audio + text
    assert run_pilot.pair_verdicts() == {"p1": None}
    run_pilot.cmd_report(server, A())
    rep = json.loads((tmp_path / "results/report.json").read_text())
    assert rep["pair"]["position_bias"] == 1.0 and rep["pair"]["consistent"] == 0
