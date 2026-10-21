"""Shared configuration, paths and helpers for the Zoya's English pipeline."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

# Raw lesson assets. The canonical folder is Study-Material/Source-Files;
# a Windows-style literal directory name and plain input_chapters/ are also
# honoured so drops from any environment land in a recognized place.
SOURCE_DIRS: tuple[Path, ...] = (
    ROOT / "Study-Material" / "Source-Files",
    ROOT / "Study-Material\\Source-Files",
    ROOT / "input_chapters",
)

EXTRACTED_DIR = ROOT / "pipeline" / "extracted"
LOGS_DIR = ROOT / "pipeline" / "logs"
STATE_FILE = ROOT / "pipeline" / ".state.json"
MATERIALS_DIR = ROOT / "materials"
CSS_PATH = ROOT / "assets" / "css" / "main.css"
MATERIALS_HTML = ROOT / "materials.html"

PDF_EXTS = {".pdf"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}

# Chapter design languages — deterministically derived from the chapter slug
# so each chapter keeps a stable, distinct visual identity across rebuilds.
THEMES: tuple[str, ...] = ("slate", "ink", "clay", "sage", "plum", "mist", "ember", "moss")


def slugify(source: Path | str) -> str:
    """Human 'Commonly Confused Words' -> commonly-confused-words."""
    stem = Path(source).stem
    stem = stem.replace("_copy_copy", "").replace("_copy", "")
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "chapter"


def humanize(source: Path | str) -> str:
    """'001 - Complete 30-Day English Study Plan' -> 'Complete 30-Day English Study Plan'."""
    stem = Path(source).stem
    stem = stem.replace("_copy_copy", "").replace("_copy", "")
    stem = re.sub(r"\s+pdf\s*$", "", stem, flags=re.IGNORECASE)  # trailing 'pdf' leak from copy-paste filenames
    stem = re.sub(r"^\d{1,3}[\s]*[-_.][\s]*", "", stem)          # numbered prefixes like '001 - ' or '5. '
    stem = re.sub(r"^0\d{1,2}[\s]+", "", stem)                   # zero-padded numbering without separator
    stem = re.sub(r"\s{2,}", " ", stem).strip()
    return " ".join(
        word.capitalize() if len(word) > 1 and word.isupper() and word.isalpha() else word
        for word in stem.split()
    )


def pick_theme(seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return THEMES[int(digest[:8], 16) % len(THEMES)]


def chapter_number(hero_text: str) -> int | None:
    """Best-effort module number from a filename/slug + title.

    Keyworded matches (chapter/unit/lesson/module/part) are trusted for any
    value; bare fallback numbers are only accepted for small counters (<= 40)
    so word counts like '500' or '300' in titles never leak in.
    """
    text = hero_text.lower()
    match = re.search(r"(?:chapter|unit|lesson|module|part|ch)[\s\-_.#]*(\d{1,3})", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b0*(\d{1,2})\b", text)
    if match and int(match.group(1)) <= 40:
        return int(match.group(1))
    return None


def ensure_runtime_dirs() -> None:
    for directory in (EXTRACTED_DIR, LOGS_DIR, MATERIALS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
