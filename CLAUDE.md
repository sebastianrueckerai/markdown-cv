# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sebastian Rücker's CV, maintained as plain markdown and rendered to HTML/PDF via Jekyll and CSS. Forked from [elipapa/markdown-cv](https://github.com/elipapa/markdown-cv).

## Branches — important

- **`gh-pages` is the working branch.** All CV content and styling edits happen here; GitHub Pages renders this branch live. It has diverged significantly from master (personalized `index.md`, heavily customized `media/kjhealy-print.css`, added `signature.jpg`).
- `master` is essentially the upstream template — do not target it for CV changes despite it being the repo's default branch.

## Commands

```sh
./generate-pdf.sh                  # regenerate "<year> CV Sebastian Ruecker.pdf" from index.md
                                   # (pandoc + headless Chrome; Jekyll NOT required or installed)
./generate-certificates-pdf.py     # regenerate "<year> Zeugnisse und Zertifikate Sebastian Ruecker.pdf"
                                   # from everything in CertificatesSebastianRuecker/
jekyll serve                       # optional live preview at http://localhost:4000 (needs Jekyll installed)
```

`generate-pdf.sh` reproduces `_layouts/cv.html` around the pandoc-converted markdown, then prints via headless Chrome with two deliberate print overrides: A4 paper, and fonts pinned to Arial/sans-serif. The pin exists because the CSS asks for Cousine (monospace) first, which renders differently depending on which fonts a machine has installed — the pinned sans-serif look is the one the CV has always shipped with. Dated PDF exports (e.g. `2026 CV Sebastian Ruecker.pdf`) live untracked in the repo root.

`generate-certificates-pdf.py` bundles the whole certificate archive into one A4 PDF for job applications that ask for a single certificates file. It walks `CertificatesSebastianRuecker/` (images and PDFs, including the `ABI Zeugnis`, `Zeugnisse Uni` and `Zeugnisse Arbeit` subfolders), dates every document, sorts newest first, and prepends a generated index page; PDF bookmarks mirror that index. Multi-page scans are regrouped into one entry via filename patterns (`… S1`/`S2`, `… 1_2`, `ABI Zeugnis 1…4`), so a "Part 2" course certificate is deliberately *not* treated as page 2 of anything.

Dates come from the filename where it carries one, else from text inside the PDF, else from the file's mtime. Where the scan date was misleading, the true date was read off the document and pinned in `DATE_OVERRIDES` — the Abitur is 2003 even though the scan is from 2005, and the diploma is 2010 even though its scan is from 2012. Add to that dict rather than renaming source files.

Size is held under the 10 MB that application portals typically cap at (currently ~7.6 MB for 128 pages) by encoding each page in whichever form suits it: plain ink-on-paper scans become bilevel CCITT G4 at 190 dpi, which is both sharper and far smaller than JPEG, while pages with a genuine coloured design stay continuous-tone. A page whose bilevel form exceeds `BI_MAX_BYTES` is speckling rather than compressing — tinted security paper, a photo, an illustrated header — and falls back to tone automatically. Every tunable reads from the environment, so `TONE_DPI=120 ./generate-certificates-pdf.py` trades quality for size without editing the file.

## Architecture

- `index.md` — the entire CV content (kramdown markdown, front matter `layout: cv`). Convention: dates in backticks (`` `07/2025 – Present` ``) on their own line, followed by bold role / italic employer.
- `_layouts/cv.html` — the only layout; wraps content and selects stylesheets from the `style` variable in `_config.yml` (currently `kjhealy`).
- `media/<style>-screen.css` and `media/<style>-print.css` — paired stylesheets per style (`kjhealy` and `davewhipp` exist). Screen and print are separate media targets: changes to on-screen appearance and to PDF output are made in different files.

When editing PDF/print appearance, edit `media/kjhealy-print.css` and verify by rerunning `./generate-pdf.sh` — screen rendering will not show print changes, and the script's font pin overrides any `font-family` set on `body`/headings in the CSS.
