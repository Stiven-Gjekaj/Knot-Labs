#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # Ensure Veil/src is importable
    root = Path(__file__).resolve().parents[1]
    veil_src = root / 'Veil' / 'src'
    if str(veil_src) not in sys.path:
        sys.path.insert(0, str(veil_src))
    from veil.run import main as veil_main  # type: ignore
    veil_main()


if __name__ == '__main__':
    main()

