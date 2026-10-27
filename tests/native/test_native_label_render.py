"""Labels in the renderer (1.11.0): a name compiles as the TeX ``name_tex``
gives, and the halo ``resolve_paint`` reports is drawn — a stroke of the
label's glyphs under them, in SVG, PNG and the video, revealed by the effects
of the video with its glyphs."""
import logging
from pathlib import Path
import re

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import native  # noqa: E402
from animageo.native.paint import resolve_paint  # noqa: E402
from animageo.native.paint_fixtures import _Doc  # noqa: E402


def _doc():
    d = _Doc('halo').free('A', 0, 0).free('B', 4, 0)
    d.segment('s', 'A', 'B')
    d.look('s', label={'mode': 'name'})
    return d.doc


def _paths(svg_text):
    return re.findall(r'<path\b[^>]*>', svg_text)


def _attr(tag, name):
    m = re.search(r'\b' + name + r'="([^"]*)"', tag)
    if m:
        return m.group(1)
    m = re.search(r'\b' + name + r':\s*([^;"]+)', tag)
    return m.group(1).strip() if m else None


def _svg(doc, style):
    result = native.render(doc, style_config=style, fmt='svg', report=False)
    with open(result.path, encoding='utf-8') as f:
        return f.read()


def _hex(value):
    """``#rrggbb`` of an SVG colour (``rgb(p%, p%, p%)`` of the cairo writer)."""
    value = (value or '').strip().lower()
    m = re.fullmatch(r'rgb\(([\d.]+)%,\s*([\d.]+)%,\s*([\d.]+)%\)', value)
    if m:
        return '#' + ''.join(f'{round(float(c) * 2.55):02x}' for c in m.groups())
    return value


def _width(tag):
    """The stroke width of ``tag`` in pixels of the file (its transform applied)."""
    width = float(_attr(tag, 'stroke-width'))
    m = re.search(r'matrix\(([-\d.e]+),\s*([-\d.e]+)', tag)
    return width * (abs(float(m.group(1))) if m else 1.0)


def _filled(tag):
    return (_attr(tag, 'fill') or 'none').lower() != 'none'


def _halo_paths(svg_text, color):
    return [tag for tag in _paths(svg_text)
            if not _filled(tag) and _hex(_attr(tag, 'stroke')) == color
            and _attr(tag, 'stroke-linejoin') == 'round']


@pytest.mark.parametrize('name', ['A_1', 'A_12', 'B_{12}', 'angle_C', 'a_', 'b__2', 'A_}', 'A_{1', 'A^',
                                  r'\alpha_1', 'my_ point', 'Точка_1', 'A_Δ', 'S_бок',
                                  'A%B', 'A#1', 'A&B', 'A$B', 'A~B', 'P_%', 'P_$', 'P_~',
                                  'A!"#$%&\'()*+,-./:;<=>?@[]^_`{|}~B'])
def test_a_name_compiles(name):
    from manim import Tex

    from animageo.labels import correctedLabel, name_tex
    from animageo.ui import RusTex
    Tex(correctedLabel('$' + name_tex(name) + '$'), tex_template=RusTex)


@pytest.mark.parametrize('name, reference', [('A₁', 'A_{1}'), ('B₁₂', 'B_{12}'), ('M₀', 'M_{0}')])
def test_unicode_subscript_name_reaches_the_svg(name, reference, tmp_path, caplog):
    doc = _Doc('subscript').free('P', 0, 0).doc

    def render(display_name, filename):
        doc['elements']['P']['displayName'] = display_name
        result = native.render(doc, fmt='svg', out=tmp_path / filename, report=True)
        assert len(_paths(Path(result.path).read_text(encoding='utf-8'))) > 1
        label = result.report['elements']['P']['label']
        assert label is not None
        x0, y0, x1, y1 = label['box']
        return x1 - x0, y1 - y0

    with caplog.at_level(logging.WARNING, logger='animageo.ui'):
        actual = render(name, 'unicode.svg')
        expected = render(reference, 'tex.svg')
    assert actual == pytest.approx(expected, abs=0.01)
    assert 'LaTeX compile failed' not in caplog.text
    assert 'plain-text fallback failed' not in caplog.text


@pytest.mark.parametrize('caption', ['A₁B₁', '$A₁B₁$'])
def test_unicode_subscript_caption_reaches_the_svg(caption, tmp_path, caplog):
    d = _Doc('subscript-caption').free('P', 0, 0)
    d.look('P', label={'mode': 'caption', 'text': caption})
    with caplog.at_level(logging.WARNING, logger='animageo.ui'):
        result = native.render(d.doc, fmt='svg', out=tmp_path / 'caption.svg', report=True)
    assert result.report['elements']['P']['label'] is not None
    assert len(_paths(Path(result.path).read_text(encoding='utf-8'))) == 5  # point and four glyphs
    assert 'LaTeX compile failed' not in caplog.text
    assert 'plain-text fallback failed' not in caplog.text


def test_unicode_subscripts_compile_in_plain_text_fallback():
    from manim import Tex

    from animageo.ui import RusTex, _label_plain_text
    label = Tex(_label_plain_text('A₁B₁'), tex_template=RusTex)
    assert len(label.family_members_with_points()) == 4


def test_no_halo_by_default():
    svg = _svg(_doc(), None)
    assert _halo_paths(svg, '#ffffff') == []


def test_the_svg_draws_the_halo_of_the_paint():
    doc = _doc()
    style = {'rendering': {'label_halo_px': 3, 'label_halo_color': '#ffee00'}}
    paint = resolve_paint(doc, style)
    halo = paint['elements']['s']['label']['halo']
    assert halo == {'widthPx': 3.0, 'color': '#ffee00', 'opacity': 1.0}
    svg = _svg(doc, style)
    halos = _halo_paths(svg, '#ffee00')
    # one stroke per glyph of each shown label (A, B and s)
    assert len(halos) == 3
    scale = paint['ptUnit'] / paint['ptUnitStyle']
    paths = _paths(svg)
    for tag in halos:
        assert _width(tag) == pytest.approx(3.0 * scale, rel=1e-3)
        # under its glyph: the glyph is the next path of the file
        assert _filled(paths[paths.index(tag) + 1])


def test_an_element_sets_its_own_halo():
    doc = _doc()
    doc['appearance'].setdefault('s', {})['overrides'] = {'label_halo_px': 2, 'label_halo_color': '#00ff00',
                                                          'label_halo_opacity': 0.5}
    svg = _svg(doc, None)
    halos = _halo_paths(svg, '#00ff00')
    assert len(halos) == 1
    assert float(_attr(halos[0], 'stroke-opacity')) == pytest.approx(0.5)
    assert _halo_paths(svg, '#ffffff') == []


def test_the_render_context_holds_the_halo():
    from animageo.animageo import AnimaGeoScene
    from animageo.native.kernel.bridge import build_construction
    doc = _doc()
    style = {'rendering': {'label_halo_px': 2.5}}
    scene = AnimaGeoScene()
    scene.loadDocument(doc, style=style)
    _, names = build_construction(doc)
    paint = resolve_paint(doc, style)
    for el_id in ('A', 'B', 's'):
        ctx = scene._build_render_ctx(scene.geo.objectByName(names.by_id[el_id]), True)
        assert ctx.label_halo == paint['elements'][el_id]['label']['halo']


def _label_group(scene, names, el_id):
    mobj = scene.mobject(names.by_id[el_id])
    return next(m for m in mobj.get_family() if getattr(m, '_animageo_is_label', False))


def test_the_write_effect_reveals_the_halo_with_its_glyph():
    from animageo.animageo import AnimaGeoScene
    from animageo.native.kernel.bridge import build_construction
    doc = _doc()
    doc['appearance'].setdefault('s', {})['label'] = {'mode': 'caption', 'text': 'abcd'}
    scene = AnimaGeoScene()
    scene.loadDocument(doc, style={'rendering': {'label_halo_px': 3}})
    _, names = build_construction(doc)
    name = names.by_id['s']
    scene._effect_write(scene.mobject(name), 0.5)
    label = _label_group(scene, names, 's')
    leaves = label.family_members_with_points()
    glyphs = [m for m in leaves if not getattr(m, '_animageo_is_halo', False)]
    halos = [m for m in leaves if getattr(m, '_animageo_is_halo', False)]
    assert len(halos) == len(glyphs) == 4
    for glyph, halo in zip(glyphs, halos):
        assert (glyph.get_fill_opacity() > 0) == (halo.get_stroke_opacity() > 0)
    assert sum(1 for h in halos if h.get_stroke_opacity() > 0) in (1, 2, 3)


def test_the_create_effect_fades_the_halo():
    from animageo.animageo import AnimaGeoScene
    from animageo.native.kernel.bridge import build_construction
    doc = _doc()
    scene = AnimaGeoScene()
    scene.loadDocument(doc, style={'rendering': {'label_halo_px': 3}})
    _, names = build_construction(doc)
    label = _label_group(scene, names, 's')
    halos = [m for m in label.family_members_with_points() if getattr(m, '_animageo_is_halo', False)]
    before = [h.points.copy() for h in halos]
    scene._effect_partial(scene.mobject(names.by_id['s']), 0.5)
    for h, pts in zip(halos, before):
        assert h.get_stroke_opacity() == pytest.approx(0.5)
        assert len(h.points) == len(pts)
