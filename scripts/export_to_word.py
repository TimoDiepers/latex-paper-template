#!/usr/bin/env python3
"""Export the manuscript to Word, for colleagues who prefer to comment there.

This is a convenience for internal review rather than part of the submission path.
Nothing a journal receives comes out of here, so the export keeps the internal front
matter that prepare_submission.py strips.

Four things need help before pandoc can produce a usable .docx.

- Cross-references. Pandoc resolves a reference to a figure but leaves one to an
  equation as its raw label, so every \\ref is replaced with the number LaTeX gave it,
  read out of the .aux of a real build.
- Citations and the bibliography. Both are taken from the .bbl that bibtex produced,
  so the numbers, the author labels natbib prints for \\citet and the entry order are
  the ones in the PDF. Pandoc's own citeproc is not used, because it would impose its
  own style.
- Figures. Word cannot display a PDF image, so PDF figures are converted to PNG and
  the paths rewritten.
- Math macros from packages. Pandoc reads \\newcommand definitions but knows nothing of
  isomath, so the few macros the template uses are defined for it.

Usage:
    uv run scripts/export_to_word.py              # the newest stage
    uv run scripts/export_to_word.py manuscript   # a specific stage

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
OUTPUT_NAME = "manuscript_for_review.docx"
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
    """Write a list of citation numbers the way natbib's sort&compress does.

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


def convert_figures(text: str, workdir: Path) -> tuple[str, int]:
    """Turn PDF figures into PNG, which Word can actually display."""
    converted = 0
    for rel in sorted(set(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]*)\}", text))):
        src = workdir / rel
        if src.suffix.lower() != ".pdf" or not src.exists():
            continue
        stem = src.with_suffix("")
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(FIGURE_DPI), "-singlefile", str(src), str(stem)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        text = text.replace(rel, str(Path(rel).with_suffix(".png")))
        converted += 1
    return text, converted


def prepare_source(src_text: str) -> str:
    """Accept tracked changes and remove what Word has no use for."""
    text = ps.flatten(src_text, ps.FLATTEN_CLEAN)
    text = "\n".join(
        line for line in text.split("\n") if not any(tok in line for tok in PREAMBLE_DROP)
    )
    text = text.replace(r"\usepackage{soul}", "")
    # The bibliography is copied next to the working file, so ../references would miss.
    text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: r"\bibliography{references}", text)
    return text.replace(r"\begin{document}", MATH_MACROS + "\n" + r"\begin{document}", 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "stage", nargs="?", type=Path, default=None, help="stage folder (default: the newest one)"
    )
    ap.add_argument("--output", type=Path, default=None, help=f"output file (default: <stage>/{OUTPUT_NAME})")
    args = ap.parse_args()

    require("pandoc", "pdftoppm", "pdflatex", "bibtex")

    if args.stage is not None:
        stage = args.stage if args.stage.is_absolute() else REPO / args.stage
    else:
        stages = ps.stage_dirs()
        if not stages:
            ap.error("no stage with a manuscript found; pass a stage folder explicitly")
        stage = stages[-1]

    source = ps.find_source(stage)
    if source is None:
        ap.error(f"none of {', '.join(ps.SOURCE_NAMES)} found in {stage}")
    if not ps.BIB.exists():
        ap.error(f"{ps.BIB} not found")

    output = args.output or stage / OUTPUT_NAME

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        tex = work / "manuscript.tex"
        tex.write_text(prepare_source(source.read_text()))
        shutil.copy2(ps.BIB, work / ps.BIB.name)
        for rel in set(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]*)\}", tex.read_text())):
            fig = stage / rel
            if not fig.exists():
                ap.error(f"figure referenced but missing: {fig}")
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fig, work / rel)

        # A real build first, so the .aux carries the numbers LaTeX assigned.
        ps.pdflatex(tex)
        ps.bibtex(tex)
        ps.pdflatex(tex)
        bbl = tex.with_suffix(".bbl")
        if not bbl.exists():
            ap.error(f"bibtex produced no .bbl; see {tex.with_suffix('.blg')}")
        labels = labels_from_aux(tex.with_suffix(".aux"))
        cites, bibliography = bibliography_from_bbl(bbl)

        text, resolved, missing = resolve_references(tex.read_text(), labels)
        text, uncited = resolve_citations(text, cites)
        missing += uncited
        text = re.sub(r"\\bibliographystyle\{[^}]*\}\n", "", text)
        text = re.sub(r"\\bibliography\{[^}]*\}", lambda _: bibliography, text)
        text, figures = convert_figures(text, work)
        tex.write_text(text)

        subprocess.run(
            [
                "pandoc",
                tex.name,
                "-o",
                "out.docx",
                "--number-sections",
                "--toc",
                f"--resource-path={work}",
            ],
            cwd=work,
            check=True,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(work / "out.docx", output)

    print(f"wrote {output.relative_to(REPO)}")
    print(
        f"  {resolved} cross-references and {len(cites)} bibliography entries resolved, "
        f"{figures} figures converted to PNG"
    )
    if missing:
        print(f"  unresolved labels: {', '.join(sorted(set(missing)))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
