"""The renderer draws the paint ``native.resolve_paint`` reports (1.11.0rc3):
for every scene of the fixtures ``animageo-paint-parity/v1`` without a
timeline, the render context of each drawn element (``_build_render_ctx``)
and the dash patterns it fits."""
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo.native import paint, paint_fixtures  # noqa: E402

# ── the renderer draws what resolve_paint says ──────────────────────────

def _scenes():
    for fixture in paint_fixtures.build_fixtures().values():
        for case in fixture['cases']:
            if case['timeline'] is None:
                yield case


@pytest.mark.parametrize('case', list(_scenes()), ids=lambda c: c['name'])
def test_the_renderer_draws_the_paint(case):
    pytest.importorskip('manim')
    from manim import ManimColor

    from animageo.animageo import _Z_AUTO_BY_TYPE, AnimaGeoScene
    from animageo.native.kernel.bridge import build_construction

    assert {cls.__name__: z for cls, z in _Z_AUTO_BY_TYPE.items()} == paint._Z_AUTO_BY_CLASS
    scene = AnimaGeoScene()
    scene.loadDocument(case['document'], style=case['style'])
    _, names = build_construction(case['document'])
    expect = case['expect']
    unit = expect['ptUnitStyle']
    assert unit == pytest.approx(paint._num(scene.style.export['ptUnit_style']))
    for el_id, entry in expect['elements'].items():
        if not entry['drawn']:
            continue
        elem = scene.geo.objectByName(names.by_id[el_id])
        ctx = scene._build_render_ctx(elem, True)
        where = f"{case['name']}.{el_id}"
        assert entry['z'] == pytest.approx(ctx.zz, abs=1e-9), where
        stroke = entry.get('stroke')
        if stroke is not None:
            if stroke['color'] is not None:
                assert ManimColor(stroke['color']).to_hex() == ctx.col_s.to_hex(), where
            assert stroke['opacity'] == pytest.approx(ctx.op_s), where
            assert stroke['widthPx'] == pytest.approx(ctx.lw * unit / 100), where
            if stroke['cap'] is not None:
                assert stroke['cap'] == ctx.cap, where
            if stroke.get('dash') is not None:
                assert [stroke['dash']['onPx'], stroke['dash']['offPx']] == pytest.approx(list(ctx.dash_px)), where
            else:
                assert ctx.dash_px is None or 'dash' not in stroke, where
        fill = entry.get('fill')
        if fill is not None and fill['color'] is not None:
            assert ManimColor(fill['color']).to_hex() == ctx.col_f.to_hex(), where
            assert fill['opacity'] == pytest.approx(ctx.op_f), where
        ticks = entry.get('ticks')
        if ticks is not None:
            assert (ticks['count'], ticks['style']) == (ctx.tick_count, ctx.tick_style), where
            assert ticks['lengthPx'] == pytest.approx(ctx.strich_len * unit), where
            assert ticks['widthPx'] == pytest.approx(ctx.strich_width * unit / 100), where
            assert ticks['shiftPx'] == pytest.approx(ctx.strich_rshift * unit), where
        if 'arrow' in entry:
            assert entry['arrow']['lengthPx'] == pytest.approx(ctx.arrow_height * unit), where
            assert entry['arrow']['widthPx'] == pytest.approx(ctx.arrow_width * unit), where
        if 'angle' in entry:
            angle = entry['angle']
            assert (angle['range'], angle['arcs'], angle['arcShiftPx'], angle['joint']) == \
                (ctx.angle_range, ctx.tick_count, ctx.arc_shift_px, ctx.ra_joint), where
        label = entry.get('label')
        if label is not None:
            halo = ctx.label_halo
            assert (label['halo']['widthPx'], label['halo']['color'], label['halo']['opacity']) == \
                (pytest.approx(halo['widthPx']), halo['color'], pytest.approx(halo['opacity'])), where
        if label is not None and label.get('shown'):
            assert ctx.has_label, where
            assert label['anchor'] == (ctx.label_anchor or 'BL'), where
            assert label['text'] == ctx.label_text, where
            assert ManimColor(label['color']).to_hex() == ctx.col_label.to_hex(), where


def test_the_drawn_dash_is_that_of_the_renderer():
    pytest.importorskip('manim')
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
