# LaTeX paper template

Write your paper once. This repository turns it into the files a journal asks for, and
keeps every version you sent exactly as you sent it.

You edit one manuscript. When you are ready to submit, one command produces the upload
package: the PDF, the graphical abstract, and a zip of the sources, with the internal
notes stripped out and the bibliography folded in. When the reviews come back, another
command opens a revision folder with the response letter ready to fill in — and the
previous round's package stays frozen beside it as the record of what you sent.

You do not need to be comfortable with the command line. There are two commands, and
they are the same every time.

## Getting started

**1. Make your own copy.** Click **Use this template** at the top of
[this repository](https://github.com/TimoDiepers/latex-paper-template), give it a name,
then download it or clone it to your computer.

**2. Install three things.** These are our recommendations - other options exist.

| | What it is | Where |
|---|---|---|
| **A LaTeX distribution** | the program that turns `.tex` files into PDFs | [MacTeX](https://www.tug.org/mactex/) (macOS) · [MiKTeX](https://miktex.org/download) (Windows) · [TeX Live](https://www.tug.org/texlive/) (Linux) |
| **VS Code** | the editor. Its settings are already in this repository, so builds just work | [code.visualstudio.com](https://code.visualstudio.com/) |
| **uv** | python package manager; runs the two commands below. | [installation guide](https://docs.astral.sh/uv/getting-started/installation/) |

<details>
<summary>Installing LaTeX with a package manager instead</summary>

```
# macOS
brew install --cask mactex

# Debian / Ubuntu
sudo apt install texlive-latex-recommended texlive-latex-extra texlive-science
```

</details>

<br>

**3. Open the folder in VS Code.** It will offer to install the extensions this template
uses; click **Install**. That gives you PDF preview, coloured tracked changes, and
spell checking.

**4. Write.** Your paper is `manuscript/manuscript.tex` — put your title, authors and
affiliations at the top, where the placeholders are. Figures go in `manuscript/figs/`,
references in `references.bib`. Save, and the PDF updates.

## The two commands

Open a terminal inside the project folder (in VS Code: *Terminal → New Terminal*, which
opens in the right place), and run:

```
uv run scripts/prepare_submission.py
```

That builds your submission into `manuscript/submission/`. Upload the three files in
there and you are done. Nothing else in the folder needs to be touched.

When the reviews arrive:

```
uv run scripts/new_revision.py
```

That opens `revision_1/`, with the manuscript ready to mark up and a response letter
ready to write. When you have answered the comments, run `prepare_submission.py` again
and upload what appears in `revision_1/submission/`.

For the next round, `new_revision.py` again. Neither command needs to be told where you
are; both work on the newest round. Both are safe to run as often as you like.

That is the whole workflow. The rest of this file is detail you can come back to.

<details>
<summary>Running the commands without uv</summary>

uv is only a convenience: it fetches a suitable Python itself, and `uv.lock` pins it so
the scripts behave the same on every machine. They use nothing but Python's standard
library, so any Python 3.9 or newer runs them directly:

```
python3 scripts/prepare_submission.py      # macOS, Linux
py scripts\prepare_submission.py           # Windows, after installing python.org
```

</details>

## Stages

One folder per submission. Each holds its own manuscript, figures and letter, and
freezes when you open the next, so what you sent stays as sent. The repository ships
only sources; everything else appears as you go.

```
references.bib              one bibliography, shared by every stage
manuscript/
  manuscript.tex            the paper, written and submitted from here
  figs/
  submission/                 generated
revision_1/                 opened by new_revision.py
  manuscript_annotated.tex    the manuscript, with changes marked
  response_to_reviewers.tex
  reviewer_comments.md, cover_letter.md
  figs/
  submission/                 generated
revision_2/                 second round, and so on
scripts/assets/             the letter and notes a revision starts from
```

Anything under `submission/` is wiped and rebuilt on every run, so never edit it.

## Writing and submitting

Edit `manuscript/manuscript.tex`, put figures in `manuscript/figs/`, add references to
`references.bib`. Lines are numbered from the abstract on, every fifth one, so coauthors
can point at them.

A long paper need not be one file: `\input{sections/results.tex}` works, and the
generator splices those files into the manuscript it ships.

`references.bib` is shared by every stage. Point Zotero or Citavi at it as an export
target. Only the entries you cite are sent, and no `.bib` is sent at all.

Notes to yourselves can stay in the source, but what happens to each kind differs:

- **Comments, the table of contents and the draft date are removed.** They cannot reach
  a journal.
- **The `Target Journal` and `Reviewer Suggestions` sections are removed whole**, by
  title, case-insensitively. Rename them and they stay in.
- **`\hl{…}` loses only its colour.** The words are kept, because highlighting usually
  marks real text you are unsure of. Every surviving highlight is listed as a warning
  when you build — read that list.

Run `prepare_submission.py` when ready. The first time there is no annotated manuscript
or letter yet, so you get the manuscript, the graphical abstract and the source zip.
Once you open the first revision, `manuscript/` freezes with that package beside it.

## Revising

Run `new_revision.py`. The folder arrives with the manuscript renamed to
`manuscript_annotated.tex`, the `changes` package in its preamble, and a letter and two
note files beside it. The letter's title and author block are copied out of the
manuscript as it is written, so you never type them twice; if they change later, correct
them in the letter directly. From the second round on it also accepts the previous round's
tracked changes, so you start from settled text and mark up only what is new
(`--no-accept-previous` keeps them). `\linelabel` anchors are never touched — the letter
points at them.

A round means editing two files.

```latex
% manuscript_annotated.tex
\replaced{the new wording}{the old wording}
\added{a sentence a reviewer asked for}
\deleted{a sentence a reviewer found redundant}
\linelabel{ln:gap}      % an anchor the response letter can point at
```

```latex
% response_to_reviewers.tex
\comm{1.1}{The comment, quoted verbatim.}          % italics
\begin{response} Your answer. \end{response}
\begin{revisedtext} The revised text. \end{revisedtext}   % blue
\lnp{ln:gap}                                       % -> (line 42), live
\todoitem{Not addressed yet.}                      % internal marker
```

Work through `reviewer_comments.md` and draft `cover_letter.md` if they help; neither is
submitted.

One ordering matters while previewing: the letter takes its line numbers from the
manuscript's `.aux`, so build the manuscript first, or the letter shows the previous
numbers.

Then run `prepare_submission.py` and send the five files in `revision_1/submission/` —
not your local previews, whose line numbers differ because the generated manuscript
drops the internal front matter and every line shifts. The generated package is always
consistent with itself.

## What the generator checks

Before it calls a package finished, `prepare_submission.py` checks it over.

**These stop the run:** a missing `pdflatex`, a LaTeX error, an undefined citation, a
figure that is not where the manuscript says, or a `\lnp{…}` pointing at a `\linelabel`
that does not exist.

**These warn, and build anyway:** placeholder text (`XX`, `TO BE DONE`, `\todoitem`) and
surviving `\hl{…}` notes, reported with file and line — a package is often assembled
before the last numbers land.

`--no-build` writes the `.tex` files and stops, which is useful for handing sources to a
coauthor.

## Word export

For colleagues who would rather comment in Word. This is the one part that needs two
extra programs, [pandoc](https://pandoc.org/installing.html) and
[poppler](https://poppler.freedesktop.org/) — skip installing them until someone
actually asks for a `.docx`.

<details>
<summary>Installing pandoc and poppler with a package manager</summary>

```
brew install pandoc poppler          # macOS
sudo apt install pandoc poppler-utils
scoop install pandoc poppler         # Windows, or run the export under WSL
```

</details>

<br>

Exporting word files:
```
uv run scripts/export_to_word.py                          # the newest stage
uv run scripts/export_to_word.py revision_1               # a specific stage
uv run scripts/export_to_word.py revision_1/response_to_reviewers.tex
```



At the manuscript stage that is the manuscript; in a revision, the annotated manuscript
and the letter. Results are written beside the sources as `<name>_for_review.docx` and
are gitignored. Feedback comes back as Word comments that you carry into the `.tex` by
hand.

The `.docx` reads like the PDF: the same citation numbers, the same reference list, the
same figure and equation numbers. Three things do not survive. Equations lose their own
numbering, though references to them stay correct. Tracked changes are accepted rather
than shown. And unusual citation commands such as `\citeauthor` are named on the console
as unhandled — check how those came out.

## Coauthors who do not use this repository

Most will not clone a git repository, and that is fine.

- **Word:** export the stage, send the `.docx`, carry their comments back yourself.
- **A zip of the sources**, for a coauthor on Overleaf: `prepare_submission.py
  --no-build` writes the generated `.tex` and figures into `submission/` without
  building or archiving them, with the bibliography already inlined. That folder uploads
  to Overleaf as-is. Their edits come back by hand — nothing syncs.

In VS Code you can jump between the source and the PDF: ctrl/cmd+alt+j in the editor,
ctrl/cmd+click in the PDF.

<details>
<summary>Using an editor other than VS Code</summary>

The build recipe is pdflatex, bibtex, pdflatex, pdflatex, with the output beside the
source, run from **inside the stage folder** — `bibtex` resolves `../references`
relative to the working directory, so building from the repository root fails.

```
pdflatex -synctex=1 -interaction=nonstopmode -file-line-error <file>.tex
bibtex <file>
pdflatex … ; pdflatex …
```

The generator uses the same flags, so a previewed PDF and a submitted PDF come out
identical. VS Code has this configured already in `.vscode/settings.json`.

</details>

<details>
<summary>Changing the scripts</summary>

`uv run scripts/selftest.py` copies the template to a temporary directory, runs the
whole lifecycle through it, and reads the generated files back to confirm what did and
did not survive. Nothing is written inside your repository. Run it after changing
anything under `scripts/` or the manuscript preamble; it also runs on every push.

</details>

## Troubleshooting

| Symptom | Cause |
|---|---|
| `not found on PATH: pdflatex` | LaTeX is not installed, or the terminal has not picked it up. If your editor builds fine, open a new terminal. |
| the build fails from the repository root | run it from inside the stage folder — `bibtex` resolves `../references` relative to the working directory |
| the letter shows last time's line numbers | build the manuscript first; the letter reads its `.aux` and is always one build behind |
| `points at line labels the manuscript does not define` | a `\lnp{ln:x}` with no matching `\linelabel{ln:x}`. Add the anchor, or drop the reference. |
| `[line ?? -- rebuild …]` in a preview | the same thing, seen in the PDF. No package can ship with one. |
| a figure is missing | `\includegraphics` paths are relative to the stage folder, so figures live in `<stage>/figs/` |
| ``File `something.sty' not found`` | a missing LaTeX package: `sudo tlmgr install something`, or MiKTeX offers to fetch it |

## Licence

MIT. See [LICENSE](LICENSE).
