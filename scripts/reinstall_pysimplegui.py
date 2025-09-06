#!/usr/bin/env python3
from __future__ import annotations

import importlib
import subprocess
import sys


PRIVATE_INDEX = "https://PySimpleGUI.net/install"


def has_valid_pysimplegui() -> bool:
    try:
        mod = importlib.import_module("PySimpleGUI")
        return hasattr(mod, "Window")
    except Exception:
        return False


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        return 127


def main() -> int:
    py = sys.executable
    if has_valid_pysimplegui():
        print("PySimpleGUI appears correctly installed.")
        return 0

    print("PySimpleGUI missing or incompatible; attempting reinstall from private index…")
    # Best-effort uninstall and cache purge
    run([py, "-m", "pip", "uninstall", "-y", "PySimpleGUI"])  # ignore status
    run([py, "-m", "pip", "cache", "purge"])  # ignore status
    code = run([py, "-m", "pip", "install", "--force-reinstall", "--extra-index-url", PRIVATE_INDEX, "PySimpleGUI"]) 
    if code != 0:
        print("Reinstall failed. See README for manual steps.")
        return code

    if not has_valid_pysimplegui():
        print("PySimpleGUI still not importable/valid after reinstall.")
        return 2

    print("PySimpleGUI installed and valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

