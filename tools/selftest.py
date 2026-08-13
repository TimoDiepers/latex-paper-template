#!/usr/bin/env python3
"""Run the whole paper lifecycle on a throwaway copy and check what comes out.

The two generators rewrite LaTeX with regular expressions, and the ways they can
go wrong are quiet ones: an internal note left in the package, a response letter
whose line numbers point nowhere, a stage that stops building because a package
was renamed in the preamble. None of that announces itself -- it is discovered by
an editor, or not at all.

So this drives the real thing. It copies the repository to a temporary directory,
writes the first submission, opens a revision, marks it up, submits that too, and
then reads the generated files back to confirm what did and did not survive.
Nothing is written inside your repository.

Run it after changing anything under tools/, or after reworking the preamble of
manuscript/manuscript.tex.

Usage:
    uv run tools/selftest.py
    uv run tools/selftest.py --keep    # leave the temporary copy for inspection

Needs pdflatex and bibtex, the same as a normal build.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import submit  # noqa: E402  (same directory, shared helpers)

REPO = submit.REPO

# Copying the working tree rather than exporting from git, so that what is tested
# is what is on disk right now -- including changes not yet committed.
SKIP = {".git", ".venv", "__pycache__", "submission", ".DS_Store"}

failures: list[str] = []


def check(condition: bool, description: str) -> None:
    print(f"  {'ok  ' if condition else 'FAIL'}  {description}")
    if not condition:
        failures.append(description)


def copy_repo(dst: Path) -> None:
    """A copy of the template as a new user would find it: sources, no output."""
    def ignore(directory: str, names: list[str]) -> set[str]:
        return {n for n in names if n in SKIP or n.startswith("revision_")}

    shutil.copytree(REPO, dst, ignore=ignore, dirs_exist_ok=True)


def run(script: str, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(cwd / "tools" / script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def submission_text(outdir: Path, name: str) -> str:
    """The .tex as shipped, which by then lives inside the archive."""
    with zipfile.ZipFile(outdir / "latex_source_submission.zip") as z:
        return z.read(name).decode()


def mark_up(path: Path) -> None:
    """Edit a revision the way an author would, exercising every markup form."""
    text = path.read_text()
    text = text.replace(
        "One paragraph summarising",
        r"\added{A sentence a reviewer asked for.} One paragraph summarising",
        1,
    )
    text = text.replace(
        "State the gap in the first two sentences",
        r"\replaced{State the gap up front}{State the gap in the first two sentences}",
        1,
    )
    text = text.replace(
        "Keep it to the word limit of\nthe target journal.",
        r"\deleted{Keep it to the word limit of the target journal.}",
        1,
    )
    path.write_text(text)


def test_first_submission(work: Path) -> None:
    print("\nfirst submission")
    result = run("submit.py", cwd=work)
    check(result.returncode == 0, f"submit.py exits 0{chr(10) + result.stderr if result.returncode else ''}")
    outdir = work / "manuscript" / "submission"
    check((outdir / "manuscript_clean.pdf").exists(), "manuscript_clean.pdf written")
    check(
        not (outdir / "manuscript_annotated.pdf").exists(),
        "no annotated variant, the manuscript having no tracked changes yet",
    )
    check((outdir / "graphical_abstract.pdf").exists(), "graphical abstract exported separately")
    check((outdir / "latex_source_submission.zip").exists(), "source archive written")
    check(
        sorted(p.name for p in outdir.iterdir()) == sorted(
            ["manuscript_clean.pdf", "graphical_abstract.pdf", "latex_source_submission.zip"]
        ),
        "the folder holds uploads only, no loose sources or logs",
    )

    shipped = submission_text(outdir, "manuscript_clean.tex")
    for title in submit.INTERNAL_SECTIONS:
        check(title not in shipped, f"the {title} section is gone")
    check(r"\hl{" not in shipped, "no highlighting reaches the journal")
    check(r"\tableofcontents" not in shipped, "no table of contents")
    check(r"\input{" not in shipped, "included files are spliced in, so the .tex stands alone")
    check("First Author" in shipped, "the shared author block arrived with them")
    check(r"\bibliography{" not in shipped, "the bibliography is inlined")
    check(r"\bibitem" in shipped, "and the cited entries are actually there")
    # Not "no % survives": an inline comment is cut back to a bare % on purpose, and
    # the inlined bibliography is full of them. What must not survive is the text.
    body = shipped.split("\n", 1)[1]
    source_comments = [
        " ".join(line[cut + 1 :].split())
        for line in (REPO / "manuscript" / "manuscript.tex").read_text().split("\n")
        if (cut := submit.comment_start(line)) is not None and len(line[cut + 1 :].strip()) > 20
    ]
    check(bool(source_comments), "the manuscript has comments to strip in the first place")
    check(
        not [c for c in source_comments if c in body],
        "our comments are stripped, bar the one line of provenance",
    )
    check(r"\linenumbers" in shipped, "line numbers are on, for the reviewers to cite")


def test_revision(work: Path) -> None:
    print("\nopening a revision")
    result = run("revise.py", cwd=work)
    check(result.returncode == 0, f"revise.py exits 0{chr(10) + result.stderr if result.returncode else ''}")
    stage = work / "revision_1"
    annotated = stage / "manuscript_annotated.tex"
    check(annotated.exists(), "manuscript_annotated.tex opened")
    check(r"\usepackage{changes}" in annotated.read_text(), "the changes package is loaded")
    letter = stage / "response_to_reviewers.tex"
    check(letter.exists(), "a response letter is waiting")
    check(
        "Working Title of the Paper" in letter.read_text() and "%%PAPER-METADATA%%" not in letter.read_text(),
        "with the title and authors copied out of the manuscript",
    )
    check((stage / "reviewer_comments.md").exists(), "so are the notes to fill in")
    check((stage / "figs").is_dir(), "and the figures came along")

    print("\nsubmitting the revision")
    mark_up(annotated)
    result = run("submit.py", cwd=work)
    check(result.returncode == 0, f"submit.py exits 0{chr(10) + result.stderr if result.returncode else ''}")
    outdir = stage / "submission"
    check((outdir / "manuscript_clean.pdf").exists(), "the clean manuscript is built")
    check((outdir / "manuscript_annotated.pdf").exists(), "so is the annotated one")
    check((outdir / "response_to_reviewers.pdf").exists(), "and the response letter")

    clean = submission_text(outdir, "manuscript_clean.tex")
    check("A sentence a reviewer asked for." in clean, "an addition survives into the clean text")
    check("State the gap up front" in clean, "a replacement leaves the new wording")
    check("State the gap in the first two sentences" not in clean, "and drops the old")
    check("Keep it to the word limit" not in clean, "a deletion is gone")
    check(r"\added" not in clean and r"\deleted" not in clean, "no markup is left in the clean .tex")

    letter = (outdir / "response_to_reviewers.pdf").read_bytes()
    check(b"rebuild manuscript" not in letter, "the letter has no unresolved line references")


def test_second_round(work: Path) -> None:
    """Round two starts from round one's markup, which should already be settled."""
    print("\nopening a second round")
    result = run("revise.py", cwd=work)
    check(result.returncode == 0, f"revise.py exits 0{chr(10) + result.stderr if result.returncode else ''}")
    stage = work / "revision_2"
    annotated = (stage / "manuscript_annotated.tex").read_text()
    check(
        not re.search(r"\\(added|replaced|deleted)\{", annotated),
        "the previous round's tracked changes are accepted for you",
    )
    check("A sentence a reviewer asked for." in annotated, "keeping what was added")
    check("Keep it to the word limit" not in annotated, "and dropping what was deleted")
    check(r"\linelabel{ln:gap}" in annotated, "the line anchors survive, the letter needs them")
    check((stage / "reviewer_comments.md").exists(), "this round gets its notes file too")
    check((stage / "cover_letter.md").exists(), "and its cover letter")

    result = run("revise.py", "--no-accept-previous", "--from", "revision_1", "--to",
                 "revision_9", cwd=work)
    check(result.returncode == 0, "--no-accept-previous is accepted")
    check(
        r"\added{" in (work / "revision_9" / "manuscript_annotated.tex").read_text(),
        "and leaves the markup alone when asked",
    )
    shutil.rmtree(work / "revision_9")


def test_guards(work: Path) -> None:
    """The checks exist to stop a broken package. Confirm they actually stop one."""
    print("\nguards")
    # Named explicitly rather than left to default to the newest stage, so that
    # adding a later round to this file does not quietly retarget these checks.
    name = "revision_1"
    stage = work / name
    annotated = stage / "manuscript_annotated.tex"

    kept = annotated.read_text()
    annotated.write_text(kept.replace(r"\linelabel{ln:gap}", "", 1))
    result = run("submit.py", name, cwd=work)
    check(result.returncode != 0, "a letter pointing at a missing line label stops the run")
    check("ln:gap" in result.stderr, "and the message names the label")
    check("Traceback" not in result.stderr, "reported as a sentence, not a traceback")
    annotated.write_text(kept)

    outside = work / "not-a-submission-folder"
    outside.mkdir()
    (outside / "important.txt").write_text("do not delete me\n")
    result = run("submit.py", name, "--outdir", str(outside), cwd=work)
    check(result.returncode != 0, "--outdir refuses to empty a folder that is not ours")
    check((outside / "important.txt").exists(), "and the files in it are still there")

    result = run("submit.py", name, "--no-build", cwd=work)
    check(result.returncode == 0, "--no-build writes the sources without building")
    check((stage / "submission" / "manuscript_clean.tex").exists(), "leaving the .tex in place")


def test_word_export(work: Path) -> None:
    """The Word export needs two more programs, so it is checked only when they are there."""
    print("\nword export")
    missing = [t for t in ("pandoc", "pdftoppm") if shutil.which(t) is None]
    if missing:
        print(f"  skip  not installed: {', '.join(missing)}")
        return
    result = run("to_word.py", "revision_1", cwd=work)
    check(result.returncode == 0, f"to_word.py exits 0{chr(10) + result.stderr if result.returncode else ''}")
    stage = work / "revision_1"
    manuscript = stage / "manuscript_annotated_for_review.docx"
    letter = stage / "response_to_reviewers_for_review.docx"
    check(manuscript.exists(), "the manuscript is exported")
    check(letter.exists(), "so is the response letter")
    if not letter.exists():
        return
    with zipfile.ZipFile(letter) as z:
        document = z.read("word/document.xml").decode()
        # Where pandoc files a document's title -- the body, the .docx metadata, or
        # both -- varies between its versions, so the whole archive is searched.
        everywhere = "".join(z.read(part).decode(errors="replace") for part in z.namelist())
    check("line ??" not in document, "the letter's line references resolved")
    check("Working Title of the Paper" in everywhere, "the letter carries the manuscript's title")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--keep", action="store_true", help="do not delete the temporary copy")
    args = ap.parse_args()

    submit.require(*submit.REQUIRED_TOOLS)

    tmp = Path(tempfile.mkdtemp(prefix="paper-selftest-"))
    work = tmp / "paper"
    copy_repo(work)
    print(f"testing a copy of the template in {work}")

    try:
        test_first_submission(work)
        test_revision(work)
        test_second_round(work)
        test_word_export(work)
        test_guards(work)
    finally:
        if args.keep:
            print(f"\ncopy left at {work}")
        else:
            shutil.rmtree(tmp)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:", file=sys.stderr)
        for description in failures:
            print(f"  {description}", file=sys.stderr)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(submit.run_cli(main))
