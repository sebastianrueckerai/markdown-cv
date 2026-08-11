#!/usr/bin/env python3
"""Assemble every certificate into one date-sorted A4 PDF.

Each page is rendered to a bitmap and then encoded in whichever form suits it:
plain ink-on-paper scans become bilevel CCITT G4 (sharp and tiny), pages with a
real coloured design stay continuous-tone.  An index page and PDF bookmarks are
generated from the same manifest that drives the ordering.
"""
import os
import re
import shutil
import subprocess
import sys
import datetime as dt
import tempfile
from collections import OrderedDict
from PIL import Image, ImageOps, ImageFilter, ImageChops

Image.MAX_IMAGE_PIXELS = None

REPO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("CERTS", os.path.join(REPO, "CertificatesSebastianRuecker"))
WORK = os.environ.get("WORK", os.path.join(tempfile.gettempdir(), "cert-pdf-build"))
PAGES = os.path.join(WORK, "pages")
OUT = os.environ.get("OUT", os.path.join(
    REPO, f"{dt.date.today().year} Zeugnisse und Zertifikate Sebastian Ruecker.pdf"))
REPORT_ONLY = os.environ.get("REPORT") == "1"
os.makedirs(WORK, exist_ok=True)

RENDER_DPI = int(os.environ.get("RENDER_DPI", 220))   # source PDF rasterisation
BI_DPI = int(os.environ.get("BI_DPI", 190))           # bilevel output pages
TONE_DPI = int(os.environ.get("TONE_DPI", 150))       # continuous-tone output pages
TONE_Q = int(os.environ.get("TONE_Q", 72))
COLOUR_FRAC = float(os.environ.get("COLOUR_FRAC", 0.02))   # above this: keep tone
BI_MAX_BYTES = int(os.environ.get("BI_MAX_BYTES", 52_000))  # bigger => speckling, use tone
KEEP_COLOUR = os.environ.get("KEEP_COLOUR", "1") == "1"

A4_IN = (8.2677, 11.6929)
MARGIN_IN = 0.16

SKIP_NAMES = {
    "certificates.txt",
    "Zeugnisse Arbeit.zip",
    # byte-identical duplicate of "Zwischenzeugnis Sebastian Rücker.pdf"
    "Interim Employment Reference Sebastian Rücker.pdf",
}

# Dates read off the documents themselves, overriding filename/mtime guesses.
DATE_OVERRIDES = {
    "ABI Zeugnis/ABI Zeugnis 1.jpg": ("2003-06-17", "day"),
    "ABI Zeugnis/ABI Zeugnis 2.jpg": ("2003-06-17", "day"),
    "ABI Zeugnis/ABI Zeugnis 3.jpg": ("2003-06-17", "day"),
    "ABI Zeugnis/ABI Zeugnis 4.jpg": ("2003-06-17", "day"),
    "Zeugnisse Uni/DiplZeugniss01.jpg": ("2010-11-19", "day"),
    "Zeugnisse Uni/DiplZeugniss02.jpg": ("2010-11-19", "day"),
    "Zeugnisse Uni/ZeugnMU.jpg": ("2007-07-09", "day"),
    "Zeugnisse Uni/ZeugnMU RSeite.jpg": ("2007-07-09", "day"),
    "Zeugnisse Arbeit/Lang & Schwarz/Zwischenzeugnis Sebastian Rücker.pdf": ("2026-07-27", "day"),
}

PART_OVERRIDES = {
    "Zeugnisse Uni/ZeugnMU.jpg": ("Zeugnisse Uni/ZeugnMU", 1),
    "Zeugnisse Uni/ZeugnMU RSeite.jpg": ("Zeugnisse Uni/ZeugnMU", 2),
}

TITLE_OVERRIDES = {
    "ABI Zeugnis/ABI Zeugnis": "Abiturzeugnis — Theodor-Heuss-Schule Wetzlar",
    "Zeugnisse Uni/DiplZeugniss": "Diplomzeugnis Betriebswirtschaftslehre — KU Eichstätt-Ingolstadt",
    "Zeugnisse Uni/ZeugnMU": "Academic Transcript — Marquette University, Milwaukee",
    "Zeugnisse Arbeit/Lang & Schwarz/Zwischenzeugnis Sebastian Rücker":
        "Zwischenzeugnis — Lang & Schwarz Gate GmbH",
    "2004 SAP Zeugnis": "SAP R/3 Seminarzeugnis — SRH",
    "Zeugnisse Arbeit/2022 Optiopay Sebastian Rücker_ZZ_2207": "Zwischenzeugnis — Optiopay",
    "Zeugnisse Arbeit/2025 Zeugnis_COMPREDICT": "Arbeitszeugnis — COMPREDICT",
    "Zeugnisse Arbeit/2009 Zeugnis Commerzbank ETF Desk": "Zeugnis — Commerzbank, ETF Desk",
    "Zeugnisse Arbeit/2017 Finales Arbeitszeugnis EXXETA": "Arbeitszeugnis — EXXETA AG",
    "Zeugnisse Arbeit/2016 Zwischenzeugnis EXXETA 2016": "Zwischenzeugnis — EXXETA AG",
    "Zeugnisse Arbeit/2007 Gutachten Pustejovski Marquette University":
        "Letter of Recommendation — Marquette University",
    "2011 Stochastische Prozesse, Optionspreisbewertung und Forwardkurvenmodellierung mit "
    "R_VorwortUndInhalt":
        "Diplomarbeit — Stochastische Prozesse, Optionspreisbewertung und "
        "Forwardkurvenmodellierung mit R (Vorwort und Inhalt)",
    "2012 Analyse Integrierter und Kointegrierter auf Rohstoffen basiernder Zeitreihen - "
    "Vorwort und Inhalt":
        "Studienarbeit — Analyse integrierter und kointegrierter, auf Rohstoffen "
        "basierender Zeitreihen (Vorwort und Inhalt)",
}

CATEGORIES = [("Zeugnisse Arbeit", "Arbeitszeugnis"),
              ("Zeugnisse Uni", "Studium"),
              ("ABI Zeugnis", "Schule")]

MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]
MONTH_WORDS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
               "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
               "november": 11, "december": 12, "januar": 1, "februar": 2,
               "märz": 3, "mai": 5, "juni": 6, "juli": 7, "oktober": 10,
               "dezember": 12}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"FAILED {cmd[:4]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}\n")
        raise SystemExit(1)
    return r


def pdf_pages(path):
    return int(re.search(r"^Pages:\s+(\d+)", run(["pdfinfo", path]).stdout, re.M).group(1))


# ---------------------------------------------------------------- date lookup
def date_from_name(name):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", name)
    if m:
        return dt.date(*map(int, m.groups())), "day"
    m = re.match(r"^(\d{4})-(\d{2})\b", name)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), 15), "month"
    m = re.match(r"^(\d{4})\b", name)
    if m:
        return dt.date(int(m.group(1)), 6, 30), "year"
    return None, None


def date_from_pdf(path):
    try:
        text = subprocess.run(["pdftotext", "-layout", path, "-"],
                              capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return None, None
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
    if m:
        mo, da, yr = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= da <= 31:
            return dt.date(yr, mo, da), "day"
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-zäöü]+)\s+(\d{4})\b", text)
    if m and m.group(2).lower() in MONTH_WORDS:
        return dt.date(int(m.group(3)), MONTH_WORDS[m.group(2).lower()], int(m.group(1))), "day"
    m = re.search(r"\b([A-Za-zäöü]{3,12})\s+(\d{4})\b", text)
    if m and m.group(1).lower() in MONTH_WORDS:
        return dt.date(int(m.group(2)), MONTH_WORDS[m.group(1).lower()], 15), "month"
    return None, None


def resolve_date(rel, path, ext):
    if rel in DATE_OVERRIDES:
        iso, prec = DATE_OVERRIDES[rel]
        return dt.date.fromisoformat(iso), prec
    d, prec = date_from_name(os.path.basename(rel))
    if d:
        return d, prec
    if ext == ".pdf":
        d, prec = date_from_pdf(path)
        if d:
            return d, prec
    return dt.date.fromtimestamp(os.path.getmtime(path)), "month"


def fmt_date(d, prec):
    if prec == "day":
        return d.strftime("%d.%m.%Y")
    if prec == "month":
        return f"{MONTHS_DE[d.month - 1]} {d.year}"
    return str(d.year)


# ------------------------------------------------------------- part grouping
# "... Part 2" is a separate course, not page 2 of a scan.
NOT_A_PART = re.compile(r"(part|teil|vol|volume|level|stufe|kurs|course|nr)$", re.I)
PART_PATTERNS = [
    re.compile(r"^(?P<stem>.*?)[ _]S(?P<part>\d)$"),
    re.compile(r"^(?P<stem>.*?)[ _](?P<part>\d)_\d$"),
    re.compile(r"^(?P<stem>.*?) (?P<part>\d)$"),
    re.compile(r"^(?P<stem>.*?)(?P<part>0\d)$"),
]


def part_key(rel):
    if rel in PART_OVERRIDES:
        return PART_OVERRIDES[rel]
    dirname = os.path.dirname(rel)
    base = os.path.splitext(os.path.basename(rel))[0]
    if base.endswith(".jpg"):
        base = base[:-4]
    for pat in PART_PATTERNS:
        m = pat.match(base)
        if m:
            stem = m.group("stem").rstrip(" _-")
            if NOT_A_PART.search(stem):
                continue
            return (os.path.join(dirname, stem) if dirname else stem), int(m.group("part"))
    return (os.path.join(dirname, base) if dirname else base), 1


def make_title(group_key, sample_rel):
    if group_key in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[group_key]
    t = os.path.basename(group_key)
    t = re.sub(r"^\d{4}(-\d{2}(-\d{2})?)?[\s_.-]*", "", t)
    t = t.replace("_", " ")
    t = re.sub(r"(?<=\S)\s-\s(?=\S)", " – ", t)
    t = re.sub(r"\s+", " ", t).strip(" –-")
    t = re.sub(r"\s*Sebastian R(ü|ue)cker\s*", " ", t).strip(" –-")
    return t or os.path.basename(sample_rel)


def category(rel):
    for prefix, label in CATEGORIES:
        if rel.startswith(prefix + os.sep):
            return label
    return "Zertifikat"


# ------------------------------------------------------------------ scanning
files = []
for dirpath, _dirs, filenames in os.walk(ROOT):
    for fn in sorted(filenames):
        if fn in SKIP_NAMES or fn.startswith("."):
            continue
        ext = os.path.splitext(fn)[1].lower()
        if ext not in {".pdf", ".jpg", ".jpeg", ".png"}:
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, ROOT)
        d, prec = resolve_date(rel, path, ext)
        stem, part = part_key(rel)
        files.append({"rel": rel, "path": path, "ext": ext, "date": d,
                      "prec": prec, "stem": stem, "part": part})

counts = {}
for f in files:
    counts[f["stem"]] = counts.get(f["stem"], 0) + 1
for f in files:
    if counts[f["stem"]] < 2:
        f["stem"] = os.path.splitext(f["rel"])[0]
        f["part"] = 1

groups = OrderedDict()
for f in sorted(files, key=lambda f: (-f["date"].toordinal(), f["stem"], f["part"])):
    groups.setdefault(f["stem"], []).append(f)

docs = []
for stem, members in groups.items():
    members.sort(key=lambda f: f["part"])
    docs.append({"stem": stem, "files": members, "date": members[0]["date"],
                 "prec": members[0]["prec"], "title": make_title(stem, members[0]["rel"]),
                 "category": category(members[0]["rel"])})
docs.sort(key=lambda d: (-d["date"].toordinal(), d["title"]))


# --------------------------------------------------------------- page encode
def colour_fraction(im):
    """Share of the page covered by genuinely coloured ink/design."""
    if im.mode not in ("RGB", "RGBA"):
        return 0.0
    small = im.convert("RGB")
    small.thumbnail((260, 260), Image.BILINEAR)
    h, s, v = small.convert("HSV").split()
    sat = s.point(lambda p: 255 if p > 60 else 0)
    val = v.point(lambda p: 255 if p > 40 else 0)
    both = ImageChops.multiply(sat, val)
    return sum(both.histogram()[255:]) / (small.width * small.height)


def binarise(im, offset=14):
    """Local-mean threshold: ink is what sits darker than its neighbourhood."""
    g = im.convert("L")
    bg = g.filter(ImageFilter.BoxBlur(max(8, g.width // 60)))
    diff = ImageChops.subtract(bg, g, scale=1, offset=-offset)
    bw = diff.point(lambda p: 0 if p > 0 else 255)
    return despeckle(bw).convert("1")


def despeckle(bw):
    """Drop black dots that have almost nothing black around them.

    Paper grain survives thresholding as isolated specks.  A pixel sitting in a
    5x5 window that is otherwise white cannot be part of a letter stroke, so it
    is erased; anything with real ink nearby is left exactly as it was.
    """
    neighbourhood = bw.filter(ImageFilter.BoxBlur(2))
    isolated = neighbourhood.point(lambda p: 255 if p >= 230 else 0)
    return ImageChops.lighter(bw, isolated)


def a4_canvas(dpi, mode, fill):
    return Image.new(mode, (round(A4_IN[0] * dpi), round(A4_IN[1] * dpi)), fill)


def place(im, dpi, mode, fill):
    page = a4_canvas(dpi, mode, fill)
    avail = (page.width - round(2 * MARGIN_IN * dpi), page.height - round(2 * MARGIN_IN * dpi))
    scale = min(avail[0] / im.width, avail[1] / im.height)
    if scale < 1 or scale > 1:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                       Image.LANCZOS)
    if im.mode != mode:
        im = im.convert(mode)
    page.paste(im, ((page.width - im.width) // 2, (page.height - im.height) // 2))
    return page


def crop_to_paper(im):
    """Trim a dark surround (photos of a document on a desk) down to the sheet.

    Walks in from each edge while the line is predominantly dark and stops at
    the first mostly-bright line, so a dark border printed *on* white paper is
    left alone — only the background around the sheet is removed.
    """
    g = im.convert("L")
    probe = g.copy()
    probe.thumbnail((420, 420), Image.BILINEAR)
    w, h = probe.size
    mask = probe.point(lambda p: 1 if p > 150 else 0)
    cols = [sum(mask.crop((x, 0, x + 1, h)).getdata()) / h for x in range(w)]
    rows = [sum(mask.crop((0, y, w, y + 1)).getdata()) / w for y in range(h)]

    def walk(profile, limit):
        i = 0
        while i < limit and profile[i] < 0.35:
            i += 1
        return i if i < limit else 0

    left = walk(cols, w // 4)
    right = walk(cols[::-1], w // 4)
    top = walk(rows, h // 4)
    bottom = walk(rows[::-1], h // 4)
    if not (left or right or top or bottom):
        return im
    pad_x, pad_y = max(1, w // 150), max(1, h // 150)
    box = (max(0, left - pad_x), max(0, top - pad_y),
           min(w, w - right + pad_x), min(h, h - bottom + pad_y))
    if (box[2] - box[0]) < w * 0.45 or (box[3] - box[1]) < h * 0.45:
        return im
    sx, sy = im.width / w, im.height / h
    return im.crop((round(box[0] * sx), round(box[1] * sy),
                    round(box[2] * sx), round(box[3] * sy)))


def ink_fraction(bw):
    """Share of the thresholded page that came out black.

    Clean ink-on-paper lands around 2-12%.  A textured or tinted background
    (security paper, watermarks, photos) speckles instead, pushing this far
    higher — which is the signal that bilevel would look bad.
    """
    h = bw.histogram()
    return h[0] / (bw.width * bw.height)


def whiten(im):
    """Lift a dim scan's paper back towards white without clipping the ink.

    The brightest few percent of a document page is its paper, so scaling that
    level up to near-white fixes the grey cast.  The gain is capped so photo
    pages are nudged rather than blown out, and every channel gets the same
    factor so colours keep their hue.
    """
    lum = im.convert("L")
    hist = lum.histogram()
    total = sum(hist)
    acc = 0
    paper = 255
    for value, count in enumerate(hist):
        acc += count
        if acc >= total * 0.92:
            paper = value
            break
    if paper >= 236 or paper < 40:
        return im
    gain = min(1.7, 248 / paper)
    lut = [min(255, round(v * gain)) for v in range(256)]
    return im.point(lut * len(im.getbands()))


def write_tone(im, dst):
    mode = "RGB" if KEEP_COLOUR else "L"
    im = whiten(im.convert(mode))
    page = place(im, TONE_DPI, mode, 255 if mode == "L" else (255, 255, 255))
    page.save(dst, "PDF", resolution=TONE_DPI, quality=TONE_Q, optimize=True)
    return "colour" if mode == "RGB" else "gray"


def encode_page(im, dst):
    """Write one source bitmap as an A4 page PDF; returns the mode chosen.

    Bilevel is the default because ink-on-paper scans come out sharper and far
    smaller that way.  A tinted or textured background instead breaks up into
    speckle, and speckle is precisely what CCITT G4 cannot compress — so an
    oversized bilevel page is the signal to fall back to continuous tone.
    """
    im = crop_to_paper(ImageOps.exif_transpose(im))
    cf = colour_fraction(im)
    if cf >= COLOUR_FRAC:
        return write_tone(im, dst), cf, 0.0
    bw = binarise(im)
    inkf = ink_fraction(bw)
    place(bw, BI_DPI, "1", 1).save(dst, "PDF", resolution=BI_DPI)
    if os.path.getsize(dst) > BI_MAX_BYTES:
        return write_tone(im, dst), cf, inkf
    return "bilevel", cf, inkf


shutil.rmtree(PAGES, ignore_errors=True)
os.makedirs(PAGES)

seq = 0
inputs = []
stats = {"bilevel": 0, "colour": 0, "gray": 0}
report = []
with tempfile.TemporaryDirectory() as tmp:
    for doc in docs:
        doc["pdfs"] = []
        for f in doc["files"]:
            if f["ext"] == ".pdf":
                for old in os.listdir(tmp):
                    os.remove(os.path.join(tmp, old))
                run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=png16m",
                     f"-r{RENDER_DPI}", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
                     "-o", os.path.join(tmp, "p%03d.png"), f["path"]])
                srcs = [os.path.join(tmp, n) for n in sorted(os.listdir(tmp))]
            else:
                srcs = [f["path"]]
            for s in srcs:
                seq += 1
                dst = os.path.join(PAGES, f"{seq:04d}.pdf")
                with Image.open(s) as im:
                    mode, cf, inkf = encode_page(im, dst)
                stats[mode] += 1
                report.append((os.path.getsize(dst), mode, cf, inkf, f["rel"]))
                inputs.append(dst)
                doc["pdfs"].append(dst)

body_pages = len(inputs)
body_bytes = sum(r[0] for r in report)
print(f"{len(docs)} documents · {len(files)} source files · {body_pages} body pages")
print(f"encoding: {stats['bilevel']} bilevel, {stats['colour']} colour, {stats['gray']} gray")
print(f"page payload: {body_bytes/1e6:.2f} MB")

if REPORT_ONLY:
    print(f"\n{'size':>7} {'mode':<8} {'col%':>5} {'ink%':>5}  file")
    for size, mode, cf, inkf, rel in sorted(report, reverse=True):
        print(f"{size/1024:6.0f}K {mode:<8} {cf*100:5.1f} {inkf*100:5.1f}  {rel[:70]}")
    raise SystemExit(0)


# ------------------------------------------------------------------- index
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_index(first_body_page):
    page = first_body_page
    rows = []
    for doc in docs:
        doc["page"] = page
        rows.append((fmt_date(doc["date"], doc["prec"]), doc["title"],
                     doc["category"], page, len(doc["pdfs"])))
        page += len(doc["pdfs"])
    html = ["""<meta charset="utf-8"><style>
@page { size: A4; margin: 15mm 14mm; }
body { font: 8.6pt/1.3 Arial, Helvetica, sans-serif; color: #111; margin: 0; }
h1 { font-size: 16pt; margin: 0 0 1.5mm; }
.sub { font-size: 8.4pt; color: #555; margin: 0 0 5mm;
       border-bottom: 1px solid #bbb; padding-bottom: 2.5mm; }
table { width: 100%; border-collapse: collapse; }
td { padding: 1.15mm 0; vertical-align: baseline; border-bottom: 1px solid #eee; }
td.d { width: 31mm; padding-right: 3mm; color: #555; white-space: nowrap; }
td.t { padding-right: 4mm; }
td.c { width: 25mm; color: #777; font-size: 7.2pt; text-align: right; white-space: nowrap; }
td.p { width: 11mm; text-align: right; white-space: nowrap; }
tr.head td { border-bottom: 1px solid #999; font-size: 7pt; letter-spacing: .08em;
             text-transform: uppercase; color: #666; padding-top: 0; }
</style>"""]
    html.append("<h1>Zeugnisse und Zertifikate</h1>")
    html.append(f'<p class="sub">Sebastian Rücker &nbsp;·&nbsp; {len(docs)} Dokumente, '
                f'{body_pages} Seiten &nbsp;·&nbsp; nach Datum sortiert, neueste zuerst</p>')
    html.append("<table><tr class='head'><td class='d'>Datum</td><td class='t'>Dokument</td>"
                "<td class='c'>Art</td><td class='p'>Seite</td></tr>")
    for date, title, cat, pg, n in rows:
        span = f"{pg}" if n == 1 else f"{pg}–{pg + n - 1}"
        html.append(f"<tr><td class='d'>{esc(date)}</td><td class='t'>{esc(title)}</td>"
                    f"<td class='c'>{esc(cat)}</td><td class='p'>{span}</td></tr>")
    html.append("</table>")
    src = os.path.join(WORK, "index.html")
    with open(src, "w") as fh:
        fh.write("\n".join(html))
    dst = os.path.join(WORK, "index.pdf")
    run(["google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
         "--no-pdf-header-footer", f"--print-to-pdf={dst}", "file://" + src])
    return dst, pdf_pages(dst)


index_pdf, n_index = render_index(1)
for _ in range(3):
    index_pdf, n2 = render_index(n_index + 1)
    if n2 == n_index:
        break
    n_index = n2


# ---------------------------------------------------------------- bookmarks
def pdfmark_str(s):
    return "(" + "".join(f"\\{c:03o}" for c in b"\xfe\xff" + s.encode("utf-16-be")) + ")"


marks = ["[ /Title (Zeugnisse und Zertifikate - Sebastian Ruecker) "
         "/Author (Sebastian Ruecker) "
         "/Subject (Arbeitszeugnisse, Diplome und Zertifikate, nach Datum sortiert) "
         "/DOCINFO pdfmark",
         f"[/Page 1 /Title {pdfmark_str('Inhaltsverzeichnis')} /OUT pdfmark"]
for doc in docs:
    marks.append(f"[/Page {doc['page']} /Title "
                 f"{pdfmark_str(fmt_date(doc['date'], doc['prec']) + ' — ' + doc['title'])} "
                 "/OUT pdfmark")
mark_file = os.path.join(WORK, "marks.ps")
with open(mark_file, "w") as fh:
    fh.write("\n".join(marks) + "\n")

run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
     "-dCompatibilityLevel=1.5", "-dFIXEDMEDIA", "-sPAPERSIZE=a4", "-dPDFFitPage",
     "-dAutoRotatePages=/None", "-dDetectDuplicateImages=true",
     "-dPassThroughJPEGImages=true", "-dEncodeColorImages=true",
     "-dAutoFilterColorImages=false", "-dColorImageFilter=/DCTEncode",
     "-dAutoFilterGrayImages=false", "-dGrayImageFilter=/DCTEncode",
     "-dDownsampleColorImages=false", "-dDownsampleGrayImages=false",
     "-dDownsampleMonoImages=false", "-dMonoImageFilter=/CCITTFaxEncode",
     f"-dJPEGQ={TONE_Q}",
     "-o", OUT, index_pdf] + inputs + [mark_file])

size = os.path.getsize(OUT)
print(f"\n{OUT}\n{pdf_pages(OUT)} pages · {size/1e6:.2f} MB")

with open(os.path.join(WORK, "contents.txt"), "w") as fh:
    for doc in docs:
        fh.write(f"p{doc['page']:>4} ({len(doc['pdfs'])})  "
                 f"{fmt_date(doc['date'], doc['prec']):<16} {doc['category']:<15} "
                 f"{doc['title']}\n")
