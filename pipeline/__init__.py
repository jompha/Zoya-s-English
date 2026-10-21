"""Zoya's English — content pipeline package.

Modules
-------
config     Shared paths, constants, slug/theme helpers.
extract    STEP A — layout-aware extraction (Docling + OCR fallback).
compile    STEP B — markdown -> fully styled standalone chapter HTML.
print_pdf  STEP C — headless Chromium (Playwright) -> pixel-perfect A4 PDF.
index      STEP D — dashboard indexer (Beautiful Soup card rendering).
"""

__version__ = "1.0.0"
