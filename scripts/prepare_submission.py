#!/usr/bin/env python3
"""Generate the submission package for a revision of the manuscript.

Each stage of the paper lives in its own folder -- manuscript/, revision_1/,
revision_2/, ... -- holding the manuscript, figs/ and the response letter. The
bibliography is shared by all of them and lives at the repository root. The manuscript there is the single
source of truth for that revision. From the first revision onwards it is called
manuscript_annotated.tex, because it carries tracked changes from the `changes`
package alongside other scaffolding that must not reach the journal: line numbers
and `\\linelabel` anchors referenced by the response letter, highlighted internal
notes (target journal, reviewer suggestions), a table of contents and a draft
date.

Every stage produces its own package, the initial submission as much as any
revision. This script strips the internal scaffolding and writes
<stage>/submission/ -- everything a journal asks for, and nothing else:

    manuscript_clean.pdf            tracked changes accepted
    manuscript_annotated.pdf        tracked changes visible
    response_to_reviewers.pdf       copied from the revision folder
    graphical_abstract.pdf          for the separate upload slot
    latex_source_submission.zip     the LaTeX source and its figures

Nothing else: the .tex files and figs/ are built, archived into the zip, and then
removed, so every file in the directory is one upload.

The annotated variant is only produced when the source actually contains tracked
changes, so the initial submission yields the clean manuscript alone.

Before the package is declared finished it is checked over: the letter's line
references must resolve against the manuscript that actually ships, placeholder
text and highlighted notes are reported, and a LaTeX error or an undefined
citation stops the run. Files reached by \\input are spliced in, so a manuscript
split across several files still ships as one.

Usage:
    uv run scripts/prepare_submission.py              # the newest stage
    uv run scripts/prepare_submission.py revision_1   # a specific stage
    uv run scripts/prepare_submission.py --no-build   # write the .tex files only

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
# tracked changes; before that it is just manuscript.tex.
SOURCE_NAMES = ("manuscript_annotated.tex", "manuscript.tex")

# The stages a paper moves through, in order: the manuscript itself, then one
# folder per round of review.
STAGE_MANUSCRIPT = "manuscript"
REVISION_PREFIX = "revision_"

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

# Internal sections removed from every submission, matched on their title,
# case-insensitively. Add your own here if the manuscript grows more of them.
INTERNAL_SECTIONS = ("Target Journal", "Reviewer Suggestions")

# Text that means "not finished yet". These reach the PDF as literal words once
# \hl is unwrapped, so they are worth shouting about -- but not worth blocking a
# build, since a package is often assembled before the last numbers land. Add
# whatever placeholder your group writes.
PLACEHOLDER_PATTERNS = (r"\bXX+\b", r"TO BE DONE", r"\\todoitem")

# The external programs a build needs. Checked before anything is written, so a
# missing LaTeX installation is one sentence rather than a traceback.
REQUIRED_TOOLS = ("pdflatex", "bibtex")

ARTIFACT_GLOBS = (
    "*.aux", "*.bbl", "*.blg", "*.fdb_latexmk", "*.fls",
    "*.loc", "*.log", "*.out", "*.soc", "*.synctex.gz", "*.toc",
)


class Failure(Exception):
    """Something the author can fix. Reported as one sentence, not a traceback."""


def run_cli(entry) -> int:
    """Run a script's main(), turning an expected failure into a readable message.

    A Python traceback tells a LaTeX author nothing they can act on, so the
    conditions we anticipate -- a missing tool, a broken reference, a figure that
    is not where the manuscript says -- surface as a single line instead.
    """
    try:
        return entry()
    except Failure as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def require(*tools: str) -> None:
    """Check for the external programs a build needs, before writing anything."""
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        raise Failure(
            f"not found on PATH: {', '.join(missing)}. A LaTeX installation provides "
            "pdflatex and bibtex -- MacTeX on macOS, MiKTeX or TeX Live on Windows, "
            "TeX Live on Linux. If your editor can build the manuscript, open a new "
            "terminal so it picks up the same PATH."
        )


def find_source(revdir: Path) -> Path | None:
    for name in SOURCE_NAMES:
        if (revdir / name).exists():
            return revdir / name
    return None


def revision_number(name: str) -> int | None:
    suffix = name[len(REVISION_PREFIX) :]
    return int(suffix) if name.startswith(REVISION_PREFIX) and suffix.isdigit() else None


def stage_dirs() -> list[Path]:
    """Every stage holding a manuscript, in the order the paper passes through them."""
    first = REPO / STAGE_MANUSCRIPT
    stages = [first] if first.is_dir() and find_source(first) is not None else []
    revisions = sorted(
        (n, p)
        for p in REPO.glob(f"{REVISION_PREFIX}*")
        if p.is_dir() and (n := revision_number(p.name)) is not None and find_source(p) is not None
    )
    return stages + [p for _, p in revisions]


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
    """Remove a \\section*{...} whose title contains `title_fragment`, up to the next section.

    Matched case-insensitively: a section retitled "Target journal" is the same
    internal note as "Target Journal", and failing to recognise it would send it
    to the journal.
    """
    pattern = re.compile(r"\\section\*?\{")
    for m in pattern.finditer(text):
        end = match_brace(text, m.end() - 1)
        if title_fragment.casefold() not in text[m.end() : end].casefold():
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


def inline_inputs(text: str, basedir: Path) -> str:
    """Splice \\input{...} files in, so a generated file stands on its own.

    The shipped .tex travels to a journal alone, and the working copies the Word
    export builds live in a temporary directory, so neither can reach a file the
    source sits beside -- the shared title block, or a manuscript split into one
    file per section. Paths resolve relative to the file that names them, which is
    what LaTeX itself does, and an \\input inside a comment is left alone.
    """
    out = []
    for line in text.split("\n"):
        cut = comment_start(line)
        code = line if cut is None else line[:cut]
        m = re.search(r"\\input\{([^}]*)\}", code)
        if m is None:
            out.append(line)
            continue
        path = basedir / m.group(1)
        if not path.suffix:
            path = path.with_suffix(".tex")
        if not path.exists():
            raise Failure(f"\\input{{{m.group(1)}}} in {basedir} points at {path}, which does not exist")
        body = inline_inputs(path.read_text().rstrip(), path.parent)
        out.append(code[: m.start()] + body + code[m.end() :])
    return "\n".join(out)


def transform(src: str, basedir: Path, *, annotated: bool) -> str:
    # Before anything else, so a preamble or a section living in its own file is
    # stripped and flattened on the same terms as one written inline.
    text = inline_inputs(src, basedir)

    drop = PREAMBLE_DROP if annotated else PREAMBLE_DROP + PREAMBLE_DROP_CLEAN
    text = "\n".join(line for line in text.split("\n") if not any(tok in line for tok in drop))

    text = text.replace(r"\date{\today}", r"\date{}")
    # The source cites ../references, the shared bibliography. During the bibtex pass
    # a copy of it sits next to the generated .tex, so point there instead.
    text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: r"\bibliography{references}", text)

    for title in INTERNAL_SECTIONS:
        text = strip_section(text, title)

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
        raise Failure(f"{tex.name}: no PDF produced; see {tex.with_suffix('.log')}")
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
        raise Failure(
            f"{tex.name}: {len(errors)} error(s), {len(undefined)} undefined "
            f"citation/reference(s), listed above. Full log: {tex.with_suffix('.log')}"
        )


def inline_bibliography(tex: Path) -> None:
    """Replace \\bibliographystyle/\\bibliography with the generated .bbl contents."""
    bbl = tex.with_suffix(".bbl")
    if not bbl.exists():
        raise Failure(f"{bbl} not found -- did the bibtex pass run? See {tex.with_suffix('.blg')}")
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
            raise Failure(
                f"figure referenced but missing: {src}. \\includegraphics paths are "
                f"relative to {revdir.name}/, so a figure belongs in {revdir.name}/figs/."
            )
        dst = outdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return figs


def warn_placeholders(tex: Path) -> int:
    """Report unfilled placeholders in a .tex. Returns how many.

    Comments and macro definitions are skipped, because the response letter both
    defines \\todoitem and documents it in a comment, and neither reaches the page.
    """
    pattern = re.compile("|".join(PLACEHOLDER_PATTERNS))
    definition = re.compile(r"\\(?:re)?newcommand\{\\?[A-Za-z]+\}")
    hits = 0
    for n, line in enumerate(tex.read_text().split("\n"), 1):
        cut = comment_start(line)
        code = line if cut is None else line[:cut]
        if definition.search(code):
            continue
        m = pattern.search(code)
        if m is None:
            continue
        hits += 1
        start = max(0, m.start() - 40)
        excerpt = " ".join(code[start : m.end() + 40].split())
        print(f"  {tex.name}:{n}: ...{excerpt}...", file=sys.stderr)
    return hits


def surviving_highlights(src: str, basedir: Path) -> list[str]:
    """The \\hl{...} notes that reach the journal, as plain text once the colour goes.

    Highlighting marks a passage as still open, and unwrapping it keeps the words:
    only the two internal sections are removed outright. A note left highlighted is
    therefore submitted verbatim, which is worth saying out loud. It doubles as the
    net under strip_section -- a retitled internal section still has its highlighted
    heading, so it shows up here.
    """
    text = strip_comments(inline_inputs(src, basedir))
    for title in INTERNAL_SECTIONS:
        text = strip_section(text, title)
    notes = []
    for m in re.finditer(r"\\(?:hl|highlight)(?![a-zA-Z])", text):
        (body,), _ = read_args(text, m.end(), 1)
        notes.append(" ".join(body.split()))
    return notes


def letter_line_references(letter_src: Path) -> set[str]:
    """The line labels a response letter points at."""
    text = strip_comments(letter_src.read_text())
    # The definitions of \lnp and \lnum refer to their own argument as #1, which is
    # a label no manuscript defines.
    return {k for k in re.findall(r"\\ln(?:p|um)\{([^}]*)\}", text) if "#" not in k}


def check_line_references(letter_src: Path, defined: set[str]) -> None:
    """Every \\lnp{...} in the letter must resolve against the manuscript that ships.

    An unresolved one is not a silent ??: the letter prints a red "[line ?? --
    rebuild manuscript_annotated.tex]" in its place, and a package carrying that
    has to be stopped rather than noticed by an editor. Checked twice -- against the
    source before anything is built, so the answer comes in a second, and against
    the shipped manuscript's .aux, which is what the letter will really read.
    """
    missing = sorted(letter_line_references(letter_src) - defined)
    if missing:
        raise Failure(
            f"{letter_src.name} points at line labels the manuscript does not define: "
            f"{', '.join(missing)}. Add \\linelabel{{...}} at the matching place in the "
            "manuscript, or drop the reference from the letter."
        )


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


def clear_outdir(outdir: Path, *, forced: bool) -> None:
    """Empty the output directory, refusing to delete anything that is not ours.

    Everything here is rebuilt from scratch on every run, so a stale .aux or .bbl
    can never mask a problem -- but --outdir accepts any path, and a mistyped one
    would take the directory with it.
    """
    if not outdir.exists():
        outdir.mkdir(parents=True)
        return
    disposable = outdir.name == "submission" or not any(outdir.iterdir())
    if not disposable and not forced:
        raise Failure(
            f"{outdir} already exists, is not empty, and is not a submission/ folder. "
            "Everything in it would be deleted. Pass --force if that is what you meant."
        )
    shutil.rmtree(outdir)
    outdir.mkdir(parents=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "stage", nargs="?", type=Path, default=None, help="stage folder (default: the newest one)"
    )
    ap.add_argument("--outdir", type=Path, default=None, help="output dir (default: <stage>/submission)")
    ap.add_argument(
        "--no-build",
        action="store_true",
        help="write the .tex files and stop, leaving them in place for inspection",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="let --outdir empty a directory that is not a submission/ folder",
    )
    args = ap.parse_args()

    if args.stage is not None:
        revdir = args.stage if args.stage.is_absolute() else REPO / args.stage
    else:
        stages = stage_dirs()
        if not stages:
            ap.error("no stage with a manuscript found; pass a stage folder explicitly")
        revdir = stages[-1]

    source = find_source(revdir)
    if source is None:
        ap.error(f"none of {', '.join(SOURCE_NAMES)} found in {revdir}")

    # Before writing anything, so a missing LaTeX installation is reported rather
    # than discovered halfway through a half-built package.
    if not args.no_build:
        require(*REQUIRED_TOOLS)

    src_text = source.read_text()

    # Cheap and first: a letter pointing at an anchor the manuscript never sets is
    # worth saying before a three-pass LaTeX build, not after one.
    letter_src = revdir / "response_to_reviewers.tex"
    if letter_src.exists():
        check_line_references(
            letter_src, set(re.findall(r"\\linelabel\{([^}]*)\}", inline_inputs(src_text, revdir)))
        )

    outdir = args.outdir or revdir / "submission"
    clear_outdir(outdir, forced=args.force)

    variants = [("manuscript_clean.tex", False)]
    if has_tracked_changes(src_text):
        variants.append(("manuscript_annotated.tex", True))

    figs: set[str] = set()
    texs = []
    for name, annotated in variants:
        tex = outdir / name
        text = transform(src_text, revdir, annotated=annotated)
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
            ap.error(f"{BIB} not found; it is the bibliography shared by every stage")
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
    # building it in the stage folder would reference the wrong lines.
    annotated_aux = outdir / "manuscript_annotated.aux"
    letter_placeholders = 0
    if letter_src.exists() and annotated_aux.exists():
        check_line_references(
            letter_src,
            set(re.findall(r"\\newlabel\{([^}]+)\}", annotated_aux.read_text(errors="replace"))),
        )
        letter = outdir / letter_src.name
        letter.write_text(inline_inputs(letter_src.read_text(), revdir))
        pdflatex(letter)
        pdflatex(letter)
        assert_log_clean(letter)
        letter_placeholders = warn_placeholders(letter)
        letter.unlink()
        print(f"built {letter.with_suffix('.pdf').relative_to(REPO)} (against the shipped manuscript)")
    elif letter_src.exists():
        print(
            f"note: {letter_src.name} skipped -- it needs the annotated manuscript's"
            " line numbers, and this revision has no annotated variant",
            file=sys.stderr,
        )

    placeholders = sum(warn_placeholders(tex) for tex in texs) + letter_placeholders
    if placeholders:
        print(
            f"WARNING: {placeholders} line(s) still contain placeholder text (above). "
            "The package was built anyway.",
            file=sys.stderr,
        )

    notes = surviving_highlights(src_text, revdir)
    if notes:
        for note in notes:
            print(f"  {note[:100]}", file=sys.stderr)
        print(
            f"WARNING: {len(notes)} highlighted note(s) above are in the submission as "
            "plain text. Highlighting is a colour, not a fence: only the "
            f"{' and '.join(INTERNAL_SECTIONS)} sections are removed outright.",
            file=sys.stderr,
        )

    for pattern in ARTIFACT_GLOBS:
        for p in outdir.glob(pattern):
            p.unlink()

    archive = make_source_zip(outdir / "manuscript_clean.tex", outdir)
    print(f"packed {archive.relative_to(REPO)}")

    # The sources now live in the archive, so the directory is left holding only
    # what gets uploaded: the PDFs and that one zip. A paper without figures never
    # had a figs/ to remove.
    for tex in outdir.glob("*.tex"):
        tex.unlink()
    if (outdir / "figs").is_dir():
        shutil.rmtree(outdir / "figs")
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(main))
