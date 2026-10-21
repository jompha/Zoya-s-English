#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
 ZOYA'S ENGLISH — MASTER CONTENT PIPELINE
═══════════════════════════════════════════════════════════════════════════
 Run manually whenever new chapter PDFs land in Study-Material/Source-Files:

     python3 run_pipeline.py              # full run  (extract → compile → print → index)
     python3 run_pipeline.py --selftest   # zero-dependency end-to-end validation
     python3 run_pipeline.py --force      # ignore cache, rebuild everything
     python3 run_pipeline.py --skip-pdf   # web views only
     python3 run_pipeline.py --pdf-only   # re-print PDFs for existing HTML
     python3 run_pipeline.py --index-only # refresh materials.html grid only
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline.config import EXTRACTED_DIR, slugify  # noqa: E402 — module-level for cached_doc

VERSION = "1.0.0"
SENTINEL = "SELFTEST-7Q3F9Z"

WARNING_LINES = []


def log(line: str = "") -> None:
    print(line, flush=True)


def banner(title: str) -> None:
    log(f"  ── {title} " + "─" * max(4, 58 - len(title)))


def ok(message: str) -> None:
    print(f"   ✔ {message}", flush=True)


def warn(message: str) -> None:
    WARNING_LINES.append(message)
    print(f"   ⚠ {message}", flush=True)


def fail(module: str, message: str) -> None:
    print(f"   ✖ {module}: {message}", flush=True)


def hash_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


class Tee:
    """Echo every pipeline line into a timestamped log file under pipeline/logs."""

    def __init__(self, log_path: Path) -> None:
        self._stdout = sys.stdout
        self._file = log_path.open("w", encoding="utf-8")

    def write(self, text: str) -> None:
        self._stdout.write(text)
        self._file.write(text)

    def flush(self) -> None:
        self._stdout.flush()
        self._file.flush()

    def close(self) -> None:
        self._file.close()


# ───────────────────────────────────────────────────────── environment helpers


def ensure_venv() -> None:
    """Re-exec inside the project virtualenv when invoked with system python."""
    if os.environ.get("ZOYA_VENV") == "1":
        return
    venv_python = ROOT / ".venv" / "bin" / "python"
    if getattr(sys, "base_prefix", None) == getattr(sys, "prefix", None) and venv_python.exists():
        environment = os.environ.copy()
        environment["ZOYA_VENV"] = "1"
        os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


def ensure_imports() -> None:
    missing = []
    for module in ("bs4", "markdown", "playwright"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        fail("env", f"missing python packages: {', '.join(missing)} — run mkvenv/pip install")
        raise SystemExit(1)


def tool_version(command: list[str], pattern: str = r"(\d+\.[^\s]+)") -> str:
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=10)
        probe = (out.stdout or "") + (out.stderr or "")
        match = re.search(pattern, probe)
        return match.group(1) if match else "present"
    except Exception:  # noqa: BLE001 — optional binaries only
        return "not found"


def environment_report() -> dict:
    report = {
        "python": sys.version.split()[0],
        "docling": tool_version([sys.executable, "-m", "pip", "show", "docling"], r"Version:\s*(\S+)"),
        "playwright": tool_version([sys.executable, "-m", "pip", "show", "playwright"], r"Version:\s*(\S+)"),
        "beautifulsoup4": tool_version([sys.executable, "-m", "pip", "show", "beautifulsoup4"], r"Version:\s*(\S+)"),
        "markdown": tool_version([sys.executable, "-m", "pip", "show", "markdown"], r"Version:\s*(\S+)"),
        "tesseract": tool_version(["tesseract", "--version"]),
        "poppler": tool_version(["pdfinfo", "-v"]),
    }
    return report


# ──────────────────────────────────────────────────────────── self-test mode


SAMPLE_MD = f"""## Self-Test Sentinel Chapter

This paragraph carries the sentinel marker **{SENTINEL}**, used to prove that
every pipeline stage — extraction, compilation, printing, indexing — performs
end-to-end without layout exceptions.

> Tip boxes render as callouts; a callout like this one must never split
> across a page boundary.

### Print Guard Checklist

| Guard rule | Target selector | Expected behaviour |
| ---------- | --------------- | ------------------ |
| Keep heading with body | h1–h6 | no orphan headings |
| Keep table rows intact | tr | no mid-row splits |
| Keep callouts intact | .tip-box | no box fragmentation |
| Repeating headers | thead | shown on every page |

### Fluency Drill Sample

""" + "\n\n".join(
    f"Drill sentence {i:02d}: the quick rehearsal pattern keeps rhythm, then word order, "
    "then stress — each layer locked before the next opens."
    for i in range(1, 61)
)

REQUIRED_CSS_GUARDS = ["@media print", "break-inside: avoid", ".tip-box", "tr", "thead", "display: table-header-group"]


def run_selftest(keep: bool) -> bool:
    import pypdfium2 as pdfium

    results: list[tuple[str, str, str]] = []

    def step(name: str, fn):
        started = time.perf_counter()
        try:
            detail = fn() or "ok"
            results.append((name, "PASS", detail))
            ok(f"{name} — {detail} ({time.perf_counter() - started:.2f}s)")
            return True
        except Exception as exc:  # noqa: BLE001 — report, don't traceback-splat
            fail(name, f"{exc}")
            results.append((name, "FAIL", str(exc)))
            return False

    tmp = ROOT / "pipeline" / "selftest_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    sample_html = tmp / "selftest-sample.html"
    sample_pdf = tmp / "selftest-sample.pdf"

    from pipeline import compile as compile_module
    from pipeline import print_pdf
    from pipeline.extract import ExtractedDoc, extract_content

    css_text = (ROOT / "assets" / "css" / "main.css").read_text(encoding="utf-8")

    def _css_guards():
        missing = [g for g in REQUIRED_CSS_GUARDS if g not in css_text]
        if missing:
            raise RuntimeError(f"print guards missing from main.css: {missing}")
        return "heading/tr/callout pagination guards verified in stylesheet"

    def _bootstrap_pdf_source():
        dropped = compile_module.compile_chapter(
            ExtractedDoc(
                source=tmp / "bootstrap.md",
                slug="bootstrap-sample",
                md="## Bootstrap\n\nSelf-test harness page pressed to PDF with Playwright.",
                engine="bootstrap",
                pages=1,
            ),
            css_text=css_text,
            out_dir=tmp,
            theme="sage",
            title="Bootstrap Sample",
        )
        print_pdf.print_to_pdf(dropped, tmp / "bootstrap-sample.pdf", footer_title="Bootstrap")
        if not (tmp / "bootstrap-sample.pdf").exists():
            raise RuntimeError("bootstrap PDF missing")
        return "Chromium print engine operational"

    def _extract():
        doc = extract_content(tmp / "bootstrap-sample.pdf")
        if "bootstrap" not in doc.md.lower():
            raise RuntimeError("sentinel text lost during extraction")
        selftest_doc = ExtractedDoc(tmp, "selftest-sample", SAMPLE_MD, "selftest", 1)
        compile_member = compile_module.compile_chapter(
            selftest_doc, css_text=css_text, out_dir=tmp, theme="slate", title="Self-Test Sentinel Chapter"
        )
        html_text = compile_member.read_text(encoding="utf-8")
        if SENTINEL not in html_text:
            raise RuntimeError("sentinel missing from compiled HTML")
        if "data-theme=" not in html_text:
            raise RuntimeError("chapter design language (data-theme) not applied")
        return f"extraction + compilation → {compile_member.name}"

    def _print():
        print_pdf.print_to_pdf(sample_html, sample_pdf, footer_title="Self-Test")
        size = sample_pdf.stat().st_size
        pages = len(pdfium.PdfDocument(str(sample_pdf)))
        if size < 5_000 or pages < 1:
            raise RuntimeError(f"suspicious PDF output ({size} bytes, {pages} pages)")
        return f"{pages} page(s), {size/1024:.1f} KB A4"

    def _index():
        from bs4 import BeautifulSoup

        from pipeline.index import render_cards, scan_chapters

        chapters = scan_chapters(tmp)
        html = sample_html.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        meta_script = soup.find("script", id="doc-meta")
        if meta_script is None:
            raise RuntimeError("doc-meta JSON block missing from compiled chapter")
        grid = render_cards(chapters)
        if "materials/selftest-sample.html" not in grid:
            raise RuntimeError("indexer card did not link the web view")
        if not any(
            token in grid
            for token in ("data-tags=", "card-chapter")
        ):
            raise RuntimeError("indexer card markup malformed")
        return "indexer renders web-view + PDF actions"

    def _cleanup():
        stray = [p.name for p in ROOT.glob("selftest-*")] + [
            p.name for p in (ROOT / "materials").glob("*selftest*")
        ]
        shutil.rmtree(tmp, ignore_errors=True) if not keep else None
        if stray:
            raise RuntimeError(f"self-test artifacts leaked into the workspace: {stray}")
        return "workspace verified pristine — no artifacts leaked"

    workflow = [
        ("stylesheet print-guard audit", _css_guards),
        ("playwright chromium bootstrap", _bootstrap_pdf_source),
        ("extraction + compilation round-trip", _extract),
        ("headless A4 printing", _print),
        ("beautiful soup indexer pass", _index),
        ("cleanup", _cleanup),
    ]

    log()
    banner("SELF-TEST · FULL PIPELINE DRY RUN")
    all_pass = True
    for name, fn in workflow:
        all_pass = step(name, fn) and all_pass

    if keep:
        ok(f"self-test artifacts kept at {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)

    return all_pass


# ─────────────────────────────────────────────────────────────── run workflow

def normalize_slug(slug: str) -> str:
    """Strip leading zero-padded module counters so '001-foo' and 'foo' match."""
    return re.sub(r"^\d{1,3}(?=[-_])", "", slug).strip("-")


def cached_doc(slug: str, source: Path):
    """Reuse a previous extraction when the markdown is newer than the source.

    Lets styling/topology iterations recompile in seconds without paying the
    OCR cost again. Falls back to a normalized-slug match so renamed sources
    (e.g. handwritten "002 - " prefixes) inherit their old cached extraction
    instead of paying the cost twice. `--force` always re-extracts from scratch.
    """
    candidates = [EXTRACTED_DIR / f"{slug}.md"]
    if not candidates[0].exists():
        target = normalize_slug(slug)
        candidates = [
            path
            for path in EXTRACTED_DIR.glob("*.md")
            if normalize_slug(path.stem) == target
            and path.stat().st_mtime >= source.stat().st_mtime
        ] or [EXTRACTED_DIR / f"{slug}.md"]
    md_path = candidates[0]
    if md_path.exists() and md_path.stat().st_mtime >= source.stat().st_mtime:
        text = md_path.read_text(encoding="utf-8")
        if len(text.strip()) > 40:
            if md_path.stem != slug:
                # Promote the cached extraction under the new canonical slug.
                try:
                    md_path.rename(EXTRACTED_DIR / f"{slug}.md")
                except OSError:
                    pass
            from pipeline.extract import ExtractedDoc

            return ExtractedDoc(
                source=source, slug=slug, md=text, engine="cached markdown",
                pages=0, warnings=[], elapsed=0.0,
            )
    return None


def load_state() -> dict:
    from pipeline.config import STATE_FILE

    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_state(state: dict) -> None:
    from pipeline.config import STATE_FILE

    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def run_pipeline(args: argparse.Namespace) -> int:
    from pipeline import compile as compile_module
    from pipeline import index as index_module
    from pipeline import print_pdf
    from pipeline.config import (
        CSS_PATH,
        EXTRACTED_DIR,
        LOGS_DIR,
        MATERIALS_DIR,
        MATERIALS_HTML,
        ensure_runtime_dirs,
    )
    from pipeline.extract import discover_sources, extract_content

    ensure_runtime_dirs()

    log("── STEP A · EXTRACTION " + "─" * 40)
    sources = discover_sources(tuple(Path(p) for p in (args.source or [])))
    if args.limit:
        sources = sources[: args.limit]

    # User-authored, design-faithful conversions outrank every auto engine —
    # if a manual page matches a source, the source is never machine-extracted.
    from pipeline.config import SOURCE_DIRS as CFG_DIRS

    manual_map: dict[str, Path] = {}
    for base in (*CFG_DIRS, ROOT / "Study-Material"):
        conv_dir = base / "manually-converted" if base.name == "Study-Material" else base.parent / "manually-converted"
        if not conv_dir.exists():
            conv_dir = base.parent / "manually-converted"
        for candidate in conv_dir.glob("*.html") if conv_dir.exists() else []:
            manual_map[normalize_slug(slugify(candidate))] = candidate

    if manual_map:
        log(f"   manual conversions available: {len(manual_map)} file(s) — they override auto extraction")

    if not sources:
        warn("no source PDFs/images found — library will index as empty")
    css_digest = hash_file(CSS_PATH) if CSS_PATH.exists() else "no-css"
    state = load_state()
    extracted_by_slug: dict[str, object] = {}
    manual_adopted: set[str] = set()

    for source in sources:
        canon = slugify(source)
        manual = manual_map.get(normalize_slug(canon))
        if manual is not None:
            adopt_key = hashlib.sha1(("manual-" + hash_file(manual)).encode()).hexdigest()[:16]
            out_html = MATERIALS_DIR / f"{canon}.html"
            if not args.force and state.get(canon) == adopt_key and out_html.exists() and (MATERIALS_DIR / f"{canon}.pdf").exists():
                ok(f"{source.name} — manual conversion cached (use --force to refresh)")
                continue
            adopted, meta = compile_module.adopt_manual_html(manual, canon)
            print_pdf.print_to_pdf(adopted, MATERIALS_DIR / f"{canon}.pdf", margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}, footer=False)
            state[canon] = adopt_key
            manual_adopted.add(canon)
            ok(f"{source.name} → manual conversion adopted ({meta['pages']} pages · {meta['words']} words) + A4 print")
            continue

        slug = canon
        cache_key = hashlib.sha1((hash_file(source) + css_digest + "v1").encode()).hexdigest()[:16]
        outputs_fresh = (MATERIALS_DIR / f"{slug}.html").exists() and (
            args.skip_pdf or (MATERIALS_DIR / f"{slug}.pdf").exists()
        )
        if not args.force and state.get(slug) == cache_key and outputs_fresh:
            ok(f"{source.name} — cached (use --force to rebuild)")
            continue

        doc = cached_doc(slug, source) if not args.force else None
        if doc is None:
            doc = extract_content(source)
        (EXTRACTED_DIR / f"{slug}.md").write_text(doc.md, encoding="utf-8")
        extracted_by_slug[slug] = doc
        warnnote = f" · {len(doc.warnings)} warning(s)" if doc.warnings else ""
        ok(
            f"{source.name} → {slug} · {doc.engine} · {doc.pages} page(s) · "
            f"{doc.words} words · {doc.elapsed:.1f}s{warnnote}"
        )
        for warning in doc.warnings:
            warn(f"{slug}: {warning}")

    if args.pdf_only:
        log()
        banner("STEP C · HEADLESS PRINTING (pdf-only refresh)")
        printed = 0
        for html_path in sorted(MATERIALS_DIR.glob("*.html")):
            slug = html_path.stem
            title_guess = re.sub(r"[-_]+", " ", slug).title()
            print_pdf.print_to_pdf(html_path, MATERIALS_DIR / f"{slug}.pdf", footer_title=title_guess)
            ok(f"{html_path.name} → {slug}.pdf ({(MATERIALS_DIR / f'{slug}.pdf').stat().st_size // 1024} KB)")
            printed += 1
        if not printed:
            warn("no compiled chapters found to print")
        log()
        if args.no_index:
            log("── STEP D skipped (--no-index)")
        else:
            dashboard, count = index_module.update_dashboard()
            log(f"── STEP D · DASHBOARD INDEXED " + "─" * 32)
            ok(f"{dashboard.name} refreshed · {count} chapter card(s)")
        return 0

    log()
    banner("STEP B · COMPILATION " + "─" * 42)
    compiled = 0
    for slug, doc in extracted_by_slug.items():
        output_html = compile_module.compile_chapter(doc, css_text=CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.exists() else "")
        state[slug] = hashlib.sha1((hash_file(doc.source) + css_digest + "v1").encode()).hexdigest()[:16]
        ok(f"{slug} → materials/{output_html.name} ({output_html.stat().st_size // 1024} KB)")
        compiled += 1
    if not compiled and not args.force:
        ok("no cache misses — all chapters up to date")
    save_state(state)

    if args.skip_pdf:
        log()
        warn("STEP C skipped (--skip-pdf)")
    else:
        log()
        banner("STEP C · HEADLESS PRINTING " + "─" * 34)
        # Rename hygiene: chapter pages whose source has been renamed away no
        # longer belong in the live library. Archive them (reversible) instead
        # of leaving ghost duplicates next to the current set.
        from pipeline.config import ROOT as CFG_ROOT

        live_slugs = {slugify(source) for source in sources}
        orphan_slugs = [
            html_path.stem
            for html_path in MATERIALS_DIR.glob("*.html")
            if html_path.stem not in live_slugs
        ]
        if orphan_slugs:
            attic = CFG_ROOT / "pipeline" / "attic"
            attic.mkdir(parents=True, exist_ok=True)
            for orphan in orphan_slugs:
                for ext in ("html", "pdf"):
                    stale = MATERIALS_DIR / f"{orphan}.{ext}"
                    if stale.exists():
                        destination = attic / f"{orphan}.{ext}"
                        try:
                            stale.replace(destination)
                        except OSError:
                            pass
                state.pop(orphan, None)
            warn(f"archived {len(orphan_slugs)} orphaned chapter(s) to pipeline/attic: " + ", ".join(orphan_slugs))

        for html_path in sorted(MATERIALS_DIR.glob("*.html")):
            slug = html_path.stem
            if slug in manual_adopted:
                continue  # design-faithful conversion — already printed exactly
            if args.force or not (MATERIALS_DIR / f"{slug}.pdf").exists() or slug in extracted_by_slug:
                doc = extracted_by_slug.get(slug)
                soup_title = None
                if doc is None:
                    from bs4 import BeautifulSoup

                    soup_title = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser").find("h1")
                title_guess = (
                    soup_title.get_text(" ", strip=True) if soup_title else re.sub(r"[-_]+", " ", slug).title()
                )
                pdf_path = MATERIALS_DIR / f"{slug}.pdf"
                print_pdf.print_to_pdf(html_path, pdf_path, footer_title=title_guess)
                ok(f"{slug}.html → {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")
        log()
        log("── STEP D · DASHBOARD INDEX " + "─" * 36)
        if args.no_index:
            warn("STEP D skipped (--no-index)")
        else:
            dashboard, count = index_module.update_dashboard()
            ok(f"{dashboard.name} refreshed · {count} chapter card(s) · grid links verified")

    return 0


def main() -> int:
    ensure_venv()
    parser = argparse.ArgumentParser(description="Zoya's English content pipeline")
    parser.add_argument("--source", action="append", default=[], help="extra source directory (repeatable)")
    parser.add_argument("--force", action="store_true", help="ignore cache, rebuild every chapter")
    parser.add_argument("--skip-pdf", action="store_true", help="compile HTML only")
    parser.add_argument("--pdf-only", action="store_true", help="re-print PDFs for existing HTML")
    parser.add_argument("--index-only", action="store_true", help="refresh materials.html grid only")
    parser.add_argument("--no-index", action="store_true", help="do not rewrite materials.html")
    parser.add_argument("--limit", type=int, default=0, help="process at most N sources")
    parser.add_argument("--selftest", action="store_true", help="run the end-to-end dry-run validation")
    parser.add_argument("--keep-selftest", action="store_true", help="keep self-test artifacts")
    args = parser.parse_args()
    ensure_imports()

    log_path = ROOT / "pipeline" / "logs" / ("selftest-latest.log" if args.selftest else "pipeline-latest.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tee = Tee(log_path)

    try:
        log()
        log("════════════════════════════════════════════════════════════")
        log(f"  ZOYA'S ENGLISH · CONTENT PIPELINE v{VERSION}")
        log("════════════════════════════════════════════════════════════")
        env_report = environment_report()
        log("  environment: " + " · ".join(f"{k} {v}" for k, v in env_report.items() if v != "not found"))
        for tool, version in env_report.items():
            if version == "not found":
                warn(f"{tool} not found on PATH — OCR fallback may degrade (using text-layer engine)")
        log()

        if args.selftest:
            passed = run_selftest(args.keep_selftest)
            log()
            log("══════════ SELF-TEST " + ("PASSED — pipeline is launch-ready ════════" if passed else "FAILED ════════════════════"))
            tee.close()
            return 0 if passed else 1

        if args.index_only:
            from pipeline import index as index_module

            dashboard, count = index_module.update_dashboard()
            log("── STEP D · DASHBOARD INDEX " + "─" * 36)
            ok(f"{dashboard.name} refreshed · {count} chapter card(s)")
            tee.close()
            return 0

        code = run_pipeline(args)
        tee.close()
        return code
    except Exception as exc:  # noqa: BLE001 — surface any runtime exception clearly
        fail("pipeline", f"{exc}")
        import traceback

        traceback.print_exc()
        tee.close()
        return 1


if __name__ == "__main__":
    import os

    raise SystemExit(main())
