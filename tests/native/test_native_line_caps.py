"""Line caps are one rule in every output (1.11.0): ``stroke_linecap`` (by
default ``rendering.line_cap``) caps a segment, a line, a ray, a vector, an arc
and the arc of a sector; every other stroke — the ticks of a segment, a
polyline, a locus, a curve, the arcs of an angle, a right-angle mark — ends
butt. The SVG (and the PDF, EPS and PNG drawn by the same cairo code), the
frame of the video, TikZ and ``resolve_paint`` draw the same caps; a stroke
without a cap of its own never takes the cap or the join of the stroke drawn
before it."""
import collections
import re
import tempfile

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

import cairo  # noqa: E402

from animageo import native  # noqa: E402
from animageo.native.document import as_document  # noqa: E402
from animageo.native.paint import resolve_paint  # noqa: E402
from animageo.native.paint_fixtures import _Doc  # noqa: E402

CAPS = {cairo.LINE_CAP_BUTT: 'butt', cairo.LINE_CAP_ROUND: 'round', cairo.LINE_CAP_SQUARE: 'square'}
JOINS = {cairo.LINE_JOIN_MITER: 'miter', cairo.LINE_JOIN_ROUND: 'round', cairo.LINE_JOIN_BEVEL: 'bevel'}
STYLES = [None, {'rendering': {'line_cap': 'round'}}, {'rendering': {'line_cap': 'square'}}]


def _doc():
    d = _Doc('caps').free('A', 0, 0).free('B', 5, 0).free('C', 1.5, 3.5).free('D', 6, 3)
    d.segment('a', 'A', 'B').polyline('w', 'B', 'D', 'C').angle('alpha', 'B', 'A', 'C')
    d.vector('v', 'C', 'D').arc('k', 'A', 'B', 'C').ray('r', 'A', 'D').right_mark('m', 'A', 'B', 'D')
    d.sector('s', 'D', 'C', 'B').segment('b', 'C', 'A')
    d.overrides('a', stroke_linecap='round', stroke_width_px=6, tick_count=2)
    d.overrides('b', stroke_linecap='square', stroke_width_px=5)
    d.overrides('w', stroke_width_px=6, z_index=2).overrides('alpha', stroke_width_px=4)
    # a round join drawn just before the polyline, whose corner is mitred
    d.overrides('m', right_angle_joint='round', z_index=1)
    d.label('C').overrides('C', label_halo_px=2)     # its halo strokes with round caps and joins
    return as_document(d.doc)


def _owner(scene):
    """``{id(mobject): element}`` of the strokes of the elements (the strokes
    of their labels — a halo — left out: those are round by design)."""
    owners = {}
    for el_id, name in scene.native_names.by_id.items():
        mob = scene.mobject(name)
        if mob is None:
            continue
        labels = {id(m) for node in mob.get_family() if getattr(node, '_animageo_is_label', False)
                  for m in node.get_family()}
        for member in mob.get_family():
            if id(member) not in labels and not getattr(member, '_animageo_is_halo', False):
                owners[id(member)] = el_id
    return owners


def _strokes(monkeypatch, style):
    """``{path: {element: Counter((cap, join))}}`` of the strokes the SVG, the
    PDF and the video camera draw, read from the cairo context as it strokes."""
    from manim import tempconfig

    import animageo.animageo as scene_module
    from animageo.native import rendering
    from animageo.parsers import svg_parser

    seen = []
    svg_stroke = svg_parser._apply_stroke

    def svg_spy(ctx, vmobject, style=None):
        out = svg_stroke(ctx, vmobject, style)
        if vmobject.get_stroke_width():
            seen.append((id(vmobject), CAPS[ctx.get_line_cap()], JOINS[ctx.get_line_join()]))
        return out

    camera_stroke = scene_module.DashCamera.apply_stroke

    def camera_spy(self, ctx, vmobject, background=False):
        out = camera_stroke(self, ctx, vmobject, background)
        if vmobject.get_stroke_width(background) and not background:
            seen.append((id(vmobject), CAPS[ctx.get_line_cap()], JOINS[ctx.get_line_join()]))
        return out

    monkeypatch.setattr(svg_parser, '_apply_stroke', svg_spy)
    monkeypatch.setattr(scene_module.DashCamera, 'apply_stroke', camera_spy)

    def collect(scene):
        owners = _owner(scene)
        out = collections.defaultdict(collections.Counter)
        for vid, cap, join in seen:
            if vid in owners:
                out[owners[vid]][(cap, join)] += 1
        seen.clear()
        return dict(out)

    doc = _doc()
    scene_class = rendering._import_scene()
    got = {}
    with tempfile.TemporaryDirectory() as tmp:
        scene = rendering._load(scene_class, doc, style, None, {})
        scene.exportSVG(tmp + '/a.svg')
        got['svg'] = collect(scene)
        scene.exportPDF(tmp + '/a.pdf')
        got['pdf'] = collect(scene)
        with tempconfig({'pixel_width': 400, 'pixel_height': 300, 'disable_caching': True,
                         'verbosity': 'ERROR', 'progress_bar': 'none', 'write_to_movie': False}):
            frame = rendering._load(scene_class, doc, style, None, {})
            frame.renderer.update_frame(frame, ignore_skipping=True)
            got['video'] = collect(frame)
    return doc, got


@pytest.mark.parametrize('style', STYLES)
def test_the_svg_the_pdf_and_the_video_frame_draw_the_caps_of_resolve_paint(monkeypatch, style):
    doc, got = _strokes(monkeypatch, style)
    assert got['svg'] == got['pdf']
    assert got['svg'] == got['video']
    paint = resolve_paint(doc, style)['elements']
    for el_id, strokes in got['svg'].items():
        caps = collections.Counter()
        for (cap, _join), n in strokes.items():
            caps[cap] += n
        expected = paint[el_id]['stroke']['cap'] or 'butt'
        assert caps[expected] >= 1, (el_id, caps)
        if el_id == 'a':                    # the ticks of the segment end butt
            assert caps == collections.Counter({expected: 1, 'butt': 2}), caps
        else:
            assert set(caps) == {expected}, (el_id, caps)
    # the caps of the style
    cap = (style or {}).get('rendering', {}).get('line_cap', 'butt')
    assert {el_id: paint[el_id]['stroke']['cap'] for el_id in ('a', 'b', 'v', 'k', 'r', 's')} == {
        'a': 'round', 'b': 'square', 'v': cap, 'k': cap, 'r': cap, 's': cap}
    assert {paint[el_id]['stroke']['cap'] for el_id in ('w', 'alpha', 'm')} == {None}


def _tikz(style):
    with tempfile.NamedTemporaryFile(suffix='.tex') as f:
        native.render(_doc(), fmt='tikz', out=f.name, style_config=style)
        return open(f.name, encoding='utf-8').read()


@pytest.mark.parametrize('style', STYLES)
def test_tikz_caps_only_the_capped_strokes(style):
    cap = (style or {}).get('rendering', {}).get('line_cap', 'butt')
    tikz = {'butt': None, 'round': 'round', 'square': 'rect'}[cap]
    draws = re.findall(r'\\draw\[([^\]]*)\] (.*);', _tikz(style))

    def cap_of(fragment):
        rows = [opts for opts, path in draws if fragment in path]
        assert len(rows) == 1, (fragment, rows)
        found = re.search(r'line cap=(\w+)', rows[0])
        return found.group(1) if found else None

    assert cap_of('(0,0) -- (5,0)') == 'round'                 # a: its own cap
    assert cap_of('(1.5,3.5) -- (0,0)') == 'rect'              # b: square
    assert cap_of('(0,0) -- (8.3333,4.1667)') == tikz          # r: the cap of the style
    assert cap_of('(1.5,3.5) -- (6,3)') == tikz                # v
    assert cap_of('(5,0) arc (0:66.8014:5)') == tikz           # k
    assert cap_of('plot coordinates {(5,0)(6,3)(1.5,3.5)}') is None   # w: a polyline
    assert cap_of('(0.17,0) arc') is None                       # alpha: the arc of an angle
    ticks = [opts for opts, path in draws if path.startswith('(2.49,') or path.startswith('(2.51,')]
    assert len(ticks) == 2 and all('line cap=butt' in opts for opts in ticks)
