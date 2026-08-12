# LaTeX paper template

Write a paper, submit it, and work through however many rounds of review it takes,
without hand-maintaining the pile of files each journal asks for. You write prose
and mark your changes; the tooling produces the clean manuscript, the marked-up
manuscript, the response letter with correct line references, the graphical
abstract and the source archive.

Everything here is placeholder text — replace it with your own. `revision_1/` is a
worked example of a revision round: it ships a manuscript carrying one of each kind
of tracked change and a response letter wired to them, so you can see the mechanism
before you need it. Overwrite its contents when your first reviews arrive.

## At a glance

```
manuscript/   ──►   revision_1/   ──►   revision_2/   ──►  …
write + submit      round 1            round 2
```

1. **Write and submit**: the paper lives in `manuscript/`. When it is ready,
   generate the package and upload it.
2. **Each round of review** gets its own `revision_<N>/`: mark up the manuscript,
   write the response letter, generate the package, upload it. Repeat per round.

**"Generate the package"** means running `uv run scripts/make_submission.py`. It
writes `<stage>/submission/`, holding exactly the files a journal asks for and
nothing else:

| File | What it is |
|---|---|
| `manuscript_clean.pdf` | the manuscript itself, with all tracked changes accepted |
| `manuscript_annotated.pdf` | the same text with the changes visible, for the editor — revisions only |
| `response_to_reviewers.pdf` | the response letter, its line numbers matching the manuscript in this folder — revisions only |
| `graphical_abstract.pdf` | the graphical abstract on its own, for the slot journals reserve for it |
| `latex_source_submission.zip` | the LaTeX source: `manuscript_clean.tex` and `figs/`, no PDFs |

Every stage produces one the same way — the initial submission as much as any
revision — so there is a single command to remember rather than a different
procedure per round. The folders sort chronologically in any file browser, so the
paper's history reads top to bottom.

The whole lifecycle in commands:

```
cd manuscript && pdflatex … manuscript.tex   # 1. write and preview
uv run scripts/make_submission.py            #    upload manuscript/submission/
uv run scripts/new_revision.py               # 2. reviews arrived -> revision_1/
uv run scripts/make_submission.py            #    upload revision_1/submission/
uv run scripts/new_revision.py               #    next round -> revision_2/
```

`new_revision.py` always opens the stage that follows the newest one, and
`make_submission.py` always builds the package for the newest one, so neither
needs to be told where you are.

## The stages

Each folder is self-contained, and the previous one freezes the moment you move
on, so you can always see exactly what was sent and when.

| Stage | Folder | You write | You get |
|---|---|---|---|
| Write and submit | `manuscript/` | `manuscript.tex` | previews for coauthors, then `submission/`: manuscript, graphical abstract, source zip |
| Revise, once per round | `revision_1/`, `revision_2/`, … | `manuscript_annotated.tex` **and** `response_to_reviewers.tex` | `submission/`: clean + annotated manuscript, response letter, and the rest |

Revising and resubmitting are the same step: you mark up the manuscript, answer
the reviewers, and generate that round's package. A resubmission is just the
package a `revision_<N>/` folder produces.

---

## 1. Write and submit — `manuscript/`

This is where the paper gets written, and where you will spend most of your time.
Edit `manuscript/manuscript.tex`, drop figures in `manuscript/figs/`, add
references to `references.bib` at the repository root.

```
cd manuscript
pdflatex -synctex=1 -interaction=nonstopmode -file-line-error manuscript.tex
bibtex manuscript
pdflatex … ; pdflatex …          # twice more, to settle refs
```

Iterate as long as you like: send the PDF round, collect comments, rewrite. Lines
are numbered from the abstract onwards, every fifth one, so coauthors can point at
them.

Keep whatever helps that internal circulation in the source — this template ships
a target journal, a list of suggested reviewers and a table of contents, and
`\hl{…}` highlights anything still open. **None of it can reach a journal**: the
generator strips all of it. So there is nothing to clean up before submitting.

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

`uv run scripts/make_submission.py [stage]` — newest folder by default:

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
