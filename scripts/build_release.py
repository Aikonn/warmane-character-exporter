"""Build warmane-character-exporter-windows.zip: sources, launcher, definition data and embedded Python 3.12.

python scripts/build_release.py [--output DIR]
Needs library/definitions/client-export.json and library/acore/items.db (both are committed).
Downloads the official Windows embeddable Python once (cached next to the zip).
"""
from __future__ import annotations

import argparse
import urllib.request
import zipfile
from pathlib import Path

PYTHON_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
ROOT = Path(__file__).resolve().parent.parent
TOP = "warmane-character-exporter"
FILES = ["Start-Report.cmd", "Start-Report.ps1", "README.md", "pyproject.toml",
         "library/definitions/client-export.json", "library/acore/items.db"]
PTH = "python312.zip\r\n.\r\n..\\..\\src\r\nimport site\r\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    embed = args.output / "python-embed.zip"
    if not embed.exists():
        urllib.request.urlretrieve(PYTHON_URL, embed)
    target = args.output / "warmane-character-exporter-windows.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for name in FILES:
            out.write(ROOT / name, f"{TOP}/{name}")
        for path in sorted((ROOT / "src").rglob("*.py")):
            out.write(path, f"{TOP}/{path.relative_to(ROOT).as_posix()}")
        with zipfile.ZipFile(embed) as py:
            for info in py.infolist():
                if info.filename.endswith("._pth"):
                    out.writestr(f"{TOP}/.tools/python312/{info.filename}", PTH)
                else:
                    out.writestr(f"{TOP}/.tools/python312/{info.filename}", py.read(info))
    print(f"built {target} ({target.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
