from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .errors import ApiError

# The server is threaded and several handlers read-modify-write the same JSON files (takes.json, audit.json).
# Every such update takes this lock so two requests cannot lose each other's write.
STATE_LOCK = threading.RLock()


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ApiError(500, f"{path.name} is not valid JSON: {e}")


def write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
