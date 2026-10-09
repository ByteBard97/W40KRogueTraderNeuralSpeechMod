from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import Config
from .errors import ApiError


@dataclass
class Request:
    cfg: Config
    model: Any
    params: dict = field(default_factory=dict)
    query: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)


Handler = Callable[[Request], Any]


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern, Handler]] = []

    def add(self, method: str, pattern: str, fn: Handler) -> None:
        rx = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$")
        self._routes.append((method, rx, fn))

    def dispatch(self, method: str, path: str, query: dict, body: dict, cfg: Config, model) -> tuple[int, object]:
        for m, rx, fn in self._routes:
            hit = rx.match(path)
            if m != method or not hit:
                continue
            try:
                out = fn(Request(cfg, model, hit.groupdict(), query, body))
            except ApiError as e:
                return e.status, {"error": e.message}
            except Exception as e:  # a bad body (missing key, wrong type) must answer, not drop the connection
                return 500, {"error": f"{type(e).__name__}: {e}"}
            return out if isinstance(out, tuple) else (200, out)
        return 404, {"error": f"no route {method} {path}"}
