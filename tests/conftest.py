import sys
from pathlib import Path

# Add component folders to the Python path for tests
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Knot-Mesh"))
sys.path.insert(0, str(ROOT / "Knot-Veil"))
sys.path.insert(0, str(ROOT / "Knot-Scribe"))
sys.path.insert(0, str(ROOT / "Knot-Drift"))
