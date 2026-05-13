"""Resolve project root and external tool paths (Poppler, Tesseract)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def project_root() -> str:
    """Repository root (parent of ``src``)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _bin_has_pdfinfo(bin_dir: str) -> bool:
    if not bin_dir or not os.path.isdir(bin_dir):
        return False
    return os.path.isfile(os.path.join(bin_dir, "pdfinfo.exe")) or os.path.isfile(
        os.path.join(bin_dir, "pdfinfo")
    )


def _poppler_from_local_vendor() -> str | None:
    """``./poppler-windows/.../Library/bin`` (see ``scripts/download_poppler.py``)."""
    vendor = Path(project_root()) / "poppler-windows"
    if not vendor.is_dir():
        return None
    for pdfinfo in vendor.rglob("pdfinfo.exe"):
        parent = str(pdfinfo.parent.resolve())
        if _bin_has_pdfinfo(parent):
            return parent
    return None


def resolve_poppler_bin() -> str | None:
    """
    Directory that contains ``pdfinfo`` / ``pdfinfo.exe`` (Poppler ``bin``).

    Order: ``POPPLER_BIN`` env → ``./poppler-windows`` (vendor download) →
    legacy bundled ``poppler-24.08.0/Library/bin`` → ``PATH``.
    """
    env = os.environ.get("POPPLER_BIN", "").strip()
    if env and _bin_has_pdfinfo(env):
        return os.path.abspath(env)

    vendor_bin = _poppler_from_local_vendor()
    if vendor_bin:
        return vendor_bin

    bundled = os.path.join(project_root(), "poppler-24.08.0", "Library", "bin")
    if _bin_has_pdfinfo(bundled):
        return os.path.abspath(bundled)

    pdfinfo = shutil.which("pdfinfo") or shutil.which("pdfinfo.exe")
    if pdfinfo:
        parent = os.path.dirname(os.path.abspath(pdfinfo))
        if _bin_has_pdfinfo(parent):
            return parent

    return None


def resolve_tesseract_cmd() -> str | None:
    """Path to ``tesseract`` executable."""
    env = os.environ.get("TESSERACT_CMD", "").strip()
    if env and os.path.isfile(env):
        return os.path.abspath(env)

    which = shutil.which("tesseract")
    if which:
        return which

    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.isfile(candidate):
            return candidate

    return None
