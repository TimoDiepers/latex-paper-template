# LaTeX paper template

Write a paper, submit it, revise it, resubmit it — without hand-maintaining the
pile of files each journal asks for. You write prose and mark your changes; the
tooling produces the clean manuscript, the marked-up manuscript, the response
letter with correct line references, the graphical abstract and the source
archive.

Everything here is placeholder text. Replace it and delete what you do not need.

## At a glance

```
draft/   ──►   rev0/   ──►   rev1/   ──►   rev2/   ──►  …
write it       submit        revise        resubmit
```

1. **Write** the paper in `draft/`, iterating with your coauthors.
2. **Submit**: open `rev0/`, drop the internal-only front matter, generate the
   package, upload it.
3. **Revise**: open `rev1/`, mark up the manuscript and write the response letter,
   generate the package, upload it.
4. **Resubmit**: open `rev2/`, and repeat step 3 for as many rounds as it takes.

The whole lifecycle in commands:

```
cd draft && pdflatex … manuscript.tex               # 1. write and preview
uv run scripts/new_revision.py --from draft --to rev0
uv run scripts/make_submission.py rev0              # 2. submit rev0/submission/
uv run scripts/new_revision.py --to rev1            # 3. reviews arrived
uv run scripts/make_submission.py                   #    upload rev1/submission/
uv run scripts/new_revision.py                      # 4. next round
```

## The four stages

The paper moves through numbered folders. Each one is self-contained, and the
previous one freezes the moment you move on, so you can always see exactly what
was sent and when.

| Stage | Folder | You write | You get |
|---|---|---|---|
| 1. Prepare | `draft/` | `manuscript.tex` | a PDF for coauthors and internal review |
| 2. Submit | `rev0/` | nothing new — carried over from `draft/` | `submission/`: manuscript, graphical abstract, source zip |
| 3. Revise | `rev1/` | `manuscript_annotated.tex` **and** `response_to_reviewers.tex` | `submission/`: clean + annotated manuscript, response letter, and the rest |
| 4. Resubmit | `rev2/`, … | same two files | same package, one round later |

Only the newest folder is live. `uv run scripts/make_submission.py` always builds
the package for it, and `uv run scripts/new_revision.py` always opens the next one.

---

## 1. Prepare the initial version — `draft/`

This is where the paper actually gets written, and where you will spend most of
your time. Edit `draft/manuscript.tex`, drop figures in `draft/figs/`, add
references to `references.bib` at the repository root.

```
cd draft
pdflatex -synctex=1 -interaction=nonstopmode -file-line-error manuscript.tex
bibtex manuscript
pdflatex … ; pdflatex …          # twice more, to settle refs
```

Iterate here as long as you like: send the PDF round, collect comments, rewrite.
Lines are numbered from the abstract onwards, every fifth one, so coauthors can
point at them.

`draft/` is also the only stage that carries the things you want for internal
review but never want a journal to see — the target journal, the suggested
reviewers, and a table of contents. Use `\hl{…}` to highlight anything still
open. All of it disappears from the next stage.

## 2. Submit — `rev0/`

When the manuscript is ready:

```
uv run scripts/new_revision.py --from draft --to rev0
```

Then delete the internal-only front matter from `rev0/manuscript.tex`: the
`Target Journal` and `Reviewer Suggestions` sections, and `\tableofcontents`.
`draft/` keeps its copy, frozen.

```
uv run scripts/make_submission.py rev0
```

`rev0/submission/` now holds the manuscript PDF, the graphical abstract as its own
file, and a zip of the LaTeX source with its figures — five files at most, each
one an upload. Send those.

## 3. Revise — `rev1/`

Reviews arrive. Open the next folder and set it up for tracked changes:

```
uv run scripts/new_revision.py --to rev1
```

Rename `rev1/manuscript.tex` to `rev1/manuscript_annotated.tex` and load the
`changes` package — copy the preamble block from the `rev1/manuscript_annotated.tex`
shipped with this template. From here on, a revision means editing **two files**:

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

Paste the comments into `rev1/reviewer_comments.md` first if it helps to work
through them, and draft the cover letter in `rev1/cover_letter.md`.

Preview as you go — manuscript first, then the letter, which reads the
manuscript's line numbers:

```
cd rev1
pdflatex … manuscript_annotated.tex ; bibtex manuscript_annotated ; pdflatex … ; pdflatex …
pdflatex … response_to_reviewers.tex ; bibtex response_to_reviewers ; pdflatex … ; pdflatex …
```

Then build the package:

```
uv run scripts/make_submission.py
```

`rev1/submission/` holds the clean manuscript, the marked-up manuscript for the
editor, the response letter, the graphical abstract, and the source zip. Send
those, not the previews.

## 4. Resubmit — `rev2/` and beyond

```
uv run scripts/new_revision.py
```

Accept the round you just finished in the new `manuscript_annotated.tex` — the
markup from round one has been answered, so clear it before marking up round
two — and go back to step 3. `rev1/` freezes with its own submission package.

---

## What you edit, what is generated

| | |
|---|---|
| **Yours** | the manuscript in the newest folder, `response_to_reviewers.tex`, `figs/`, `references.bib`, the two `.md` notes |
| **Generated** | everything in `rev<N>/submission/`. Wiped and rebuilt on every run — never edit it, and never keep a clean `.tex` of your own in step with the annotated one. Accepting the tracked changes happens inside the generator |

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

For VS Code's LaTeX Workshop:

```jsonc
"latex-workshop.latex.outDir": "%DIR%",
"latex-workshop.latex.tools": [
  { "name": "pdflatex", "command": "pdflatex",
    "args": ["-synctex=1", "-interaction=nonstopmode", "-file-line-error", "%DOC%"] },
  { "name": "bibtex", "command": "bibtex", "args": ["%DOCFILE%"] }
],
"latex-workshop.latex.recipes": [
  { "name": "Full build", "tools": ["pdflatex", "bibtex", "pdflatex", "pdflatex"] }
]
```

Rendered PDFs are tracked, so each stage's output is in the history beside its
source. Intermediate artifacts (`.aux`, `.log`, `.synctex.gz`, …) are gitignored.

## What the generator does

`uv run scripts/make_submission.py [rev<N>]` — newest folder by default:

- accepts every tracked change into a **clean** manuscript, and keeps an
  **annotated** one with the changes visible for the editor (only when the source
  has tracked changes, so a first submission yields the clean one alone);
- numbers the lines of both from the abstract, printing every fifth number;
- removes the highlighting, the table of contents, the draft date, and the
  `Target Journal` and `Reviewer Suggestions` sections;
- keeps the graphical abstract in the document and exports it separately for the
  upload slot journals reserve for it;
- inlines the bibliography, so the shipped `.tex` needs no `.bib`;
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
draft/                    the initial version, for internal review
  manuscript.tex            keeps target journal, reviewer suggestions, TOC
  figs/
rev0/                     first submission — none of those three
  manuscript.tex
  figs/
rev1/                     first revision
  manuscript_annotated.tex  the manuscript, with changes marked
  response_to_reviewers.tex
  reviewer_comments.md, cover_letter.md
  figs/
  submission/               GENERATED — the upload
references.bib            one bibliography, shared by every stage
scripts/                  make_submission.py, new_revision.py
```

`references.bib` is shared, cited as `../references`. An old stage's *working*
build can therefore pick up later reference edits — but everything already sent
has its bibliography inlined inside `submission/`, so the record never moves.

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
