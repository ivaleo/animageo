"""1.10.0a2: the hatching of one element — ``fill_pattern`` and ``hatch_*`` in
``appearance.overrides`` (G1-D of the web, decision 2 of the tech lead).

The keys reach the classic renderer as the element's own style, so the
pattern is drawn in every static format the style hatching reaches (SVG, PNG,
PDF, EPS, TikZ) and only on that element; an unknown key is still a
diagnostic.
"""
import io
import re
import zlib

import pytest

from animageo import native
from animageo.hatch import HATCH_DEFAULTS
from animageo.native.rendering import APPEARANCE_STYLE_KEYS, appearance_plan
from tests.native.conftest import DocBuilder, ref

BOUNDS = (-6, -4, 6, 4)
HATCH_KEYS = set(HATCH_DEFAULTS)
# shape → (its type in the style, its neighbour of the same type)
SHAPES = {'t': ('polygon', 'u'), 'k': ('circle', 'm'), 'q': ('circlesector', 'r')}
VECTOR_FORMATS = ('svg', 'pdf', 'eps', 'tikz')


def shapes_doc(appearance=None):
    """Two polygons, two circles and two sectors, no labels."""
    b = DocBuilder('hatch', registry_version='1.5', bounds=BOUNDS)
    b.free('A', -5.5, -3.5).free('B', -2.5, -3.5).free('C', -4.0, -0.8)
    b.free('D', -1.5, -3.5).free('E', 1.5, -3.5).free('F', 0.0, -1.0)
    for pid, verts in (('t', 'ABC'), ('u', 'DEF')):
        b.op('op_' + pid, 'polygon.by_points',
             {'vertices': {'kind': 'list', 'items': [ref(v) for v in verts]}}, [('polygon', pid, 'polygon')])
    b.free('O', -4.0, 2.0).free('P', -2.8, 2.0).circle('k', 'O', 'P')
    b.free('O2', -0.5, 2.0).free('P2', 0.9, 2.0).circle('m', 'O2', 'P2')
    b.free('S', 2.5, -3.0).free('S1', 5.0, -3.0).free('S2', 2.5, -0.5)
    b.free('T', 2.5, 0.5).free('T1', 5.5, 0.5).free('T2', 2.5, 3.5)
    for sid, (c, a, e) in (('q', ('S', 'S1', 'S2')), ('r', ('T', 'T1', 'T2'))):
        b.op('op_' + sid, 'sector.center_two_points', {'center': ref(c), 'a': ref(a), 'b': ref(e)},
             [('sector', sid, 'sector')])
    for el in b.doc['elements'].values():
        if el['type'] == 'point':
            el['displayName'] = ''
    if appearance:
        b.doc['appearance'] = appearance
    return b.doc


# ── the plan (no manim) ───────────────────────────────────────────────────

def test_hatch_keys_are_appearance_keys():
    assert native.has('appearance.hatch')
    assert HATCH_KEYS == {'fill_pattern', 'hatch_angle_deg', 'hatch_spacing_px', 'hatch_width_px', 'hatch_color',
                          'hatch_opacity'}
    assert HATCH_KEYS <= APPEARANCE_STYLE_KEYS


def test_the_plan_carries_the_hatch_of_one_element():
    overrides = {'fill_pattern': 'crosshatch', 'hatch_angle_deg': 135, 'hatch_spacing_px': 10,
                 'hatch_width_px': 1.5, 'hatch_color': '#ff0000', 'hatch_opacity': 0.5}
    plan, diagnostics = appearance_plan(shapes_doc({'t': {'overrides': overrides}}), 50.0)
    assert diagnostics == []
    assert {k: plan['t']['style'][k] for k in overrides} == overrides
    assert not HATCH_KEYS & set(plan['u']['style'])


def test_an_unknown_key_is_still_a_diagnostic():
    doc = shapes_doc({'t': {'overrides': {'fill_pattern': 'hatch', 'hatch_bogus': 1}}})
    plan, diagnostics = appearance_plan(doc, 50.0)
    assert diagnostics == [{'code': 'unknown_style_key', 'elementId': 't', 'key': 'hatch_bogus'}]
    assert plan['t']['style']['fill_pattern'] == 'hatch' and 'hatch_bogus' not in plan['t']['style']


# ── the files (manim) ─────────────────────────────────────────────────────

def _moves(fmt: str, data: bytes) -> int:
    """Subpaths of the drawing: SVG ``M``, PDF/EPS ``m`` operators, TikZ ``--``
    pieces (a hatch is one subpath per segment in every format)."""
    if fmt == 'svg':
        return sum(d.count(b'M') for d in re.findall(rb' d="([^"]*)"', data))
    if fmt == 'tikz':
        return data.count(b' -- ')
    if fmt == 'pdf':
        chunks = []
        for m in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', data, re.S):
            try:
                chunks.append(zlib.decompress(m.group(1)))
            except zlib.error:
                chunks.append(m.group(1))
        data = b'\n'.join(chunks)
    return len(re.findall(rb'(?<![\w.])m(?![\w])', data))


@pytest.fixture(scope='module')
def render_bytes(tmp_path_factory):
    pytest.importorskip('manim')
    out = tmp_path_factory.mktemp('hatch')
    cache = {}

    def run(fmt, appearance=None, style=None):
        key = (fmt, repr(appearance), repr(style))
        if key not in cache:
            path = out / f'f{len(cache)}.{fmt}'
            result = native.render(shapes_doc(appearance), fmt=fmt, out=path, style_config=style)
            cache[key] = (path.read_bytes(), result.report)
        return cache[key]
    return run


def _style_hatch(type_):
    return {'overlay': {'per_type': {type_: {'fill_pattern': 'hatch'}}}}


@pytest.mark.manim
@pytest.mark.parametrize('fmt', VECTOR_FORMATS)
@pytest.mark.parametrize('shape', sorted(SHAPES))
def test_only_the_element_with_the_override_is_hatched(render_bytes, fmt, shape):
    type_, neighbour = SHAPES[shape]
    plain, _ = render_bytes(fmt)
    own, report = render_bytes(fmt, {shape: {'overrides': {'fill_pattern': 'hatch'}}})
    both, _ = render_bytes(fmt, None, _style_hatch(type_))
    assert report['diagnostics'] == []
    mine = _moves(fmt, own) - _moves(fmt, plain)
    style_both = _moves(fmt, both) - _moves(fmt, plain)
    assert mine > 10, (fmt, shape)                       # the element is hatched
    assert style_both - mine > 10, (fmt, shape)          # the neighbour is not (the style hatches it)


@pytest.mark.manim
@pytest.mark.parametrize('shape', sorted(SHAPES))
def test_the_hatch_lies_inside_the_element(render_bytes, shape):
    _, neighbour = SHAPES[shape]
    svg, report = render_bytes('svg', {shape: {'overrides': {'fill_pattern': 'hatch'}}})
    paths = [d for d in re.findall(rb' d="([^"]*)"', svg) if d.count(b'M') > 10]
    assert len(paths) == 1
    # a stroked path is written in world units under the transform of the canvas
    nums = [float(v) for v in re.findall(rb'-?\d+(?:\.\d+)?(?:e-?\d+)?', paths[0])]
    xs, ys = nums[0::2], nums[1::2]
    unit = report['canvas']['unit']
    ox, oy = report['canvas']['origin']

    def world(box):
        x0, y0, x1, y1 = box
        return (x0 - ox) / unit, (oy - y1) / unit, (x1 - ox) / unit, (oy - y0) / unit
    x0, y0, x1, y1 = world(report['elements'][shape]['box'])
    eps = 2 / unit
    assert x0 - eps <= min(xs) and max(xs) <= x1 + eps and y0 - eps <= min(ys) and max(ys) <= y1 + eps
    nx0, ny0, nx1, ny1 = world(report['elements'][neighbour]['box'])
    assert max(xs) < nx0 or min(xs) > nx1 or max(ys) < ny0 or min(ys) > ny1


@pytest.mark.manim
@pytest.mark.parametrize('shape', sorted(SHAPES))
def test_png_has_stripes_on_the_element_only(render_bytes, shape):
    from PIL import Image
    _, neighbour = SHAPES[shape]
    png, report = render_bytes('png', {shape: {'overrides': {'fill_pattern': 'hatch', 'hatch_spacing_px': 8,
                                                             'hatch_width_px': 2}}})
    image = Image.open(io.BytesIO(png)).convert('L')

    def changes(el_id):
        x0, y0, x1, y1 = report['elements'][el_id]['box']
        y = int((y0 + 2 * y1) / 3)                     # a row through the lower part of the shape
        row = [image.getpixel((x, y)) < 128 for x in range(int(x0) + 3, int(x1) - 3)]
        inner = row[len(row) // 4: 3 * len(row) // 4]
        return sum(1 for a, b in zip(inner, inner[1:]) if a != b)
    assert changes(shape) >= 4
    assert changes(neighbour) <= 1


@pytest.mark.manim
def test_the_hatch_settings_of_an_element_apply(render_bytes):
    base, _ = render_bytes('svg', {'t': {'overrides': {'fill_pattern': 'hatch'}}})
    sparse, _ = render_bytes('svg', {'t': {'overrides': {'fill_pattern': 'hatch', 'hatch_spacing_px': 12}}})
    cross, _ = render_bytes('svg', {'t': {'overrides': {'fill_pattern': 'crosshatch'}}})
    red, _ = render_bytes('svg', {'t': {'overrides': {'fill_pattern': 'hatch', 'hatch_color': '#ff0000'}}})
    plain, _ = render_bytes('svg')
    n = _moves('svg', base) - _moves('svg', plain)
    assert _moves('svg', sparse) - _moves('svg', plain) < n * 0.7
    assert _moves('svg', cross) - _moves('svg', plain) > n * 1.5
    assert b'rgb(100%, 0%, 0%)' in red and b'rgb(100%, 0%, 0%)' not in base
    dots, _ = render_bytes('tikz', {'q': {'overrides': {'fill_pattern': 'dots'}}})
    plain_tikz, _ = render_bytes('tikz')
    assert dots.count(b'circle') - plain_tikz.count(b'circle') > 20


@pytest.mark.manim
def test_an_override_wins_over_the_style(render_bytes):
    plain, _ = render_bytes('svg')
    both, _ = render_bytes('svg', None, _style_hatch('polygon'))
    solid_t, report = render_bytes('svg', {'t': {'overrides': {'fill_pattern': 'solid'}}}, _style_hatch('polygon'))
    assert report['diagnostics'] == []
    only_u = _moves('svg', solid_t) - _moves('svg', plain)
    assert 10 < only_u < _moves('svg', both) - _moves('svg', plain) - 10
