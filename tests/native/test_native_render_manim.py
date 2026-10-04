"""``native.render`` and ``AnimaGeoScene.loadDocument`` (needs manim and LaTeX)."""
import math
import re
import struct
from collections import Counter

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import AnimaGeoScene, native  # noqa: E402
from animageo.label_placement import DEFAULT_CONFIG  # noqa: E402
from tests.native.conftest import DocBuilder, path_input, point_input  # noqa: E402

BOUNDS = (-6, -4, 6, 4)


def builder(doc_id, bounds=BOUNDS):
    return DocBuilder(doc_id, registry_version='1.1', bounds=bounds)


def no_labels(doc):
    doc['appearance'] = {e: {'label': {'mode': 'none'}} for e in doc['elements']}
    return doc


def path_tags(svg_path):
    with open(svg_path, encoding='utf-8') as fh:
        return Counter(re.findall(r'<path[^>]*>', fh.read()))


def to_px(report, x, y):
    canvas = report['canvas']
    return canvas['origin'][0] + canvas['unit'] * x, canvas['origin'][1] - canvas['unit'] * y


def center(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


# ── report ───────────────────────────────────────────────────────────────

def demo():
    b = builder('render_demo')
    b.free('A', -4, -2).free('B', 4, -2).free('C', 1, 3).free('F', 2, 2)
    b.polygon('T', 'A', 'B', 'C', sides=[(1, 'a'), (2, 'b'), (3, 'c')])
    b.midpoint('M', 'A', 'B').circle('k', 'M', 'C').on_path('P', 'k', 1.0)
    b.circle('z', 'F', 'F')                                   # zero radius: undefined
    b.doc['appearance'] = {'k': {'overrides': {'stroke': '#cc3333', 'bogus': 1}},
                           'M': {'visible': False}}
    return b.doc


def test_svg_and_report(tmp_path):
    doc = demo()
    result = native.render(doc, out=tmp_path / 'a.svg')
    assert result.fmt == 'svg' and result.path == str(tmp_path / 'a.svg')
    text = (tmp_path / 'a.svg').read_text(encoding='utf-8')
    report = result.report
    assert report['format'] == 'animageo-render-report/v1'
    assert report['documentId'] == 'render_demo'
    assert report['kernel'] == {'library': native_version(), 'registry': native.__registry_version__}
    assert report['canvas'] == {'width': 800, 'height': 533, 'unit': 800 / 12,
                                'origin': [400.0, 4 * 800 / 12]}
    assert f'width="{report["canvas"]["width"]}" height="{report["canvas"]["height"]}"' in text
    assert set(report['elements']) == set(doc['elements'])
    states = native.evaluate(doc).elements
    for el_id, record in report['elements'].items():
        assert record['state'] == states[el_id]['state']
    # a point: its box is centred on its position, its name label is near it
    a = report['elements']['A']
    assert center(a['box']) == pytest.approx(to_px(report, -4, -2), abs=0.01)
    assert a['label']['text'] == '$A$'
    assert a['label']['anchor'] == pytest.approx(list(to_px(report, -4, -2)), abs=0.01)
    assert math.dist(center(a['label']['box']), a['label']['anchor']) < 30
    # the polygon spans its vertices; sides have no labels by default
    (x0, y0), (x1, y1) = to_px(report, -4, 3), to_px(report, 4, -2)
    assert report['elements']['T']['box'] == pytest.approx([x0, y0, x1, y1], abs=0.01)
    assert report['elements']['a']['label'] is None
    # hidden and undefined elements are not drawn
    assert report['elements']['M'] == {'state': 'defined', 'visible': False, 'box': None, 'label': None}
    assert report['elements']['z'] == {'state': 'undefined', 'visible': False, 'box': None, 'label': None}
    # an override reaches the drawing; an unknown key is reported
    assert 'stroke="rgb(80%, 20%, 20%)"' in text
    assert report['diagnostics'] == [{'code': 'unknown_style_key', 'elementId': 'k', 'key': 'bogus'}]
    assert report['overlaps'] == []


def native_version():
    import animageo
    return animageo.__version__


def test_png_and_pdf(tmp_path):
    doc = demo()
    png = native.render(doc, fmt='png', out=tmp_path / 'a.png', report=False)
    assert png.report is None
    data = (tmp_path / 'a.png').read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', data[16:24]) == (800, 533)
    pdf = native.render(doc, fmt='pdf', out=tmp_path / 'a.pdf')
    assert (tmp_path / 'a.pdf').read_bytes()[:5] == b'%PDF-'
    assert pdf.report['canvas']['width'] == 800


def test_temporary_output():
    result = native.render(demo(), report=False)
    try:
        assert result.path.endswith('.svg')
        with open(result.path, encoding='utf-8') as fh:
            assert fh.read().lstrip().startswith('<?xml')
    finally:
        import os
        os.unlink(result.path)


def test_export_layout_and_inputs(tmp_path):
    doc = demo()
    layout = {'export': {'size': {'width': 400, 'height': 300}, 'fit': 'contain'}}
    report = native.render(doc, export_layout=layout, out=tmp_path / 'b.svg',
                           inputs={'A': point_input(-5, -3)}).report
    canvas = report['canvas']
    assert (canvas['width'], canvas['height']) == (400, 300)
    assert canvas['unit'] == pytest.approx(400 / 12)
    assert center(report['elements']['A']['box']) == pytest.approx(to_px(report, -5, -3), abs=0.01)
    assert 'width="400" height="300"' in (tmp_path / 'b.svg').read_text(encoding='utf-8')


def test_path_parameter_input_moves_the_point(tmp_path):
    doc = demo()
    first = native.render(doc, out=tmp_path / 'c.svg').report['elements']['P']['box']
    second = native.render(doc, out=tmp_path / 'd.svg', inputs={'P': path_input(2.5)}).report
    ev = native.evaluate(doc, inputs={'P': path_input(2.5)}).elements['P']['value']
    assert center(second['elements']['P']['box']) == pytest.approx(to_px(second, ev['x'], ev['y']), abs=0.01)
    assert center(first) != pytest.approx(center(second['elements']['P']['box']), abs=1)


def test_label_offset_and_overlaps(tmp_path):
    b = builder('labels')
    b.free('A', 0, 0).free('B', 0.05, 0).free('C', 3, 0)
    b.doc['appearance'] = {'C': {'label': {'mode': 'name', 'offsetWorld': [1.0, 0.5]}}}
    report = native.render(b.doc, out=tmp_path / 'e.svg').report
    assert report['overlaps'] == [['A', 'B']]
    # a pinned offset (world units) moves the bottom-left corner off the point;
    # an unpinned point label hangs clear of its marker (1.8.1a2)
    moved = report['elements']['C']['label']['box']
    px, py = to_px(report, 3, 0)
    unit = report['canvas']['unit']
    assert moved[0] == pytest.approx(px + 1.0 * unit, abs=0.5)
    assert moved[3] == pytest.approx(py - 0.5 * unit, abs=0.5)
    plain = native.render({**b.doc, 'appearance': {}}, out=tmp_path / 'f.svg').report
    still = plain['elements']['C']['label']['box']
    assert still[0] > px and still[3] < py
    assert not [pair for pair in plain['pointOverlaps'] if pair[0] == pair[1]]


def test_point_labels_do_not_cover_their_points(tmp_path):
    b = builder('points')
    b.free('A', -4, -2).free('B', 4, -2).free('C', 1, 3).segment('s', 'A', 'B')
    report = native.render(b.doc, out=tmp_path / 'q.svg').report
    assert report['pointOverlaps'] == []
    for el_id in 'ABC':
        record = report['elements'][el_id]
        x0, y0, x1, y1 = record['box']
        cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2
        lx0, ly0, lx1, ly1 = record['label']['box']
        gap = math.hypot(cx - min(max(cx, lx0), lx1), cy - min(max(cy, ly0), ly1))
        assert gap >= r + DEFAULT_CONFIG['point_gap_px'] - 0.05, el_id
    # a label centred on its point is reported
    b.doc['appearance'] = {'A': {'overrides': {'label_anchor': 'MC'}}}
    assert native.render(b.doc, out=tmp_path / 'r.svg').report['pointOverlaps'] == [['A', 'A']]


def test_classic_scenes_keep_their_point_labels():
    scene = AnimaGeoScene()
    assert scene.label_point_clearance is False
    scene.loadDocument(demo())
    assert scene.label_point_clearance is True
    scene.resetScene()
    assert scene.label_point_clearance is False


def test_value_and_caption_labels(tmp_path):
    b = builder('values')
    b.free('A', 0, 0).free('B', 3, 4).segment('s', 'A', 'B')
    b.doc['appearance'] = {'s': {'label': {'mode': 'name_value'}},
                           'B': {'label': {'mode': 'caption', 'text': '$B_1$'}}}
    report = native.render(b.doc, out=tmp_path / 'g.svg').report
    assert report['elements']['s']['label']['text'] == '$s = 5$'
    assert report['elements']['B']['label']['text'] == '$B_1$'


def test_style_config_dict_and_preset(tmp_path):
    doc = demo()
    native.render(doc, style_config='book_blue', out=tmp_path / 'h.svg', report=False)
    native.render(doc, style_config={'presets': {'color': {'strong': '#123456'}}},
                  out=tmp_path / 'i.svg', report=False)
    assert 'rgb(7.058824%, 20.392157%, 33.72549%)' in (tmp_path / 'i.svg').read_text(encoding='utf-8')


def test_load_document_on_a_scene():
    scene = AnimaGeoScene()
    doc = demo()
    scene.loadDocument(doc)
    names = scene.native_names
    assert scene.geo.element(names.by_id['A']).data.coords.tolist() == [-4.0, -2.0]
    assert scene.mobject(names.by_id['k']) is not None
    assert scene.mobject(names.by_id['M']) is None
    assert scene.style.export['ptUnit_ggb'] == native.source_view(doc)['ptUnit']
    # loading again replaces the construction
    b = builder('second')
    b.free('Q', 1, 1)
    scene.loadDocument(b.doc)
    assert [e.name for e in scene.geo.elements if e.name.startswith('e_')] == ['e_Q']


# ── same drawing as the classic DSL ──────────────────────────────────────
#
# The DSL code lists the objects in the order the bridge creates them
# (Kahn's order of the operations, ties by operation ID): the renderer breaks
# z-index ties by that order, and cairo merges a fill and a stroke drawn one
# right after the other into one <path>.

def dsl_svg(code, bounds, path, style=None):
    """Draw DSL ``code``; ``style``: ``{name: {key: value}}`` written to the elements."""
    from animageo.parsers import dsl
    view_doc = builder('view', bounds).doc
    view = native.source_view(view_doc)
    scene = AnimaGeoScene()
    scene.resetScene()
    scene.style.export = dict(view)
    scene.style.export['ptUnit_ggb'] = view['ptUnit']
    dsl.run(scene.geo, code)
    scene.geo.rebuild(full=True)
    for elem in scene.geo.elements:
        elem.style['label_visible'] = False
    for name, keys in (style or {}).items():
        for key, value in keys.items():
            scene.geo.element(name).style[key] = value
    scene.applyStyle()
    scene.addAllGeometry(show=True)
    scene.exportSVG(str(path))
    return path


def pair_triangle():
    b = builder('triangle')
    b.free('A', -4, -2).free('B', 4, -2).free('C', 1, 3)
    b.polygon('T', 'A', 'B', 'C', sides=[(1, 'a'), (2, 'b'), (3, 'c')])
    return b.doc, 'A = Point(-4, -2)\nB = Point(4, -2)\nC = Point(1, 3)\nT, a, b, c = Polygon(A, B, C)\n'


def pair_midpoints():
    b = builder('midpoints')
    b.free('A', -4, -2).free('B', 4, -1).free('C', 0, 3)
    b.segment('s', 'A', 'B').segment('t', 'B', 'C').midpoint('M', 'A', 'B').midpoint('N', 'B', 'C')
    b.segment('m', 'M', 'N')
    return b.doc, ('A = Point(-4, -2)\nB = Point(4, -1)\nC = Point(0, 3)\nM = Midpoint(A, B)\n'
                   'N = Midpoint(B, C)\nm = Segment(M, N)\ns = Segment(A, B)\nt = Segment(B, C)\n')


def pair_line_ray():
    b = builder('line_ray')
    b.free('A', -3, -2).free('B', 2, 1).free('C', 0, 2).free('D', 1, -1)
    b.line('l', 'A', 'B').ray('r', 'C', 'D')
    return b.doc, ('A = Point(-3, -2)\nB = Point(2, 1)\nC = Point(0, 2)\nD = Point(1, -1)\n'
                   'l = Line(A, B)\nr = Ray(C, D)\n')


def pair_circle():
    b = builder('circle')
    b.free('O', 0.5, -0.5).free('R', 3, 1).circle('c', 'O', 'R').segment('s', 'O', 'R')
    return b.doc, 'O = Point(0.5, -0.5)\nR = Point(3, 1)\nc = Circle(O, R)\ns = Segment(O, R)\n'


def pair_line_line():
    b = builder('line_line')
    b.free('A', -4, -3).free('B', 3, 2).free('C', -4, 2).free('D', 4, -1)
    b.line('l', 'A', 'B').line('m', 'C', 'D').intersect('X', 'l', 'm')
    return b.doc, ('A = Point(-4, -3)\nB = Point(3, 2)\nC = Point(-4, 2)\nD = Point(4, -1)\n'
                   'l = Line(A, B)\nm = Line(C, D)\nX = Intersect(l, m)\n')


def pair_line_circle():
    b = builder('line_circle')
    b.free('A', -5, -1).free('B', 5, 1).free('O', 0, 0).free('R', 3, 0)
    b.line('l', 'A', 'B').circle('c', 'O', 'R').line_circle('P', 'Q', 'l', 'c')
    return b.doc, ('A = Point(-5, -1)\nB = Point(5, 1)\nO = Point(0, 0)\nR = Point(3, 0)\n'
                   'c = Circle(O, R)\nl = Line(A, B)\nP, Q = Intersect(l, c)\n')


def pair_circle_circle():
    b = builder('circle_circle')
    b.free('O', -1, 0).free('R', 2, 0).free('K', 1.5, 0.5).free('S', 1.5, 3)
    b.circle('c', 'O', 'R').circle('k', 'K', 'S').circle_circle('P', 'Q', 'c', 'k')
    return b.doc, ('K = Point(1.5, 0.5)\nO = Point(-1, 0)\nR = Point(2, 0)\nS = Point(1.5, 3)\n'
                   'c = Circle(O, R)\nk = Circle(K, S)\nP, Q = Intersect(c, k)\n')


def pair_other_point():
    doc, code = pair_circle_circle()
    b = builder('other_point')
    b.doc.update({k: v for k, v in doc.items() if k in ('operations', 'elements', 'inputs')})
    b.other_than('Z', 'c', 'k', 'P')
    b.doc['appearance'] = {'Q': {'visible': False}}
    return b.doc, code


def pair_on_paths():
    b = builder('on_paths')
    b.free('A', -4, -2).free('B', 4, 1).free('O', 0, 0).free('R', 2, 2)
    b.segment('s', 'A', 'B').circle('c', 'O', 'R').on_path('P', 's', 0.25).on_path('Q', 'c', 1.0)
    values = native.evaluate(b.doc).elements
    p, q = values['P']['value'], values['Q']['value']
    return b.doc, ('A = Point(-4, -2)\nB = Point(4, 1)\nO = Point(0, 0)\nR = Point(2, 2)\n'
                   f'c = Circle(O, R)\nQ = Point({q["x"]!r}, {q["y"]!r})\ns = Segment(A, B)\n'
                   f'P = Point({p["x"]!r}, {p["y"]!r})\n')


def pair_quad():
    b = builder('quad')
    b.free('A', -4, -3).free('B', 3, -2).free('C', 4, 2).free('D', -2, 3)
    b.polygon('T', 'A', 'B', 'C', 'D', sides=[(1, 'a'), (2, 'b'), (3, 'c'), (4, 'd')])
    return b.doc, ('A = Point(-4, -3)\nB = Point(3, -2)\nC = Point(4, 2)\nD = Point(-2, 3)\n'
                   'T, a, b, c, d = Polygon(A, B, C, D)\n')


def builder2(doc_id, bounds=BOUNDS):
    return DocBuilder(doc_id, registry_version='1.2', bounds=bounds)


def pair_parallel_perpendicular():
    b = builder2('parallel_perpendicular')
    b.free('A', -4, -2).free('B', 3, 1).free('C', -1, 2)
    b.line('l', 'A', 'B').parallel('p', 'C', 'l').perpendicular('q', 'C', 'l')
    return b.doc, ('A = Point(-4, -2)\nB = Point(3, 1)\nC = Point(-1, 2)\nl = Line(A, B)\n'
                   'p = Line(C, l)\nq = OrthogonalLine(C, l)\n')


def pair_bisectors():
    b = builder2('bisectors')
    b.free('A', -3, -2).free('B', 4, -1).free('C', 0, 3)
    b.perp_bisector('m', 'A', 'B').angle_bisector('w', 'B', 'A', 'C')
    return b.doc, ('A = Point(-3, -2)\nB = Point(4, -1)\nC = Point(0, 3)\n'
                   'm = PerpendicularBisector(A, B)\nw = AngularBisector(B, A, C)\n')


def pair_vector():
    b = builder2('vector')
    b.free('A', -3, -2).free('B', 2, 2).vector('v', 'A', 'B')
    return b.doc, 'A = Point(-3, -2)\nB = Point(2, 2)\nv = Vector(A, B)\n'


def pair_circle_radius():
    b = builder2('circle_radius')
    b.free('O', -2, 0).free('K', 2, 1).number('r', 1.5).circle_radius('c', 'O', 2.5).circle_radius('k', 'K', 'r')
    return b.doc, ('K = Point(2, 1)\nO = Point(-2, 0)\nc = Circle(O, 2.5)\nr = 1.5\nk = Circle(K, r)\n')


def pair_circumcircle():
    b = builder2('circumcircle')
    b.free('A', -3, -2).free('B', 3, -1).free('C', 0, 2).circle3('k', 'A', 'B', 'C', center='O')
    return b.doc, ('A = Point(-3, -2)\nB = Point(3, -1)\nC = Point(0, 2)\nk = Circle(A, B, C)\n'
                   'O = Center(k)\n')


def pair_projection():
    b = builder2('projection')
    b.free('A', -4, -1).free('B', 4, 1).free('P', 0, 3)
    b.line('l', 'A', 'B').projection('H', 'P', 'l').segment('s', 'P', 'H')
    return b.doc, ('A = Point(-4, -1)\nB = Point(4, 1)\nP = Point(0, 3)\nl = Line(A, B)\n'
                   'H = ClosestPoint(l, P)\ns = Segment(P, H)\n')


def builder3(doc_id, bounds=BOUNDS):
    return DocBuilder(doc_id, registry_version='1.3', bounds=bounds)


def pair_angles():
    b = builder3('angles')
    b.free('A', -4, -2).free('B', 3, -1).free('C', 0, 3)
    b.angle('g', 'B', 'A', 'C').angle('h', 'A', 'B', 'C').angle('k', 'A', 'C', 'B')
    return b.doc, ('A = Point(-4, -2)\nB = Point(3, -1)\nC = Point(0, 3)\ng = Angle(B, A, C)\n'
                   'h = Angle(A, B, C)\nk = Angle(A, C, B)\n')


def pair_incircle():
    b = builder3('incircle')
    b.free('A', -4, -3).free('B', 4, -2).free('C', 0, 3)
    b.incircle('k', 'A', 'B', 'C', center='I', touches=('T1', 'T2', 'T3'))
    values = native.evaluate(b.doc).elements

    def lit(el_id):
        v = values[el_id]['value']
        return f'Point({v["x"]!r}, {v["y"]!r})'
    return b.doc, ('A = Point(-4, -3)\nB = Point(4, -2)\nC = Point(0, 3)\n'
                   f'I = {lit("I")}\nk = Incircle(A, B, C)\nT1 = {lit("T1")}\nT2 = {lit("T2")}\n'
                   f'T3 = {lit("T3")}\n')


def pair_equal_marks():
    b = builder3('equal_marks')
    b.free('A', -4, -2).free('B', 4, -2).free('C', 0, 3)
    b.segment('s', 'A', 'C').segment('t', 'B', 'C').angle('g', 'B', 'A', 'C').angle('h', 'C', 'B', 'A')
    b.equal_segments('m', 's', 't', count=2).equal_angles('n', 'g', 'h', count=3)
    return b.doc, ('A = Point(-4, -2)\nB = Point(4, -2)\nC = Point(0, 3)\ng = Angle(B, A, C)\n'
                   'h = Angle(C, B, A)\ns = Segment(A, C)\nt = Segment(B, C)\n'), \
        {'s': {'tick_count': 2}, 't': {'tick_count': 2}, 'g': {'tick_count': 3}, 'h': {'tick_count': 3}}


def pair_right_angle():
    b = builder3('right_angle')
    b.free('A', -1, -1).free('B', 3, 1).free('C', -3, 3).right_mark('r', 'B', 'A', 'C')
    return b.doc, 'A = Point(-1, -1)\nB = Point(3, 1)\nC = Point(-3, 3)\nr = Angle(B, A, C)\n', \
        {'r': {'right_angle_marker': True}}


PAIRS = [pair_triangle, pair_midpoints, pair_line_ray, pair_circle, pair_line_line, pair_line_circle,
         pair_circle_circle, pair_other_point, pair_on_paths, pair_quad,
         pair_parallel_perpendicular, pair_bisectors, pair_vector, pair_circle_radius, pair_circumcircle,
         pair_projection, pair_angles, pair_incircle, pair_equal_marks, pair_right_angle]


@pytest.mark.parametrize('pair', PAIRS, ids=[p.__name__[5:] for p in PAIRS])
def test_same_paths_as_the_dsl(pair, tmp_path):
    doc, code, *style = pair()
    appearance = doc.get('appearance', {})
    no_labels(doc)
    for el_id, entry in appearance.items():
        doc['appearance'][el_id].update(entry)
    native.render(doc, out=tmp_path / 'native.svg', report=False)
    dsl_svg(code, BOUNDS, tmp_path / 'dsl.svg', style[0] if style else None)
    native_paths, dsl_paths = path_tags(tmp_path / 'native.svg'), path_tags(tmp_path / 'dsl.svg')
    assert sum(native_paths.values()) > 0
    assert native_paths == dsl_paths


def test_cyrillic_labels(tmp_path):
    b = builder('cyrillic')
    b.free('A', 0, 0).free('B', 3, 0)
    b.doc['elements']['A']['displayName'] = 'Б'
    b.doc['appearance'] = {'B': {'label': {'mode': 'caption', 'text': 'точка $B$'}}}
    report = native.render(b.doc, out=tmp_path / 'ru.svg').report
    assert report['elements']['A']['label']['text'] == '$Б$'
    assert report['elements']['B']['label']['text'] == 'точка $B$'
    for el_id in 'AB':
        box = report['elements'][el_id]['label']['box']
        assert box[2] > box[0] and box[3] > box[1]


def test_vector_is_drawn_and_a_number_is_not(tmp_path):
    b = builder2('l2_report')
    b.free('A', -3, -2).free('B', 2, 2).vector('v', 'A', 'B').number('r', 2).circle_radius('c', 'A', 'r')
    b.number('bad', 1, min=2, max=1)
    report = native.render(b.doc, out=tmp_path / 'l2.svg').report
    els = report['elements']
    assert els['v']['visible'] and els['v']['box'] is not None and els['v']['label'] is None
    assert els['c']['visible'] and els['c']['box'] is not None
    for el_id in ('r', 'bad'):
        assert els[el_id]['visible'] is False and els[el_id]['box'] is None and els[el_id]['label'] is None
    assert els['bad']['state'] == 'undefined'
    x0, y0 = to_px(report, -3, -2)
    x1, y1 = to_px(report, 2, 2)
    box = els['v']['box']
    assert box[0] <= min(x0, x1) + 1 and box[2] >= max(x0, x1) - 1
    assert box[1] <= min(y0, y1) + 1 and box[3] >= max(y0, y1) - 1


def test_marks_in_the_report(tmp_path):
    b = builder3('marks_report')
    b.free('A', -4, -2).free('B', 4, -2).free('C', 0, 3)
    b.segment('s', 'A', 'C').segment('t', 'B', 'C').angle('g', 'B', 'A', 'C').angle('h', 'C', 'B', 'A')
    b.equal_segments('m', 's', 't', count=2).equal_angles('n', 'g', 'h', count=3)
    b.right_mark('r', 'B', 'A', 'C')                      # not a right angle: the marker is forced
    doc = b.doc
    report = native.render(doc, out=tmp_path / 'm.svg').report
    els = report['elements']
    s, t, m = els['s']['box'], els['t']['box'], els['m']['box']
    assert m == [min(s[0], t[0]), min(s[1], t[1]), max(s[2], t[2]), max(s[3], t[3])]
    assert els['m']['visible'] and els['m']['label'] is None
    assert els['n']['visible'] and els['n']['box'] is not None
    assert els['r']['visible'] and els['r']['box'] is not None and els['r']['label'] is None
    # hidden or undefined: no ticks, no box
    hidden = native.render(doc | {'appearance': {'m': {'visible': False}}}, out=tmp_path / 'h.svg').report
    assert hidden['elements']['m'] == {'state': 'defined', 'visible': False, 'box': None, 'label': None}
    gone = native.render(doc, out=tmp_path / 'u.svg', inputs={'B': point_input(-4, -2)}).report
    assert gone['elements']['n']['state'] == 'undefined'
    assert gone['elements']['n']['visible'] is False and gone['elements']['n']['box'] is None
    assert gone['elements']['r']['visible'] is False
    with open(tmp_path / 'h.svg', encoding='utf-8') as fh:
        hidden_paths = len(re.findall(r'<path', fh.read()))
    with open(tmp_path / 'm.svg', encoding='utf-8') as fh:
        assert len(re.findall(r'<path', fh.read())) == hidden_paths + 4     # 2 ticks on each of s, t
