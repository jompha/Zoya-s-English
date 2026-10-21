"""STEP A — Layout-aware extraction.

Primary engine : Docling — visual layout model, semantic tables, bold headers,
                 built-in OCR for scanned pages.
Fallback engine: pypdfium2 text-layer readers + pdf2image/tesseract OCR fed
                 into a structured plain-text -> markdown layout compiler.

Both engines return markdown so downstream compilation knows nothing about
where the content came from.
"""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import IMG_EXTS, PDF_EXTS, SOURCE_DIRS, ensure_runtime_dirs, slugify

# ---------------------------------------------------------------- data model


@dataclass
class ExtractedDoc:
    source: Path
    slug: str
    md: str
    engine: str
    pages: int
    warnings: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def words(self) -> int:
        return len(re.findall(r"\w+", self.md))

    @property
    def source_name(self) -> str:
        return self.source.name


# -------------------------------------------------------------- docling path

_CONVERTER = None
_OCR_LOGGED = {"done": False}


def _get_converter():
    # First conversion downloads Docling's layout/tableformer models into the
    # user cache — subsequent processes reuse it silently.
    global _CONVERTER
    if _CONVERTER is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TesseractCliOcrOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        # RapidOCR (docling 2.141's default here) returned empty results across
        # several scan batches; tesseract 5 CLI is the proven, honest engine for
        # this library. tesserocr (TesseractOcrOptions) is not installed.
        pipeline_options.ocr_options = TesseractCliOcrOptions(lang=["eng"])
        pipeline_options.do_table_structure = True
        if not _OCR_LOGGED["done"]:
            _OCR_LOGGED["done"] = True
        _CONVERTER = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
    return _CONVERTER


def _md_from_docling(path: Path) -> tuple[str, int]:
    converter = _get_converter()
    result = converter.convert(str(path))
    document = result.document
    try:
        pages = len(getattr(document, "pages", None) or [])
    except Exception:  # noqa: BLE001 — page count is advisory only
        pages = 0

    md = ""
    try:
        from docling_core.types.doc import ImageRefMode

        md = document.export_to_markdown(image_mode=ImageRefMode.DISCARD) or ""
    except Exception:  # noqa: BLE001 — older docling typings
        md = document.export_to_markdown() or ""

    # Embedded/base64 image artefacts have no place in a print document.
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "\n", md)
    md = re.sub(r"<!--[^>]*image[^>]*-->", "\n", md, flags=re.IGNORECASE)
    return md.strip(), pages


# ---------------------------------------------------------- fallback engines

def _pdf_text_pages(path: Path) -> list[str]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    try:
        texts: list[str] = []
        for page in document:
            try:
                texts.append((page.get_textpage().get_text_bounded() or "").strip())
            except Exception:  # noqa: BLE001 — odd page geometries
                texts.append("")
    finally:
        document.close()
    return texts


def _pdf_ocr_pages(path: Path, dpi: int = 220) -> list[str]:
    if shutil.which("tesseract") is None:
        raise RuntimeError("tesseract binary not found")
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(str(path), dpi=dpi)
    pages = []
    for image in images:
        pages.append((pytesseract.image_to_string(image, lang="eng") or "").strip())
    return pages


def _image_ocr_page(path: Path) -> list[str]:
    if shutil.which("tesseract") is None:
        raise RuntimeError("tesseract binary not found")
    import pytesseract
    from PIL import Image

    return [(pytesseract.image_to_string(Image.open(path), lang="eng") or "").strip()]


# ----------------------------------------------- plain-text layout compiler

_NOISE = re.compile(
    r"^(?:page\s*\d+(?:\s*(?:of|/)\s*\d+)?|\d+\s*/\s*\d+|[-–—_=•.]{3,})$",
    re.IGNORECASE,
)
_HEADING_KEYWORDS = re.compile(
    r"^(?:chapter|lesson|unit|part|section|module|exercise|activity|practice|"
    r"review|worksheet|starter|topic|speaking|grammar|vocabulary|reading|"
    r"writing|appendix|answer\s+key)\b",
    re.IGNORECASE,
)
_KEEP_OPENERS = ("chapter", "unit", "lesson", "module", "part")


def _heading_level(line: str, prev_blank: bool) -> int:
    """Heuristic for OCR/plain pages: isolated, short, title-like lines."""
    text = line.strip()
    if not prev_blank or not text or len(text) > 86:
        return 0
    if text.endswith((".", ",", ";", ":", "?", "!")):
        return 0
    words = text.split()
    if not 1 <= len(words) <= 18:
        return 0
    letters = [c for c in text if c.isalpha()]
    if letters and text.upper() == text:
        return 2 if len(letters) <= 44 else 1
    if _HEADING_KEYWORDS.match(text) and not text.endswith("."):
        return 1
    if len(words) >= 2:
        caps = sum(1 for word in words if word[:1].isupper())
        if caps >= max(2, len(words) - 1):
            return 1
    return 0


def _plain_pages_to_markdown(pages: list[str]) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            text = " ".join(part for part in paragraph if part)
            if text.strip():
                blocks.append(text)
            paragraph.clear()

    for index, raw in enumerate(pages, start=1):
        blocks.append(f"<!-- page {index} -->")
        prev_blank = True
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                flush()
                prev_blank = True
                continue
            if _NOISE.match(stripped):
                continue
            level = _heading_level(stripped, prev_blank)
            if level:
                flush()
                blocks.append("#" * (level + 1) + " " + stripped.rstrip("."))
                prev_blank = True
                continue
            paragraph.append(stripped)
            prev_blank = False
        flush()
    return "\n\n".join(blocks)


_OCR_PAGES_CACHE: dict[str, list[str]] = {}


def _cached_ocr_pages(path: Path) -> list[str]:
    key = str(path.resolve())
    texts = _OCR_PAGES_CACHE.get(key)
    if texts is None:
        texts = _pdf_ocr_pages(path)
        _OCR_PAGES_CACHE[key] = texts
    return texts


def _tesseract_reference_words(path: Path) -> int:
    """Whole-page tesseract yield — the honest word-count baseline a layout
    model must at least approach before its structure can be trusted."""
    return sum(len(re.findall(r"\w+", text)) for text in _cached_ocr_pages(path))


def _fallback_md(path: Path, warnings: list[str]) -> tuple[str, str, int]:
    if path.suffix.lower() in PDF_EXTS:
        texts = _pdf_text_pages(path)
        if any(text.strip() for text in texts):
            sparse_pages = sum(1 for text in texts if len(text) < 40)
            if sparse_pages >= len(texts) / 2:
                warnings.append("text layer sparse — rasterizing via pdf2image + tesseract OCR")
                texts = _cached_ocr_pages(path)
                engine = "pdf2image + tesseract OCR"
            else:
                engine = "pdf text layer"
        else:
            warnings.append("no text layer — rasterizing via pdf2image + tesseract OCR")
            texts = _cached_ocr_pages(path)
            engine = "pdf2image + tesseract OCR"
        if not any(text.strip() for text in texts):
            raise RuntimeError("no extractable text (no layer, no OCR output)")
        return _plain_pages_to_markdown(texts), engine, len(texts)

    texts = _image_ocr_page(path)
    if not any(text.strip() for text in texts):
        raise RuntimeError("no OCR result from image source")
    return _plain_pages_to_markdown(texts), "tesseract OCR (image)", len(texts)


# ------------------------------------------------------------------ public


def discover_sources(extra_dirs: tuple[Path, ...] = ()) -> list[Path]:
    """Collect every recognized source file, de-duplicated, sorted by name."""
    ensure_runtime_dirs()
    found: dict[str, Path] = {}
    for base in [*SOURCE_DIRS, *extra_dirs]:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() in PDF_EXTS | IMG_EXTS:
                found[str(path.resolve())] = path
    return sorted(found.values(), key=lambda item: item.name.lower())


def extract_content(path: Path) -> ExtractedDoc:
    """Extract one source to markdown. Never hard-fails: degradation is loud."""
    ensure_runtime_dirs()
    slug = slugify(path)
    warnings: list[str] = []
    md, engine, pages = "", "unknown", 0

    started = time.perf_counter()
    if path.suffix.lower() in PDF_EXTS:
        # Docling first (layout model + semantic tables); OCR fallback second.
        try:
            md, pages = _md_from_docling(path)
            engine = "docling"
        except Exception as exc:  # noqa: BLE001 — engine swap, not a crash
            warnings.append(f"docling unavailable ({exc.__class__.__name__}: {exc}) — graceful fallback engaged")
            try:
                md, engine, pages = _fallback_md(path, warnings)
            except Exception as exc2:  # noqa: BLE001
                warnings.append(f"fallback failed ({exc2}) — emitting stub chapter")
                md, engine = "", "stub"
        else:
            # Coverage gate: the layout model sometimes silently drops content
            # (dense two-column quiz sheets get mis-segmented into degraded
            # tables). Cross-check the word yield against plain tesseract; if
            # Docling returns far less text than the OCR layer found on the
            # same pages, trust the full-coverage OCR instead.
            try:
                reference_words = _tesseract_reference_words(path)
                if reference_words and len(re.findall(r"\w+", md)) < 0.6 * reference_words:
                    coverage = len(re.findall(r"\w+", md)) / reference_words
                    warnings.append(
                        f"docling coverage {coverage:.0%} of tesseract baseline "
                        f"({len(md.split())} vs {reference_words} words) — full-coverage fallback engaged"
                    )
                    full_md, full_engine, full_pages = _fallback_md(path, warnings)
                    md, engine, pages = full_md, full_engine, full_pages
            except Exception as exc:  # noqa: BLE001 — gate failure never aborts
                warnings.append(f"coverage gate skipped ({exc.__class__.__name__})")
    else:
        try:
            md, engine, pages = _fallback_md(path, warnings)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"extraction failed ({exc}) — emitting stub chapter")
            md, engine = "", "stub"

    if not md.strip():
        md = (
            f"## {humanized_title(slugify(path))}\n\n"
            "_This source could not be parsed automatically. Move it into "
            "`Study-Material/Source-Files/` and rerun the pipeline._"
        )

    return ExtractedDoc(
        source=path,
        slug=slug,
        md=md,
        engine=engine,
        pages=pages,
        warnings=warnings,
        elapsed=round(time.perf_counter() - started, 2),
    )


def humanized_title(slug: str) -> str:
    return " ".join(part.capitalize() if len(part) > 3 else part for part in slug.split("-"))
