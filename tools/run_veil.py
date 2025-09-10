#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    from veil.run import main as veil_main  # type: ignore
    veil_main()


if __name__ == '__main__':
    main()

