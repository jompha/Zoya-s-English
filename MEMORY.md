# Project memory — Zoya's English

Durable context that isn't obvious from the code. Update after every
significant session. Newest entries last.

## Environment

- Always run Python through `.venv` (`run_pipeline.py` re-execs itself into it
  automatically). Bare `python3` lacks `markdown`, `bs4` etc.'
- Docling stack: transformers is pinned `<5`
  (5.x removed `AutoImageProcessor`); torchvision must be the `+cpu` wheel
  (0.29.1+cpu) matching CPU-only torch, else ABI mismatch crashes imports.
- Docling's default OCR engine in 2.141 (RapidOCR) **returns empty results on
  several scan batches** — silently losing most content. Config now forces the
  tesseract-CLI engine inside Docling; `TesseractOcrOptions` (the tesserocr
  variant) is not installed and fails cleanly.
- The extraction **coverage gate** exists because Docling's layout model can
  mis-segment dense two-column quiz sheets (e.g. "Choose the Correct Word –
  500 Questions" collapsed to ~660/5,700 words). Rule: if docling < 60% of the
  plain-tesseract word baseline, use the full-coverage OCR fallback instead.

## Naming & content conventions (owner's rules)

- **Source serial prefixes**: the owner renumbers source PDFs ("001 - ",
  "002 - ", …) as a maintenance scheme so newly added files slot into a serial
  order. The pipeline must treat prefixes as canonical ordering, survive
  renames (normalized-slug md migration) and archive orphans to
  `pipeline/attic/` (added 2026-10-21).
- Filenames are the source of truth for chapter titles/numbers; bare numbers
  > 40 in filenames are word counts, not module numbers.
- Sidecar `<source>.json` (`{"theme": ..., "title": ..., "subtitle": ...}`)
  pins a chapter's design language.
- **Manual conversions rule everything**: any HTML in
  `Study-Material/manually-converted/` matched by normalized slug replaces the
  auto-built chapter verbatim (only doc-meta + hidden back-bar injected;
  printed margin-0, footerless). The owner benchmarks quality against their
  conversion of the 30-Day Plan — page-facet faithful, zero information loss.

## Git & deploy

- Repo: `jompha/Zoya-s-English`, branch `main`. GitHub Pages: deploy from
  branch root. Repo-local identity: "Zoya's English"
  `<jompha@users.noreply.github.com>`.
- Pushes must use the explicit form
  `git push https://x-access-token:<TOKEN>@github.com/jompha/Zoya-s-English.git main:main`
  — the ambient system credential helper belongs to an unrelated account
  ("mmknit") and 403s. Never persist the token to `.git/config`.
- `Zoya-Portfolio.pdf` (personal data) is banned from the repo; history was
  rewritten with filter-branch and force-pushed. The copy remaining on disk is
  local-only — keep it gitignored.
- Raw sources (`Study-Material/Source-Files/`) are gitignored; only generated
  `materials/` + site chrome ship.

## Design history

- v1: warm editorial glass (Fraunces/Inter, slate-blue, rounded glass cards).
- **v2 (current, 2026-10-21): "Forge, light edition"** — the owner supplied the
  FORGE fitness-site prompt (dark + lime) as inspiration and asked for a light
  re-skin. System: paper `#fafaf7`, ink `#17181a`, lime `#b5f030`, sharp
  corners, Space Grotesk uppercase display + Inter Tight, ticker strip,
  animated stat counters, lime-glow hover cards. 8 `data-theme` accent
  families retained; strict A4 print guards untouched.
- Gotcha: uppercase display means printed headings OCR in CAPS — the
  self-test sentinel check must be case-insensitive.

## Open items

- ⚠ The GitHub token shared in chat was to be rotated after use — remind the
  owner until confirmed.
- The owner may add more manual conversions; each needs only a normalized-slug
  match to the source filename.
- Chapter "Choose the Correct Word – 500 Questions" relies on the OCR fallback
  (Docling mis-segments it); candidate for a manual conversion later.
