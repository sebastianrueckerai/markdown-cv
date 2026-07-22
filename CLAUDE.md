# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sebastian Rücker's CV, maintained as plain markdown and rendered to HTML/PDF via Jekyll and CSS. Forked from [elipapa/markdown-cv](https://github.com/elipapa/markdown-cv).

## Branches — important

- **`gh-pages` is the working branch.** All CV content and styling edits happen here; GitHub Pages renders this branch live. It has diverged significantly from master (personalized `index.md`, heavily customized `media/kjhealy-print.css`, added `signature.jpg`).
- `master` is essentially the upstream template — do not target it for CV changes despite it being the repo's default branch.

## Commands

```sh
./generate-pdf.sh   # regenerate "<year> CV Sebastian Ruecker.pdf" from index.md
                    # (pandoc + headless Chrome; Jekyll NOT required or installed)
jekyll serve        # optional live preview at http://localhost:4000 (needs Jekyll installed)
```

`generate-pdf.sh` reproduces `_layouts/cv.html` around the pandoc-converted markdown, then prints via headless Chrome with two deliberate print overrides: A4 paper, and fonts pinned to Arial/sans-serif. The pin exists because the CSS asks for Cousine (monospace) first, which renders differently depending on which fonts a machine has installed — the pinned sans-serif look is the one the CV has always shipped with. Dated PDF exports (e.g. `2026 CV Sebastian Ruecker.pdf`) live untracked in the repo root.

## Architecture

- `index.md` — the entire CV content (kramdown markdown, front matter `layout: cv`). Convention: dates in backticks (`` `07/2025 – Present` ``) on their own line, followed by bold role / italic employer.
- `_layouts/cv.html` — the only layout; wraps content and selects stylesheets from the `style` variable in `_config.yml` (currently `kjhealy`).
- `media/<style>-screen.css` and `media/<style>-print.css` — paired stylesheets per style (`kjhealy` and `davewhipp` exist). Screen and print are separate media targets: changes to on-screen appearance and to PDF output are made in different files.

When editing PDF/print appearance, edit `media/kjhealy-print.css` and verify by rerunning `./generate-pdf.sh` — screen rendering will not show print changes, and the script's font pin overrides any `font-family` set on `body`/headings in the CSS.
