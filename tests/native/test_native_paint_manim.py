"""The renderer draws the paint ``native.resolve_paint`` reports (1.11.0rc3):
for every scene of the fixtures ``animageo-paint-parity/v1`` the render
context of each drawn element (``_build_render_ctx``) and what it draws —
the colour, opacity, width and cap of the stroke layer, the font size of the
label text, the layers of the fill and the label, the size and the shape of a point, the
hatch, the lines or the wave of the ticks, the radii of the arcs of an angle
and the corners of a right-angle square, the dash patterns. A scene with a
timeline is the frame ``render(t)`` draws (1.11.0): the document loaded as
the video loads it and the timeline seeked to ``t`` — its style tracks, the
elements in the frame."""
import math

import numpy as np
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo.native import paint, paint_fixtures  # noqa: E402

# ── the renderer draws what resolve_paint says ──────────────────────────


def _scenes(timeline=False):
    for fixture in paint_fixtures.build_fixtures().values():
        for case in fixture['cases']:
            if (case['timeline'] is not None) == timeline:
                yield case


@pytest.fixture
def drawn(monkeypatch):
    """What the renderer passes to the builders of a point and of a wave,
    by element name: ``{'point': {name: (shape, radius)}, 'wave': {name:
    (corners, radius)}}``."""
    import animageo.animageo as scene_module
    seen = {'point': {}, 'wave': {}}
    current = {'name': None}
    build_ctx = scene_module.AnimaGeoScene._build_render_ctx
    make_point = scene_module.AnimaGeoScene._make_point_mobject
    round_corners = scene_module.round_corners_vmobject

    def build_ctx_spy(self, elem, z_auto):
        current['name'] = elem.name
        return build_ctx(self, elem, z_auto)

    def make_point_spy(shape, pos, radius, *args, **kwargs):
        seen['point'][current['name']] = (shape, radius)
        return make_point(shape, pos, radius, *args, **kwargs)

    def round_corners_spy(points, radius, **kwargs):
        seen['wave'][current['name']] = ([list(p[:2]) for p in points], radius)
        return round_corners(points, radius=radius, **kwargs)

    monkeypatch.setattr(scene_module.AnimaGeoScene, '_build_render_ctx', build_ctx_spy)
    monkeypatch.setattr(scene_module.AnimaGeoScene, '_make_point_mobject', staticmethod(make_point_spy))
    monkeypatch.setattr(scene_module, 'round_corners_vmobject', round_corners_spy)
    return seen


def _load(case):
    from animageo.animageo import AnimaGeoScene
    from animageo.native import rendering
    from animageo.native.document import as_document
    if case['timeline'] is None:
        scene = AnimaGeoScene()
        scene.loadDocument(case['document'], style=case['style'])
        return scene
    return rendering._still_scene(as_document(case['document']), case['style'], None, {},
                                  case['timeline'], case['t'])


@pytest.mark.parametrize('case', list(_scenes()) + list(_scenes(timeline=True)), ids=lambda c: c['name'])
def test_the_renderer_draws_the_paint(case, drawn):
    from manim import ManimColor

    from animageo.animageo import _Z_AUTO_BY_TYPE
    from animageo.constants import GGB_FONT_SCALE
    from animageo.native.kernel.bridge import build_construction

    assert {cls.__name__: z for cls, z in _Z_AUTO_BY_TYPE.items()} == paint._Z_AUTO_BY_CLASS
    scene = _load(case)
    _, names = build_construction(case['document'])
    expect = case['expect']
    unit = expect['ptUnitStyle']
    assert unit == pytest.approx(paint._num(scene.style.export['ptUnit_style']))
    for el_id, entry in expect['elements'].items():
        name = names.by_id[el_id]
        if not entry['drawn']:
            if case['timeline'] is not None:      # not in the frame
                assert scene.mobject(name) is None or scene.mobject(name) not in scene.mobjects, el_id
            continue
        elem = scene.geo.objectByName(name)
        group = scene.mobject(name)
        where = f"{case['name']}.{el_id}"
        assert group is not None, where
        ctx = scene._build_render_ctx(elem, True)
        assert entry['z'] == pytest.approx(ctx.zz, abs=1e-9), where
        stroke = entry.get('stroke')
        if stroke is not None:
            if stroke['color'] is not None:
                assert ManimColor(stroke['color']).to_hex() == ctx.col_s.to_hex(), where
            assert stroke['opacity'] == pytest.approx(ctx.op_s), where
            assert stroke['widthPx'] == pytest.approx(ctx.lw * unit / 100), where
            if stroke['cap'] is not None:
                assert stroke['cap'] == ctx.cap, where
            hidden = (entry.get('point') or {}).get('display') == 'only_labels'
            _assert_drawn_stroke(stroke, group, unit, where, hidden=hidden, alpha=_fade_alpha(entry))
            if stroke.get('dash') is not None:
                assert [stroke['dash']['onPx'], stroke['dash']['offPx']] == pytest.approx(list(ctx.dash_px)), where
            else:
                assert ctx.dash_px is None or 'dash' not in stroke, where
        fill = entry.get('fill')
        if fill is not None and fill['color'] is not None:
            assert ManimColor(fill['color']).to_hex() == ctx.col_f.to_hex(), where
            assert fill['opacity'] == pytest.approx(ctx.op_f), where
        if fill is not None and 'z' in fill:
            assert fill['z'] == pytest.approx(group.submobjects[0].z_index, abs=1e-9), where
        if fill is not None and fill.get('hatch') is not None:
            _assert_hatch(fill['hatch'], group.submobjects[0], unit, where)
        point = entry.get('point')
        if point is not None:
            shape, radius = drawn['point'][name]
            assert (point['shape'], point['sizePx']) == (shape, pytest.approx(2 * radius * unit)), where
        ticks = entry.get('ticks')
        if ticks is not None:
            assert (ticks['count'], ticks['style']) == (ctx.tick_count, ctx.tick_style), where
            assert ticks['lengthPx'] == pytest.approx(ctx.strich_len * unit), where
            assert ticks['widthPx'] == pytest.approx(ctx.strich_width * unit / 100), where
            assert ticks['shiftPx'] == pytest.approx(ctx.strich_rshift * unit), where
            _assert_ticks(ticks, group, drawn['wave'].get(name), where)
        if 'arrow' in entry:
            assert entry['arrow']['lengthPx'] == pytest.approx(ctx.arrow_height * unit), where
            assert entry['arrow']['widthPx'] == pytest.approx(ctx.arrow_width * unit), where
        if 'angle' in entry:
            angle = entry['angle']
            assert (angle['range'], angle['arcs'], angle['arcShiftPx'], angle['joint']) == \
                (ctx.angle_range, ctx.tick_count, ctx.arc_shift_px, ctx.ra_joint), where
            _assert_angle(angle, elem, group, unit, where)
        label = entry.get('label')
        if label is not None:
            halo = ctx.label_halo
            assert (label['halo']['widthPx'], label['halo']['color'], label['halo']['opacity']) == \
                (pytest.approx(halo['widthPx']), halo['color'], pytest.approx(halo['opacity'])), where
            assert label['fontSizePx'] * GGB_FONT_SCALE / unit == pytest.approx(ctx.font_size), where
        if label is not None and label.get('shown'):
            assert ctx.has_label, where
            assert label['anchor'] == (ctx.label_anchor or 'BL'), where
            assert label['text'] == ctx.label_text, where
            assert ManimColor(label['color']).to_hex() == ctx.col_label.to_hex(), where
            assert label['z'] == pytest.approx(ctx.zz_label, abs=1e-9), where
            drawn_label = [m for m in group.get_family() if getattr(m, '_animageo_is_label', False)]
            assert drawn_label and drawn_label[0].z_index == pytest.approx(label['z'], abs=1e-9), where
            sizes = _drawn_font_sizes(drawn_label[0])
            assert sizes, where
            for size in sizes:
                assert label['fontSizePx'] * GGB_FONT_SCALE / unit == pytest.approx(size, rel=1e-6), where


def _fade_alpha(entry):
    """The factor a fade of the frame puts on the opacity of what is drawn:
    ``progress`` of an entrance, ``1 − progress`` of an exit (``effect`` of
    the entry; the other effects draw part of the element, not less of it)."""
    effect = entry.get('effect')
    if effect is None or effect['effect'] != 'fade':
        return 1.0
    return effect['progress'] if effect['phase'] == 'enter' else 1.0 - effect['progress']


def _assert_drawn_stroke(stroke, group, unit, where, hidden=False, alpha=1.0):
    """The stroke the renderer draws: the first glyph-free layer of the
    element at the layer of its stroke (the line of a segment, the outline of
    a polygon or a point, the arc of an angle; ticks, labels and halos come
    after it or sit apart) — its colour, opacity (times the fade of the frame,
    ``alpha``), width and cap. A point of ``points_display: only_labels``
    (``point.display``) is drawn transparent."""
    from manim import ManimColor

    from animageo.animageo import _CAP_MAP
    layers = [m for m in group.family_members_with_points()
              if not _in_label(m, group) and abs(m.z_index - stroke['z']) < 1e-9]
    assert layers, where
    layer = layers[0]
    if hidden:
        assert (layer.get_stroke_opacity(), layer.get_fill_opacity()) == (0, 0), where
        return
    if stroke['color'] is not None:
        assert ManimColor(stroke['color']).to_hex() == layer.get_stroke_color().to_hex(), where
    assert stroke['opacity'] * alpha == pytest.approx(layer.get_stroke_opacity()), where
    assert stroke['widthPx'] == pytest.approx(layer.get_stroke_width() * unit / 100), where
    if stroke['cap'] is not None:
        assert _CAP_MAP[stroke['cap']] == layer.cap_style, where


def _in_label(mob, group):
    """Whether ``mob`` belongs to a label (or its halo) of ``group``."""
    return any(mob in m.get_family() for m in group.get_family()
               if getattr(m, '_animageo_is_label', False))


def _drawn_font_sizes(label):
    """The font size of each text piece of a drawn label: the ``Tex`` itself,
    or the prefix, the number and the suffix of a ``ValueLabel`` — measured
    from what is drawn (the height against the height at creation)."""
    from manim import DecimalNumber, SingleStringMathTex

    from animageo.ui import ValueLabel
    if isinstance(label, ValueLabel):
        parts = [p for p in (label.prefix, label.value, label.suffix) if p is not None]
    else:
        parts = [label]
    sizes = []
    for part in parts:
        assert isinstance(part, (SingleStringMathTex, DecimalNumber)), type(part)
        sizes.append(part.font_size)
    return sizes


def _ends(mob):
    """The two ends of each straight piece of ``mob`` (a path of lines)."""
    pts = np.asarray(mob.points)[:, :2]
    return [(pts[i], pts[i + 3]) for i in range(0, len(pts), 4)]


def _assert_hatch(hatch, layer, unit, where):
    from manim import ManimColor
    if hatch['pattern'] == 'dots':
        assert ManimColor(hatch['color']).to_hex() == layer.get_fill_color().to_hex(), where
        assert hatch['opacity'] == pytest.approx(layer.get_fill_opacity()), where
        pts = np.asarray(layer.points)[:, :2].reshape(-1, 16, 2)
        centers = pts.mean(axis=1)
        radius = (pts[0, :, 0].max() - pts[0, :, 0].min()) / 2
        assert hatch['widthPx'] == pytest.approx(radius * unit), where
        gaps = np.hypot(*(centers[1:] - centers[0]).T)
        assert hatch['spacingPx'] == pytest.approx(gaps.min() * unit), where
        return
    assert ManimColor(hatch['color']).to_hex() == layer.get_stroke_color().to_hex(), where
    assert hatch['opacity'] == pytest.approx(layer.get_stroke_opacity()), where
    assert hatch['widthPx'] == pytest.approx(layer.get_stroke_width() * unit / 100), where
    base = math.radians(hatch['angleDeg'])
    families = [base] + ([base + math.pi / 2] if hatch['pattern'] == 'crosshatch' else [])
    by_family = {i: [] for i in range(len(families))}
    for a, b in _ends(layer):
        direction = math.atan2(b[1] - a[1], b[0] - a[0])
        match = [i for i, f in enumerate(families) if abs(math.sin(direction - f)) < 1e-9]
        assert len(match) == 1, where
        f = families[match[0]]
        by_family[match[0]].append(-a[0] * math.sin(f) + a[1] * math.cos(f))
    for offsets in by_family.values():
        steps = np.diff(np.unique(np.round(offsets, 9)))
        assert len(steps) and hatch['spacingPx'] == pytest.approx(steps.min() * unit), where


def _assert_ticks(ticks, group, wave, where):
    if ticks['count'] <= 0:
        return
    if ticks['style'] == 'wave':
        corners, radius = wave
        assert np.allclose(ticks['wave'], corners, rtol=0, atol=1e-9), where
        assert ticks['cornerRadius'] == pytest.approx(radius, abs=1e-12), where
        return
    pieces = [end for m in group.get_family() if len(m.points) == 4 for end in [_ends(m)[0]]]
    for x1, y1, x2, y2 in ticks['lines']:
        line = (np.array([x1, y1]), np.array([x2, y2]))
        assert any(np.allclose(a, line[0], atol=1e-9) and np.allclose(b, line[1], atol=1e-9) or
                   np.allclose(a, line[1], atol=1e-9) and np.allclose(b, line[0], atol=1e-9)
                   for a, b in pieces), where


def _assert_angle(angle, elem, group, unit, where):
    vertex = np.asarray(elem.data.vertex[:2], float)
    if angle['right']:
        stroke = group.submobjects[1]
        anchors = np.asarray(stroke.points)[:, :2]
        corners = [anchors[0]] + [anchors[i + 3] for i in range(0, len(anchors), 4)]
        assert np.allclose(corners, angle['square'], atol=1e-9), where
        return
    arcs = group.submobjects[1:1 + angle['arcs']]
    assert len(arcs) == len(angle['arcRadiiPx']), where
    for arc, radius_px in zip(arcs, angle['arcRadiiPx']):
        anchors = np.asarray(arc.points)[::4, :2]
        assert np.hypot(*(anchors - vertex).T) * unit == pytest.approx(radius_px, rel=1e-9), where


def test_the_drawn_dash_is_that_of_the_renderer():
    from animageo.animageo import AnimaGeoScene
    from animageo.dash import get_dash
    from animageo.native.kernel.bridge import build_construction

    case = next(c for c in _scenes() if c['name'] == 'dash_fit')
    scene = AnimaGeoScene()
    scene.loadDocument(case['document'])
    _, names = build_construction(case['document'])
    unit = case['expect']['ptUnitStyle']
    for el_id, rel in (('a', 1e-9), ('l', 1e-9), ('k', 1e-3), ('c', 1e-3)):
        drawn = case['expect']['elements'][el_id]['stroke']['dash']['drawn']
        group = scene.mobject(names.by_id[el_id])
        patterns = [get_dash(m) for m in group.get_family() if get_dash(m) is not None]
        assert len(patterns) == 1, el_id
        p = patterns[0]
        assert p.on * unit == pytest.approx(drawn['onPx'], rel=rel), el_id
        assert p.off * unit == pytest.approx(drawn['offPx'], rel=rel), el_id
