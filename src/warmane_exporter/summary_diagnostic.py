from __future__ import annotations

import argparse
import json
from pathlib import Path

from .summary_parser import parse_summary_capture_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a saved Warmane summary DOM capture offline.")
    parser.add_argument("capture_file", help="Path to saved HTML file")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = parse_summary_capture_file(Path(args.capture_file))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
