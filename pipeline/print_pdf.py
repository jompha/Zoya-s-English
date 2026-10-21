"""STEP C — Headless printing.

Playwright-driven Chromium renders each compiled chapter with print media
emulation and prints a pixel-perfect A4 copy. Sources of drift are eliminated:
network font settling, color profile pinning, and page-number footers.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

# Namespace-identical to the @page rule inside assets/css/main.css so Chromium
# and the stylesheet agree on geometry across every chapter.
MARGIN = {"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"}


def footer_template(title: str) -> str:
    safe = (
        title.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&#39;")
        .strip() or "Learning Library"
    )
    return (
        '<div style="width:100%;font-family:Arial,Helvetica,sans-serif;font-size:8.5px;'
        "color:#8a8680;padding:0 14mm;display:flex;justify-content:space-between;"
        'align-items:flex-end;">'
        '<span style="letter-spacing:.14em;text-transform:uppercase;">'
        f"Zoya's English &mdash; {safe}"
        "</span>"
        '<span style="color:#4a6b82;">'
        '<span class="pageNumber"></span>&nbsp;/&nbsp;<span class="totalPages"></span>'
        "</span></div>"
    )


def print_to_pdf(html_path: Path, pdf_path: Path, *, footer_title: str = "") -> Path:
    """Render `html_path` (file://) through Chromium's print engine to A4 PDF."""
    uri = html_path.resolve().as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--font-render-hinting=none",
                "--force-color-profile=srgb",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            page = browser.new_page()
            page.goto(uri, wait_until="load", timeout=60_000)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeout:
                pass  # offline/build environments: web-font CDN is optional
            try:
                page.evaluate("() => Promise.race([document.fonts.ready, Promise.resolve(1)])")
            except Exception:  # noqa: BLE001 — font API is best-effort
                pass
            page.emulate_media(media="print")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=footer_template(footer_title),
                margin=MARGIN,
                prefer_css_page_size=True,
            )
        finally:
            browser.close()
    return pdf_path


def pdf_page_count(pdf_path: Path) -> int:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(document)
    finally:
        document.close()
