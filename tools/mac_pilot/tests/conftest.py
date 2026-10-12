import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "audio_emotion_labeling"))   # families.py (bundled next to run_pilot.py on the Mac)
