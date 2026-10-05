"""``native.from_ggb``: the import of ``.ggb`` and ``import_report.v1`` (kernel stage L5, plan §3.5–§3.8, §7)."""
import json
import math
import uuid
import zipfile
from pathlib import Path

import pytest

from animageo import native
from animageo.native.cli import main
from animageo.native.convert import LIMITS, ImportRefused, from_ggb, report_problems
from animageo.native.convert.ggb import parse_xml, read_ggb
from tests.native.conftest import NATIVE_DIR, REPO_ROOT
from tests.native.ggb_synth import (command, element, expression, ggb_bytes, ggb_xml, line_style, point,
                                    triangle)

jsonschema = pytest.importorskip('jsonschema')

NS = uuid.UUID('6f1c5a52-6b5e-4d0c-9d51-4a1c1f3b2e10')
SCHEMA = json.loads((NATIVE_DIR / 'schema' / 'import_report.v1.schema.json').read_text(encoding='utf-8'))
REAL_FILES = ['docs/guide/assets/ggb/sample_triangle.ggb', 'examples/ai_style_generation_scene10/scene10.ggb',
              'tests/fixtures/text_static.ggb', 'tests/fixtures/text_dynamic.ggb',
              'tests/fixtures/label_offset_points.ggb', 'tests/fixtures/label_anchor_types.ggb']
CIRCLE_R3 = '<matrix A0="1" A1="1" A2="-9" A3="0" A4="0" A5="0"/>'


def _import(data, **kw):
    doc, rep = from_ggb(data, id_namespace=NS, name=kw.pop('name', 'case.ggb'), **kw)
    _check(doc, rep)
    return doc, rep


def _check(doc, rep):
    errors = [e.message for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(rep)]
    assert errors == []
    assert report_problems(rep, doc) == []
    if doc is not None:
        assert native.validate(native.load(doc)) == []
        assert rep['document_hash'] == native.content_hash(doc)
    else:
        assert rep['document_hash'] is None


def _by_name(rep):
    return {e['ggb_name']: e for e in rep['elements']}


def test_schema_is_a_valid_json_schema():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize('rel', REAL_FILES)
def test_real_files_one_entry_per_element(rel):
    path = REPO_ROOT / rel
    doc, rep = _import(path, name=Path(rel).name)
    with zipfile.ZipFile(path) as zf:
        root = parse_xml(zf.read('geogebra.xml'))
    labels = [n.attrib['label'] for n in root.find('construction') if n.tag == 'element']
    assert [e['ggb_name'] for e in rep['elements']] == labels
    assert rep['source']['objects'] == len(labels)
    assert rep['summary']['editable'] > 0
    assert rep['summary']['differs'] == 0


def test_sample_triangle_is_fully_editable_and_deterministic():
    path = REPO_ROOT / 'docs/guide/assets/ggb/sample_triangle.ggb'
    doc, rep = _import(path)
    assert set(rep['summary'].items()) >= {('editable', 11), ('unsupported', 0), ('closure', 0)}
    doc2, rep2 = from_ggb(path.read_bytes(), id_namespace=NS, name='case.ggb')
    assert native.dumps(doc) == native.dumps(doc2) and rep == rep2
    doc3, _ = from_ggb(path, id_namespace=uuid.uuid4())
    assert set(doc3['elements']).isdisjoint(doc['elements'])
    assert doc['documentId'] == str(uuid.uuid5(NS, 'document'))
    # the names stay the GGB labels
    assert sorted(doc['bindings']['legacyNames'].values()) == sorted(e['ggb_name'] for e in rep['elements'])


def test_ids_follow_the_labels_not_the_order():
    a = ggb_bytes(triangle(command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.0, 0.0)))
    b = ggb_bytes(point('Z', 5.0, 5.0) + triangle(command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.0, 0.0)))
    ra, rb = _import(a)[1], _import(b)[1]
    ids_a = {e['ggb_name']: e['native_ids'] for e in ra['elements']}
    ids_b = {e['ggb_name']: e['native_ids'] for e in rb['elements']}
    assert all(ids_b[k] == v for k, v in ids_a.items())


def test_values_are_checked_and_free_inputs_kept():
    data = ggb_bytes(triangle(command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.0, 0.0)
                              + command('Circle', ['M', 'C'], ['k'])
                              + element('conic', 'k', extra='<matrix A0="1" A1="1" A2="-6" A3="0" A4="-2" A5="0"/>')))
    doc, rep = _import(data)
    e = _by_name(rep)
    assert all(x['category'] == 'editable' and x['value_check'] == 'passed' for x in rep['elements'])
    assert e['M']['ggb_value'] == {'kind': 'point', 'value': [2.0, 0.0]}
    assert e['M']['native_value']['kind'] == 'point'
    assert e['k']['ggb_value'] == {'kind': 'circle', 'value': {'center': [2.0, 0.0], 'radius': pytest.approx(10 ** 0.5)}}
    assert doc['inputs'][e['A']['native_ids'][0]] == {'kind': 'point', 'value': [0.0, 0.0]}
    assert e['M']['signature'] == 'midpoint_pp' and e['M']['command'] == 'Midpoint'
    assert 'command' not in e['A']


def test_value_mismatch_is_differs_with_delta():
    doc, rep = _import(ggb_bytes(triangle(command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.5, 0.0))))
    m = _by_name(rep)['M']
    assert (m['category'], m['reason'], m['value_check']) == ('differs', 'value_mismatch', 'failed')
    assert m['delta'] == pytest.approx(0.5)
    assert m['native_ids'][0] in doc['elements']


def test_intersections_pick_slots_by_value():
    body = (point('A', -3.0, 0.0) + point('B', 3.0, 0.0) + command('Line', ['A', 'B'], ['g'])
            + element('line', 'g', extra='<coords x="0" y="1" z="0"/>') + point('O', 0.0, 0.0)
            + command('Circle', ['O', 'B'], ['k']) + element('conic', 'k', extra=CIRCLE_R3))
    for outputs, pts in ((['E', 'F'], [(3.0, 0.0), (-3.0, 0.0)]), (['F', 'E'], [(-3.0, 0.0), (3.0, 0.0)])):
        data = ggb_bytes(body + command('Intersect', ['g', 'k'], outputs)
                         + ''.join(point(n, *xy) for n, xy in zip(outputs, pts)))
        doc, rep = _import(data)
        ev = native.evaluate(native.load(doc))
        for name, xy in zip(outputs, pts):
            entry = _by_name(rep)[name]
            assert entry['category'] == 'editable'
            assert ev.elements[entry['native_ids'][0]]['value']['x'] == pytest.approx(xy[0])
    # the indexed form
    doc, rep = _import(ggb_bytes(body + command('Intersect', ['g', 'k', '2'], ['F']) + point('F', -3.0, 0.0)))
    assert _by_name(rep)['F']['category'] == 'editable'


def test_slider_is_a_free_number_with_its_range():
    data = ggb_bytes(element('numeric', 'n', extra='<value val="3"/><slider min="0" max="5" width="200" x="10" '
                                                   'y="10" fixed="true" horizontal="true" showAlgebra="true"/>')
                     + point('A', 0.0, 0.0) + command('Circle', ['A', 'n'], ['k']) + element('conic', 'k', extra=CIRCLE_R3))
    doc, rep = _import(data)
    n = _by_name(rep)['n']
    assert n['category'] == 'editable'
    eid = n['native_ids'][0]
    assert doc['inputs'][eid] == {'kind': 'number', 'value': 3.0}
    op = doc['operations'][doc['elements'][eid]['producer']['operationId']]
    assert op['op'] == 'number.free'
    assert {k: v['value'] for k, v in op['args'].items()} == {'min': 0.0, 'max': 5.0}


def test_unsupported_and_closure():
    data = ggb_bytes(point('A', 0.0, 0.0) + point('B', 2.0, 0.0) + point('C', 0.0, 3.0)
                     + command('Ellipse', ['A', 'B', 'C'], ['e'])
                     + element('conic', 'e', extra='<matrix A0="1" A1="2" A2="-9" A3="0" A4="0" A5="0"/>')
                     + command('Point', ['e'], ['P']) + point('P', 3.0, 0.0)
                     + command('Segment', ['A', 'P'], ['s']) + element('segment', 's', extra='<coords x="0" y="1" z="0"/>'))
    doc, rep = _import(data)
    e = _by_name(rep)
    assert (e['e']['category'], e['e']['reason']) == ('unsupported', 'no_registry_op')
    assert e['e']['detail']                       # a Russian line for the web
    assert (e['P']['category'], e['P']['reason'], e['P']['depends_on']) == ('closure', 'depends_on_unsupported', ['e'])
    assert e['s']['category'] == 'closure' and e['s']['native_ids'] == []
    assert rep['summary'] == {'editable': 3, 'picture': 0, 'unsupported': 1, 'closure': 2, 'differs': 0}
    assert len(doc['elements']) == 3


@pytest.mark.parametrize('body, name, category, reason, kind', [
    (expression('L', '{1,2,3}') + element('list', 'L'), 'L', 'unsupported', 'list', None),
    (element('button', 'b1', extra='<javascript val="alert(1)"/>'), 'b1', 'unsupported', 'script', 'script'),
    (element('textfield', 'tf'), 'tf', 'unsupported', 'ui_object', None),
    (element('point3d', 'P', extra='<coords x="1" y="2" z="3" w="1"/>'), 'P', 'unsupported', '3d', '3d'),
    (command('RandomPointIn', ['t1'], ['R']) + point('R', 1.0, 1.0), 'R', 'picture', 'random_point', None),
    (expression('f', 'x^2') + element('function', 'f'), 'f', 'unsupported', 'formula_unsupported', None),
    (element('image', 'pic1'), 'pic1', 'unsupported', 'image', 'image'),
])
def test_reasons(body, name, category, reason, kind):
    doc, rep = _import(ggb_bytes(body))
    entry = _by_name(rep)[name]
    assert (entry['category'], entry['reason']) == (category, reason)
    if kind:
        assert kind in {d['kind'] for d in rep['dropped']}


def test_a_script_drops_only_its_object():
    body = triangle().replace('<labelMode val="0"/></element>',
                              '<labelMode val="0"/><ggbscript val="SetValue[a,1]"/></element>', 1)
    doc, rep = _import(ggb_bytes(body + command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.0, 0.0)))
    e = _by_name(rep)
    assert e['t1']['reason'] == 'script' and e['t1']['category'] in ('picture', 'unsupported')
    assert all(e[n]['category'] == 'editable' for n in ('A', 'B', 'C', 'a', 'b', 'c', 'M'))
    assert {'kind': 'script', 'count': 1, 'names': ['t1']} in rep['dropped']
    # a global script beyond the default ggbOnInit
    _, rep = _import(ggb_bytes(point('A', 0.0, 0.0), js='function ggbOnInit() { ggbApplet.evalCommand("B=(1,1)") }'))
    assert {'kind': 'script', 'count': 1} in rep['dropped']
    _, rep = _import(ggb_bytes(point('A', 0.0, 0.0)))
    assert rep['dropped'] == []


def test_texts_are_pictures():
    _, rep = _import(REPO_ROOT / 'tests/fixtures/text_static.ggb')
    texts = [e for e in rep['elements'] if e['ggb_type'] == 'text']
    assert texts and all(e['category'] == 'picture' for e in texts)
    assert {e['reason'] for e in texts} <= {'latex_macros', 'fixed_text'}
    assert all(e['ggb_value']['kind'] == 'text' for e in texts)


def _numeric(label, value, exp=None):
    return (expression(label, exp) if exp else '') + element('numeric', label, extra=f'<value val="{value!r}"/>')


def _angle(label, value, exp=None):
    return (expression(label, exp) if exp else '') + element('angle', label, extra=f'<value val="{value!r}"/>')


def _with_text(doc, value, by_name):
    """``doc`` with the ``text.free`` the web builds from ``ggb_value`` of a
    text: a number insert as is, a length or an area through ``measure.*``."""
    doc = json.loads(json.dumps(doc))
    items = []
    for k, ref in enumerate(value['refs']):
        eid = by_name[ref['ggb_name']]['native_ids'][0]
        if ref['as'] in ('length', 'area'):
            op = {'length': 'measure.length', 'area': 'measure.area'}[ref['as']]
            doc['operations'][f'op_m{k}'] = {'id': f'op_m{k}', 'op': op, 'args': {'of': {'kind': 'ref', 'elementId': eid}},
                                             'outputs': [{'slot': 'number', 'elementId': f'm{k}'}]}
            doc['elements'][f'm{k}'] = {'id': f'm{k}', 'type': 'number', 'displayName': '',
                                        'producer': {'operationId': f'op_m{k}', 'slot': 'number'}}
            eid = f'm{k}'
        items.append({'kind': 'ref', 'elementId': eid})
    if 'anchor_ref' in value:
        anchor = by_name[value['anchor_ref']]['native_ids'][0]
    else:                   # a text at a fixed place: a hidden free point
        anchor = 'p'
        doc['operations']['op_p'] = {'id': 'op_p', 'op': 'point.free', 'args': {},
                                     'outputs': [{'slot': 'point', 'elementId': 'p'}]}
        doc['elements']['p'] = {'id': 'p', 'type': 'point', 'displayName': '',
                                'producer': {'operationId': 'op_p', 'slot': 'point'}}
        doc['inputs']['p'] = {'kind': 'point', 'value': value['anchor']}
    doc['operations']['op_t'] = {'id': 'op_t', 'op': 'text.free', 'args': {
        'text': {'kind': 'template', 'value': value['template']}, 'anchor': {'kind': 'ref', 'elementId': anchor},
        'refs': {'kind': 'list', 'items': items}, 'decimals': {'kind': 'number', 'value': value['decimals']}},
        'outputs': [{'slot': 'text', 'elementId': 't'}]}
    doc['elements']['t'] = {'id': 't', 'type': 'text', 'displayName': '', 'producer': {'operationId': 'op_t', 'slot': 'text'}}
    return doc


def test_a_dependent_text_has_a_template_and_an_anchor():
    """``ggb_value`` of a text (1.10.0a2): the anchor of every text, the
    template of ``text.free`` with its references and the text as shown —
    the ``text.free`` built from them shows what the classic shows."""
    from animageo.geo.construction import Construction
    from animageo.geo.lib_elements import resolve_text_string
    from animageo.parsers import ggb_parser
    path = REPO_ROOT / 'tests/fixtures/text_dynamic.ggb'
    doc, rep = _import(path)
    e = _by_name(rep)
    area, parts = e['надпись3']['ggb_value'], e['надпись4']['ggb_value']
    assert (area['template'].replace('\xa0', ' '), area['refs']) == (       # the file has no-break spaces
        'Площадь = {0} ', [{'ggb_name': 't1', 'as': 'area'}])
    assert (parts['template'].replace('\xa0', ' '), parts['refs'], parts['anchor_ref']) == (
        'элементы: точка {0}, сторона {1}', [{'ggb_name': 'A', 'as': 'point'}, {'ggb_name': 'a', 'as': 'length'}], 'A')
    assert parts['anchor'] == e['A']['ggb_value']['value']
    assert all(x['ggb_value']['anchor'] is not None for x in rep['elements'] if x['ggb_type'] == 'text')
    constr = Construction()
    constr.strict_unsupported = constr.log_unsupported = False
    ggb_parser.load(constr, {}, str(path))
    for label, value in (('надпись3', area), ('надпись4', parts)):
        classic = resolve_text_string(constr, constr.element(label).data, value['decimals'])
        assert value['shown'] == classic
        built = _with_text(doc, value, e)
        assert native.validate(native.load(built)) == []
        assert native.evaluate(native.load(built)).elements['t']['value']['text'] == classic
    assert native.has('import_report.text_template')


@pytest.mark.parametrize('body, expected', [
    # a text fixed on the screen: its pixel in drawing coordinates (view: origin 400, 300; 50 px a unit)
    (expression('t', '"Задача"') + element('text', 't', extra='<absoluteScreenLocation x="500" y="200"/>'),
     {'anchor': [2.0, 2.0], 'screen': True, 'template': 'Задача', 'refs': [], 'shown': 'Задача'}),
    # braces of a literal are doubled; a number insert
    (_numeric('k', 2.5) + expression('t', '"{k} = " + k') + element('text', 't', extra='<startPoint x="1" y="2" z="1"/>'),
     {'anchor': [1.0, 2.0], 'template': '{{k}} = {0}', 'refs': [{'ggb_name': 'k', 'as': 'number'}], 'shown': '{k} = 2.5'}),
    # an angle prints degrees
    (element('angle', 'w', extra='<value val="0.5235987755982988"/>') + expression('t', '"w = " + w')
     + element('text', 't', extra='<startPoint x="0" y="0" z="1"/>'),
     {'anchor': [0.0, 0.0], 'template': 'w = {0}', 'refs': [{'ggb_name': 'w', 'as': 'angle'}], 'shown': 'w = 30°'}),
    # a part that is not an object GeoGebra prints as a number or a point: no template
    (point('A', 1.0, 1.0) + expression('t', '"x = " + x(A)') + element('text', 't', extra='<startPoint exp="A"/>'),
     {'anchor': [1.0, 1.0], 'anchor_ref': 'A'}),
])
def test_text_anchor_and_template(body, expected):
    _, rep = _import(ggb_bytes(body))
    value = _by_name(rep)['t']['ggb_value']
    got = {k: v for k, v in value.items() if k not in ('kind', 'text', 'decimals')}
    assert got == expected


def test_dropped_and_warnings():
    body = triangle(command('Midpoint', ['A', 'B'], ['M'])
                    + point('M', 2.0, 0.0, extra='<condition showObject="a&gt;1"/><dynamicColor val1="1" val2="0" '
                                                  'val3="0"/><animation step="0.1" speed="1" type="0" playing="true"/>')
                    + point('Q', 1.0, 1.0).replace('<layer val="0"/>', '<layer val="2"/>'))
    body += '<cascell><inputCell><expression value="x+1"/></inputCell></cascell>'
    _, rep = _import(ggb_bytes(body))
    kinds = {d['kind']: d for d in rep['dropped']}
    assert set(kinds) == {'conditional_visibility', 'dynamic_color', 'animation', 'layers', 'cas'}
    assert kinds['layers']['names'] == ['Q'] and 'names' not in kinds['cas']
    assert _by_name(rep)['Q']['layer'] == 2
    codes = {(w['code'], w.get('ggb_name')) for w in rep['warnings']}
    assert ('conditional_visibility_dropped', 'M') in codes and ('animation_dropped', 'M') in codes


def test_style_and_labels():
    body = (point('A', 0.0, 0.0) + point('B', 4.0, 0.0, show=False)
            + point('C', 1.0, 3.0, label_shown=False)
            + command('Segment', ['A', 'B'], ['s'])
            + element('segment', 's', color=(255, 0, 0), extra=line_style(thickness=6, type_=15, opacity=255)
                      + '<coords x="0" y="1" z="0"/>').replace('<labelMode val="0"/>', '<labelMode val="3"/>'
                                                               '<caption val="основание"/>'))
    doc, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    assert e['s']['ggb_style'] == {'label_color': '#ff0000', 'stroke': '#ff0000', 'stroke_dash_ratio': 0.65,
                                   'stroke_opacity': 1.0, 'stroke_width_px': 3.0}
    assert e['s']['label'] == {'visible': True, 'mode': 'caption', 'caption': 'основание'}
    assert e['A']['ggb_style']['size_px'] == 10.0
    assert all(len(v) == 7 for x in rep['elements'] for k, v in x.get('ggb_style', {}).items()
               if isinstance(v, str) and v.startswith('#'))
    assert e['B']['hidden'] is True and 'hidden' not in e['A']
    app = doc['appearance']
    assert app[e['B']['native_ids'][0]]['visible'] is False
    assert app[e['C']['native_ids'][0]]['label'] == {'mode': 'none'}
    assert app[e['s']['native_ids'][0]]['label'] == {'mode': 'caption', 'text': 'основание'}
    # the GGB colours are not written into the document (decision 8)
    assert all('overrides' not in a for a in app.values())


# the keys of ggb_style and the classic elem.ggb_style they come from
STYLE_KEYS = ('fill', 'fill_opacity', 'stroke', 'stroke_opacity', 'stroke_width_px', 'stroke_dash_ratio',
              'size_px', 'point_shape', 'label_color', 'tick_count', 'angle_range')


@pytest.mark.parametrize('rel', REAL_FILES + sorted(f'tests/native/import/synthetic/{n}.ggb' for n in (
    'triangle_editable', 'intersections', 'style_labels', 'dropped_effects', 'macro', 'regular_polygon')))
def test_ggb_style_is_that_of_the_classic(rel):
    """``ggb_style`` is what the classic ``loadGGB`` puts in ``elem.ggb_style``,
    key for key — a shape without fill too (alpha 0: ``fill_opacity`` 0, not
    the default fill of the style; 1.10.0a2)."""
    from animageo.geo.construction import Construction
    from animageo.parsers import ggb_parser
    _, rep = from_ggb(str(REPO_ROOT / rel), id_namespace=NS)
    constr = Construction()
    constr.strict_unsupported = constr.log_unsupported = False
    ggb_parser.load(constr, {}, str(REPO_ROOT / rel))
    compared = 0
    for e in rep['elements']:
        el = constr.element(e['ggb_name'])
        if el is None or e['category'] not in ('editable', 'differs'):
            continue
        classic = {k: el.ggb_style[k] for k in STYLE_KEYS if k in el.ggb_style}
        assert set(e.get('ggb_style', {})) == set(classic), e['ggb_name']
        for key, value in classic.items():
            assert e['ggb_style'][key] == (pytest.approx(value, abs=1e-6) if isinstance(value, float) else value), \
                (e['ggb_name'], key)
        compared += 1
    assert compared >= 3


def test_a_shape_without_fill_keeps_a_zero_fill():
    body = (point('A', 0.0, 0.0) + point('B', 3.0, 0.0)
            + command('Circle', ['A', 'B'], ['k']) + element('conic', 'k', alpha=0.0, extra=line_style() + CIRCLE_R3))
    _, rep = _import(ggb_bytes(body))
    assert _by_name(rep)['k']['ggb_style']['fill_opacity'] == 0.0
    assert _by_name(rep)['k']['ggb_style']['fill'] == '#1565c0'


def test_a_second_definition_of_a_name_is_a_warning():
    """A name defined twice — two ``<element>``, a text over a polygon, two
    commands: the first definition stands, the second is the warning
    ``duplicate_definition`` (1.10.0a2: the ``<element>`` and the expression
    were dropped silently)."""
    body = triangle(point('A', 5.0, 5.0)
                    + expression('t1', '"Треугольник"') + element('text', 't1', extra='<startPoint x="0" y="4" z="1"/>')
                    + command('Midpoint', ['A', 'B'], ['M']) + point('M', 2.0, 0.0)
                    + command('Midpoint', ['B', 'C'], ['M']))
    doc, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    assert e['t1']['ggb_type'] == 'polygon' and e['t1']['category'] == 'editable'
    assert e['A']['ggb_value']['value'] == [0.0, 0.0]
    dup = sorted(w['ggb_name'] for w in rep['warnings'] if w['code'] == 'duplicate_definition')
    assert dup == ['A', 'M', 't1']


def test_arithmetic_of_numbers_is_editable():
    """``c = a + b``, ``d = (c - 7)^2 / 4``, ``h = r / 2`` of a distance:
    ``number.expression`` with the inputs as ``refs`` (1.10.0a2); the saved
    value is checked. (``sqrt(a)``, ``sin(a)`` and ``2a`` as GeoGebra writes
    them the classic parser does not parse; the import reads them itself —
    :func:`test_expressions_geogebra_writes_are_formulas`, 1.10.0a3.)"""
    body = (_numeric('a', 2.0) + _numeric('b', 3.0) + _numeric('c', 5.0, 'a + b')
            + _numeric('d', 1.0, '(c - 7)^2 / 4')
            + point('A', 0.0, 0.0) + point('B', 3.0, 0.0) + command('Distance', ['A', 'B'], ['r'])
            + _numeric('r', 3.0) + _numeric('h', 1.5, 'r / 2') + _numeric('w', 7.0, 'a * b'))
    doc, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    assert {n: (x['category'], x.get('reason')) for n, x in e.items()} == {
        n: ('editable', None) for n in ('a', 'b', 'c', 'd', 'A', 'B', 'r', 'h')} | {'w': ('differs', 'value_mismatch')}
    op = doc['operations'][doc['elements'][e['c']['native_ids'][0]]['producer']['operationId']]
    assert op['op'] == 'number.expression'
    assert [r['elementId'] for r in op['args']['refs']['items']] == [e['a']['native_ids'][0], e['b']['native_ids'][0]]
    loaded = native.load(doc)
    moved = native.evaluate(loaded, inputs={e['a']['native_ids'][0]: {'kind': 'number', 'value': 4.0}})
    assert moved.elements[e['c']['native_ids'][0]]['value']['value'] == pytest.approx(7.0)
    assert native.has('convert.formula')


def test_an_expression_argument_is_not_carried():
    """A command or a formula inside an argument has no object of its own:
    ``formula_unsupported`` with the expression in ``detail``; the parts of an
    arithmetic expression go into one formula (1.10.0a2)."""
    circle = lambda label, r: element('conic', label, extra=f'<matrix A0="1" A1="1" A2="{-r * r!r}" A3="0" A4="0" A5="0"/>')
    body = (_numeric('r', 2.0) + point('A', 0.0, 0.0) + point('B', 3.0, 0.0)
            + command('Circle', ['A', 'r/2'], ['c']) + circle('c', 1.0)
            + command('Circle', ['A', 'Distance(A, B)'], ['k']) + circle('k', 3.0)
            + _numeric('d', 9.25, 'Distance(A, B) + (r - 7)^2 / 4')
            + _numeric('m', 6.25, '(r - 7)^2 / 4'))
    doc, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    assert {n: (e[n]['category'], e[n]['reason'], e[n].get('detail')) for n in ('c', 'k')} == {
        'c': ('unsupported', 'formula_unsupported', 'аргумент задан выражением: r/2'),
        'k': ('unsupported', 'formula_unsupported', 'аргумент задан выражением: Distance(A, B)')}
    assert (e['d']['category'], e['d']['reason']) == ('unsupported', 'formula_unsupported')
    assert e['m']['category'] == 'editable'
    op = doc['operations'][doc['elements'][e['m']['native_ids'][0]]['producer']['operationId']]
    assert op['args']['expr']['ast'] == {'op': '/', 'args': [
        {'op': '^', 'args': [{'op': '-', 'args': [{'ref': 0}, {'num': 7.0}]}, {'num': 2.0}]}, {'num': 4.0}]}
    assert sorted(el['type'] for el in doc['elements'].values()) == ['number', 'number', 'point', 'point']


def _op_of(doc, entry):
    return doc['operations'][doc['elements'][entry['native_ids'][0]]['producer']['operationId']]


def test_a_fixed_latex_text_refers_to_nothing():
    """The names inside the string literals of a text are not references
    (1.10.0a3): a fixed LaTeX text whose formula has ``a`` and ``n`` has no
    ``depends_on`` and a template without references; a text with the value
    of ``n`` keeps both."""
    from tests.native.ggb_synth import SYNTHETIC
    _, rep = _import(SYNTHETIC['latex_texts'][1]())
    e = _by_name(rep)
    fixed, valued = e['t2'], e['t3']
    assert (fixed['category'], fixed['reason'], fixed['depends_on']) == ('picture', 'latex_macros', [])
    assert (fixed['ggb_value']['template'], fixed['ggb_value']['refs']) == (
        '$S = \\frac{{1}}{{2}} a \\cdot h_a, \\; n \\ge 2$', [])
    assert (valued['category'], valued['depends_on']) == ('picture', ['n'])
    assert (valued['ggb_value']['template'], valued['ggb_value']['refs']) == (
        'n = {0}', [{'ggb_name': 'n', 'as': 'number'}])
    # a label with an index in braces
    body = (_numeric('t_{AB}', 2.0) + expression('t', '"t = " + t_{AB} + " (\\alpha)"')
            + element('text', 't', extra='<startPoint x="0" y="0" z="1"/>'))
    _, rep = _import(ggb_bytes(body))
    t = _by_name(rep)['t']
    assert t['depends_on'] == ['t_{AB}'] and t['ggb_value']['refs'] == [{'ggb_name': 't_{AB}', 'as': 'number'}]
    assert native.has('import_report.text_literals')


def test_angle_bisector_is_angular_bisector(tmp_path):
    """``AngleBisector`` — the name of the interface of GeoGebra — is
    ``AngularBisector`` for the import (1.10.0a3); the classic ``loadGGB``
    reads the file as it is."""
    from animageo.geo.construction import Construction
    from animageo.parsers import ggb_parser
    from tests.native.ggb_synth import SYNTHETIC
    path = tmp_path / 'bisector.ggb'
    path.write_bytes(SYNTHETIC['command_synonym'][1]())
    doc, rep = _import(path)
    e = _by_name(rep)
    g, h = e['g'], e['h']
    assert (g['category'], g['command'], g['signature']) == (h['category'], h['command'], h['signature']) == (
        'editable', 'AngularBisector', 'angular_bisector_ppp')
    assert _op_of(doc, g)['op'] == _op_of(doc, h)['op']
    assert g['native_value'] == h['native_value'] and g['value_check'] == 'passed'
    assert native.has('convert.command_synonyms')
    constr = Construction()
    constr.strict_unsupported = constr.log_unsupported = False
    ggb_parser.load(constr, {}, str(path))
    assert [c.name for c in constr.commands] == ['AngleBisector', 'AngularBisector']


def test_a_point_by_numbers_of_objects_is_not_editable():
    """``P = (A1, B1)``: a free point at the saved place would lose the
    dependency on the numbers — not editable until L4 brings the ops of
    points by coordinates (1.10.0a3; it was a false ``editable``)."""
    body = (_numeric('a', 3.0) + _numeric('b', 6.0) + expression('P', '(a, b)') + point('P', 3.0, 6.0)
            + expression('Q', '(1, 2)') + point('Q', 1.0, 2.0) + command('Midpoint', ['P', 'Q'], ['M'])
            + point('M', 2.0, 4.0))
    _, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    assert (e['P']['category'], e['P']['reason'], e['P']['detail']) == (
        'picture', 'unsupported_signature', 'точка задана числами (координаты или параметр на пути)')
    assert e['P']['depends_on'] == ['a', 'b']
    assert (e['M']['category'], e['M']['reason']) == ('picture', 'depends_on_unsupported')
    assert e['Q']['category'] == e['a']['category'] == e['b']['category'] == 'editable'


def test_expressions_geogebra_writes_are_formulas():
    """``sqrt(a)``, ``sin(a)``, ``2a``, ``a²``, ``abs(a - 7)`` — what GeoGebra
    writes and the classic parser does not parse — are read by the import
    itself into ``number.expression`` (1.10.0a3, decision 3 of the tech lead:
    the classic parser is not changed); the saved value is checked, moving
    the input moves them. What stays outside the formulas says why."""
    from tests.native.ggb_synth import SYNTHETIC
    doc, rep = _import(SYNTHETIC['number_expressions'][1]())
    e = _by_name(rep)
    asts = {'r': {'fn': 'sqrt', 'args': [{'ref': 0}]}, 'si': {'fn': 'sin', 'args': [{'ref': 0}]},
            'd': {'op': '*', 'args': [{'num': 2.0}, {'ref': 0}]}, 'q': {'op': '^', 'args': [{'ref': 0}, {'num': 2.0}]},
            'm': {'fn': 'abs', 'args': [{'op': '-', 'args': [{'ref': 0}, {'num': 7.0}]}]},
            'u': {'op': '-', 'args': [{'op': '*', 'args': [{'fn': 'sqrt', 'args': [{'ref': 0}]}, {'ref': 1}]},
                                      {'num': 4.0}]}}
    a_id, d_id = e['a']['native_ids'][0], e['d']['native_ids'][0]
    for name, ast in asts.items():
        assert (e[name]['category'], e[name]['value_check']) == ('editable', 'passed'), name
        op = _op_of(doc, e[name])
        assert (op['op'], op['args']['expr']['ast']) == ('number.expression', ast), name
        assert [r['elementId'] for r in op['args']['refs']['items']] == ([a_id, d_id] if name == 'u' else [a_id])
    assert e['u']['depends_on'] == ['a', 'd']
    moved = native.evaluate(native.load(doc), inputs={a_id: {'kind': 'number', 'value': 2.25}})
    value = {n: moved.elements[e[n]['native_ids'][0]]['value']['value'] for n in asts}
    assert value == pytest.approx({'r': 1.5, 'si': math.sin(2.25), 'd': 4.5, 'q': 5.0625, 'm': 4.75, 'u': 2.75})
    assert {n: (e[n]['category'], e[n]['reason'], e[n]['detail']) for n in ('fl', 'h')} == {
        'fl': ('unsupported', 'formula_unsupported', 'функции floor нет в формулах'),
        'h': ('unsupported', 'formula_unsupported',
              'вычисление с точками, векторами, углами или отрезками пока не переносится')}
    assert native.has('convert.ggb_expressions')


@pytest.mark.parametrize('exp, value, want', [
    ('2a', 9.0, ('differs', 'value_mismatch')),                 # the saved value is checked
    ('2π', 2 * math.pi, ('editable', None)),                    # a constant: a free number of the saved value
    ('x(A) + a', 5.0, ('unsupported', 'formula_unsupported')),
    ('round(a)', 4.0, ('unsupported', 'formula_unsupported')),
    ('2a +', 8.0, ('unsupported', 'parse_error')),
    ('sqrt(s)', 3.0, ('unsupported', 'formula_unsupported')),
])
def test_an_expression_of_a_number_is_checked(exp, value, want):
    body = (point('A', 1.0, 0.0) + point('B', 1.0, 9.0) + command('Segment', ['A', 'B'], ['s'])
            + element('segment', 's', extra='<coords x="1" y="0" z="-1"/>') + _numeric('a', 4.0)
            + _numeric('k', value, exp) + command('Circle', ['A', 'k'], ['c'])
            + element('conic', 'c', extra=f'<matrix A0="1" A1="1" A2="{1 - value * value!r}" A3="0" A4="-1" A5="0"/>'))
    doc, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    assert (e['k']['category'], e['k'].get('reason')) == want
    if want[0] == 'unsupported':
        assert e['k']['detail'] and (e['c']['category'], e['c']['reason']) == ('closure', 'depends_on_unsupported')
    else:                       # the circle of the radius k: as k
        assert e['c']['category'] == want[0]
    if want == ('differs', 'value_mismatch'):
        assert e['k']['delta'] == pytest.approx(1.0)


def test_abs_of_a_measure():
    """``abs(r - 7)`` of a distance: the classic parses it into commands whose
    ``abs`` has no signature (1.10.0a2: not translated); the import reads the
    expression itself — one formula with the reference ``r``, no element
    without its object (1.10.0a3)."""
    body = (point('A', 0.0, 0.0) + point('B', 3.0, 4.0) + command('Distance', ['A', 'B'], ['r']) + _numeric('r', 5.0)
            + _numeric('m', 2.0, 'abs(r - 7)') + _numeric('m2', 15.0, 'abs(r) + 2 r') + _numeric('k', 3.0, 'm + 1'))
    doc, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    assert all(x['category'] == 'editable' for x in rep['elements'])
    assert _op_of(doc, e['m'])['args']['expr']['ast'] == {
        'fn': 'abs', 'args': [{'op': '-', 'args': [{'ref': 0}, {'num': 7.0}]}]}
    assert sorted(doc['bindings']['legacyNames'].values()) == sorted(e) and len(doc['elements']) == len(e)


def test_an_angle_by_an_expression():
    """An ``angle`` by an expression the classic does not parse: a constant is
    the free angle of its saved value; computed from objects it stays
    outside — ``number.expression`` gives a number, not an angle; a formula
    over an angle of a figure stays outside too (1.10.0a3)."""
    body = (element('angle', 'α', extra='<value val="0.5"/>') + _angle('b1', 2 * math.pi / 3, '2π/3')
            + _angle('b4', 1.0, '2 α') + point('A', 0.0, 0.0) + point('B', 1.0, 0.0) + point('C', 0.0, 1.0)
            + command('Angle', ['B', 'A', 'C'], ['γ']) + _angle('γ', math.pi / 2) + _numeric('k', 1.0, 'sin(γ)')
            + _numeric('h', 0.25, 'α/2') + command('Rotate', ['B', 'b1', 'A'], ['B1'])
            + point('B1', -0.5, math.sqrt(3) / 2))
    doc, rep = _import(ggb_bytes(body))
    e = _by_name(rep)
    note = 'вычисление с точками, векторами, углами или отрезками пока не переносится'
    assert {n: (e[n]['category'], e[n].get('reason'), e[n].get('detail')) for n in ('b1', 'b4', 'k', 'h', 'B1')} == {
        'b1': ('editable', None, None), 'b4': ('unsupported', 'formula_unsupported', note),
        'k': ('unsupported', 'formula_unsupported', note), 'h': ('editable', None, None), 'B1': ('editable', None, None)}
    assert _op_of(doc, e['b1'])['op'] == 'number.angle'
    assert _op_of(doc, e['h'])['op'] == 'number.expression'


def test_seq_and_steps_from_breakpoints():
    body = (point('A', 0.0, 0.0, extra='<breakpoint val="true"/>') + point('B', 4.0, 0.0)
            + command('Segment', ['A', 'B'], ['s'])
            + element('segment', 's', extra='<coords x="0" y="1" z="0"/><breakpoint val="true"/>')
            + command('Midpoint', ['s'], ['M']) + point('M', 2.0, 0.0))
    doc, rep = _import(ggb_bytes(body))
    op_of = {e['ggb_name']: doc['elements'][e['native_ids'][0]]['producer']['operationId'] for e in rep['elements']}
    assert [doc['operations'][op_of[n]]['seq'] for n in ('A', 'B', 's', 'M')] == [1, 2, 3, 4]
    assert [s['operationIds'] for s in doc['steps']] == [[op_of['A']], [op_of['B'], op_of['s']], [op_of['M']]]
    assert [s.operationIds for s in native.steps(native.load(doc))] == [s['operationIds'] for s in doc['steps']]
    # no breakpoints — no steps
    doc, _ = _import(ggb_bytes(triangle()))
    assert 'steps' not in doc


def test_strict_mode():
    path = REPO_ROOT / 'tests/fixtures/label_anchor_types.ggb'
    with pytest.raises(native.ConvertError) as exc:
        from_ggb(path, id_namespace=NS, mode='strict')
    assert {i['name'] for i in exc.value.items} == {'e1', 'e2'}
    doc, rep = from_ggb(REPO_ROOT / 'docs/guide/assets/ggb/sample_triangle.ggb', id_namespace=NS, mode='strict')
    assert rep['summary']['editable'] == len(rep['elements'])


def test_nothing_to_carry_over():
    doc, rep = _import(ggb_bytes(element('point3d', 'P', extra='<coords x="1" y="2" z="3" w="1"/>')))
    assert doc is None and rep['summary']['unsupported'] == 1
    doc, rep = _import(ggb_bytes(''))
    assert doc is None and rep['elements'] == []


def test_an_empty_document_on_request():
    # a file of pictures only: the web places them on an empty document (1.10.0a2)
    pictures = ggb_bytes(expression('t', '"Задача 1"')
                         + element('text', 't', extra='<startPoint x="1" y="2" z="1"/>')
                         + element('point3d', 'P', extra='<coords x="1" y="2" z="3" w="1"/>'))
    doc, rep = _import(pictures)
    assert doc is None
    doc, rep = _import(pictures, empty_document=True)
    assert doc['operations'] == {} and doc['elements'] == {}
    assert doc['viewDefaults']['bounds'] == [-8.0, -6.0, 8.0, 6.0]        # the view of the file
    assert rep['document_hash'] == native.content_hash(doc)
    assert {e['category'] for e in rep['elements']} == {'picture', 'unsupported'}
    assert doc['documentId'] == from_ggb(pictures, id_namespace=NS, empty_document=True)[0]['documentId']
    doc, rep = _import(ggb_bytes(''), empty_document=True)
    assert doc['elements'] == {} and rep['elements'] == []
    full, _ = _import(ggb_bytes(triangle()), empty_document=True)
    assert full == _import(ggb_bytes(triangle()))[0]
    assert native.has('from_ggb.empty_document')


# ── untrusted input (plan §7) ───────────────────────────────────────────

def test_expression_cannot_reach_dunders(tmp_path):
    marker = tmp_path / 'pwned'
    exp = ("[c for c in ().__class__.__base__.__subclasses__() if c.__name__ == 'Popen'][0]"
           f"(['touch', '{marker}'])")
    data = ggb_bytes(expression('a', exp) + element('numeric', 'a', extra='<value val="0"/>')
                     + point('A', 0.0, 0.0) + command('Translate', ['A', "().__class__.__base__"], ['B'])
                     + point('B', 1.0, 1.0))
    doc, rep = _import(data)
    assert not marker.exists()
    e = _by_name(rep)
    assert (e['a']['category'], e['a']['reason']) == ('unsupported', 'parse_error')
    assert e['B']['category'] != 'editable'
    assert e['A']['category'] == 'editable'


@pytest.mark.parametrize('data, code', [
    (b'not a zip', 'import_not_ggb'),
    (ggb_bytes(xml=b'', extra=None).replace(b'geogebra.xml', b'geogebra.txt'), 'import_not_ggb'),
])
def test_refused_files(data, code):
    with pytest.raises(ImportRefused) as exc:
        from_ggb(data, id_namespace=NS)
    assert exc.value.code == code


def test_limits():
    small = ggb_bytes(triangle())
    with pytest.raises(ImportRefused) as exc:
        from_ggb(small, id_namespace=NS, limits={'file_bytes': 100})
    assert exc.value.code == 'import_too_large'
    with pytest.raises(ImportRefused) as exc:
        from_ggb(small, id_namespace=NS, limits={'objects': 3})
    assert exc.value.code == 'import_too_many_objects'
    many = ggb_bytes(triangle(), extra={f'f{i}.txt': b'x' for i in range(LIMITS['entries'] + 1)})
    with pytest.raises(ImportRefused) as exc:
        from_ggb(many, id_namespace=NS)
    assert exc.value.code == 'import_too_large'


def test_zip_bomb_is_refused_without_inflating():
    bomb = ggb_bytes(triangle(), extra={'thumbnail.png': b'\0' * (LIMITS['unpacked_bytes'] + 1)})
    assert len(bomb) < 200_000
    with pytest.raises(ImportRefused) as exc:
        read_ggb(bomb)
    assert exc.value.code == 'import_too_large'
    # an XML larger than its limit
    with pytest.raises(ImportRefused) as exc:
        from_ggb(ggb_bytes(triangle()), id_namespace=NS, limits={'xml_bytes': 200})
    assert exc.value.code == 'import_too_large'


def test_lying_entry_size_is_caught_by_the_bounded_read():
    data = bytearray(ggb_bytes(triangle()))
    # the central directory claims 100 bytes for geogebra.xml (the first entry); the real one is larger
    cd = bytes(data).find(b'PK\x01\x02')
    assert int.from_bytes(data[cd + 24:cd + 28], 'little') == len(ggb_xml(triangle())) > 1000
    data[cd + 24:cd + 28] = (100).to_bytes(4, 'little')
    with pytest.raises(ImportRefused) as exc:
        read_ggb(bytes(data), limits={'xml_bytes': 1000})
    assert exc.value.code in ('import_too_large', 'import_not_ggb')


def test_dtd_and_entities_are_refused():
    evil = (b'<?xml version="1.0"?><!DOCTYPE g [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;">]>'
            b'<geogebra><construction><element type="point" label="&b;"/></construction></geogebra>')
    with pytest.raises(ImportRefused) as exc:
        from_ggb(ggb_bytes(xml=evil), id_namespace=NS)
    assert exc.value.code == 'ggb_invalid'
    external = b'<?xml version="1.0"?><!DOCTYPE g SYSTEM "file:///etc/passwd"><geogebra/>'
    with pytest.raises(ImportRefused):
        from_ggb(ggb_bytes(xml=external), id_namespace=NS)


def test_xml_depth_is_limited():
    deep = b'<geogebra><construction>' + b'<a>' * 100 + b'</a>' * 100 + b'</construction></geogebra>'
    with pytest.raises(ImportRefused) as exc:
        from_ggb(ggb_bytes(xml=deep), id_namespace=NS)
    assert exc.value.code == 'ggb_invalid'
    with pytest.raises(ImportRefused):
        from_ggb(ggb_bytes(xml=b'<geogebra><construction>'), id_namespace=NS)


# ── CLI ────────────────────────────────────────────────────────────────

def test_cli_from_ggb(tmp_path, capsys):
    src = REPO_ROOT / 'tests/fixtures/label_anchor_types.ggb'
    out, rep_path = tmp_path / 'doc.json', tmp_path / 'rep.json'
    assert main(['from-ggb', str(src), '-o', str(out), '--report', str(rep_path),
                 '--namespace', str(NS)]) == 0
    doc, rep = json.loads(out.read_text(encoding='utf-8')), json.loads(rep_path.read_text(encoding='utf-8'))
    assert doc == from_ggb(src, id_namespace=NS)[0]
    assert rep['summary']['unsupported'] == 2
    assert main(['from-ggb', str(src), '--mode', 'strict']) == 1
    bad = tmp_path / 'bad.ggb'
    bad.write_bytes(b'not a zip')
    assert main(['from-ggb', str(bad)]) == 2
    assert main(['from-ggb', str(tmp_path / 'missing.ggb')]) == 2
    capsys.readouterr()
    # the default namespace comes from the file: the same file, the same IDs
    assert main(['from-ggb', str(src), '-o', str(out)]) == 0
    first = out.read_text(encoding='utf-8')
    assert main(['from-ggb', str(src), '-o', str(out)]) == 0
    assert out.read_text(encoding='utf-8') == first


def test_feature_flags():
    assert native.has('from_ggb') and native.has('from_construction') and native.has('import_report.v1')
    assert native.from_ggb is from_ggb


def test_a_picture_and_its_dependents():
    # Rotate by an arithmetic of a slider: the point is a picture; what depends on it does not translate
    data = ggb_bytes(element('angle', 'α', extra='<value val="1.7"/><slider min="0" max="6.28" width="100" x="1" '
                                               'y="1" fixed="true" horizontal="true" showAlgebra="true"/>')
                     + point('I', 1.0, 0.0) + point('G', 0.0, 0.0)
                     + command('Rotate', ['I', '(4 * (α - 90°))', 'G'], ["I'"]) + point("I'", 0.0, 1.0)
                     + command('Midpoint', ["I'", 'G'], ['M']) + point('M', 0.0, 0.5)
                     + command('Circle', ['M', '0.35'], ['r']) + element('conic', 'r', extra=CIRCLE_R3))
    doc, rep = _import(data)
    e = _by_name(rep)
    assert (e["I'"]['category'], e["I'"]['reason']) == ('picture', 'formula_unsupported')
    assert '4 * (α - 90°)' in e["I'"]['detail']
    assert (e['M']['category'], e['M']['reason']) == ('picture', 'depends_on_unsupported')
    assert (e['r']['category'], e['r']['reason']) == ('unsupported', 'depends_on_unsupported')
    assert e['α']['category'] == 'editable'


def test_a_command_the_classic_cannot_run():
    data = ggb_bytes(point('A', 0.0, 0.0) + command('FooBar', ['A'], ['B']) + point('B', 1.0, 1.0)
                     + command('Segment', ['A', 'B'], ['s']) + element('segment', 's', extra='<coords x="1" y="-1" z="0"/>')
                     + point('C', 0.0, 1.0) + command('Plane', ['A', 'B', 'C'], ['p']) + element('plane3d', 'p'))
    doc, rep = _import(data)
    e = _by_name(rep)
    assert (e['B']['category'], e['B']['reason']) == ('picture', 'no_registry_op')
    assert e['B']['detail'] == 'команда FooBar не переносится'
    assert (e['s']['category'], e['s']['reason']) == ('picture', 'depends_on_unsupported')
    assert e['s']['ggb_value'] == {'kind': 'segment', 'value': [[0.0, 0.0], [1.0, 1.0]]}
    assert (e['p']['category'], e['p']['reason']) == ('unsupported', '3d')


@pytest.mark.parametrize('style, stored', [(1, 1.5 * 3.141592653589793), (1, 0.5 * 3.141592653589793),
                                           (2, 1.5 * 3.141592653589793), (None, 1.5 * 3.141592653589793)])
def test_angle_values_by_style(style, stored):
    # A at 135°, B at 45°: the ccw angle AOB is 270°, the angle shown not reflex is 90°
    extra = (f'<angleStyle val="{style}"/>' if style is not None else '') + f'<value val="{stored!r}"/>'
    data = ggb_bytes(point('O', 0.0, 0.0) + point('A', -1.0, 1.0) + point('B', 1.0, 1.0)
                     + command('Angle', ['A', 'O', 'B'], ['α']) + element('angle', 'α', extra=extra))
    doc, rep = _import(data)
    a = _by_name(rep)['α']
    assert a['category'] == 'editable'
    if style is not None:
        assert a['ggb_style']['angle_range'] == ('reflex' if style == 2 else 'minor')
    wrong = ggb_bytes(point('O', 0.0, 0.0) + point('A', -1.0, 1.0) + point('B', 1.0, 1.0)
                      + command('Angle', ['A', 'O', 'B'], ['α']) + element('angle', 'α', extra='<value val="1.0"/>'))
    assert _by_name(_import(wrong)[1])['α']['category'] == 'differs'
