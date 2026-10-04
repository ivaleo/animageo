#!/usr/bin/env python3
"""Build ``animageo/native/labels/metrics.v1.json``: font metrics of the label template.

    python scripts/native/build_label_metrics.py [--out PATH] [--check]

The ``metrics`` label measurer (``animageo.native.labels``) sets label TeX
without TeX: it needs, for every font the ``RusTex`` template (``animageo.ui``)
uses in labels, the TFM metrics of each character (width, height, depth,
italic correction, the ligature/kern program, the font parameters) and the
ink box of its outline as dvisvgm writes it (manim measures a ``Tex`` by the
points of those outlines, Bezier handles included). A few composite symbols
of the template (``\\angle``, ``\\triangle``, …) are measured whole, per math
style. Everything is stored in TeX points (dvisvgm writes PostScript points:
1 bp = 72.27/72 pt). The scale from TeX points to manim units per font size is
measured on a real ``Tex``.

Needs the classic render environment: manim, ``latex``, ``dvisvgm`` and
``kpsewhich``. ``--check`` rebuilds in memory and exits 1 when the file on
disk differs.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / 'animageo' / 'native' / 'labels' / 'metrics.v1.json'
FORMAT = 'animageo-label-metrics/v1'

# Fonts of label TeX: math italic, roman, symbols, AMS symbols (text, script,
# scriptscript sizes of \DeclareMathSizes{10}{10}{7}{5}) and the T2A text font.
GLYPH_FONTS = (
    'cmmi10', 'cmmi7', 'cmmi5',
    'cmr10', 'cmr7', 'cmr5',
    'cmsy10', 'cmsy7', 'cmsy5',
    'msam10', 'msam7', 'msam5',
    'msbm10', 'msbm7', 'msbm5',
    'larm1000', 'larm0700', 'larm0500',
)
PARAM_FONTS = ('cmex10',)     # default_rule_thickness only

# Composite symbols measured whole: TeX name → math class.
MACROS = {
    r'\angle': 'bin',             # RusTex: \mathbin{\text{0.8em \oldangle}}
    r'\triangle': 'bin',          # RusTex: \mathbin{\text{0.8em \oldtriangle}}
    r'\Longleftrightarrow': 'rel',
    r'\Longrightarrow': 'rel',
    r'\Longleftarrow': 'rel',
    r'\longrightarrow': 'rel',
    r'\longleftarrow': 'rel',
    r'\notin': 'rel',
    r'\neq': 'rel',
    r'\ne': 'rel',
    r'\iff': 'rel',
    r'\implies': 'rel',
    r'\dots': 'inner',
    r'\ldots': 'inner',
    r'\cdots': 'inner',
}
STYLES = {'T': r'\textstyle', 'S': r'\scriptstyle', 'SS': r'\scriptscriptstyle'}
MARK_W, MARK_H, MARK_GAP = 0.77, 3.33, 5.0     # origin marker rule (pt)
BP = 72.27 / 72        # dvisvgm writes PostScript points (bp); TeX points per bp
ROUND = 6


# ── TFM ─────────────────────────────────────────────────────────────────

def parse_tfm(path: Path) -> dict:
    """``{design, chars: {code: [w, h, d, ic]}, ligkern: {code: [[next, kind, value]]},
    params: [p1…pn]}``; dimensions in points at the design size, ``kind``
    ``"k"`` (kern, points) or ``"l<op>"`` (ligature: ``value`` is the new char)."""
    data = path.read_bytes()
    lf, lh, bc, ec, nw, nh, nd, ni, nl, nk, ne, np = struct.unpack('>12H', data[:24])
    words = [data[i:i + 4] for i in range(24, 4 * lf, 4)]

    def fix(word: bytes) -> float:
        return struct.unpack('>i', word)[0] / 2 ** 20

    design = fix(words[1])
    pos = lh
    char_info = words[pos:pos + ec - bc + 1]
    pos += ec - bc + 1
    width = [fix(w) * design for w in words[pos:pos + nw]]
    pos += nw
    height = [fix(w) * design for w in words[pos:pos + nh]]
    pos += nh
    depth = [fix(w) * design for w in words[pos:pos + nd]]
    pos += nd
    italic = [fix(w) * design for w in words[pos:pos + ni]]
    pos += ni
    lig_kern = words[pos:pos + nl]
    pos += nl
    kern = [fix(w) * design for w in words[pos:pos + nk]]
    pos += nk + ne
    param = [fix(w) for w in words[pos:pos + np]]
    params = [param[0]] + [p * design for p in param[1:]]   # p1 (slant) is not a dimension

    chars, ligkern = {}, {}
    for code in range(bc, ec + 1):
        wi, hd, it, rem = char_info[code - bc]
        if wi == 0:
            continue
        chars[code] = [width[wi], height[hd >> 4], depth[hd & 15], italic[it >> 2]]
        if it & 3 == 1:                    # lig_tag: a lig/kern program
            i = rem
            skip, nxt, op, r = lig_kern[i]
            if skip > 128:                 # indirect start
                i = 256 * op + r
            program = []
            while True:
                skip, nxt, op, r = lig_kern[i]
                if skip <= 128:
                    if op >= 128:
                        program.append([nxt, 'k', kern[256 * (op - 128) + r]])
                    else:
                        program.append([nxt, 'l%d' % op, r])
                if skip >= 128:
                    break
                i += skip + 1
            if program:
                ligkern[code] = program
    return {'design': design, 'chars': chars, 'ligkern': ligkern, 'params': params}


def kpsewhich(name: str) -> Path:
    out = subprocess.run(['kpsewhich', name], capture_output=True, text=True).stdout.strip()
    if not out:
        raise SystemExit(f'kpsewhich: {name} not found')
    return Path(out)


# ── SVG paths ───────────────────────────────────────────────────────────

_TOKEN = re.compile(r'[MmLlHhVvCcSsQqTtZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


def path_points(d: str) -> list:
    """Every point of an SVG path as manim reads it: anchors and Bezier
    handles (a quadratic segment becomes a cubic, as manim converts it)."""
    tokens = _TOKEN.findall(d)
    pts, i = [], 0
    cmd = None
    cx = cy = sx = sy = 0.0
    last_c = last_q = None

    def num():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        if re.fullmatch(r'[A-Za-z]', tokens[i]):
            cmd = tokens[i]
            i += 1
            if cmd in 'Zz':
                cx, cy = sx, sy
                last_c = last_q = None
                continue
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (cx, cy) if rel else (0.0, 0.0)
        if c == 'M':
            cx, cy = ox + num(), oy + num()
            sx, sy = cx, cy
            pts.append((cx, cy))
            cmd = 'l' if rel else 'L'
            last_c = last_q = None
        elif c == 'L':
            cx, cy = ox + num(), oy + num()
            pts.append((cx, cy))
            last_c = last_q = None
        elif c == 'H':
            cx = ox + num() if rel else num()
            pts.append((cx, cy))
            last_c = last_q = None
        elif c == 'V':
            cy = oy + num() if rel else num()
            pts.append((cx, cy))
            last_c = last_q = None
        elif c == 'C':
            x1, y1, x2, y2 = ox + num(), oy + num(), ox + num(), oy + num()
            cx, cy = ox + num(), oy + num()
            pts += [(x1, y1), (x2, y2), (cx, cy)]
            last_c, last_q = (x2, y2), None
        elif c == 'S':
            x1, y1 = (2 * cx - last_c[0], 2 * cy - last_c[1]) if last_c else (cx, cy)
            x2, y2 = ox + num(), oy + num()
            cx, cy = ox + num(), oy + num()
            pts += [(x1, y1), (x2, y2), (cx, cy)]
            last_c, last_q = (x2, y2), None
        elif c in 'QT':
            if c == 'Q':
                qx, qy = ox + num(), oy + num()
            else:
                qx, qy = (2 * cx - last_q[0], 2 * cy - last_q[1]) if last_q else (cx, cy)
            ex, ey = ox + num(), oy + num()
            pts += [(cx + 2 / 3 * (qx - cx), cy + 2 / 3 * (qy - cy)),
                    (ex + 2 / 3 * (qx - ex), ey + 2 / 3 * (qy - ey)), (ex, ey)]
            cx, cy = ex, ey
            last_c, last_q = None, (qx, qy)
        else:
            raise ValueError(f'unsupported path command {cmd!r}')
    return pts


def _bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


_PATH_DEF = re.compile(r"<path id='g(\d+)-(\d+)' d='([^']*)'/>")
_USE = re.compile(r"<use x='([^']+)' y='([^']+)' xlink:href='#g(\d+)-(\d+)'/>")
_RECT = re.compile(r"<rect x='([^']+)' y='([^']+)' height='([^']+)' width='([^']+)'/>")
# a glyph of another size of the same outlines: <use id='g2-92' xlink:href='#g1-92' transform='scale(s)'/>
_SCALED_DEF = re.compile(r"<use id='g(\d+)-(\d+)' xlink:href='#g(\d+)-(\d+)' transform='scale\(([^)]+)\)'/>")


def glyph_boxes(svg: str) -> dict:
    """``{(font, code): (x0, y0, x1, y1)}`` of the glyph definitions of a page (SVG axes)."""
    boxes = {}
    for f, c, d in _PATH_DEF.findall(svg):
        pts = path_points(d)
        if pts:
            boxes[(int(f), int(c))] = _bbox(pts)
    for f, c, rf, rc, s in _SCALED_DEF.findall(svg):
        b = boxes.get((int(rf), int(rc)))
        if b:
            k = float(s)
            boxes[(int(f), int(c))] = (b[0] * k, b[1] * k, b[2] * k, b[3] * k)
    return boxes


# ── TeX runs ────────────────────────────────────────────────────────────

def _document(body: str) -> str:
    from animageo.ui import RusTex
    return ('\\documentclass{article}\n' + RusTex.preamble
            + '\n\\pagestyle{empty}\n\\begin{document}\n' + body + '\n\\end{document}\n')


def _run_tex(body: str, workdir: Path) -> tuple:
    """Compile ``body`` with the template; ``(log, [svg of each page])``."""
    tex = workdir / 'probe.tex'
    tex.write_text(_document(body), encoding='utf-8')
    proc = subprocess.run(['latex', '-interaction=nonstopmode', '-halt-on-error', 'probe.tex'],
                          cwd=workdir, capture_output=True, text=True)
    log = (workdir / 'probe.log').read_text(encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        raise SystemExit('latex failed:\n' + log[-3000:])
    subprocess.run(['dvisvgm', '--no-fonts', '--page=1-', '--output=page-%p.svg', 'probe.dvi'],
                   cwd=workdir, capture_output=True, text=True, check=True)
    pages = sorted(workdir.glob('page-*.svg'), key=lambda p: int(re.findall(r'\d+', p.stem)[0]))
    svgs = [p.read_text(encoding='utf-8') for p in pages]
    for p in pages:
        p.unlink()
    return log, svgs


def glyph_inks(fonts, tfms, workdir: Path) -> dict:
    """``{font: {code: [x0, y0, x1, y1]}}`` — ink boxes (points, y up, origin
    at the reference point), one page per font."""
    pages = []
    for font in fonts:
        codes = sorted(tfms[font]['chars'])
        cells = ''.join(r'\setbox0\hbox{\char%d}\box0\hskip 3pt plus 1pt ' % c for c in codes)
        pages.append(r'\font\probe=%s\probe\noindent ' % font + cells + r'\par\newpage')
    _, svgs = _run_tex('\n'.join(pages), workdir)
    if len(svgs) != len(fonts):
        raise SystemExit(f'expected {len(fonts)} pages, got {len(svgs)}')
    inks = {}
    for font, svg in zip(fonts, svgs):
        if _SCALED_DEF.search(svg) or len({f for f, _c, _d in _PATH_DEF.findall(svg)}) > 1:
            raise SystemExit(f'{font}: the page holds more than one font')
        inks[font] = {code: [x0 * BP, -y1 * BP, x1 * BP, -y0 * BP]
                      for (_f, code), (x0, y0, x1, y1) in glyph_boxes(svg).items()}
    return inks


def macro_boxes(workdir: Path) -> dict:
    """``{macro: {style: [w, h, d, x0, y0, x1, y1]}}`` of the composite symbols."""
    keys = [(m, s) for m in MACROS for s in STYLES]
    body = []
    for n, (macro, style) in enumerate(keys):
        body.append(
            r'\noindent\rule{%gpt}{%gpt}\kern %gpt' % (MARK_W, MARK_H, MARK_GAP)
            + r'\setbox0\hbox{$%s%s$}' % (STYLES[style], macro)
            + r'\typeout{AGMAC:%d:\the\wd0:\the\ht0:\the\dp0}\box0\par\newpage' % n)
    log, svgs = _run_tex('\n'.join(body), workdir)
    dims = {int(n): [float(v[:-2]) for v in (w, h, d)]
            for n, w, h, d in re.findall(r'AGMAC:(\d+):([-\d.]+pt):([-\d.]+pt):([-\d.]+pt)', log)}
    out = {}
    for n, ((macro, style), svg) in enumerate(zip(keys, svgs)):
        paths = glyph_boxes(svg)
        rects = [tuple(float(v) for v in r) for r in _RECT.findall(svg)]
        marker = [r for r in rects
                  if abs(r[3] * BP - MARK_W) < 0.02 and abs(r[2] * BP - MARK_H) < 0.02]
        if len(marker) != 1:
            raise SystemExit(f'{macro} {style}: origin marker not found')
        mx, my, mh, mw = marker[0]
        ox, oy = mx + mw + MARK_GAP / BP, my + mh
        boxes = []
        for x, y, f, c in _USE.findall(svg):
            b = paths.get((int(f), int(c)))
            if b:
                boxes.append((float(x) + b[0], float(y) + b[1], float(x) + b[2], float(y) + b[3]))
        for r in rects:
            if r is not marker[0]:
                boxes.append((r[0], r[1], r[0] + r[3], r[1] + r[2]))
        w, h, d = dims[n]
        if boxes:
            x0 = min(b[0] for b in boxes) - ox
            x1 = max(b[2] for b in boxes) - ox
            y0 = oy - max(b[3] for b in boxes)
            y1 = oy - min(b[1] for b in boxes)
            ink = [x0 * BP, y0 * BP, x1 * BP, y1 * BP]
        else:
            ink = None
        out.setdefault(macro, {'class': MACROS[macro]})[style] = [w, h, d] + (ink or [])
    return out


def manim_scale(inks) -> float:
    """Manim units per TeX point per unit of ``font_size``, measured on ``$M$``."""
    from manim import Tex
    from animageo.ui import RusTex
    tex = Tex('$M$', tex_template=RusTex).set(font_size=48)
    x0, _y0, x1, _y1 = inks['cmmi10'][ord('M')]
    return float(tex.width) / ((x1 - x0) * 48)


def _rounded(value):
    if isinstance(value, float):
        return round(value, ROUND) + 0.0
    if isinstance(value, list):
        return [_rounded(v) for v in value]
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    return value


def build() -> dict:
    tfms = {f: parse_tfm(kpsewhich(f + '.tfm')) for f in GLYPH_FONTS + PARAM_FONTS}
    with tempfile.TemporaryDirectory(prefix='animageo_metrics_') as tmp:
        workdir = Path(tmp)
        inks = glyph_inks(GLYPH_FONTS, tfms, workdir)
        macros = macro_boxes(workdir)
    fonts = {}
    for name in GLYPH_FONTS + PARAM_FONTS:
        tfm = tfms[name]
        entry = {'design': tfm['design'], 'params': tfm['params']}
        if name in GLYPH_FONTS:
            ink = inks[name]
            entry['chars'] = {str(c): v + (ink.get(c) or []) for c, v in sorted(tfm['chars'].items())}
            entry['ligkern'] = {str(c): p for c, p in sorted(tfm['ligkern'].items())}
        fonts[name] = entry
    from animageo.ui import RusTex
    import hashlib
    out = _rounded({
        'format': FORMAT,
        'generatedBy': 'scripts/native/build_label_metrics.py',
        'template': 'sha256:' + hashlib.sha256(RusTex.preamble.encode('utf-8')).hexdigest(),
        'scriptSpace': 0.5,
        'chars': 'code: [width, height, depth, italic, inkX0, inkY0, inkX1, inkY1] '
                 '(points, y up; no ink box for a blank character)',
        'macros_doc': 'macro: {class, T|S|SS: [width, height, depth, inkX0, inkY0, inkX1, inkY1]}',
        'fonts': fonts,
        'macros': macros,
    })
    out['muPerPtPerFontSize'] = float('%.12g' % manim_scale(inks))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--check', action='store_true', help='compare with the file on disk')
    args = parser.parse_args(argv)
    text = json.dumps(build(), ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
    if args.check:
        same = args.out.exists() and args.out.read_text(encoding='utf-8') == text
        print('up to date' if same else f'{args.out} differs')
        return 0 if same else 1
    args.out.write_text(text, encoding='utf-8')
    print(f'wrote {args.out} ({len(text)} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
