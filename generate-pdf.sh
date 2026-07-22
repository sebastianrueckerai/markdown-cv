#!/usr/bin/env bash
# Generate the CV PDF from index.md — no Jekyll required.
# Requires: pandoc, google-chrome (or chromium).
#
# Usage: ./generate-pdf.sh [output.pdf]
#        default output: "<current year> CV Sebastian Ruecker.pdf"
set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-$(date +%Y) CV Sebastian Ruecker.pdf}"
STYLE=$(awk '/^style:/{print $2}' _config.yml)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Strip the Jekyll front matter, convert the markdown body to HTML
awk 'NR==1 && /^---$/ {fm=1; next} fm==1 {if (/^---$/) fm=2; next} {print}' index.md > "$TMP/body.md"
pandoc -f markdown -t html --wrap=none "$TMP/body.md" -o "$TMP/body.html"

# Reproduce _layouts/cv.html, plus print-only overrides:
#  - A4 paper (Chrome headless defaults to Letter)
#  - pin sans-serif fonts so the output looks the same on every machine,
#    regardless of whether Cousine/Verdana happen to be installed
cat > "$TMP/cv.html" <<EOF
<!doctype html>
<html>
<head>
  <meta charset=utf-8 />
  <title>Sebastian Rücker's CV</title>
  <link href="file://$PWD/media/$STYLE-screen.css" type="text/css" rel="stylesheet" media="screen">
  <link href="file://$PWD/media/$STYLE-print.css" type="text/css" rel="stylesheet" media="print">
  <style media="print">
    @page { size: A4; }
    body, h1, h2, h3, h4 { font-family: Arial, Helvetica, sans-serif; }
  </style>
</head>
<body>
  <div id="main">
    <div id="content">
$(cat "$TMP/body.html")
    </div>
  </div>
</body>
</html>
EOF

CHROME=$(command -v google-chrome || command -v chromium || command -v chromium-browser)
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$TMP/out.pdf" "file://$TMP/cv.html" 2>/dev/null
mv "$TMP/out.pdf" "$OUT"

echo "Wrote: $OUT"
pdfinfo "$OUT" 2>/dev/null | grep -E "Pages|Page size" || true
