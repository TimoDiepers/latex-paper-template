# LaTeX paper template

One command turns the manuscript you write into the exact set of files a journal
asks for, and keeps every submitted version intact.

## What it does

**While you write**, it stays out of the way. A normal manuscript: `manuscript.tex`,
`figs/` beside it, one `references.bib` shared by the whole paper. No markup, nothing
special to learn. One command turns that into the initial submission — the manuscript
PDF, the graphical abstract on its own, and a source archive with the cited
references inlined in the `.tex` source file.

**When the reviews come back, it earns its place.** You mark the changes in the
manuscript itself with `\added{…}`, `\replaced{…}{…}` and `\deleted{…}`, and write
`response_to_reviewers.tex` pointing at them by label. The same command then hands
you everything that round needs:

- `manuscript_clean.pdf` — the manuscript, changes accepted
- `manuscript_annotated.pdf` — the same text, changes visible for the editor
- `response_to_reviewers.pdf` — the letter, its line numbers matching those PDFs
- `graphical_abstract.pdf` and `latex_source_submission.zip` — as before

You never keep a clean copy of the text in step with the marked-up one, and the
letter's `(line 42)` always points at the manuscript in the same package rather than
a stale local build. Two more things happen on the way out: internal notes — target
journal, suggested reviewers, table of contents, your `%` comments — are stripped
from everything that ships, and only the references you actually cite are inlined, so
`references.bib` can stay a Zotero or Citavi export without ever being sent.

## Stages

One folder per submission — `manuscript/`, then `revision_1/`, `revision_2/`, … Each
holds its own manuscript, figures and letter, and freezes when you open the next, so
what you sent stays exactly as sent. 

| Stage | You write | You upload |
|---|---|---|
| `manuscript/` | `manuscript.tex` | manuscript, graphical abstract, source zip |
| `revision_1/`, `revision_2/`, … | `manuscript_annotated.tex` **and** `response_to_reviewers.tex` | the same, plus the annotated manuscript and the response letter |

Revising and resubmitting are one step: mark up the manuscript, answer the
reviewers, generate that round's package. `revision_1/` ships filled in as a worked
example — one of each kind of tracked change, wired to the letter — so overwrite it
when your first reviews arrive.

The whole lifecycle:

```
# 1. write in manuscript/, previewing the PDF in your editor
uv run scripts/make_submission.py     # then upload manuscript/submission/

# 2. reviews arrive
uv run scripts/new_revision.py        # opens revision_1/
#    mark up the manuscript, write the letter
uv run scripts/make_submission.py     # then upload revision_1/submission/

# 3. more reviews
uv run scripts/new_revision.py        # opens revision_2/, and so on
```

`new_revision.py` always opens the stage that follows the newest one, and
`make_submission.py` always builds the package for the newest one, so neither
needs to be told where you are.

## Setup, once

**1. VS Code**, recommended — this template ships its settings, so builds work out
of the box and tracked changes are coloured in the editor as you type. Open the
folder and VS Code offers to install these; accepting is enough.

| Extension | | What it does for you |
|---|---|---|
| [LaTeX Workshop](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) | **required** | builds and previews the PDF, and jumps between source and page. Without it you have no build button |
| [Highlight](https://marketplace.visualstudio.com/items?itemName=fabiospampinato.vscode-highlight) | recommended | paints `\added` blue and `\deleted` struck-through grey *in the editor*, matching the annotated PDF. Rules ship in `.vscode/settings.json` |
| [LTeX](https://marketplace.visualstudio.com/items?itemName=valentjn.vscode-ltex) | optional | grammar and spell checking that understands LaTeX instead of tripping over it |
| [ZoTeX](https://marketplace.visualstudio.com/items?itemName=raykr.zotex) or [Zotero](https://marketplace.visualstudio.com/items?itemName=mblode.zotero) | optional | insert `\cite{…}` keys straight from your library |

The build recipe is already configured in `.vscode/settings.json`, and it is the
same one the submission generator uses, so the PDF you preview and the PDF you
submit are built identically. Any other editor works too — you just set the recipe
up yourself (see [Builds](#builds)).

**2. A LaTeX installation.** MacTeX on macOS, MiKTeX or TeX Live on Windows, TeX
Live on Linux. If `pdflatex` already works in your editor, you have this.

**3. uv**, which is what runs the two helper scripts. Follow the one-line install
for your system in the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)
(macOS and Linux use a `curl` command, Windows a PowerShell one, and it is also in
Homebrew, winget and pip).

It keeps to itself, and fetches the Python version it needs the first time you run a
script. You will not have to think about it again.

That is all — nothing to configure, no packages to install.

## The two commands

Type these in a Terminal **opened in this folder**:

- In VS Code, *Terminal → New Terminal* opens in the right place already — the
  simplest route on any system.
- On macOS from Finder: right-click the folder → *Services → New Terminal at Folder*.
- On Windows from Explorer: right-click inside the folder → *Open in Terminal*.

Then copy and paste:

```
uv run scripts/make_submission.py     # build the files to upload
uv run scripts/new_revision.py        # start the next round of review
```

Both work out where you are in the paper on their own, and both are safe to run
again — they only ever write into a `submission/` folder or create the next stage.

Writing and previewing the PDF needs no Terminal at all if your editor builds
LaTeX for you — see [Builds](#builds).

---

## 1. Write and submit — `manuscript/`

This is where the paper gets written, and where you will spend most of your time.
Edit `manuscript/manuscript.tex`, drop figures in `manuscript/figs/`, add
references to `references.bib` at the repository root.

Preview it however you normally build LaTeX — in VS Code, the build button on
`manuscript/manuscript.tex` is enough, as long as your recipe is set up as under
[Builds](#builds). Iterate as long as you like: send the PDF round, collect
comments, rewrite. Lines are numbered from the abstract onwards, every fifth one, so
coauthors can point at them.

**References.** `references.bib` at the top of the folder is shared by every stage,
cited as `\bibliography{../references}`, so there is one bibliography for the whole
paper rather than a copy per stage. Point Zotero or Citavi at it as an export target
and let them keep it in sync; you never edit it by hand. When you build the
submission package, only the entries you actually cite are copied into the shipped
`.tex` — the rest of your library stays behind, and no `.bib` file is sent at all.

**Notes to yourselves stay in the source.** This template ships a target journal, a
list of suggested reviewers and a table of contents, and `\hl{…}` highlights
anything still open. Keep whatever helps while the paper circulates internally:
**none of it can reach a journal**, because the generator strips all of it. There is
nothing to clean up before submitting.

When the manuscript is ready:

```
uv run scripts/make_submission.py
```

`manuscript/submission/` now holds the package: the manuscript, the graphical
abstract and the source zip. There is no annotated variant or response letter yet,
since there are no tracked changes and no reviewers to answer. Send what is there.

Once you open the first revision, `manuscript/` freezes with that package beside
it, a record of exactly what was submitted.

## 2. Each round of review — `revision_<N>/`

Reviews arrive. Open the next folder and set it up for tracked changes:

```
uv run scripts/new_revision.py
```

Rename `manuscript.tex` to `manuscript_annotated.tex` and load the `changes`
package — copy the preamble block from this template's `revision_1/`, along with
its `response_to_reviewers.tex`, since the manuscript stage has no letter to carry
forward. From here on, a round means editing **two files**:

**`manuscript_annotated.tex`** — the manuscript, with every change marked:

```latex
\replaced{the new wording}{the old wording}
\added{a sentence a reviewer asked for}
\deleted{a sentence a reviewer found redundant}
\linelabel{ln:gap}      % an anchor the response letter can point at
```

**`response_to_reviewers.tex`** — the letter, with the conventions ready to use:

```latex
\comm{1.1}{The comment, quoted verbatim.}          % italics
\begin{response} Your answer. \end{response}
\begin{revisedtext} The revised text. \end{revisedtext}   % blue
\lnp{ln:gap}                                       % -> (line 42), live
\todoitem{Not addressed yet.}                      % internal marker
```

Paste the comments into `reviewer_comments.md` first if it helps to work through
them, and draft the cover letter in `cover_letter.md`.

Preview as you go — manuscript first, then the letter, which reads the
manuscript's line numbers:

```
cd revision_1
pdflatex … manuscript_annotated.tex ; bibtex manuscript_annotated ; pdflatex … ; pdflatex …
pdflatex … response_to_reviewers.tex ; bibtex response_to_reviewers ; pdflatex … ; pdflatex …
```

Then build the package:

```
uv run scripts/make_submission.py
```

`revision_1/submission/` now holds the full package — all five files this time,
the annotated manuscript and the response letter included. Send those, not the
previews.

## Later rounds

```
uv run scripts/new_revision.py
```

This opens `revision_2/`. Accept the round you just finished in its
`manuscript_annotated.tex` — the markup from round one has been answered, so clear
it before marking up round two — then work through step 2 again. `revision_1/`
freezes with its own submission package.

---

## What you edit, what is generated

| | |
|---|---|
| **Yours** | the manuscript in the newest folder, `response_to_reviewers.tex`, `figs/`, `references.bib`, the two `.md` notes |
| **Generated** | everything in `<stage>/submission/`. Wiped and rebuilt on every run — never edit it, and never keep a clean `.tex` of your own in step with the annotated one. Accepting the tracked changes happens inside the generator |

## Why the previews are not what you send

Building in the revision folder gives you working drafts. The generated manuscript
differs from them slightly — the internal front matter is gone, comments are
stripped — which shifts every line. So the letter you build locally cites
different line numbers than the one in `submission/`, which is rebuilt against the
manuscript that actually ships. Always send the `submission/` copies.

A missing or stale reference prints in red as
`[line ?? -- rebuild manuscript_annotated.tex]` rather than a silent `??`, so a
broken pointer cannot slip past you.

## Builds

The recipe is **pdflatex, bibtex, pdflatex, pdflatex**, output beside the source:

```
pdflatex -synctex=1 -interaction=nonstopmode -file-line-error <file>.tex
bibtex <file>
pdflatex … ; pdflatex …
```

Run it **from inside the folder** — `bibtex` resolves `../references` relative to
the working directory, so building from the repository root fails.

In VS Code this is already set up: `.vscode/settings.json` defines the recipe, so
the build button does the right thing. Other editors need the four steps configured
by hand.

Rendered PDFs are tracked, so each stage's output is in the history beside its
source. Intermediate artifacts (`.aux`, `.log`, `.synctex.gz`, …) are gitignored.

## What the generator does

`uv run scripts/make_submission.py [stage]` — newest folder by default:

- accepts every tracked change into a **clean** manuscript, and keeps an
  **annotated** one with the changes visible for the editor (only when the source
  has tracked changes, so a first submission yields the clean one alone);
- numbers the lines of both from the abstract, printing every fifth number;
- removes the highlighting, the table of contents, the draft date, and the
  `Target Journal` and `Reviewer Suggestions` sections;
- keeps the graphical abstract in the document and exports it separately for the
  upload slot journals reserve for it;
- runs `bibtex` and splices the result into the shipped `.tex` as a
  `thebibliography` block, so it carries **only the entries actually cited** and
  needs no `.bib` alongside it — your whole library stays behind;
- rebuilds the response letter in place, so its line references match the shipped
  manuscript;
- strips your comments, leaving one line of provenance — notes to yourself never
  reach the journal;
- archives the source and figures into `latex_source_submission.zip`, then removes
  the loose files, leaving a directory where every file is one upload;
- warns if placeholder text (`XX`, `HARDWARE`, `TO BE DONE`, `\todoitem`) survived,
  naming file and line, and builds anyway.

Flags: `--no-build` stops after writing the `.tex` files, `--outdir` writes
elsewhere.

## Layout

```
manuscript/                 the paper: written here, submitted from here
  manuscript.tex              may keep target journal, reviewer suggestions, TOC —
                              the generator strips them
  figs/
  submission/                 GENERATED — the upload
revision_1/                 first round of review
  manuscript_annotated.tex    the manuscript, with changes marked
  response_to_reviewers.tex
  reviewer_comments.md, cover_letter.md
  figs/
  submission/                 GENERATED — the upload
revision_2/                 second round, and so on
references.bib              one bibliography, shared by every stage
scripts/                    make_submission.py, new_revision.py
```

`references.bib` is shared, cited as `../references`, and can be regenerated from
a reference manager at will. An old stage's *working* build therefore picks up
later reference edits — but everything already sent has its cited entries inlined
inside `submission/`, so the record of what was submitted never moves.

The manuscript is called `manuscript_annotated.tex` from the first revision
onwards, because that is what it is. Before that it is just `manuscript.tex`.

## Tooling

Both scripts are standard library only; `uv.lock` pins an interpreter and nothing
else.

```
uv run scripts/make_submission.py           # build the package for the newest stage
uv run scripts/new_revision.py --dry-run    # see what the next stage would get
uv run scripts/new_revision.py              # open it
```

`python3 scripts/…` works equally well. `pdflatex` and `bibtex` must be on `PATH`.
