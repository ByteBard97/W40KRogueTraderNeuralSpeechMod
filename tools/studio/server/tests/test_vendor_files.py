import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio_server import vendor_files  # noqa: E402
from studio_server.app import REPO_ROOT, make_server  # noqa: E402
from studio_server.config import Config  # noqa: E402
from studio_server.model import ModelClient  # noqa: E402

WASM_MAGIC = b"\0asm"


@pytest.fixture
def root(tmp_path):
    for folder, names in {"faustwasm": ["index.js"], "libfaust-wasm": ["libfaust-wasm.wasm", "libfaust-wasm.data", "libfaust-wasm.js", "x.d.ts"]}.items():
        d = tmp_path / "tools/fx_lab/vendor" / folder
        d.mkdir(parents=True)
        for n in names:
            (d / n).write_bytes(WASM_MAGIC + b"\1\0\0\0")
    (tmp_path / "tools/fx_lab/vendor/secret.txt").write_text("x")
    return tmp_path


@pytest.mark.parametrize("url, ctype", [
    ("/faustwasm/index.js", "text/javascript; charset=utf-8"),
    ("/libfaust-wasm/libfaust-wasm.wasm", "application/wasm"),
    ("/libfaust-wasm/libfaust-wasm.data", "application/octet-stream"),
    ("/libfaust-wasm/libfaust-wasm.js", "text/javascript; charset=utf-8"),
    ("/libfaust-wasm/x.d.ts", "application/octet-stream"),
])
def test_resolve_finds_each_vendor_file_with_its_content_type(root, url, ctype):
    f, got = vendor_files.resolve(root, url)
    assert f.is_file() and f.name == url.rsplit("/", 1)[1] and got == ctype


@pytest.mark.parametrize("url", [
    "/faustwasm/../../x", "/faustwasm/../secret.txt", "/faustwasm/%2e%2e/secret.txt", "/faustwasm/..%2fsecret.txt",
    "/faustwasm/%2e%2e%2f%2e%2e%2fx", "/faustwasm//etc/passwd", "/faustwasm/..\\secret.txt", "/faustwasm/",
    "/faustwasm", "/faustwasm/nope.js", "/libfaust-wasm/index.js", "/vendor/faustwasm/index.js",
    "/faustwasmx/index.js", "/faustwasm/sub/index.js", "/index.js", "/api/ref/speakers",
])
def test_resolve_refuses_traversal_unknown_names_and_other_prefixes(root, url):
    assert vendor_files.resolve(root, url) is None


@pytest.fixture
def base(tmp_path):
    srv = make_server(Config(root=tmp_path), ModelClient("http://127.0.0.1:9"), port=0, web_dist=tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_the_server_sends_the_compiler_wasm_with_the_wasm_type(base):
    if not (REPO_ROOT / vendor_files.VENDOR_REL / "libfaust-wasm/libfaust-wasm.wasm").is_file():
        pytest.skip("vendor folder not present")
    with urllib.request.urlopen(base + "/libfaust-wasm/libfaust-wasm.wasm") as r:
        assert r.status == 200 and r.headers["Content-Type"] == "application/wasm" and r.headers["Cache-Control"] == "no-store"
        assert r.read().startswith(WASM_MAGIC)


def test_the_server_does_not_serve_files_outside_the_vendor_folders(base):
    with pytest.raises(urllib.error.HTTPError) as e:           # falls through to the static fallback: no dist, so 503, never the file
        urllib.request.urlopen(base + "/faustwasm/%2e%2e/README.md")
    assert e.value.code == 503
