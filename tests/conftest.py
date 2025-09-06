import os
import sys

# Ensure repository root is on sys.path for imports like Mesh, Drift, demo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Also add module subdirs whose modules rely on direct imports
DRIFT_DIR = os.path.join(ROOT, 'Drift')
if DRIFT_DIR not in sys.path:
    sys.path.insert(0, DRIFT_DIR)
