#!/usr/bin/env python3
"""Export the manuscript, and a revision's response letter, to Word.

This is a convenience for internal review rather than part of the submission path.
Nothing a journal receives comes out of here, so the export keeps the internal front
matter that prepare_submission.py strips.

By default it works on the newest stage. At the manuscript stage that means the
manuscript alone. In a revision it also converts response_to_reviewers.tex, so whoever
reads the round sees the answers beside the text. A single .tex file can be named
instead.

Pandoc on its own does not produce a document worth circulating, so the export runs a
real LaTeX build first and takes what it needs from it.

- Cross-references. Pandoc resolves a reference to a figure but leaves one to an
  equation as its raw label, and it numbers figures on its own count rather than
  LaTeX's, so every reference is replaced with the number in the .aux.
- Citations and the bibliography. Both come from the .bbl that bibtex wrote, so the
  superscript numbers, the author labels natbib prints for \\citet, the compression of
  several citations into a range and the order of the reference list match the PDF.
- Figures. Word cannot display a PDF image, so PDF figures are converted to PNG.
- Macros. Pandoc reads \\newcommand but knows nothing of the packages behind isomath's
  math symbols, or of the letter's own commands, so both are translated first.

Tracked changes are accepted, so the manuscript reads as the revised text.

Usage:
    uv run scripts/export_to_word.py                          # the newest stage
    uv run scripts/export_to_word.py revision_1               # a specific stage
    uv run scripts/export_to_word.py revision_1/response_to_reviewers.tex

Needs pandoc and pdftoppm (poppler) in addition to pdflatex and bibtex.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_submission as ps  # noqa: E402  (same directory, shared helpers)

REPO = ps.REPO
LETTER = "response_to_reviewers.tex"
SUFFIX = "_for_review.docx"
FIGURE_DPI = 200

# Pandoc reads \newcommand, but not the packages that define these.
MATH_MACROS = r"""
\newcommand{\vectorsym}[1]{\boldsymbol{#1}}
\newcommand{\matrixsym}[1]{\boldsymbol{#1}}
"""

# Dropped because they mean nothing in Word.
PREAMBLE_DROP = (
    r"\usepackage[left]{lineno}",
    r"\modulolinenumbers",
    r"\linenumbers",
    r"\tableofcontents",
    r"\externaldocument",
)


def require(*tools: str) -> None:
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        sys.exit(f"not found on PATH: {', '.join(missing)}")


def labels_from_aux(aux: Path) -> dict[str, str]:
    """Map every \\label to the number LaTeX printed for it."""
    pattern = re.compile(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}")
    return {m.group(1): m.group(2) for m in pattern.finditer(aux.read_text(errors="replace"))}


def resolve_references(text: str, labels: dict[str, str]) -> tuple[str, int, list[str]]:
    """Replace \\ref and friends with their numbers. Returns the text, hits and misses."""
    resolved = 0
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        nonlocal resolved
        key = m.group(2)
        number = labels.get(key)
        if number is None:
            missing.append(key)
            return m.group(0)
        resolved += 1
        return f"({number})" if m.group(1) == "eqref" else number

    text = re.sub(r"\\(ref|eqref|autoref)\{([^}]+)\}", sub, text)
    return text, resolved, missing


def bibliography_from_bbl(bbl: Path) -> tuple[dict[str, tuple[int, str]], str]:
    """Read the .bbl into citation data and a numbered LaTeX bibliography.

    Returns {key: (number, author label)} plus the bibliography to splice in. The
    numbers and the order are bibtex's, so they agree with the PDF.
    """
    text = bbl.read_text(errors="replace")
    entry = re.compile(
        r"\\bibitem\[([^\]]*)\]\{([^}]+)\}(.*?)(?=\\bibitem\[|\\end\{thebibliography\})",
        re.S,
    )
    cites: dict[str, tuple[int, str]] = {}
    items: list[str] = []
    for number, m in enumerate(entry.finditer(text), start=1):
        label, key, body = m.group(1), m.group(2), m.group(3)
        # natbib writes the label as "Author(year)", and \citet prints the author part.
        cites[key] = (number, label.split("(")[0].strip())
        body = body.replace(r"\newblock", " ")
        body = re.sub(r"\\penalty\d+\s*", "", body)
        body = re.sub(r"\\doi\{([^}]*)\}", r"doi: \1", body)
        body = re.sub(r"\\url\{([^}]*)\}", r"\1", body)
        body = re.sub(r"\\natexlab\{([^}]*)\}", r"\1", body)
        items.append(r"\item " + " ".join(body.split()))
    bibliography = (
        "\\section*{References}\n\\begin{enumerate}\n" + "\n".join(items) + "\n\\end{enumerate}\n"
    )
    return cites, bibliography


def compress(numbers: list[int]) -> str:
    """Write citation numbers the way natbib's sort&compress does.

    Runs of three or more become a range, shorter runs stay separate, so [1,2,3,7]
    prints as 1--3,7.
    """
    ordered = sorted(set(numbers))
    parts: list[str] = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        run = ordered[i : j + 1]
        if len(run) >= 3:
            parts.append(f"{run[0]}--{run[-1]}")
        else:
            parts.extend(str(n) for n in run)
        i = j + 1
    return ",".join(parts)


def resolve_citations(text: str, cites: dict[str, tuple[int, str]]) -> tuple[str, list[str]]:
    """Render \\cite as superscript numbers and \\citet as author plus number."""
    missing: list[str] = []

    def numbers(keys: list[str]) -> str:
        found = []
        for k in keys:
            if k in cites:
                found.append(cites[k][0])
            else:
                missing.append(k)
        return compress(found)

    def textual(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(",")]
        author = cites[keys[0]][1] if keys[0] in cites else ""
        return f"{author}\\textsuperscript{{{numbers(keys)}}}"

    def parenthetical(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(",")]
        return f"\\textsuperscript{{{numbers(keys)}}}"

    text = re.sub(r"\\citet\{([^}]*)\}", textual, text)
    text = re.sub(r"\\cite[p]?\{([^}]*)\}", parenthetical, text)
    return text, missing


def replace_macro(text: str, name: str, nargs: int, render) -> str:
    """Replace every use of a macro, matching braces so nested markup survives."""
    pattern = re.compile(rf"\\{name}(?![a-zA-Z])")
    while True:
        m = pattern.search(text)
        if not m:
            return text
        args, end = ps.read_args(text, m.end(), nargs)
        text = text[: m.start()] + render(*args) + text[end:]


def prepare_manuscript(src_text: str) -> str:
    """Accept tracked changes and remove what Word has no use for."""
    # Comments go first, so a macro mentioned in one is not mistaken for a use of it.
    text = ps.strip_comments(ps.flatten(src_text, ps.FLATTEN_CLEAN))
    text = "\n".join(
        line for line in text.split("\n") if not any(tok in line for tok in PREAMBLE_DROP)
    )
    text = text.replace(r"\usepackage{soul}", "")
    # The bibliography is copied next to the working file, so ../references would miss.
    text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: r"\bibliography{references}", text)
    return text.replace(r"\begin{document}", MATH_MACROS + "\n" + r"\begin{document}", 1)


def skip_blanks(s: str, i: int) -> int:
    """Advance past whitespace and comment lines between a macro's arguments."""
    while i < len(s):
        if s[i] in " \n\t":
            i += 1
        elif s[i] == "%":
            i = s.find("\n", i) + 1 or len(s)
        else:
            break
    return i


def drop_definition(text: str, kind: str, name: str, groups: int) -> str:
    """Remove a \\newcommand or \\newenvironment, however many lines it spans.

    The definitions have to go before the uses are replaced, otherwise the definition
    of \\lnp looks like a call to it.
    """
    pattern = re.compile(rf"\\{kind}\{{\\?{re.escape(name)}\}}")
    while True:
        m = pattern.search(text)
        if not m:
            return text
        i = skip_blanks(text, m.end())
        while i < len(text) and text[i] == "[":
            i = skip_blanks(text, text.index("]", i) + 1)
        for _ in range(groups):
            i = skip_blanks(text, i)
            i = ps.match_brace(text, i)
        text = text[: m.start()] + text[i:].lstrip("\n")


def line_labels(src_text: str, work: Path) -> dict[str, str]:
    """Build the manuscript with its line numbers on, to learn what \\linelabel resolves to.

    The Word manuscript has no line numbers, so the letter's references point at the
    numbers in the PDF. Those only exist in a build that keeps lineno and \\linelabel,
    which the export otherwise removes.
    """
    keep_linelabel = {k: v for k, v in ps.FLATTEN_CLEAN.items() if k != "linelabel"}
    text = ps.strip_comments(ps.flatten(src_text, keep_linelabel))
    text = ps.ensure_line_numbers(text)
    text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: r"\bibliography{references}", text)
    numbered = work / "numbered.tex"
    numbered.write_text(text)
    ps.pdflatex(numbered)
    ps.bibtex(numbered)
    ps.pdflatex(numbered)
    aux = numbered.with_suffix(".aux")
    if not aux.exists():
        return {}
    return {k: v for k, v in labels_from_aux(aux).items() if k.startswith("ln:")}


def prepare_letter(src_text: str, labels: dict[str, str]) -> tuple[str, list[str]]:
    """Translate the letter's own commands into ones pandoc understands.

    The colour coding cannot survive the trip, so the three roles are told apart by
    shape instead. A comment becomes a heading and italics, an answer stays plain, and
    quoted manuscript text becomes an indented block.
    """
    missing: list[str] = []
    # LaTeX plumbing that only exists to keep bibtex happy, then the comments, so the
    # block documenting \\comm and \\lnp is not mistaken for uses of them.
    text = re.sub(r"\\makeatletter.*?\\makeatother", "", src_text, flags=re.S)
    text = ps.strip_comments(text)
    text = "\n".join(
        line for line in text.split("\n") if not any(tok in line for tok in PREAMBLE_DROP)
    )

    for kind, name, groups in (
        ("newcommand", "lnp", 1),
        ("newcommand", "lnum", 1),
        ("newcommand", "comm", 1),
        ("newcommand", "todoitem", 1),
        ("newenvironment", "response", 2),
        ("newenvironment", "revisedtext", 2),
    ):
        text = drop_definition(text, kind, name, groups)

    def line_reference(key: str) -> str:
        number = labels.get(key)
        if number is None:
            missing.append(key)
            return "line ??"
        return f"line~{number}"

    text = replace_macro(text, "lnp", 1, lambda key: f"({line_reference(key)})")
    text = replace_macro(text, "lnum", 1, line_reference)
    text = replace_macro(
        text, "comm", 2, lambda n, body: f"\n\\subsection*{{Comment {n}}}\n\\emph{{{body}}}\n"
    )
    text = replace_macro(text, "todoitem", 1, lambda body: f"\n\\textbf{{[TO BE DONE]}} {body}\n")

    for env in ("response", "revisedtext"):
        text = text.replace(rf"\begin{{{env}}}", r"\begin{quote}")
        text = text.replace(rf"\end{{{env}}}", r"\end{quote}")
    return text, missing


def convert_figures(text: str, workdir: Path) -> tuple[str, int]:
    """Turn PDF figures into PNG, which Word can actually display."""
    converted = 0
    for rel in sorted(set(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]*)\}", text))):
        src = workdir / rel
        if src.suffix.lower() != ".pdf" or not src.exists():
            continue
        subprocess.run(
            [
                "pdftoppm", "-png", "-r", str(FIGURE_DPI), "-singlefile",
                str(src), str(src.with_suffix("")),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        text = text.replace(rel, str(Path(rel).with_suffix(".png")))
        converted += 1
    return text, converted


def copy_figures(text: str, stage: Path, work: Path) -> None:
    for rel in set(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]*)\}", text)):
        fig = stage / rel
        if not fig.exists():
            sys.exit(f"figure referenced but missing: {fig}")
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fig, work / rel)


def pandoc(tex: Path, out_name: str, *, toc: bool) -> Path:
    command = [
        "pandoc", tex.name, "-o", out_name, "--number-sections", f"--resource-path={tex.parent}"
    ]
    if toc:
        command.append("--toc")
    subprocess.run(command, cwd=tex.parent, check=True)
    return tex.parent / out_name


def report_missing(keys: list[str]) -> None:
    if keys:
        print(f"    unresolved: {', '.join(sorted(set(keys)))}", file=sys.stderr)


def export(stage: Path, work: Path, only: Path | None) -> list[Path]:
    """Convert a stage's documents, or only the file named, and return what was written."""
    source = ps.find_source(stage)
    if source is None:
        sys.exit(f"none of {', '.join(ps.SOURCE_NAMES)} found in {stage}")

    # The manuscript is built even when only the letter was asked for, because the
    # letter's line references are numbers out of the manuscript's .aux.
    tex = work / "manuscript.tex"
    tex.write_text(prepare_manuscript(source.read_text()))
    shutil.copy2(ps.BIB, work / ps.BIB.name)
    copy_figures(tex.read_text(), stage, work)

    ps.pdflatex(tex)
    ps.bibtex(tex)
    ps.pdflatex(tex)
    bbl = tex.with_suffix(".bbl")
    if not bbl.exists():
        sys.exit(f"bibtex produced no .bbl; see {tex.with_suffix('.blg')}")
    labels = labels_from_aux(tex.with_suffix(".aux"))
    cites, bibliography = bibliography_from_bbl(bbl)

    written: list[Path] = []

    if only is None or only.name == source.name:
        text, refs, missing = resolve_references(tex.read_text(), labels)
        text, uncited = resolve_citations(text, cites)
        text = re.sub(r"\\bibliographystyle\{[^}]*\}\n", "", text)
        text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: bibliography, text)
        text, figures = convert_figures(text, work)
        tex.write_text(text)
        target = stage / (source.stem + SUFFIX)
        shutil.copy2(pandoc(tex, "manuscript.docx", toc=True), target)
        written.append(target)
        print(
            f"  {source.name}: {refs} references, {len(cites)} bibliography entries, "
            f"{figures} figures"
        )
        report_missing(missing + uncited)

    letter_source = stage / LETTER
    if letter_source.exists() and (only is None or only.name == LETTER):
        letter = work / LETTER
        letter_labels = {**labels, **line_labels(source.read_text(), work)}
        text, missing = prepare_letter(letter_source.read_text(), letter_labels)
        text, refs, ref_missing = resolve_references(text, letter_labels)
        text, uncited = resolve_citations(text, cites)
        copy_figures(text, stage, work)
        text, figures = convert_figures(text, work)
        letter.write_text(text)
        target = stage / (letter_source.stem + SUFFIX)
        shutil.copy2(pandoc(letter, "letter.docx", toc=False), target)
        written.append(target)
        print(f"  {LETTER}: {refs} references, {figures} figures")
        report_missing(missing + ref_missing + uncited)

    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "target",
        nargs="?",
        type=Path,
        default=None,
        help="a stage folder, or a single .tex file (default: the newest stage)",
    )
    args = ap.parse_args()

    require("pandoc", "pdftoppm", "pdflatex", "bibtex")
    if not ps.BIB.exists():
        ap.error(f"{ps.BIB} not found")

    only: Path | None = None
    if args.target is None:
        stages = ps.stage_dirs()
        if not stages:
            ap.error("no stage with a manuscript found; name a stage or a file")
        stage = stages[-1]
    else:
        target = args.target if args.target.is_absolute() else REPO / args.target
        if target.is_dir():
            stage = target
        elif target.is_file() and target.suffix == ".tex":
            stage, only = target.parent, target
        else:
            ap.error(f"{target} is neither a stage folder nor a .tex file")

    print(f"exporting {stage.name}")
    with tempfile.TemporaryDirectory() as tmp:
        written = export(stage, Path(tmp), only)
    for path in written:
        print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
