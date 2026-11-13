"""Regions (registry 1.9) in paint and output: the default paint is that of a
polygon of the fill tool (no stroke), the classic ``Region`` of the bridge
draws the rings with their holes (nonzero over oriented rings in cairo, the
even-odd rule in TikZ), the hatch runs over the flattened rings, JSXGraph
gets a static filled curve."""
import math

import numpy as np
import pytest

from animageo import native
from animageo.hatch import pattern_segments
from animageo.native.kernel import region as R
from animageo.native.kernel.bridge import from_classic, to_classic
from tests.native.conftest import ref
from tests.native.test_native_area_between import Doc, poly

ACCENT = '#d05456'
# the appearance the web fill tool writes (canvas/fill/actions.ts)
FILL_TOOL = {'visible': True, 'label': {'mode': 'none'},
             'overrides': {'fill': '#3366cc', 'stroke_opacity': 0, 'stroke_width_px': 0}}


def annulus(r_out=2.0, r_in=1.0):
    """A disc of ``r_out`` with a hole of ``r_in``: a full arc is a piece whose
    start is its end."""
    def full(r):
        return [[r, 0.0], [r, 0.0], [0.0, 0.0, r]]
    return {'rings': [[full(r_out)], [full(r_in)]], 'shape': [[['ccw', 'inside.0']], [['cw', 'outside.0']]],
            'area': math.pi * (r_out ** 2 - r_in ** 2)}


def area_doc(appearance=None, polygon=False, a=None, b=None):
    d = Doc(bounds=(-3, -3, 3, 3))
    d.function('f', poly(1, 0, -1))
    d.area('S', 'f', a=a, b=b)
    if polygon:
        d.free('A', -2.5, -2.5).free('B', -1.5, -2.5).free('C', -2.0, -1.5)
        d.op('op_t', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [ref(v) for v in 'ABC']}},
             [('polygon', 't', 'polygon')])
        for v in 'ABC':
            d.doc['elements'][v]['displayName'] = ''
    if appearance:
        d.doc['appearance'] = appearance
    return d.doc


# ── paint (no manim) ──────────────────────────────────────────────────────

def test_the_default_paint_is_the_fill_of_a_polygon_without_a_stroke():
    paint = native.resolve_paint(area_doc(polygon=True))
    region, polygon = paint['elements']['S'], paint['elements']['t']
    assert region['fill']['color'] == ACCENT
    assert region['fill']['opacity'] == polygon['fill']['opacity'] == 1.0
    assert region['stroke']['opacity'] == 0.0 and region['stroke']['widthPx'] == 0.0
    assert region['fill']['pattern'] == 'solid' and region['fill']['hatch'] is None
    assert round(region['fill']['z'], 3) == round(polygon['fill']['z'], 3) == 0.01
    assert region['label']['anchor'] == 'MC' and region['label']['shown'] is False


def test_the_fill_tool_paints_a_region_as_it_paints_a_polygon():
    paint = native.resolve_paint(area_doc({'S': FILL_TOOL, 't': FILL_TOOL}, polygon=True))
    region, polygon = paint['elements']['S'], paint['elements']['t']
    for key in ('color', 'opacity', 'isBackground', 'pattern', 'hatch'):
        assert region['fill'][key] == polygon['fill'][key], key
    assert region['fill']['color'] == '#3366cc'
    assert round(region['fill']['z'], 3) == round(polygon['fill']['z'], 3)
    for key in ('opacity', 'widthPx'):
        assert region['stroke'][key] == polygon['stroke'][key] == 0.0


def test_the_keys_of_a_region():
    keys = native.style_keys()['types']['region']
    assert keys['style'] == 'region'
    assert {'fill', 'fill_opacity', 'fill_pattern', 'hatch_spacing_px', 'stroke_dash_period_px', 'z_index_fill',
            'label_value_precision'} <= set(keys['keys'])
    assert keys['keys']['fill_opacity']['default'] == 1


def test_a_dash_is_fitted_to_each_ring():
    appearance = {'S': {'overrides': {'stroke_opacity': 1, 'stroke_width_px': 2, 'stroke_dash_ratio': 0.5,
                                      'stroke_dash_period_px': 8}}}
    doc = area_doc(appearance, a=-2.0, b=2.0)
    value = native.evaluate(doc).elements['S']['value']
    assert len(value['rings']) == 3
    dash = native.resolve_paint(doc)['elements']['S']['stroke']['dash']
    assert dash['fit'] == 'closed' and dash['drawn'] is None
    assert len(dash['rings']) == 3
    for i, ring in enumerate(dash['rings']):
        periods = R.ring_length(value, i) * native.resolve_paint(doc)['ptUnitStyle'] / (ring['onPx'] + ring['offPx'])
        assert periods == pytest.approx(round(periods), abs=1e-6)


def test_a_hatched_region_has_the_hatch_in_its_paint():
    appearance = {'S': {'overrides': {'fill_pattern': 'crosshatch', 'hatch_spacing_px': 9}}}
    fill = native.resolve_paint(area_doc(appearance))['elements']['S']['fill']
    assert fill['pattern'] == 'crosshatch'
    assert fill['hatch']['spacingPx'] == 9.0


def test_the_value_label_is_the_area_at_the_label_anchor():
    appearance = {'S': {'label': {'mode': 'value'}}}
    doc = area_doc(appearance)
    label = native.resolve_paint(doc)['elements']['S']['label']
    assert label['shown'] is True
    assert label['text'] == '$1.3$'
    spot = R.label_anchor(native.evaluate(doc).elements['S']['value'])
    assert label['spotWorld'] == [pytest.approx(spot[0], abs=1e-6), pytest.approx(spot[1], abs=1e-6)]


# ── the bridge and the hatch (no manim) ───────────────────────────────────

def test_the_bridge_carries_the_kernel_value():
    from animageo.geo.lib_elements import Region
    from animageo.labels import label_value_of
    value = annulus()
    obj = to_classic('region', value)
    assert isinstance(obj, Region)
    assert from_classic('region', obj) is value
    assert obj.area == pytest.approx(3 * math.pi)
    assert label_value_of(obj).value == pytest.approx(3 * math.pi)


def test_the_hatch_skips_the_hole():
    rings = R.flatten(annulus())
    segs = pattern_segments({'rings': rings}, 'hatch', math.radians(30), 0.25)
    assert segs
    for x0, y0, x1, y1 in segs:
        for t in np.linspace(0, 1, 11):
            r = math.hypot(x0 + t * (x1 - x0), y0 + t * (y1 - y0))
            assert 1.0 - 1e-3 <= r <= 2.0 + 1e-3


# ── output (manim) ────────────────────────────────────────────────────────

def _scene_with(value):
    """The scene of ``area_doc`` with the region drawn as ``value``."""
    pytest.importorskip('manim')
    from animageo.animageo import AnimaGeoScene
    from animageo.geo.lib_elements import Region
    scene = AnimaGeoScene()
    scene.loadDocument(area_doc(), export={'size': {'width': 300, 'height': 300}})
    elem = next(e for e in scene.geo.elements if isinstance(e.data, Region))
    elem.data = Region(value)
    return scene, elem


def _rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def test_cairo_keeps_the_hole():
    """SVG, PDF and EPS (``svg_parser``) and the camera of PNG and video fill
    the oriented rings by cairo's nonzero rule: the hole stays empty."""
    pytest.importorskip('manim')
    import cairo
    from manim.camera.camera import Camera
    from animageo.parsers.svg_parser import _create_svg_from_vmobject_internal
    scene, elem = _scene_with(annulus())
    fill = scene.CreateMObject(elem)[0]
    assert len(fill.get_subpaths()) == 2

    camera = Camera(pixel_width=200, pixel_height=200, frame_width=5, frame_height=5, background_color='#ffffff')
    camera.capture_mobject(fill)
    image = np.array(camera.get_image().convert('RGB'))
    assert tuple(image[100, 100]) == (255, 255, 255)
    assert tuple(image[100, 160]) == _rgb(ACCENT)

    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 200, 200)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    ctx.set_matrix(cairo.Matrix(40, 0, 0, -40, 100, 100))
    _create_svg_from_vmobject_internal(fill, ctx)
    data = np.ndarray((200, 200, 4), dtype=np.uint8, buffer=surface.get_data())
    assert tuple(data[100, 100][2::-1]) == (255, 255, 255)        # BGRA
    assert tuple(data[100, 160][2::-1]) == _rgb(ACCENT)


def test_the_svg_fills_the_region_with_its_paint(tmp_path):
    pytest.importorskip('manim')
    out = native.render(area_doc({'S': FILL_TOOL}), fmt='svg', out=str(tmp_path / 'a.svg'))
    svg = open(out.path).read()
    assert 'fill="rgb(20%, 40%, 80%)"' in svg
    assert out.report['elements']['S']['state'] == 'defined'


def test_tikz_fills_the_rings_by_the_even_odd_rule():
    scene, _elem = _scene_with(annulus())
    tex = scene.exportTikZ()
    line = next(l for l in tex.splitlines() if 'even odd rule' in l)
    assert line.count('arc (') == 2 and line.count('-- cycle') == 2
    assert 'arc (0:360:2)' in line and 'arc (0:-360:1)' in line
    assert '\\draw' not in line


def test_tikz_hatches_the_rings():
    scene, elem = _scene_with(annulus())
    elem.style['fill_pattern'] = 'hatch'
    tex = scene.exportTikZ()
    assert 'even odd rule' not in tex
    assert any('--' in l and 'line width' in l for l in tex.splitlines())


def test_jsxgraph_draws_a_static_filled_curve():
    pytest.importorskip('manim')
    from animageo.exporters.jsxgraph.builder import build_board
    from animageo.exporters.jsxgraph.options import JSXGraphOptions
    scene, elem = _scene_with(annulus())
    model = build_board(scene, JSXGraphOptions())
    assert (elem.name, 'static') in {(name, kind) for name, kind, _ in model.coverage}
    stmt = next(s for s in model.statements if f'"{elem.name}"' in s and '"curve"' in s)
    assert stmt.count('NaN') == 2           # x and y: one break between the two rings
    assert 'fillColor' in stmt and 'fillOpacity' in stmt


def boundary_annulus_doc(appearance=None):
    """Registry 1.9 rc2: a disc of radius 2 with a hole of radius 1 by ``region.by_boundary``."""
    from tests.native.conftest import ref_list
    d = Doc(bounds=(-3, -3, 3, 3)).free('O', 0, 0).free('T', 2, 0).free('U', 1, 0)
    d.circle('big', 'O', 'T').circle('small', 'O', 'U')
    d.op('op_S', 'region.by_boundary', {'curves': ref_list(), 'from': ref_list(), 'to': ref_list(),
                                        'inside': ref_list('big'), 'outside': ref_list('small')},
         [('region', 'S', 'region')])
    d.doc['appearance'] = {'big': {'visible': False}, 'small': {'visible': False}, 'O': {'visible': False},
                           'T': {'visible': False}, 'U': {'visible': False}, **(appearance or {})}
    return d.doc


def test_the_bridge_draws_a_boundary_region_with_its_hole():
    """The classic ``Region`` of a ``region.by_boundary`` annulus (§9.3): the
    colour and the opacity of its paint, the hole empty by nonzero."""
    pytest.importorskip('manim')
    from manim.camera.camera import Camera
    from animageo.animageo import AnimaGeoScene
    from animageo.geo.lib_elements import Region
    doc = boundary_annulus_doc({'S': FILL_TOOL})
    paint = native.resolve_paint(doc)['elements']['S']
    scene = AnimaGeoScene()
    scene.loadDocument(doc, export={'size': {'width': 300, 'height': 300}})
    elem = next(e for e in scene.geo.elements if isinstance(e.data, Region))
    assert elem.data.area == pytest.approx(3 * math.pi)
    fill = scene.CreateMObject(elem)[0]
    assert len(fill.get_subpaths()) == 2
    assert fill.get_fill_color().to_hex().lower() == paint['fill']['color'].lower() == '#3366cc'
    assert fill.get_fill_opacity() == pytest.approx(paint['fill']['opacity'])
    camera = Camera(pixel_width=200, pixel_height=200, frame_width=5, frame_height=5, background_color='#ffffff')
    camera.capture_mobject(fill)
    image = np.array(camera.get_image().convert('RGB'))
    assert tuple(image[100, 100]) == (255, 255, 255)
    assert tuple(image[100, 160]) == _rgb('#3366cc')
