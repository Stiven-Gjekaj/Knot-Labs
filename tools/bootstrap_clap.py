#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from urllib.parse import urlparse


def main() -> None:
    ap = argparse.ArgumentParser(description="Download a CLAP checkpoint to a local path")
    ap.add_argument('--url', required=True, help='Checkpoint URL (e.g., https://.../clap_ckpt.pt)')
    ap.add_argument('--out', default='clap_ckpt.pt', help='Destination filepath')
    args = ap.parse_args()

    # Basic URL validation for friendlier errors
    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or "..." in parsed.netloc:
        print("Error: --url must be a full HTTP(S) URL to a checkpoint file.")
        print("Example (LAION-CLAP htsat-unfused):")
        print("  https://huggingface.co/laion/clap-htsat-unfused/resolve/main/630k-best.pt")
        sys.exit(2)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    print(f"Downloading {args.url} -> {args.out}")
    try:
        urllib.request.urlretrieve(args.url, args.out)
    except Exception as e:
        print("Download failed. Common fixes:")
        print("- Verify the URL is public and correct (no login needed)")
        print("- If behind a proxy, set HTTPS_PROXY/HTTP_PROXY env vars")
        print("- If using a corporate CA, set REQUESTS_CA_BUNDLE/PIP_CERT to your CA pem")
        print(f"Exception: {e}")
        sys.exit(1)
    print("Done.")
    print("Set environment for runtime:")
    print(f"  PowerShell:  $env:CLAP_CKPT_PATH = '{os.path.abspath(args.out)}'")
    print(f"  bash/zsh:    export CLAP_CKPT_PATH='{os.path.abspath(args.out)}'")


if __name__ == '__main__':
    main()
