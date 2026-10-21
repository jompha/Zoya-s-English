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
- v2 (2026-10-21): "Forge, light edition" — the owner supplied the FORGE
  fitness-site prompt (dark + lime) as inspiration; re-skinned to paper/ink/
  lime sharpness with Space Grotesk.
- **v3 (current, 2026-10-21): "Violet glass"** — the owner built their own
  reference implementation at zoyasenglish.ai.studio (React/Tailwind) and
  asked for the redesign to match it. Extracted system from the deployed
  bundle: Nunito display + Plus Jakarta Sans chrome + Lora study prose;
  `#FAF8FD` ground / `#292233` ink; brand gradient `#654A93→#8E6BB8`; deep
  `#381E57`; dark-violet hero + footer; lavender glass panels; per-chapter
  accents remapped to violet-family hues (THEME_ACCENTS); rose for warning
  tones. Reference features ported: learner-wish rotator, daily-habit
  checklist (localStorage), Listen button on chapter pages (Web Speech API).
- Privacy note: the reference site publishes the trainer's identity details
  (Tech@Home role, England English-Literature/DfE-2015 credentials, 100+
  learners, 5.0/5.0 rating) — mirror those on the portfolio. The résumé PDF
  remains private/off-repo. If the owner wants anonymization, change is
  index.html copy only.
- Gotcha: uppercase/vitrine display styles change printed glyphs; the
  self-test sentinel check is case-insensitive for this reason.

## Open items

- ⚠ The GitHub token shared in chat was to be rotated after use — remind the
  owner until confirmed.
- The owner may add more manual conversions; each needs only a normalized-slug
  match to the source filename.
- Chapter "Choose the Correct Word – 500 Questions" relies on the OCR fallback
  (Docling mis-segments it); candidate for a manual conversion later.
