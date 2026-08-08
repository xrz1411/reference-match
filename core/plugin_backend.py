#!/usr/bin/env python3
"""Small JSON entry point used by the Resolve Workflow Integration plugin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate_lut import load_rgb_tensor
from lutcore.reference_analysis import analyse_reference


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyse a reference image for the Resolve LUT plugin.")
    parser.add_argument("--reference", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.reference.is_file():
        raise FileNotFoundError(args.reference)
    print(json.dumps(analyse_reference(load_rgb_tensor(args.reference)), ensure_ascii=False))


if __name__ == "__main__":
    main()
