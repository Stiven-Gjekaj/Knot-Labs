"""Veil package.

This lightweight wrapper ensures that the actual implementation under
``Veil/src`` is available on the Python path.  Importing ``veil`` will
prepend the internal source directory to both ``sys.path`` and the
package's ``__path__`` so that submodules like ``veil.run`` are
discoverable without manually tweaking ``PYTHONPATH``.
"""

from __future__ import annotations

import os
import sys

# Resolve "Veil/src/veil" relative to this file
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(os.path.dirname(_PKG_DIR), "Veil", "src")
_SRC_PKG = os.path.join(_SRC_DIR, "veil")

if os.path.isdir(_SRC_PKG):
    if _SRC_DIR not in sys.path:
        sys.path.insert(0, _SRC_DIR)
    if _SRC_PKG not in __path__:
        __path__.append(_SRC_PKG)  # type: ignore[name-defined]

