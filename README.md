# Zoya's English

**A unified teacher portfolio and dynamic study-materials platform — built for static deployment.**

[![Pipeline](https://img.shields.io/badge/pipeline-%20extract%C2%A0%3E%C2%A0compile%C2%A0%3E%C2%A0print%C2%A0%3E%C2%A0index-4a6b82)](#architecture)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)](requirements.txt)
[![Docling](https://img.shields.io/badge/Docling-layout--aware%20extraction-2f605c)](https://github.com/docling-project/docling)
[![Playwright](https://img.shields.io/badge/Playwright-headless%20A4%20printing-2ea44f?logo=playwright&logoColor=white)](https://playwright.dev)
[![Static](https://img.shields.io/badge/Deploy-GitHub%20Pages-ready-b98a4b)](#deployment)

---

**Zoya** is currently an **English Trainer at Tech@Home** with 5+ years of experience — from absolute beginners to working professionals — specialising in *spoken fluency* and *confidence building*. The repository pairs a premium portfolio site with a self-streaming content pipeline: raw (even scanned) chapter PDFs go in one side; beautifully designed, print-perfect study modules and an auto-updating learning dashboard come out the other.

- **`index.html`** — the teacher portfolio: pedagogy, method, and expertise in a sharp, light "Forge-edition" design — warm paper, near-black ink, electric-lime sparks.
- **`materials.html`** — the learning library: every chapter as an *interactive web view* **and** a *pixel-perfect printable PDF*, indexed automatically.
- **`run_pipeline.py`** — the manual, one-command content engine behind both.
- **`ARCHITECTURE.md`** — the full system map, naming conventions and month-to-month design contracts.
- **`MEMORY.md`** — operational memory: environment gotchas, decisions, security rules.

## Architecture

```
Study-Material/Source-Files/         raw uploads — scanned or digital PDFs, serial-numbered
Study-Material/manually-converted/   user-authored design-faithful HTML conversions (outrank all engines)
        │
        ▼  STEP A — Extraction (pipeline/extract.py)
        │   Docling layout model (tesseract-CLI OCR) → semantic markdown,
        │   with a coverage gate: if the layout model silently drops content
        │   (< 60% of the tesseract baseline), full-coverage OCR fallback.
        │   Manual conversions in manually-converted/ bypass extraction.
        ▼  STEP B — Compilation (pipeline/compile.py)
        │   Markdown → fully styled standalone chapter page.
        │   Global typographic tone + per-chapter design language (data-theme).
        ▼  STEP C — Headless printing (pipeline/print_pdf.py)
        │   Playwright Chromium, print-media emulation → pixel-perfect A4 PDF.
        │   Manual conversions print margin-0/footerless to preserve their own @page geometry.
        ▼  STEP D — Indexing (pipeline/index.py)
        │   Beautiful Soup reads chapter metadata and rewrites the card grid
        │   inside materials.html — titles, teasers, web links, PDF downloads.
        ▼
materials/                           generated HTML + PDF study modules
```

## Quick start

```bash
python3 -m venv .venv                      # one-time
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium --with-deps
```

Then, whenever new chapter PDFs land in `Study-Material/Source-Files/`:

```bash
python3 run_pipeline.py                # full run: extract → compile → print → index
python3 run_pipeline.py --selftest     # end-to-end dry-run validation (no website changes)
python3 run_pipeline.py --force        # ignore cache, rebuild everything
python3 run_pipeline.py --skip-pdf     # web views only
python3 run_pipeline.py --pdf-only     # re-print PDFs for compiled HTML
python3 run_pipeline.py --index-only   # refresh the materials.html grid only
python3 run_pipeline.py --source path/to/extra/dir
```

The script re-executes itself inside `.venv` automatically, caches per-chapter fingerprint hashes in `pipeline/.state.json`, and logs every run to `pipeline/logs/`.

## Conventions

| Thing | Rule |
| --- | --- |
| Source files | `.pdf` (scanned or digital) or `.png/.jpg/.tif` images in `Study-Material/Source-Files/` |
| **Serial numbering** | Source filenames carry zero-padded serial prefixes — `001 - …`, `002 - …` — which set module order/numbering. Renames are safe: cached extractions migrate by normalized slug; orphaned chapters are archived to `pipeline/attic/` |
| Chapter naming | Filenames refine titles and module numbering; bare numbers > 40 in a filename are word counts, never module numbers |
| **Manual conversions** | A hand-made HTML in `Study-Material/manually-converted/` matched to a source filename (prefix ignored) is adopted verbatim as the chapter page and printed margin-0 — drop one in and rerun the pipeline |
| Per-chapter design language | Auto-assigned deterministically (violet-family accents); pin one by dropping a sidecar `My-Chapter.pdf` → `My-Chapter.json` with `{"theme": "clay", "title": "…", "subtitle": "…"}` |
| Chapter themes | `slate` · `ink` · `clay` · `sage` · `plum` · `mist` · `ember` · `moss` |
| Dashboard grid | Never hand-edit inside the `<!-- MATERIALS:START -->…<!-- MATERIALS:END -->` markers of `materials.html` — the indexer owns that region |

## Design system — "Violet glass" (zoyasenglish.ai.studio reference)

Defined once in **`assets/css/main.css`** and inlined at build time into every chapter page, so web views and PDFs never drift apart:

| Token | Value |
| --- | --- |
| Ground | `#FAF8FD` lavender-white |
| Ink | `#292233` dark plum (headings `#381E57`) |
| Brand gradient | `#654A93 → #8E6BB8` — buttons, brand mark, icon tiles |
| Hero & footer | deep-violet gradient (`#2A1838→#381E57→#170E24`) with `#EADBFA` text |
| Display type | *Nunito* (800–900) · Body chrome: *Plus Jakarta Sans* · Study prose: *Lora* serif |
| Surfaces | glass blur panels, `rounded-3xl` softness, pill chips/buttons, soft violet shadows |
| Signature widgets | rotating learner-wish quotes · daily-habit tracker (localStorage) · read-aloud "Listen" button on every chapter (Web Speech API) |

The `@media print` block enforces a strict A4 pagination contract:

- headings never orphan from their first paragraph (`break-after: avoid`),
- callouts (`.tip-box`) and table rows (`tr`) never split across pages,
- `thead` repeats on every page; widows/orphans protected; color-exact printing.

## Project layout

```
.
├── index.html                        # Portfolio homepage (Zoya)
├── materials.html                    # Dynamic learning dashboard
├── Photo-Zoya.jpeg                   # Portfolio portrait
├── assets/css/main.css               # Master layout stylesheet (web + print) — Forge-light system
├── materials/                        # AUTO — compiled chapter HTML + A4 PDFs
├── pipeline/
│   ├── config.py                     # Paths, slugs, chapter numbering, themes
│   ├── extract.py                    # STEP A — Docling (+tesseract CLI) with coverage gate
│   ├── compile.py                    # STEP B — Styled compilation + manual-conversion adoption
│   ├── print_pdf.py                  # STEP C — Playwright A4 print engine
│   ├── index.py                      # STEP D — Beautiful Soup dashboard indexer
│   ├── extracted/                    # AUTO — raw markdown intermediates
│   ├── attic/                        # AUTO — archived chapters whose sources were renamed away
│   └── logs/                         # AUTO — run & self-test logs
├── Study-Material/Source-Files/      # RAW — serial-numbered uploads land here
├── Study-Material/manually-converted/ # RAW — user-authored design-faithful conversions
├── ARCHITECTURE.md                   # System map & contracts
├── MEMORY.md                         # Operational memory (gotchas, decisions, security)
├── run_pipeline.py                   # Master execution script
└── requirements.txt                  # Pinned dependency set
```

## Deployment (GitHub Pages)

1. Push `main` to this repository.
2. **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `/(root)`**.
3. `index.html`, `materials.html`, `assets/` and everything under `materials/` is deployable as-is — the site is 100% static, JavaScript-optional and privacy-first.
4. Optional: set the repository **Website** field to `https://<user>.github.io/Zoya-s-English/`.

Suggested commit for the pipeline itself:

```bash
git add -A && git commit -m "feat: portfolio site, learning library, and Docling→Playwright materials pipeline"
```

## Security note

Never commit API keys or tokens — deploy credentials live outside the repo (environment variables, `git`, or your platform's secret store). If a token has ever been pasted into a chat, ticket, or terminal history, revoke it from GitHub **Settings → Developer settings → Personal access tokens**.
