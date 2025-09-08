#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import urllib.request


def main() -> None:
    ap = argparse.ArgumentParser(description="Download a CLAP checkpoint to a local path")
    ap.add_argument('--url', required=True, help='Checkpoint URL (e.g., https://.../clap_ckpt.pt)')
    ap.add_argument('--out', default='clap_ckpt.pt', help='Destination filepath')
    args = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    print(f"Downloading {args.url} -> {args.out}")
    urllib.request.urlretrieve(args.url, args.out)
    print("Done.")
    print("Set environment for runtime:")
    print(f"  PowerShell:  $env:CLAP_CKPT_PATH = '{os.path.abspath(args.out)}'")
    print(f"  bash/zsh:    export CLAP_CKPT_PATH='{os.path.abspath(args.out)}'")


if __name__ == '__main__':
    main()

