# Zoya's English — Architecture

The system is a **static site + content pipeline**. Two artifacts ship: a teacher
portfolio (`index.html`) and an auto-indexed learning library (`materials.html`
+ `materials/`). Nothing dynamic runs in production — all generation happens
locally through one command.

```
Study-Material/Source-Files/         raw uploads — scanned or digital PDFs
Study-Material/manually-converted/   user-authored design-faithful HTML conversions
        │
        ▼  STEP A — Extraction (pipeline/extract.py)
        │   Primary: Docling layout model (Heron segmentation + TableFormer,
        │            tesseract-CLI OCR engine) → semantic markdown.
        │   Coverage gate: docling's word yield is cross-checked against a
        │            plain-tesseract baseline; below 60% ⇒ full-coverage OCR
        │            fallback (pdf2image + tesseract, page-structured markdown).
        │   Manual conversions outrank every engine (see below).
        ▼  STEP B — Compilation (pipeline/compile.py)
        │   Markdown → standalone styled chapter page; per-chapter data-theme.
        ▼  STEP C — Headless printing (pipeline/print_pdf.py)
        │   Playwright Chromium, print-media emulation → A4 PDF.
        ▼  STEP D — Indexing (pipeline/index.py)
        │   Rebuilds the card grid in materials.html between the
        │   <!-- MATERIALS:START/END --> markers.
        ▼
materials/                           generated HTML + PDF study modules
```

## Module/vue contracts (do not break)

| Contract | Location | Consumers |
| --- | --- | --- |
| `article.chapter-doc[data-chapter][data-theme]` | every auto-compiled chapter | indexer card scan |
| `<script id="doc-meta" type="application/json">` | every chapter page (incl. manual adoptions) | indexer meta (title, teaser, counts, theme, number) |
| `h1.doc-title`, `.doc-kicker` | auto chapters only | indexer readable title/kicker |
| `<!-- MATERIALS:START/END -->` markers | `materials.html` | indexer writes only inside them |
| `.tip-box`, `tr`, heading print-guards | `assets/css/main.css` | self-test audits the stylesheet for them |

## Naming conventions (serial maintenance)

Source files carry **zero-padded serial prefixes** — the owner renumbers the
library for maintainability, so ordering/numbering follow the filename:

```
001 - Complete 30-Day English Study Plan.pdf     → module 01
002 - 50 Useful English Sentence Patterns.pdf    → module 02
```

- Slugs include the prefix (`002-50-useful-english-sentence-patterns`);
  `chapter_number()` rejects bare numbers > 40 so word counts ("500 Error
  Detection") are never mistaken for module numbers.
- **Rename resilience**: cached markdown is matched across renames by
  normalized slug (prefix stripped), then promoted to the new canonical slug —
  no re-OCR bill for a serial change.
- **Orphan hygiene**: chapter outputs whose source no longer exists are
  archived (reversibly) to `pipeline/attic/` and dropped from state.

## Manual conversions — the user-authored tier

A hand-made, design-faithful conversion in
`Study-Material/manually-converted/` matched to a source by normalized slug
**outranks all machine extraction** ("Complete_30_Day_English_Study_Plan.html"
→ module `001`). Adoption rules:

- The manual file is copied verbatim into `materials/<canonical-slug>.html`;
  visible content, styles and print geometry are untouched.
- Only invisible plumbing is injected: an embedded `doc-meta` JSON block and a
  back-link bar hidden during printing.
- Printed with **zero margins, no running footer** (`prefer_css_page_size`) so
  the file's own `@page` rules (e.g. 15in × 20in page-facet pages) decide
  geometry. Generic A4 printing is skipped for these chapters in Step C.
- Add more conversions any time; the pipeline adopts them on the next run.
  Use `--force` to refresh an adopted chapter after editing its manual file.

## Design system — "Forge, light edition"

Defined once in `assets/css/main.css` and inlined at build time into every
chapter page (web views and PDFs cannot drift apart).

| Token | Value |
| --- | --- |
| Ground | `#fafaf7` warm paper |
| Ink | `#17181a` near-black |
| Spark | `#b5f030` electric lime (CTAs, kickers, hover glow) |
| Lines | `#e6e4da` / `#d4d2c6` (sharp 0-radius corners everywhere) |
| Display type | *Space Grotesk* (uppercase, tight tracking) |
| Body type | *Inter Tight* (weight 300) |
| Chapter accents | 8 `data-theme` families: slate · ink · clay · sage · plum · mist · ember · moss |

Inherited from the FORGE inspiration (near-black→paper inversion): scrolling
ticker strip, animated stat counters, lime-glow hover cards, sharp editorial
grids. The `@media print` block keeps the strict A4 contract: no orphaned
headings, no split `.tip-box`/`tr`, `thead` repeats, color-exact output.

## Pipeline operations

```bash
python3 run_pipeline.py                # full run (caches aggressively)
python3 run_pipeline.py --selftest     # 6-check dry run; must stay 6/6 PASS
python3 run_pipeline.py --force        # re-extract everything from scratch
python3 run_pipeline.py --index-only   # refresh materials.html grid only
python3 run_pipeline.py --skip-pdf / --pdf-only / --source <dir> / --limit N
```

Runtime state lives in `pipeline/.state.json` (per-chapter fingerprint cache),
`pipeline/extracted/*.md` (markdown intermediates) and `pipeline/logs/`.

## Security posture

- Raw sources and the personal résumé PDF never ship; they are gitignored.
- Personal information stays off the deployed site (academic info only).
- Pushes use an explicit token URL embedded in the command, never stored in
  `.git/config`; leaked tokens must be rotated.
