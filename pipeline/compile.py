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

from .config import CSS_PATH, MATERIALS_DIR, THEMES, chapter_number, humanize, pick_theme, slugify

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
<title>%%TITLE%% · Zoya's English — Study Guide</title>
<meta name="description" content="%%DESCRIPTION%%">
<meta name="robots" content="index, follow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap" rel="stylesheet">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%23654A93'/%3E%3Cstop offset='1' stop-color='%238E6BB8'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='64' height='64' rx='14' fill='url(%23g)'/%3E%3Ctext x='32' y='45' font-family='Arial,sans-serif' font-size='34' font-weight='900' fill='%23fff' text-anchor='middle'%3EZ%3C/text%3E%3C/svg%3E">
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
      <button class="listen-btn no-print" id="listen-btn" type="button" title="Read this study guide aloud">▶&nbsp;Listen</button>
    </header>
    <div class="doc-body prose">
%%BODY%%
    </div>
  </article>
  <script type="application/json" id="doc-meta">%%META_JSON%%</script>
  <script>
    // Read-aloud (Web Speech API) — no dependencies, progressive enhancement.
    (function () {
      const btn = document.getElementById('listen-btn');
      if (!btn || !('speechSynthesis' in window)) { if (btn) btn.remove(); return; }
      let playing = false;
      btn.addEventListener('click', () => {
        if (playing) {
          speechSynthesis.cancel();
          return;
        }
        const prose = document.querySelector('.doc-body.prose');
        if (!prose) return;
        const text = prose.innerText.replace(/\\s+/g, ' ').trim().slice(0, 30000);
        if (!text) return;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.97;
        utterance.lang = 'en-GB';
        utterance.onend = utterance.onerror = () => {
          playing = false;
          btn.classList.remove('playing');
          btn.textContent = '▶\\u00a0Listen';
        };
        playing = true;
        btn.classList.add('playing');
        btn.textContent = '⏹\\u00a0Stop';
        speechSynthesis.cancel();
        speechSynthesis.speak(utterance);
      });
      addEventListener('beforeunload', () => { try { speechSynthesis.cancel(); } catch (e) {} });
    })();
  </script>
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


def adopt_manual_html(
    manual_html: Path,
    slug: str,
    *,
    out_dir: Path | None = None,
) -> tuple[Path, dict]:
    """Publish a user-authored, design-faithful conversion as the chapter page.

    The manual file is the visual truth: content, styles and print geometry are
    preserved untouched. Only invisible plumbing is injected — an embedded
    doc-meta JSON block (for the dashboard indexer) and a lightweight back-link
    bar hidden during printing.
    """
    import math
    import re

    from bs4 import BeautifulSoup

    from .config import chapter_number as cfg_chapter_number, pick_theme

    out_dir = out_dir or MATERIALS_DIR
    html = manual_html.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title is not None and soup.title.string:
        title = str(soup.title.string).strip()
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else slugify_title_from_slug(slug)

    number = cfg_chapter_number(slug)
    page_sections = soup.select(".page")
    pages_n = len(page_sections) if page_sections else 0

    teaser_el = soup.select_one(".tagline") or soup.select_one(".subtitle") or soup.find("h1")
    teaser = teaser_el.get_text(" ", strip=True) if teaser_el else ""
    if len(teaser) > 168:
        teaser = teaser[:168].rsplit(" ", 1)[0].rstrip(",;:.") + "…"

    words = len(re.findall(r"\w+", soup.get_text(" ", strip=True)))
    reading = max(1, math.ceil(words / 180))
    theme = pick_theme(slug)

    meta = {
        "slug": slug,
        "number": number,
        "theme": theme,
        "engine": "manual conversion (user-authored)",
        "source": manual_html.name,
        "pages": pages_n,
        "words": words,
        "sections": len(soup.select("h2, h3")),
        "tables": len(soup.select("table, .day-row")),
        "reading_min": reading,
        "title": title,
        "date": date.today().isoformat(),
        "teaser": teaser or "Design-faithful user-authored conversion of the original PDF.",
    }

    back_bar = (
        '<nav class="doc-backbar no-print" style="max-width:1500px;margin:0 auto;padding:16px 14px 4px;'
        "font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b6b6b;\">"
        '<a style="color:#4a6b82;text-decoration:none" href="../index.html">&larr; Portfolio</a>'
        '<span style="margin:0 8px;color:#bbb">·</span>'
        '<a style="color:#4a6b82;text-decoration:none" href="../materials.html">Learning library</a>'
        "</nav>"
        '<style>@media print{.doc-backbar{display:none!important}}</style>'
        '<script type="application/json" id="doc-meta">'
        + json.dumps(meta, ensure_ascii=True)
        + "</script>"
    )
    if "</body>" in html:
        html = html.replace("</body>", back_bar + "</body>", 1)
    else:
        html += back_bar

    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{slug}.html"
    output.write_text(html, encoding="utf-8")
    return output, meta


def slugify_title_from_slug(slug: str) -> str:
    words = [word.capitalize() if len(word) > 3 else word.upper() if len(word) <= 2 else word for word in slug.split("-")]
    return " ".join(words)


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
