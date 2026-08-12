#!/usr/bin/env python3
"""Generate the submission package for a revision of the manuscript.

Each rev<N>/ folder holds a revision's working set: the manuscript, figs/ and the
response letter. The bibliography is shared by all revisions and lives at the
repository root. The manuscript there is the single
source of truth for that revision. From the first revision onwards it is called
manuscript_annotated.tex, because it carries tracked changes from the `changes`
package alongside other scaffolding that must not reach the journal: line numbers
and `\\linelabel` anchors referenced by the response letter, highlighted internal
notes (target journal, reviewer suggestions), a table of contents and a draft
date.

This script strips the internal scaffolding and writes rev<N>/submission/ --
everything a journal asks for, and nothing else:

    manuscript_clean.pdf            tracked changes accepted
    manuscript_annotated.pdf        tracked changes visible
    response_to_reviewers.pdf       copied from the revision folder
    graphical_abstract.pdf          for the separate upload slot
    latex_source_submission.zip     the LaTeX source and its figures

Nothing else: the .tex files and figs/ are built, archived into the zip, and then
removed, so every file in the directory is one upload.

The annotated variant is only produced when the source actually contains tracked
changes, so an original submission (rev0) yields the clean manuscript alone.

Usage:
    uv run scripts/make_submission.py              # newest rev<N>/
    uv run scripts/make_submission.py rev1         # a specific revision
    uv run scripts/make_submission.py --no-build   # write the .tex files only

No third-party dependencies; needs pdflatex and bibtex on PATH.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# One bibliography, shared by every revision. The generated submission files do
# not use it: their bibliography ends up inline, so they travel on their own.
BIB = REPO / "references.bib"

# A revision's manuscript is called manuscript_annotated.tex once it carries
# tracked changes; the original submission just has manuscript.tex.
SOURCE_NAMES = ("manuscript_annotated.tex", "manuscript.tex")

# Preamble lines dropped from every variant: review highlighting and the
# table of contents are never wanted in a submission.
PREAMBLE_DROP = (
    r"\usepackage{soul}",
    r"\definecolor{reviewyellow}",
    r"\sethlcolor{reviewyellow}",
    r"\tableofcontents",
)

# Dropped from the clean variant only: the definitions that style the tracked
# changes, which the clean variant no longer has. Line numbers stay in both --
# reviewers and the response letter cite them.
PREAMBLE_DROP_CLEAN = (
    r"\usepackage{changes}",
    r"\definechangesauthor",
    r"\setaddedmarkup",
    r"\setdeletedmarkup",
)

# Print every fifth number only; lineno still counts every line, so a reference
# to line 118 lands between the printed 115 and 120.
LINE_NUMBER_INTERVAL = 5

# Macro -> which argument survives (None = drop the macro and its argument).
FLATTEN_CLEAN = {
    "replaced": 0,   # \replaced{new}{old} -> new
    "added": 0,      # \added{text}        -> text
    "deleted": None, # \deleted{text}      -> (nothing)
    "linelabel": None,
    "highlight": 0,
    "hl": 0,         # \hl{text}           -> text
}
# The annotated variant keeps the tracked changes; only the review highlighting
# goes, because the soul package that provides \hl is dropped.
FLATTEN_ANNOTATED = {"highlight": 0, "hl": 0}

NARGS = {"replaced": 2, "added": 1, "deleted": 1, "highlight": 1, "hl": 1, "linelabel": 1}

# The build recipe this project uses (mirrors the editor's LaTeX Workshop
# settings): pdflatex, bibtex, pdflatex, pdflatex, output beside the source.
PDFLATEX_ARGS = ("-synctex=1", "-interaction=nonstopmode", "-file-line-error")

# Text that means "not finished yet". These reach the PDF as literal words once
# \hl is unwrapped, so they are worth shouting about -- but not worth blocking a
# build, since a package is often assembled before the last numbers land.
PLACEHOLDER_PATTERNS = (r"\bXX+\b", r"\bHARDWARE\b", r"TO BE DONE", r"\\todoitem")

ARTIFACT_GLOBS = (
    "*.aux", "*.bbl", "*.blg", "*.fdb_latexmk", "*.fls",
    "*.loc", "*.log", "*.out", "*.soc", "*.synctex.gz", "*.toc",
)


def find_source(revdir: Path) -> Path | None:
    for name in SOURCE_NAMES:
        if (revdir / name).exists():
            return revdir / name
    return None


def rev_dirs() -> list[Path]:
    """All rev<N>/ working sets, oldest first."""
    revs = sorted(
        (int(p.name[3:]), p)
        for p in REPO.glob("rev[0-9]*")
        if p.is_dir() and p.name[3:].isdigit() and find_source(p) is not None
    )
    return [p for _, p in revs]


def has_tracked_changes(src: str) -> bool:
    return re.search(r"\\(replaced|added|deleted)(?![a-zA-Z])", src) is not None


def match_brace(s: str, i: int) -> int:
    """Index just past the group starting at s[i] == '{'. Handles nesting and \\{."""
    assert s[i] == "{", f"expected {{ at {i}, got {s[i]!r}"
    depth = 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced braces")


def read_args(s: str, i: int, n: int) -> tuple[list[str], int]:
    """Read an optional [..] then n brace groups starting at i. Returns (args, end)."""
    if i < len(s) and s[i] == "[":
        i = s.index("]", i) + 1
    args = []
    for _ in range(n):
        while i < len(s) and s[i] in " \n\t":
            i += 1
        end = match_brace(s, i)
        args.append(s[i + 1 : end - 1])
        i = end
    return args, i


def flatten(text: str, macros: dict) -> str:
    """Resolve the given macros, innermost-last.

    Applied repeatedly because a surviving argument may itself contain markup
    (e.g. \\replaced{...\\added{x}...}{old}).
    """
    pattern = re.compile(r"\\(" + "|".join(macros) + r")(?![a-zA-Z])")
    for _ in range(10):
        if not pattern.search(text):
            return text
        out = []
        pos = 0
        while True:
            m = pattern.search(text, pos)
            if not m:
                out.append(text[pos:])
                break
            name = m.group(1)
            args, end = read_args(text, m.end(), NARGS[name])
            keep = macros[name]
            out.append(text[pos : m.start()])
            out.append("" if keep is None else args[keep])
            pos = end
        text = "".join(out)
    raise RuntimeError("markup did not converge; nested too deeply?")


def strip_section(text: str, title_fragment: str) -> str:
    """Remove a \\section*{...} whose title contains `title_fragment`, up to the next section."""
    pattern = re.compile(r"\\section\*?\{")
    for m in pattern.finditer(text):
        end = match_brace(text, m.end() - 1)
        if title_fragment not in text[m.end() : end]:
            continue
        nxt = pattern.search(text, end)
        return text[: m.start()] + text[nxt.start() if nxt else len(text) :]
    return text


def ensure_line_numbers(text: str) -> str:
    """Number the lines of both variants, printing every LINE_NUMBER_INTERVAL-th.

    Reviewers refer to line numbers in both the clean and the marked-up
    manuscript, so neither variant may lose them -- and a source that never had
    the lineno package (an original submission) gets it added.

    Counting starts at the abstract rather than at \\begin{document}, so the title
    block does not consume the first handful of numbers.
    """
    if not re.search(r"\\usepackage(?:\[[^]]*\])?\{lineno\}", text):
        text = text.replace(
            r"\begin{document}", "\\usepackage[left]{lineno}\n\n" + r"\begin{document}", 1
        )
    if r"\modulolinenumbers" not in text:
        text = re.sub(
            r"(\\usepackage(?:\[[^]]*\])?\{lineno\}[^\n]*\n)",
            lambda m: m.group(1) + f"\\modulolinenumbers[{LINE_NUMBER_INTERVAL}]\n",
            text,
            count=1,
        )
    # Re-anchor wherever \linenumbers currently sits.
    text = re.sub(r"^\\linenumbers[ \t]*\n\n?", "", text, flags=re.MULTILINE)
    anchor = r"\section*{Abstract}"
    if anchor in text:
        text = text.replace(anchor, "\\linenumbers\n\n" + anchor, 1)
    else:
        text = text.replace(r"\begin{document}", "\\begin{document}\n\n\\linenumbers", 1)
    return text


def comment_start(line: str) -> int | None:
    """Index of the % that begins a comment, honouring \\% escapes."""
    escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "%":
            return i
    return None


def strip_comments(text: str) -> str:
    """Drop the source's comments, which are notes to ourselves, not to the journal.

    A trailing % swallows the following newline, so an inline comment is cut back
    to a bare % rather than removed outright -- otherwise words would run together
    or gain spaces. Whole-line comments contribute nothing and simply go.
    """
    kept = []
    for line in text.split("\n"):
        i = comment_start(line)
        if i is None:
            kept.append(line)
        elif not line[:i].strip():
            continue
        else:
            kept.append(line[:i] + "%")
    return "\n".join(kept)


def transform(src: str, source_name: str, *, annotated: bool) -> str:
    text = src

    drop = PREAMBLE_DROP if annotated else PREAMBLE_DROP + PREAMBLE_DROP_CLEAN
    text = "\n".join(line for line in text.split("\n") if not any(tok in line for tok in drop))

    text = text.replace(r"\date{\today}", r"\date{}")
    # The source cites ../references, the shared bibliography. During the bibtex pass
    # a copy of it sits next to the generated .tex, so point there instead.
    text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: r"\bibliography{references}", text)

    text = strip_section(text, "Target Journal")
    text = strip_section(text, "Reviewer Suggestions")

    text = flatten(text, FLATTEN_ANNOTATED if annotated else FLATTEN_CLEAN)
    text = ensure_line_numbers(text)
    text = strip_comments(text)

    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"(\\maketitle\n)(\s*\\newpage\n)+", r"\1", text)

    # One neutral line of provenance. The journal receives this file, so it carries
    # no notes to ourselves -- strip_comments above has removed the rest.
    shown = "tracked changes shown" if annotated else "tracked changes accepted"
    header = f"% Generated submission version: {shown}, bibliography inlined.\n"
    return header + text


def pdflatex(tex: Path) -> None:
    """One pdflatex pass, with the same flags the editor's build recipe uses."""
    subprocess.run(
        ["pdflatex", *PDFLATEX_ARGS, tex.name],
        cwd=tex.parent,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def bibtex(tex: Path) -> None:
    subprocess.run(
        ["bibtex", tex.stem],
        cwd=tex.parent,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def assert_log_clean(tex: Path) -> None:
    """Fail loudly on LaTeX errors or unresolved citations/references."""
    if not tex.with_suffix(".pdf").exists():
        raise RuntimeError(f"{tex.name}: no PDF produced")
    log = tex.with_suffix(".log").read_text(errors="replace")
    # -file-line-error reports "file.tex:12: message" instead of "! message",
    # so both shapes have to be recognised.
    errors = re.findall(r"^!.*", log, re.MULTILINE) + re.findall(
        r"^[^\n:]+\.tex:\d+:.*", log, re.MULTILINE
    )
    undefined = re.findall(r"(?:Citation|Reference).*undefined", log)
    if errors or undefined:
        for line in (errors + undefined)[:10]:
            print(f"  {line.strip()}", file=sys.stderr)
        raise RuntimeError(
            f"{tex.name}: {len(errors)} error(s), {len(undefined)} undefined citation/reference(s)"
        )


def inline_bibliography(tex: Path) -> None:
    """Replace \\bibliographystyle/\\bibliography with the generated .bbl contents."""
    bbl = tex.with_suffix(".bbl")
    if not bbl.exists():
        raise FileNotFoundError(f"{bbl} not found -- did the bibtex pass run?")
    text = tex.read_text()
    text = re.sub(r"\\bibliographystyle\{[^}]*\}\n", "", text)
    # lambda, not a template string: .bbl content is full of backslashes.
    entries = bbl.read_text().rstrip() + "\n"
    text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: entries, text)
    tex.write_text(text)


def copy_figures(text: str, revdir: Path, outdir: Path) -> set[str]:
    figs = set(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]*)\}", text))
    for rel in figs:
        src = revdir / rel
        if not src.exists():
            raise FileNotFoundError(f"figure referenced but missing: {src}")
        dst = outdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return figs


def warn_placeholders(tex: Path) -> int:
    """Report unfilled placeholders in a generated .tex. Returns how many."""
    pattern = re.compile("|".join(PLACEHOLDER_PATTERNS))
    hits = [
        (n, line) for n, line in enumerate(tex.read_text().split("\n"), 1) if pattern.search(line)
    ]
    for n, line in hits:
        excerpt = " ".join(line.split())
        for m in pattern.finditer(line):
            start = max(0, m.start() - 40)
            excerpt = " ".join(line[start : m.end() + 40].split())
            break
        print(f"  {tex.name}:{n}: ...{excerpt}...", file=sys.stderr)
    return len(hits)


def make_source_zip(tex: Path, outdir: Path) -> Path:
    """Archive the manuscript sources: the clean .tex and its figures, nothing else.

    Deliberately excludes every PDF -- the manuscript, the response letter and
    the graphical abstract are uploaded as their own files and sit beside this
    archive. Only the clean manuscript is archived; the annotated variant is a
    review aid, not what gets typeset by the journal.
    """
    archive = outdir / "latex_source_submission.zip"
    members = [tex] + sorted(
        p for p in (outdir / "figs").rglob("*") if p.is_file() and not p.name.startswith(".")
    )
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in members:
            z.write(p, p.relative_to(outdir))
    return archive


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "rev", nargs="?", type=Path, default=None, help="revision folder (default: the newest rev<N>)"
    )
    ap.add_argument("--outdir", type=Path, default=None, help="output dir (default: <rev>/submission)")
    ap.add_argument(
        "--no-build",
        action="store_true",
        help="write the .tex files and stop, leaving them in place for inspection",
    )
    args = ap.parse_args()

    if args.rev is not None:
        revdir = args.rev if args.rev.is_absolute() else REPO / args.rev
    else:
        revs = rev_dirs()
        if not revs:
            ap.error("no rev<N> with a manuscript found; pass a revision folder explicitly")
        revdir = revs[-1]

    source = find_source(revdir)
    if source is None:
        ap.error(f"none of {', '.join(SOURCE_NAMES)} found in {revdir}")

    outdir = args.outdir or revdir / "submission"
    # Rebuild from scratch, so a stale .aux or .bbl can never mask a problem.
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)

    src_text = source.read_text()
    variants = [("manuscript_clean.tex", False)]
    if has_tracked_changes(src_text):
        variants.append(("manuscript_annotated.tex", True))

    figs: set[str] = set()
    texs = []
    for name, annotated in variants:
        tex = outdir / name
        text = transform(src_text, source.name, annotated=annotated)
        tex.write_text(text)
        figs |= copy_figures(text, revdir, outdir)
        texs.append(tex)

    # The graphical abstract stays in the document, and is also exported on its own
    # because submission systems ask for it as a separate upload.
    ga = next(revdir.glob("figs/graphical_abstract*.pdf"), None)
    if ga is not None:
        shutil.copy2(ga, outdir / "graphical_abstract.pdf")

    print(f"prepared {', '.join(t.name for t in texs)} ({len(figs)} figures) "
          f"in {outdir.relative_to(REPO)}")

    if args.no_build:
        print("(--no-build: sources left in place, not built and not archived)")
        return 0

    # The recipe is pdflatex, bibtex, pdflatex, pdflatex. The .bbl bibtex writes
    # is folded into the .tex between the passes, so the shipped source needs no
    # .bib. A source whose bibliography is already inline -- an archived
    # submission, for instance -- skips bibtex entirely.
    needs_bibtex = any(r"\bibliography{" in tex.read_text() for tex in texs)
    if needs_bibtex:
        if not BIB.exists():
            ap.error(f"{BIB} not found; it is the bibliography shared by all revisions")
        shutil.copy2(BIB, outdir / BIB.name)

    for tex in texs:
        pdflatex(tex)
        if needs_bibtex:
            bibtex(tex)
            inline_bibliography(tex)
        pdflatex(tex)
        pdflatex(tex)
        assert_log_clean(tex)
        print(f"built {tex.with_suffix('.pdf').relative_to(REPO)}")

    if needs_bibtex:
        (outdir / BIB.name).unlink()

    # The response letter cites the manuscript's line numbers through xr. Those
    # numbers shift once the internal front matter is stripped, so the letter has
    # to be built here, against the annotated manuscript that actually ships --
    # building it in the revision folder would reference the wrong lines.
    letter_src = revdir / "response_to_reviewers.tex"
    annotated_aux = outdir / "manuscript_annotated.aux"
    if letter_src.exists() and annotated_aux.exists():
        letter = outdir / letter_src.name
        shutil.copy2(letter_src, letter)
        pdflatex(letter)
        pdflatex(letter)
        assert_log_clean(letter)
        letter.unlink()
        print(f"built {letter.with_suffix('.pdf').relative_to(REPO)} (against the shipped manuscript)")
    elif letter_src.exists():
        print(
            f"note: {letter_src.name} skipped -- it needs the annotated manuscript's"
            " line numbers, and this revision has no annotated variant",
            file=sys.stderr,
        )

    placeholders = sum(warn_placeholders(tex) for tex in texs)
    if placeholders:
        print(
            f"WARNING: {placeholders} line(s) still contain placeholder text (above). "
            "The package was built anyway.",
            file=sys.stderr,
        )

    for pattern in ARTIFACT_GLOBS:
        for p in outdir.glob(pattern):
            p.unlink()

    archive = make_source_zip(outdir / "manuscript_clean.tex", outdir)
    print(f"packed {archive.relative_to(REPO)}")

    # The sources now live in the archive, so the directory is left holding only
    # what gets uploaded: the PDFs and that one zip.
    for tex in outdir.glob("*.tex"):
        tex.unlink()
    shutil.rmtree(outdir / "figs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
