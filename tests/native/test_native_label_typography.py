"""The typography of labels as data (1.11.0): the underscore of a name, the
parts of a label (``resolve_paint`` ``label.parts``) and the halo of a label
(``label_halo_px``, ``label_halo_color``, ``label_halo_opacity``)."""
import pytest

from animageo import native
from animageo.labels import label_parts_of_name, name_tex
from animageo.native.paint import resolve_paint
from animageo.native.paint_fixtures import _Doc


# ── the underscore of a name ─────────────────────────────────────────────

@pytest.mark.parametrize('name, tex', [
    ('A', 'A'),
    ('A_1', 'A_1'),                 # one character is the index, as in TeX and GeoGebra
    ('A_12', 'A_12'),               # A₁2: a longer index needs braces
    ('A_{12}', 'A_{12}'),
    ('angle_B', 'angle_B'),
    ("A'", "A'"),
    (r'\alpha_1', r'\alpha_1'),
    ('A_', r'A\_'),                 # nothing to index: a literal underscore
    ('A__1', r'A\__1'),
    ('my_ point', r'my\_ point'),
    ('A_}', r'A\_\}'),             # a brace without its pair is the character
    ('A_{1', r'A\_\{1'),           # an unclosed group is no index
    (r'A\_1', r'A\_1'),             # an escaped underscore stays
    ('A^2', 'A^2'),
    ('A^', r'A\text{\textasciicircum}'),
    # the signs TeX reads as commands in math mode are the characters
    ('A%B', r'A\%B'),
    ('A#1', r'A\#1'),
    ('A&B', r'A\&B'),
    ('A$B', r'A{\text{\textdollar}}B'),
    ('A~B', r'A{\sim}B'),
    ('P_%', r'P_\%'),
    ('P_$', r'P_{\text{\textdollar}}'),
    (r'A\%', r'A\%'),               # an escaped sign stays
])
def test_the_underscore_of_a_name(name, tex):
    assert name_tex(name) == tex


def _runs(parts):
    return [(p['text'], p['italic'], p['script']) for p in parts]


@pytest.mark.parametrize('name, runs', [
    ('A', [('A', True, None)]),
    ('A_1', [('A', True, None), ('1', False, 'sub')]),
    ('A_12', [('A', True, None), ('1', False, 'sub'), ('2', False, None)]),
    ('A_{12}', [('A', True, None), ('12', False, 'sub')]),
    ('angle_B', [('angle', True, None), ('B', True, 'sub')]),
    ('A_{1b}', [('A', True, None), ('1', False, 'sub'), ('b', True, 'sub')]),
    ("A'", [('A', True, None), ('′', False, None)]),
    ('α_1', [('α', True, None), ('1', False, 'sub')]),
    ('Δ', [('Δ', False, None)]),
    (r'\alpha', [('α', True, None)]),
    ('A_', [('A', True, None), ('_', False, None)]),
    ('Точка', [('Точка', False, None)]),
    ('x^2', [('x', True, None), ('2', False, 'sup')]),
    # a Cyrillic index is one letter, as a Latin one (GeoGebra)
    ('S_бок', [('S', True, None), ('б', False, 'sub'), ('ок', False, None)]),
    ('S_{бок}', [('S', True, None), ('бок', False, 'sub')]),
    ('A%B', [('A', True, None), ('%', False, None), ('B', True, None)]),
    ('A~B', [('A', True, None), ('∼', False, None), ('B', True, None)]),
    ('P_$', [('P', True, None), ('$', False, 'sub')]),
])
def test_the_parts_of_a_name(name, runs):
    assert _runs(label_parts_of_name(name)) == runs


@pytest.mark.parametrize('name, tex', [
    ('S_бок', r'$S_{\text{б}}\text{ок}$'),
    ('S_{бок}', r'$S_{\text{бок}}$'),
    ('Б_1', r'$\text{Б}_1$'),
    ('S_бок2', r'$S_{\text{б}}\text{ок}2$'),
])
def test_the_tex_of_a_cyrillic_index_is_that_of_the_parts(name, tex):
    """The TeX the renderer compiles indexes what the parts index."""
    from animageo.labels import correctedLabel
    assert correctedLabel('$' + name_tex(name) + '$') == tex


def test_a_name_with_an_unknown_command_has_no_parts():
    assert label_parts_of_name(r'\frac{1}{2}') is None


# ── resolve_paint: label.parts and label.halo ───────────────────────────

def _doc():
    d = _Doc('typo').free('A_1', 0, 0).free('B', 5, 0).free('C', 1.5, 3.5)
    d.segment('a', 'A_1', 'B').segment('b', 'B', 'C').angle('alpha', 'B', 'A_1', 'C')
    d.label('a', 'name_value').label('b', 'value').label('alpha', 'value')
    d.look('C', label={'mode': 'caption', 'text': r'$C_{\text{вершина}}$'})
    d.doc['elements']['alpha']['displayName'] = 'angle_A'
    return d.doc


def test_resolve_paint_gives_the_parts_of_a_label():
    els = resolve_paint(_doc())['elements']
    assert _runs(els['A_1']['label']['parts']) == [('A', True, None), ('1', False, 'sub')]
    assert els['A_1']['label']['text'] == '$A_1$'
    assert _runs(els['a']['label']['parts']) == [('a', True, None), (' = 5', False, None)]
    assert _runs(els['b']['label']['parts']) == [('4.9', False, None)]
    assert _runs(els['alpha']['label']['parts']) == [('66.8°', False, None)]
    assert els['C']['label']['parts'] is None            # a caption is TeX as written


def test_the_parts_of_a_value():
    from animageo.labels import label_parts_of_value
    assert _runs(label_parts_of_value('-2.5')) == [('−2.5', False, None)]
    assert _runs(label_parts_of_value(r'60^{\circ}')) == [('60°', False, None)]
    assert _runs(label_parts_of_value(r'\infty')) == [('∞', False, None)]


def test_the_halo_of_a_label():
    doc = _doc()
    halo = resolve_paint(doc)['elements']['A_1']['label']['halo']
    assert halo == {'widthPx': 0.0, 'color': '#ffffff', 'opacity': 1.0}
    style = {'rendering': {'label_halo_px': 3}}
    els = resolve_paint(doc, style)['elements']
    assert els['A_1']['label']['halo'] == {'widthPx': 3.0, 'color': '#ffffff', 'opacity': 1.0}
    doc['appearance'].setdefault('a', {})['overrides'] = {'label_halo_px': 4, 'label_halo_color': '#ffee00',
                                                          'label_halo_opacity': 0.5}
    els = resolve_paint(doc, style)['elements']
    assert els['a']['label']['halo'] == {'widthPx': 4.0, 'color': '#ffee00', 'opacity': 0.5}
    dark = resolve_paint(doc, {'presets': {'color': {'background': '#1e1e1e'}},
                               'rendering': {'label_halo_px': 2}})['elements']
    assert dark['B']['label']['halo']['color'] == '#1e1e1e'


def test_the_halo_keys_are_in_the_contract():
    types = native.style_keys()['types']
    for type_ in ('point', 'segment', 'line', 'ray', 'vector', 'circle', 'arc', 'sector', 'polygon', 'angle',
                  'mark.right_angle', 'text'):
        keys = types[type_]['keys']
        assert keys['label_halo_px'] == {'unit': 'px', 'default': 0.0}, type_
        assert keys['label_halo_color']['unit'] == 'color' and keys['label_halo_color']['default'] is None
        assert keys['label_halo_opacity'] == {'unit': 'opacity', 'default': 1.0}
    assert 'label_halo_px' not in types['polyline']['keys']
    from animageo.native.rendering import APPEARANCE_STYLE_KEYS
    assert {'label_halo_px', 'label_halo_color', 'label_halo_opacity'} <= APPEARANCE_STYLE_KEYS
