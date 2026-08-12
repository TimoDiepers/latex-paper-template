# LaTeX paper template

A repository structure for scientific manuscripts, covering writing, submission and
the revision rounds that follow. You keep a handful of source files. Everything a
journal receives is generated from them, and every version you sent stays as it was.

Two scripts do the work.

- **`scripts/prepare_submission.py`** builds the files you upload, for whichever stage
  the paper is at.
- **`scripts/new_revision.py`** opens the next revision with its documents already
  prepared, meaning the manuscript carried over and set up for tracked changes, and a
  response letter and notes ready to fill in.

A third script is a convenience rather than part of that path.
**`scripts/export_to_word.py`** exports the manuscript to Word, which is useful while a
draft circulates internally and colleagues would rather comment there.

The whole lifecycle looks like this.

```
# 1. write the paper in manuscript/, previewing the PDF in your editor
uv run scripts/export_to_word.py       # optional, for feedback in Word
uv run scripts/prepare_submission.py   # then upload manuscript/submission/

# 2. reviews arrive
uv run scripts/new_revision.py         # opens revision_1/, ready to edit
#    mark up the manuscript, write the response letter
uv run scripts/export_to_word.py       # optional again, manuscript and letter
uv run scripts/prepare_submission.py   # then upload revision_1/submission/

# 3. more reviews
uv run scripts/new_revision.py         # opens revision_2/, and so on
```

Neither script has to be told where you are. Both work on the newest stage.

## Stages

One folder per submission. Each holds its own manuscript, figures and letter, and
freezes when you open the next, so what you sent stays as sent.

The repository ships only sources.

```
manuscript/
  manuscript.tex            the paper, written and submitted from here
  figs/
references.bib              one bibliography, shared by every stage
scripts/
  assets/                   the letter and notes a revision starts from
```

Everything else appears as you go.

```
manuscript/submission/      the initial submission, generated
revision_1/                 first round of review, opened by new_revision.py
  manuscript_annotated.tex    the manuscript, with changes marked
  response_to_reviewers.tex
  reviewer_comments.md, cover_letter.md
  figs/
  submission/                 generated
revision_2/                 second round, and so on
```

Anything under a `submission/` folder is wiped and rebuilt on every run, so never
edit it. In particular, you never keep a clean copy of the manuscript in step with the
marked-up one. Accepting the tracked changes happens inside the generator.

## Setup

**1. VS Code**, recommended. Its settings are included here, so builds use the right
recipe, tracked changes are coloured as you type, and saving rebuilds the file you are
editing. On opening the folder, VS Code offers to install these extensions.

| Extension | | What it does |
|---|---|---|
| [LaTeX Workshop](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) | **required** | builds and previews the PDF, and jumps between source and page with SyncTeX |
| [Highlight](https://marketplace.visualstudio.com/items?itemName=fabiospampinato.vscode-highlight) | recommended | colours `\added` blue and `\deleted` struck-through grey in the editor, matching the annotated PDF |
| [LTeX](https://marketplace.visualstudio.com/items?itemName=valentjn.vscode-ltex) | optional | grammar and spell checking that parses LaTeX rather than flagging its markup |
| [ZoTeX](https://marketplace.visualstudio.com/items?itemName=raykr.zotex) or [Zotero](https://marketplace.visualstudio.com/items?itemName=mblode.zotero) | optional | inserts `\cite{…}` keys from a Zotero library |

**2. A LaTeX installation.** MacTeX on macOS, MiKTeX or TeX Live on Windows, TeX Live
on Linux. If `pdflatex` already works in your editor, you have this.

**3. A way to run the two scripts.** They use only the Python standard library, so any
Python 3.9 or newer will do, as `python3 scripts/prepare_submission.py`. For a setup
that needs no thought about which Python is which,
[uv](https://docs.astral.sh/uv/getting-started/installation/) is recommended. Its
installation guide has the one-line command for each system, it fetches a suitable
interpreter itself, and `uv.lock` pins that interpreter so the scripts behave the same
on every machine. The rest of this file writes `uv run` for brevity.

Run the scripts from a Terminal opened in this folder. In VS Code, *Terminal → New
Terminal* opens in the right place. Both scripts are safe to run again, since they only
write into a `submission/` folder or create the next stage.

## Writing and submitting

Edit `manuscript/manuscript.tex`, put figures in `manuscript/figs/`, and add references
to `references.bib`. Preview however you normally build LaTeX. Iterate as long as you
like, sending the PDF round and rewriting. Lines are numbered from the abstract onwards,
every fifth one, so coauthors can point at them.

`references.bib` is cited as `\bibliography{../references}` and shared by every stage,
so there is one bibliography for the whole paper. Point Zotero or Citavi at it as an
export target and let them keep it in sync. Only the entries you actually cite end up
in the files you send, and no `.bib` is sent at all.

Notes to yourselves can stay in the source. The template ships a target journal, a list
of suggested reviewers and a table of contents, and `\hl{…}` highlights anything still
open. Keep whatever helps while the paper circulates internally, because the generator
strips all of it and none of it can reach a journal.

When the manuscript is ready, run `prepare_submission.py`. There is no annotated
manuscript or response letter yet, so `manuscript/submission/` holds the manuscript, the
graphical abstract and the source zip. Send those. Once you open the first revision,
`manuscript/` freezes with that package beside it as the record of what was submitted.

## Revising

Run `new_revision.py`. The new folder arrives ready to work in, with the manuscript
renamed to `manuscript_annotated.tex` and the `changes` package loaded into its
preamble, and a response letter and two note files placed beside it. From here on a
round means editing two files.

`manuscript_annotated.tex`, the manuscript, with every change marked.

```latex
\replaced{the new wording}{the old wording}
\added{a sentence a reviewer asked for}
\deleted{a sentence a reviewer found redundant}
\linelabel{ln:gap}      % an anchor the response letter can point at
```

`response_to_reviewers.tex`, the letter, with the conventions ready to use.

```latex
\comm{1.1}{The comment, quoted verbatim.}          % italics
\begin{response} Your answer. \end{response}
\begin{revisedtext} The revised text. \end{revisedtext}   % blue
\lnp{ln:gap}                                       % -> (line 42), live
\todoitem{Not addressed yet.}                      % internal marker
```

Work through the comments in `reviewer_comments.md` if that helps, and draft the cover
letter in `cover_letter.md`. Neither is submitted.

One ordering matters while previewing. The letter takes its line numbers from the
manuscript's `.aux`, so save the manuscript and let it build before rebuilding the
letter, or the letter still shows the previous numbers. A reference that cannot be
resolved prints in red rather than as a silent `??`.

Then run `prepare_submission.py`. Send the five files in `revision_1/submission/` and
not your local previews, which carry different line numbers because the generated
manuscript drops the internal front matter and every line shifts. The package is always
consistent with itself, since the generator builds the manuscript and the letter
together, in that order.

For the next round, run `new_revision.py` again. Clear the markup you have just
answered in the new `manuscript_annotated.tex` before marking up the new round.

## Word export for internal review

Some people would rather write their comments in Word. This exports the current stage
for them.

```
uv run scripts/export_to_word.py                          # the newest stage
uv run scripts/export_to_word.py revision_1               # a specific stage
uv run scripts/export_to_word.py revision_1/response_to_reviewers.tex
```

At the manuscript stage that is the manuscript alone. In a revision it is the annotated
manuscript and the response letter, since whoever reads the round wants both. Name a
single `.tex` file to convert only that one. The results are written beside the sources
as `<name>_for_review.docx` and are gitignored, being a convenience rather than a
version of the paper. Feedback comes back as Word comments or edits that you carry into
the `.tex` by hand.

The export reads like the PDF. It runs a real LaTeX build first and takes the numbers
from it, so citations appear as the same superscript numbers, `\citet` prints the same
author label, several citations at once compress to the same range such as 1–3, and the
reference list at the end is numbered in the same order. References to a figure or an
equation carry the number LaTeX gave them, and captions are numbered to match, since
pandoc writes neither. Figures are embedded as PNG, because Word
cannot display the PDF figures the manuscript uses. The internal front matter is kept,
since this is not a document a journal sees.

The letter keeps its structure without its colours, which do not survive the trip. Each
comment becomes a heading followed by the comment in italics, your answer stays plain,
and quoted manuscript text becomes an indented block. Its line references show the
numbers from the line-numbered PDF, because a Word file has no line numbers of its own.

Two things do not carry over. Equations become Word equations and lose their own
numbering, though references to them in the text stay correct. Tracked changes are
accepted rather than shown, so the Word manuscript reads as the revised text. The export
needs `pandoc` and `pdftoppm` from poppler, on top of the LaTeX installation.

## What the generator does

`uv run scripts/prepare_submission.py [stage]` works on the newest stage by default. It

- accepts every tracked change into a clean manuscript, and keeps an annotated one with
  the changes visible for the editor, the latter only when the source has tracked
  changes;
- numbers the lines of both from the abstract, printing every fifth number;
- removes the highlighting, the table of contents, the draft date, and the
  `Target Journal` and `Reviewer Suggestions` sections;
- keeps the graphical abstract in the document and exports it separately for the upload
  slot journals reserve for it;
- inlines the cited references as a `thebibliography` block, so the shipped `.tex` needs
  no `.bib` beside it;
- rebuilds the response letter in place, so its line references match the shipped
  manuscript;
- strips your comments, leaving one line saying where the file came from;
- archives the source and figures into `latex_source_submission.zip`, then removes the
  loose files, leaving a folder where every file is one upload;
- warns if placeholder text such as `XX`, `HARDWARE`, `TO BE DONE` or `\todoitem`
  survived, naming file and line, and builds anyway.

Two flags are available. `--no-build` stops after writing the `.tex` files, and
`--outdir` writes elsewhere.

## Builds

The recipe is pdflatex, bibtex, pdflatex, pdflatex, with output beside the source.

```
pdflatex -synctex=1 -interaction=nonstopmode -file-line-error <file>.tex
bibtex <file>
pdflatex … ; pdflatex …
```

Run it from inside the stage folder, since `bibtex` resolves `../references` relative to
the working directory and building from the repository root fails. VS Code has this
configured in `.vscode/settings.json`, and the generator uses the same flags, so a
previewed PDF and a submitted PDF come out identical. Other editors need the four steps
set up by hand.

The `-synctex=1` flag is what lets you jump between source and page. In VS Code press
ctrl/cmd+alt+j in the editor to find the spot in the PDF, and ctrl/cmd+click in the PDF
to jump back to the line that produced it.

Rendered PDFs are tracked, so each stage's output sits in the history beside its source.
Intermediate files such as `.aux`, `.log` and `.synctex.gz` are gitignored.
