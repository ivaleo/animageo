"""Draw the native text-block artifact with the same explicit T2A glyphs everywhere."""
from __future__ import annotations

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

from .constants import GGB_FONT_SCALE
from .geo.lib_elements import resolve_text_position
from .native.labels.tex import metrics
from .native.text_block import (ACCENT_OUTLINE_POINTS, BASE_OUTLINE_POINTS, EM_PT, FONT, GLYPH_FONTS, _ACCENTS,
                                block_font_size, drawing_glyphs, layout_ink, layout_text_block, line_tex)
from .style.resolver import resolve


# The atlas has a fixed input: the 256 slots of the block font on page 1 and
# the symbol glyphs of the other template fonts, one font per page. Text,
# positions and style never enter its subprocesses. Cache only font paths
# globally; scene vectors stay local.
@lru_cache(maxsize=1)
def _glyph_outlines():
    from manim.mobject.svg.svg_mobject import VMobjectFromSVGPath
    from svgelements import Path as SVGPath

    pages = [(FONT, {code: code for code in range(256)})]
    for gid, (font, code) in GLYPH_FONTS.items():
        if font != pages[-1][0]:
            pages.append((font, {}))
        pages[-1][1][code] = gid
    if len({font for font, _ in pages}) != len(pages):
        raise RuntimeError('text.block: symbol glyphs must be grouped by font')
    bodies = []
    for font, codes in pages:
        boxes = [r'\hbox{\char%d}\kern1pt ' % code for code in codes]
        rows = [''.join(boxes[start:start + 16]) for start in range(0, len(boxes), 16)]
        bodies.append(r'\font\probe=' + font + r'\probe '
                      + '\n'.join(r'\noindent ' + row + r'\par' for row in rows))
    source = (r'\documentclass{article}\begin{document}\pagestyle{empty} '
              + '\n\\newpage\n'.join(bodies) + r'\end{document}')
    commands = (('latex', '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error', 'atlas.tex'),
                ('dvisvgm', '--no-fonts', f'--page=1-{len(pages)}', '--output=atlas-%p.svg', 'atlas.dvi'))
    with tempfile.TemporaryDirectory(prefix='animageo_block_font_') as work:
        root = Path(work)
        (root / 'atlas.tex').write_text(source, encoding='ascii')
        for command in commands:
            try:
                subprocess.run(command, cwd=work, check=True, timeout=5,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError) as exc:
                raise RuntimeError(f'text.block: could not build {FONT} outlines with {command[0]}: {exc}') from exc
        files = sorted(root.glob('atlas-*.svg'), key=lambda path: int(path.stem.rsplit('-', 1)[1]))
        if len(files) != len(pages):
            raise RuntimeError(f'text.block: the glyph atlas has {len(files)} pages, not {len(pages)}')
        svgs = [ElementTree.parse(path) for path in files]
    outlines = {}
    for (font, codes), svg in zip(pages, svgs):
        for path in svg.findall('.//{http://www.w3.org/2000/svg}defs/{http://www.w3.org/2000/svg}path'):
            code = int(path.attrib['id'].rsplit('-', 1)[1])
            if code not in codes:
                continue
            gid = codes[code]
            points = VMobjectFromSVGPath(SVGPath(path.attrib['d'])).points
            limit = ACCENT_OUTLINE_POINTS if gid in _ACCENTS.values() else BASE_OUTLINE_POINTS
            if len(points) > limit:
                raise RuntimeError(f'text.block: {font} glyph {code} exceeds the outline budget')
            # SVG uses PostScript points and a downward y axis, at the font
            # baseline; every font is set at its design size.
            points *= [72.27 / 72 / EM_PT, -72.27 / 72 / EM_PT, 1]
            outlines[gid] = points.astype('float32')
    return outlines


def _line_vectors(layout):
    """Batch positioned outlines in reading order, with bounded path sizes."""
    import numpy as np

    atlas = _glyph_outlines()
    batches, pending = [], []
    for line in layout['lines']:
        for glyph in drawing_glyphs(line):
            code = glyph['code']
            if code not in atlas:
                raise ValueError(f'text.block: no {FONT} outline for glyph {code}')
            offset = np.array([line['x'] + glyph['x'], -line['baseline'] - glyph['y'], 0], dtype='float32')
            pending.append(atlas[code] + offset)
            if len(pending) == 64:
                batches.append(np.concatenate(pending))
                pending.clear()
    if pending:
        batches.append(np.concatenate(pending))
    return batches


def _layout(scene, elem, font_size_px):
    block = elem.data._native_text_block
    cached = scene._native_block_layouts.get(elem.name)
    if cached is None or cached[:2] != (block, font_size_px):
        layout = layout_text_block(block['content'], block['widthEm'], block['size'], block['align'],
                                   text_style={'font_size_px': font_size_px})
        scene._native_block_layouts[elem.name] = block, font_size_px, layout
        return layout
    return cached[2]


def block_projection(scene, elem, *, ptUnit_style, ptUnit_ggb):
    """Resolve the source layout and world transform for every backend."""
    font_size_px = block_font_size(resolve(scene, elem, 'font_size_px', default=14.0))
    layout = _layout(scene, elem, font_size_px)
    em = (EM_PT * metrics()['muPerPtPerFontSize'] * layout['fontSizePx'] * GGB_FONT_SCALE
          / ptUnit_style * layout['size'])
    base = resolve_text_position(scene.geo, elem.data)
    x, y = float(base[0]), float(base[1])
    off = resolve(scene, elem, 'label_offset_px', default=None)
    if off:
        x += off[0] / ptUnit_ggb
        y += off[1] / ptUnit_ggb
    return {'layout': layout, 'emToWorld': em, 'origin': [x, y]}


def block_box(projection):
    """Bounds of the logical rectangle and any overhanging ink."""
    layout, em = projection['layout'], projection['emToWorld']
    x, y = projection['origin']
    bounds = [0, 0, layout['width'], layout['height']]
    ink = layout_ink(layout)
    if ink is not None:
        bounds = [min(bounds[0], ink[0]), min(bounds[1], ink[1]),
                  max(bounds[2], ink[2]), max(bounds[3], ink[3])]
    return x + bounds[0] * em, y - bounds[3] * em, x + bounds[2] * em, y - bounds[1] * em


def render_block(scene, elem, ctx):
    """Project cached line vectors. Anchor motion only changes the transform."""
    from manim import Rectangle, UL, VGroup, VMobject

    projection = block_projection(scene, elem, ptUnit_style=ctx.ptUnit_style, ptUnit_ggb=ctx.ptUnit_ggb)
    layout, em = projection['layout'], projection['emToWorld']
    origin = [*projection['origin'], 0]
    bounds = Rectangle(width=layout['width'] * em, height=layout['height'] * em,
                       stroke_opacity=0, fill_opacity=0)
    bounds.shift(origin - bounds.get_corner(UL))
    group = VGroup(bounds, name=elem.name)
    cached = scene._native_block_vectors.get(elem.name)
    # Font-size changes affect projection only. Use the em layout's parameters
    # and content as the key, independently of the current style and anchor.
    key = elem.data._native_text_block
    if cached is None or cached[0] != key:
        cached = key, _line_vectors(layout) if any(line['glyphs'] for line in layout['lines']) else []
        scene._native_block_vectors[elem.name] = cached
    if cached[1]:
        drawing = VGroup()
        for points in cached[1]:
            path = VMobject(fill_color=ctx.col_label, fill_opacity=1, stroke_width=0)
            path.points = points.astype(float)
            path.points *= em
            path.points += origin
            path._animageo_block_path = True
            drawing.add(path)
        scene._add_label_halo(drawing, ctx)
        group.add(drawing)
    group.set_z_index(ctx.zz)
    group._animageo_text_block = projection
    return group


def emit_block(ctx, elem, labels):
    """Explicit baseline nodes, independent of TikZ's font/reflow settings."""
    from .exporters.tikz.document import fmt_num

    projection = block_projection(ctx.scene, elem, ptUnit_style=ctx.ptUnit_style, ptUnit_ggb=ctx.ptUnit_ggb)
    layout, em = projection['layout'], projection['emToWorld']
    x, y = projection['origin']
    color = ctx.doc.color(ctx.resolve(elem, 'label_color', default='#000000'))
    # A 1pt glyph at scale=em*cm_per_mu*72.27/2.54 occupies one em in world.
    scale = em * ctx.cm_per_mu * 72.27 / 2.54
    left, bottom, right, top = ctx.frame()
    with ctx.part('body'):
        for i, line in enumerate(layout['lines']):
            # Keep the complete reading-order artifact, including clipped rows.
            ctx.doc.line(f'% text.block line {i}: {line["text"].encode("unicode_escape").decode("ascii")}')
            px, py = x + line['x'] * em, y - line['baseline'] * em
            ink = [g['ink'] for g in line['glyphs'] if g['ink'] is not None]
            if not ink:
                continue
            if ctx.opt.clip:
                x0 = px + min(b[0] for b in ink) * em
                x1 = px + max(b[2] for b in ink) * em
                y0 = py - max(b[3] for b in ink) * em
                y1 = py - min(b[1] for b in ink) * em
                if x1 < left or x0 > right or y1 < bottom or y0 > top:
                    continue
            ctx.doc.line(f'\\node[anchor=base west, inner sep=0pt, outer sep=0pt, minimum width=0pt, minimum height=0pt, text={color}, '
                         f'scale={fmt_num(scale, 9)}] at ({fmt_num(px, 9)},{fmt_num(py, 9)}) '
                         '{' + line_tex(line) + '};')
