"""The render lab's audio helpers live in tools/render_corpus/recipe_audio.py so the render workers can use the same code."""
import sys
from pathlib import Path

_RC = str(Path(__file__).resolve().parents[4] / "tools/render_corpus")
if _RC not in sys.path:
    sys.path.insert(0, _RC)

from recipe_audio import *  # noqa: E402,F401,F403
from recipe_audio import __dict__ as _d  # noqa: E402,F401
globals().update({k: v for k, v in _d.items() if not k.startswith("__")})
