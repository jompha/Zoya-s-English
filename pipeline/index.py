"""STEP D — Dashboard indexer.

Beautiful Soup scans the generated `materials/` directory, reads each chapter's
embedded metadata, and rewrites the card grid inside `materials.html` between
the MATERIALS:START / MATERIALS:END markers — idempotent on every pipeline run.
"""

from __future__ import annotations

import json
import re
from datetime import date
from html import escape as html_escape
from pathlib import Path

from bs4 import BeautifulSoup

from .config import MATERIALS_DIR, MATERIALS_HTML

GRID_START = "<!-- MATERIALS:START -->"
GRID_END = "<!-- MATERIALS:END -->"

# Mirrors the [data-theme] accent declarations in assets/css/main.css so cards
# can render their chapter's design language without parsing the stylesheet.
THEME_ACCENTS = {
    "slate": {"accent": "#4a6b82", "tint": "#edf2f6"},
    "ink": {"accent": "#46474b", "tint": "#f1efe9"},
    "clay": {"accent": "#b06a48", "tint": "#f9efe7"},
    "sage": {"accent": "#5f7c60", "tint": "#eff5ef"},
    "plum": {"accent": "#7d5a72", "tint": "#f6eff4"},
    "mist": {"accent": "#3f7a75", "tint": "#ebf4f2"},
    "ember": {"accent": "#a8543f", "tint": "#f9ece8"},
    "moss": {"accent": "#72783f", "tint": "#f5f5e9"},
}

EMPTY_GRID = f"""{GRID_START}
<div class="card card-empty">
  <div class="card-kicker">Library empty</div>
  <h3>No study modules published yet</h3>
  <p>Drop chapter PDFs into <code>Study-Material/Source-Files/</code> and run
  <code>python3 run_pipeline.py</code> — finished web views and print-ready PDFs
  will appear here automatically.</p>
</div>
{GRID_END}"""


def scan_chapters(materials_dir: Path | None = None) -> list[dict]:
    directory = materials_dir or MATERIALS_DIR
    chapters: list[dict] = []

    for html_path in sorted(directory.glob("*.html")):
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        article = soup.find("article", class_="chapter-doc")

        def _meta() -> dict:
            script = soup.find("script", id="doc-meta")
            if script is None:
                return {}
            try:
                return json.loads(script.string or "{}")
            except Exception:  # noqa: BLE001 — malformed meta stays non-fatal
                return {}

        if article is not None:
            meta = _meta()
            title_element = soup.find("h1", class_="doc-title")
            kicker = soup.select_one(".doc-kicker")
            chapter_data = {
                "slug": article.get("data-chapter") or html_path.stem,
                "theme": article.get("data-theme") or "slate",
                "number": meta.get("number"),
                "kicker": kicker.get_text(" ", strip=True) if kicker else "Study Module",
                "title": title_element.get_text(" ", strip=True) if title_element else html_path.stem,
                "meta": meta,
                "html_name": html_path.name,
                "pdf_exists": (directory / f"{html_path.stem}.pdf").exists(),
            }
        else:
            meta = _meta()
            if not meta:  # not a pipeline chapter page — leave it untouched
                continue
            pdf_path = directory / f"{html_path.stem}.pdf"
            chapter_data = {
                "slug": meta.get("slug") or html_path.stem,
                "theme": meta.get("theme") or "slate",
                "number": meta.get("number"),
                "kicker": (
                    f"Zoya's English — Study Module {int(meta['number']):02d}"
                    if meta.get("number")
                    else "Zoya's English — Study Module"
                ),
                "title": meta.get("title") or html_path.stem,
                "meta": meta,
                "html_name": html_path.name,
                "pdf_exists": pdf_path.exists(),
            }

        pdf_size = (directory / chapter_data["slug"]).with_suffix(".pdf")
        chapter_data["pdf_size"] = pdf_size.stat().st_size if pdf_size.exists() else 0
        chapters.append(chapter_data)

    chapters.sort(
        key=lambda c: (
            c["number"] is None,
            c["number"] if isinstance(c["number"], int) else 0,
            str(c["title"]).lower(),
        )
    )
    return chapters


def _human_size(num_bytes: int) -> str:
    if num_bytes >= 1_048_576:
        return f"{num_bytes / 1_048_576:.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes} B"


def _card(chapter: dict) -> str:
    accents = THEME_ACCENTS.get(chapter["theme"], THEME_ACCENTS["slate"])
    slug = html_escape(str(chapter["slug"]), quote=True)
    title = html_escape(str(chapter["title"]))
    kicker = html_escape(str(chapter["kicker"]))
    meta = chapter["meta"] or {}
    teaser = html_escape(str(meta.get("teaser") or "") or "Compiled from the original source — see the web edition for full module content.")
    number_value = chapter["number"]
    number_label = html_escape(f"{int(number_value):02d}") if number_value else "·"
    sections = meta.get("sections", 0)
    pages = meta.get("pages") or 0
    reading = max(1, int(meta.get("reading_min") or ((meta.get("words") or 0) + 179) // 180))
    meta_bits = [f"{sections} sections", f"~{reading} min read"]
    if pages:
        meta_bits.append(f"{pages} source pages")
    meta_html = "".join(f"<li>{html_escape(str(bit))}</li>" for bit in meta_bits)

    if chapter["pdf_exists"]:
        pdf_button = (
            f'<a class="btn btn-ghost btn-sm" href="materials/{slug}.pdf" download>'
            f'Download PDF<span class="btn-note">{_human_size(int(chapter["pdf_size"]))}</span></a>'
        )
        tags = "web pdf"
    else:
        pdf_button = '<span class="btn btn-ghost btn-sm is-disabled" aria-disabled="true">PDF prints on next run</span>'
        tags = "web"

    return (
        f'<article class="card card-chapter" data-theme="{chapter["theme"]}" data-tags="{tags}" '
        f'style="--card-accent:{accents["accent"]};--card-tint:{accents["tint"]}">'
        f'<p class="chapter-num" aria-hidden="true">{number_label}</p>'
        f'<div class="card-kicker">{kicker}</div>'
        f'<h3 class="card-title"><a href="materials/{slug}.html">{title}</a></h3>'
        f'<p class="card-teaser">{teaser}</p>'
        f'<ul class="card-meta">{meta_html}</ul>'
        f'<div class="card-actions no-print">'
        f'<a class="btn btn-solid btn-sm" href="materials/{slug}.html">Open web view</a>'
        f"{pdf_button}"
        f"</div></article>"
    )


def render_cards(chapters: list[dict]) -> str:
    if not chapters:
        return EMPTY_GRID
    parts = [GRID_START]
    for chapter in chapters:
        parts.append(_card(chapter))
    parts.append(GRID_END)
    return "\n".join(parts)


def update_dashboard(dashboard: Path | None = None, chapters: list[dict] | None = None) -> tuple[Path, int]:
    """Rewrite the card grid region of materials.html in one idempotent pass."""
    dashboard = dashboard or MATERIALS_HTML
    chapters = scan_chapters() if chapters is None else chapters
    text = dashboard.read_text(encoding="utf-8")

    if GRID_START not in text or GRID_END not in text:
        raise RuntimeError(
            "materials.html is missing the MATERIALS:START/END markers — "
            "restore them around the card grid before indexing."
        )

    grid_pattern = re.compile(re.escape(GRID_START) + r".*?" + re.escape(GRID_END), re.S)
    text = grid_pattern.sub(lambda _match: render_cards(chapters), text, count=1)

    text, n_count = re.subn(
        r'(<span id="materials-count">)[^<]*(</span>)',
        lambda match: match.group(1) + str(len(chapters)) + match.group(2),
        text,
        count=1,
    )
    if not n_count:  # template may not carry the counter — non-fatal
        pass

    text, n_date = re.subn(
        r'(<time\b[^>]*id="materials-updated"[^>]*>)[^<]*(</time>)',
        lambda match: match.group(1) + date.today().strftime("%B %d, %Y") + match.group(2),
        text,
        count=1,
    )
    if not n_date:  # template may not carry the stamp — non-fatal
        pass

    dashboard.write_text(text, encoding="utf-8")
    return dashboard, len(chapters)
