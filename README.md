# LaTeX paper template

A structure for taking a manuscript from internal draft through submission and
however many rounds of revision, with the journal-facing files generated rather
than maintained by hand.

Everything here is placeholder text. Replace it and delete what you do not need.

## Workflow

There is exactly **one file you edit** per revision, and everything a journal
receives is generated from it:

| | |
|---|---|
| **You edit** | `rev<N>/manuscript_annotated.tex` — the marked-up manuscript, plus `response_to_reviewers.tex` and the figures beside it |
| **Generated** | everything in `rev<N>/submission/`, including the clean manuscript. Regenerated from scratch on every run, so nothing there is worth editing |

A round of revision goes:

1. **Edit** `rev<N>/manuscript_annotated.tex`. Mark every change with `\added`,
   `\replaced` or `\deleted`, and drop a `\linelabel{ln:…}` wherever the response
   letter needs to point.
2. **Preview** in the revision folder: build `manuscript_annotated.tex`, then
   `response_to_reviewers.tex` (it reads the manuscript's line numbers, so the
   manuscript goes first). These are drafts for your own eyes.
3. **Generate the package**: `uv run scripts/make_submission.py`. This writes
   `rev<N>/submission/` with the clean and annotated manuscripts, the response
   letter rebuilt against the shipped manuscript, the graphical abstract, and a
   source archive.
4. **Upload** the files in `rev<N>/submission/` — those, not the previews.
5. **Next round**: `uv run scripts/new_revision.py` copies the sources into
   `rev<N+1>/`, leaving this revision frozen. Accept the round you just finished
   in the new `manuscript_annotated.tex`, then start again at step 1.

There is no clean `.tex` to keep in step with the annotated one: accepting the
tracked changes happens inside the generator, and the result only exists in
`submission/`.

## Starting a new paper

Write in `draft/` until the manuscript is ready to submit. Then

```
uv run scripts/new_revision.py --from draft --to rev0
```

and strip the internal-only front matter from `rev0/manuscript.tex` — the target
journal, the reviewer suggestions and the table of contents belong to internal
review, not to a journal. When the reviews arrive,
`uv run scripts/new_revision.py --to rev1`, rename the manuscript to
`manuscript_annotated.tex`, and add the `changes` package block from
`rev1/manuscript_annotated.tex` in this template.

The `rev0/` and `rev1/` folders shipped here are worked examples of those two
stages. Delete them once your own paper has replaced them.

## Layout

Each `rev<N>/` folder holds one revision's working set: the manuscript, the
figures and the response letter. `references.bib` is shared by all revisions and
lives at the repository root, cited as `../references` from a revision folder.

The newest `rev<N>/` is the one being worked on. Older ones are frozen. Because
the bibliography is shared, an old revision's *working* build can pick up later
reference edits — but every **submitted** artifact has its bibliography inlined
(everything under `rev<N>/submission/`), so the record of what was actually sent
never moves.

```
draft/                    pre-submission internal draft
  manuscript.tex            the only version that carries the target journal, the
                            reviewer suggestions and the table of contents
  figs/
rev0/                     first submission — none of those three
  manuscript.tex
  figs/
rev1/                     first revision
  manuscript_annotated.tex  THE source you edit
  figs/                     figures used by this revision, plus their editable sources
  response_to_reviewers.tex
  reviewer_comments.md, cover_letter.md
  submission/               GENERATED — the journal-ready upload
references.bib            the shared bibliography
scripts/                  tooling shared across revisions
pyproject.toml, uv.lock, .python-version
```

The manuscript is named `manuscript_annotated.tex` from the first revision
onwards, because that is what it is — the marked-up source. An original
submission has no tracked changes and just uses `manuscript.tex`.

## Builds

The build recipe is **pdflatex, bibtex, pdflatex, pdflatex**, with output beside
the source:

```
pdflatex -synctex=1 -interaction=nonstopmode -file-line-error <file>.tex
bibtex <file>
pdflatex … ; pdflatex …
```

Run these from inside the revision folder — `bibtex` resolves `../references`
relative to the working directory, so building from the repository root fails.
The manuscript goes first, because the response letter pulls its line numbers
via `xr`.

To get the same recipe out of VS Code's LaTeX Workshop, put this in your
settings:

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

The working builds are previews. **Their line numbers are not the ones the editor
sees**, because the generated manuscript differs slightly, so the letter built
here cites different numbers than the one in `submission/`. Send the
`submission/` copies.

The rendered PDFs are tracked, so every revision's rendered state is in the
history next to its sources. Intermediate artifacts (`.aux`, `.log`,
`.synctex.gz`, …) are gitignored — they are regenerable and produce
multi-thousand-line diffs.

## Tooling

The two scripts are standard library only, so `uv.lock` pins an interpreter and
nothing else. From the repository root:

```
uv run scripts/make_submission.py           # build the submission package
uv run scripts/new_revision.py --dry-run    # start the next revision
```

`uv sync` if you want the environment up front. Plain `python3 scripts/…` works
equally well; `pdflatex` and `bibtex` must be on `PATH`.

## Submission package

```
uv run scripts/make_submission.py          # newest rev<N>
uv run scripts/make_submission.py rev1     # a specific revision
```

It derives the journal-ready files from that revision's manuscript, so the two
never drift apart. It:

- writes a **clean** variant with every tracked change accepted, and an
  **annotated** variant that keeps the changes visible for the editor — the
  latter only when the source actually has tracked changes, so an original
  submission yields the clean manuscript alone;
- numbers the lines of both variants from the abstract onwards, printing every
  fifth number, since reviewers cite line numbers in both;
- removes the highlighting, the table of contents, the draft date, and the
  internal-only "Target Journal" and "Reviewer Suggestions" sections;
- keeps the graphical abstract in the document and also exports it on its own,
  for the separate upload slot;
- inlines the bibliography as a `thebibliography` environment, so the shipped
  `.tex` needs nothing from the shared `references.bib`;
- copies the referenced figures and builds each variant, then builds the response
  letter *in place*, so its `xr` line references match the annotated manuscript
  that ships rather than the working preview;
- strips the source's comments, so notes to yourself never travel to the journal,
  leaving one line of provenance at the top;
- archives the clean source and the figures into `latex_source_submission.zip`,
  then removes the loose `.tex` files and `figs/` again, so every remaining file
  in the directory is one upload;
- warns about leftover placeholder text (`XX`, `HARDWARE`, `TO BE DONE`,
  `\todoitem`) naming the file and line, and builds anyway.

`rev<N>/submission/` then holds everything a journal asks for and nothing else:

| | |
|---|---|
| `manuscript_clean.pdf` | the manuscript to upload |
| `manuscript_annotated.pdf` | the marked-up version for the editor |
| `response_to_reviewers.pdf` | rebuilt here, citing the shipped manuscript's line numbers |
| `graphical_abstract.pdf` | the graphical abstract on its own |
| `latex_source_submission.zip` | the LaTeX source — `manuscript_clean.tex` and `figs/`, no PDFs |

Flags: `--no-build` writes the `.tex` files and stops, leaving them in place for
inspection; `--outdir` places the directory elsewhere.

## Response letter

`rev<N>/response_to_reviewers.tex` carries the conventions ready to use:

- `\comm{1.1}{…}` for the quoted comment, in italics;
- `response` and `revisedtext` environments for the answer and the quoted
  manuscript text, the latter in blue;
- `\lnp{ln:label}` for a live line reference into the annotated manuscript,
  which turns red if the reference cannot be resolved rather than silently
  printing `??`;
- `\todoitem{…}` to mark a comment you have not addressed yet — the generator
  warns if one survives.

Its title block mirrors the manuscript's, so both carry the same authors and
affiliations at the same sizes.
