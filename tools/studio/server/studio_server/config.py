from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BACKEND_URL = "http://127.0.0.1:8909"


@dataclass(frozen=True)
class Config:
    root: Path = REPO_ROOT
    backend_url: str = DEFAULT_BACKEND_URL

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def studio(self) -> Path:
        return self.data / "studio"

    @property
    def voice_design(self) -> Path:
        return self.data / "voice_design"

    @property
    def voices(self) -> Path:
        return self.data / "voices"

    @property
    def render(self) -> Path:
        return self.data / "render"

    def file_roots(self) -> tuple[Path, ...]:
        return (self.voices, self.render, self.studio, self.voice_design, self.data / "bg3_voices", self.data / "portraits")

    def _inside(self, rel: str, roots: tuple[Path, ...]) -> Path | None:
        if not rel or rel.startswith("/") or "\x00" in rel:
            return None
        p = (self.root / rel).resolve()
        if p.is_file() and any(r.resolve() in p.parents for r in roots):
            return p
        return None

    def resolve_file(self, rel: str) -> Path | None:
        """Repo-relative path -> real file under a served root, else None."""
        return self._inside(rel, self.file_roots())

    def under_data(self, rel: str) -> Path | None:
        """Repo-relative path -> real file anywhere under data/, else None (used for clone references)."""
        return self._inside(rel, (self.data,))
