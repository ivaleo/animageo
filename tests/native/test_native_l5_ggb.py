"""``native.from_ggb``: the import of ``.ggb`` and ``import_report.v1`` (kernel stage L5, plan §3.5–§3.8, §7)."""
import json
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
