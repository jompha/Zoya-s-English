"""STEP B — Chapter compilation.

Turns extracted markdown into a fully self-styled standalone HTML page:
global typographic tone, a per-chapter design language (deterministic theme
accents + cover motif), global CSS inlined so web view and print never drift.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

import markdown as markdown_lib

from .config import CSS_PATH, THEMES, chapter_number, humanize, pick_theme, slugify

FIRST_PARAGRAPH = re.compile(r"<p[^>]*>(.*?)</p>", re.S)


def render_body(md_text: str) -> tuple[str, int, int]:
    body = markdown_lib.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "toc"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
    )
    sections = len(re.findall(r"<h2\b", body))
    tables = len(re.findall(r"<table\b", body))
    return body, sections, tables


def _first_paragraph(body: str) -> str:
    """Teaser picking: skip OCR noise, shouting banners, symbol soup."""
    for match in FIRST_PARAGRAPH.finditer(body):
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        letters = [c for c in text if c.isalpha()]
        if len(text) < 60 or not letters:
            continue
        if sum(1 for c in letters if c.isupper()) / len(letters) > 0.6:
            continue  # banner-caps line, not prose
        non_space = len(re.sub(r"\s", "", text))
        if len(letters) / max(1, non_space) < 0.55:
            continue  # OCR symbol soup — reject
        if len(text) > 168:
            text = text[:168].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
        return text
    return ""


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


_TEMPLATE = """<!doctype html>
<html lang="en" data-theme="%%THEME%%">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%% · Zoya's English — Study Module</title>
<meta name="description" content="%%DESCRIPTION%%">
<meta name="robots" content="index, follow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>%%CSS%%</style>
</head>
<body class="doc-page">
<a class="skip-link" href="#doc-main">Skip to content</a>
<main id="doc-main">
  <div class="doc-crumbs no-print">
    <a href="../index.html">&larr; Portfolio</a><span aria-hidden="true">/</span>
    <a href="../materials.html">Learning library</a>
  </div>
  <article class="doc-frame chapter-doc" data-chapter="%%SLUG%%" data-theme="%%THEME%%">
    <header class="doc-cover">
      <p class="doc-kicker">%%KICKER%%</p>
      <h1 class="doc-title">%%TITLE%%</h1>
      <p class="doc-subtitle">%%SUBTITLE%%</p>
      <div class="doc-meta">
        <span>Source: %%SOURCE%%</span>
        %%PAGES_CHIP%%
        <span>%%WORDS%% words</span>
        <span>~%%READING%% min read</span>
      </div>
    </header>
    <div class="doc-body prose">
%%BODY%%
    </div>
  </article>
  <script type="application/json" id="doc-meta">%%META_JSON%%</script>
</main>
</body>
</html>
"""


def _sidecar(source: Path) -> dict:
    sidecar_path = source.with_suffix(".json")
    if sidecar_path.exists():
        try:
            return json.loads(sidecar_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — a bad sidecar must never abort a run
            return {}
    return {}


def compile_chapter(
    extracted,
    *,
    css_text: str | None = None,
    out_dir: Path | None = None,
    theme: str | None = None,
    title: str | None = None,
    forced_chapter: int | None = None,
) -> Path:
    from .config import MATERIALS_DIR  # local import: avoids cycle at package import

    out_dir = out_dir or MATERIALS_DIR
    css_text = css_text if css_text is not None else CSS_PATH.read_text(encoding="utf-8")
    slug = extracted.slug
    sidecar = _sidecar(extracted.source)

    body, sections, tables = render_body(extracted.md)
    words = extracted.words
    reading = max(1, math.ceil(words / 180))

    number = forced_chapter
    if number is None:
        number = sidecar.get("chapter")
    if number is None:
        number = chapter_number(f"{slug} {title or ''} {humanize(extracted.source)}")
    if isinstance(number, str) and number.isdigit():
        number = int(number)

    title = (title or sidecar.get("title")) or humanize(extracted.source) or "Study Module"
    kicker = f"Zoya's English — Study Module {number:02d}" if number else "Zoya's English — Study Module"
    subtitle = sidecar.get("subtitle") or "Rebuilt from the original source — interactive web edition plus print-ready A4."

    resolved_theme = (theme or sidecar.get("theme") or "").lower()
    if resolved_theme not in THEMES:
        resolved_theme = pick_theme(slug)

    teaser = sidecar.get("teaser") or _first_paragraph(body)
    clean_source = extracted.source.name.replace("_copy_copy", "").replace("_copy", "")
    meta = {
        "slug": slug,
        "number": number,
        "theme": resolved_theme,
        "engine": extracted.engine,
        "source": clean_source,
        "pages": extracted.pages,
        "words": words,
        "sections": sections,
        "tables": tables,
        "reading_min": reading,
        "date": date.today().isoformat(),
        "teaser": teaser,
    }

    description = f"{title} — study module from Zoya's English learning library: speaking and confidence coaching materials."
    pages_chip = f'<span>{extracted.pages} source pages</span>' if extracted.pages else ""
    html = _TEMPLATE
    replacements = {
        "%%THEME%%": resolved_theme,
        "%%TITLE%%": _escape(title),
        "%%DESCRIPTION%%": _escape(description),
        "%%CSS%%": css_text,
        "%%SLUG%%": _escape(slug),
        "%%KICKER%%": _escape(kicker),
        "%%SUBTITLE%%": _escape(subtitle),
        "%%SOURCE%%": _escape(clean_source),
        "%%PAGES%%": str(extracted.pages if extracted.pages else "—"),
        "%%WORDS%%": str(words),
        "%%READING%%": str(reading),
        "%%BODY%%": body,
        "%%META_JSON%%": json.dumps(meta, ensure_ascii=True),
    }
    for token, value in replacements.items():
        html = html.replace(token, value)
    html = html.replace("%%PAGES_CHIP%%", pages_chip)

    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{slug}.html"
    output.write_text(html, encoding="utf-8")
    return output
