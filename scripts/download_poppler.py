"""
Download Poppler for Windows into ./poppler-windows (gitignored).

Run from the repository root:

    python scripts/download_poppler.py
"""

from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

# Pinned release (update URL when upgrading)
ZIP_URL = (
    "https://github.com/oschwartz10612/poppler-windows/releases/download/"
    "v26.02.0-0/Release-26.02.0-0.zip"
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    dest_dir = root / "poppler-windows"
    zip_path = root / ".poppler-download.zip"

    if dest_dir.is_dir():
        print(f"Removing existing {dest_dir}")
        shutil.rmtree(dest_dir)

    print(f"Downloading Poppler from:\n  {ZIP_URL}")
    urllib.request.urlretrieve(ZIP_URL, zip_path)  # noqa: S310 — trusted release URL

    print(f"Extracting to {dest_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    zip_path.unlink(missing_ok=True)

    for pdfinfo in dest_dir.rglob("pdfinfo.exe"):
        print(f"OK — Poppler bin: {pdfinfo.parent}")
        return 0

    print("ERROR: pdfinfo.exe not found after extract.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
