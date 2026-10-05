"""1.9.0a1: ``seq``, ``steps[]``, ``appearance.role`` in the document,
``native.steps``/``steps_merge``/``steps_split``/``assign_seq``,
``native.describe`` with the phrase table, ``native.has`` (plan L3 §2.3–§2.6)."""
import copy
import os
import re

import pytest

from animageo import native
from animageo.native import parity
from animageo.native.describe import PHRASES_PATH, phrase_table
from animageo.native.registry import registry
from tests.native.conftest import NATIVE_DIR, REPO_ROOT, SCENES_DIR, DocBuilder, num, read_json, ref

STEPS_DIR = NATIVE_DIR / 'parity' / 'v1' / 'steps'
SNAPSHOTS = REPO_ROOT / 'tests' / 'native' / 'snapshots' / 'describe'
SCENES = sorted(SCENES_DIR.glob('*.json'))


def triangle_doc(polygon=True):
    b = DocBuilder(registry_version='1.5')
    b.free('A', 1, 3).free('B', 0, 0).free('C', 4, 0)
    if polygon:
        b.op('op_T', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [ref('A'), ref('B'), ref('C')]}},
             [('polygon', 't', 'polygon')])
    b.segment('a', 'B', 'C')
    b.doc['elements']['a']['displayName'] = ''
    b.op('op_h', 'triangle.altitude', {'vertex': ref('A'), 'side': ref('a')},
         [('altitude', 'h', 'segment'), ('foot', 'H', 'point')])
    b.op('op_o', 'circle.three_points', {'a': ref('A'), 'b': ref('B'), 'c': ref('C')}, [('circle', 'o', 'circle')])
    return b.doc


def codes(issues):
    return [i.code for i in issues]


# ── document: seq, steps, role ───────────────────────────────────────────

def test_validate_steps_errors():
    doc = triangle_doc()
    doc['steps'] = [{'id': 'g1', 'kind': 'group', 'operationIds': ['op_h', 'nope']},
                    {'id': 'g2', 'kind': 'group', 'operationIds': ['op_h']},
                    {'id': 'g3', 'kind': 'group', 'operationIds': []},
                    {'id': 'g1', 'kind': 'group', 'operationIds': ['op_o']}]
    assert codes(native.validate(doc)) == ['step_unknown_operation', 'step_duplicate_operation', 'step_empty',
                                           'step_duplicate_id']
    with pytest.raises(native.StepError):
        native.steps(doc)


def test_validate_step_cycle():
    doc = triangle_doc()
    # a group of A and the altitude needs a, which needs B and C outside the group … and the group
    # of B holds the circle that needs A: g1 → g2 → g1
    doc['steps'] = [{'id': 'g1', 'kind': 'group', 'operationIds': ['op_A', 'op_h']},
                    {'id': 'g2', 'kind': 'group', 'operationIds': ['op_B', 'op_o']}]
    assert codes(native.validate(doc)) == ['step_cycle', 'step_cycle']


def test_validate_seq_duplicate_and_role_unknown_are_warnings():
    doc = triangle_doc()
    doc['operations']['op_h']['seq'] = 2
    doc['operations']['op_o']['seq'] = 2
    doc['appearance'] = {'h': {'role': 'sought'}, 'o': {'role': 'main'}}
    issues = native.validate(doc)
    assert [(i.code, i.severity) for i in issues] == [('seq_duplicate', 'warning'), ('role_unknown', 'warning')]
    assert issues[0].operationId == 'op_o'


def test_a_document_without_the_new_fields_validates_as_before():
    for path in SCENES:
        doc = read_json(path)['document']
        assert not any(i.code.startswith(('step_', 'seq_', 'role_')) for i in native.validate(doc)), path.stem


# ── steps ────────────────────────────────────────────────────────────────

def test_steps_given_then_one_step_per_operation():
    rows = [(s.id, s.kind, s.operationIds, s.elementIds) for s in native.steps(triangle_doc())]
    assert rows == [('given', 'given', ['op_A', 'op_B', 'op_C'], ['A', 'B', 'C']),
                    ('op:op_T', 'op', ['op_T'], ['t']),
                    ('op:op_a', 'op', ['op_a'], ['a']),
                    ('op:op_h', 'op', ['op_h'], ['h', 'H']),
                    ('op:op_o', 'op', ['op_o'], ['o'])]


def test_steps_order_by_seq_after_operations_without_seq():
    doc = triangle_doc()
    doc['operations']['op_T']['seq'] = 1
    doc['operations']['op_a']['seq'] = 2
    assert [s.id for s in native.steps(doc)] == ['given', 'op:op_o', 'op:op_T', 'op:op_a', 'op:op_h']


def test_steps_hidden_outputs_are_aux_and_explicit_given_cancels_the_automatic():
    doc = triangle_doc()
    doc['appearance'] = {'a': {'visible': False}}
    doc['steps'] = [{'id': 'g', 'kind': 'given', 'operationIds': ['op_A', 'op_B']}]
    steps = native.steps(doc)
    assert [s.id for s in steps] == ['g', 'op:op_C', 'op:op_T', 'op:op_a', 'op:op_h', 'op:op_o']
    a = steps[3]
    assert a.elementIds == [] and a.auxElementIds == ['a']


def test_steps_group_keeps_dependency_order_inside():
    doc = triangle_doc()
    doc['steps'] = [{'id': 'g', 'kind': 'group', 'title': 'Высота', 'operationIds': ['op_h', 'op_a']}]
    steps = native.steps(doc)
    group = next(s for s in steps if s.id == 'g')
    assert group.operationIds == ['op_a', 'op_h'] and group.title == 'Высота'


def test_assign_seq():
    doc = triangle_doc()
    doc['operations']['op_T']['seq'] = 4
    out = native.assign_seq(doc, ['op_h', 'op_a'])
    assert out['operations']['op_h']['seq'] == 5 and out['operations']['op_a']['seq'] == 6
    assert 'seq' not in doc['operations']['op_h']            # a copy
    with pytest.raises(ValueError):
        native.assign_seq(doc, ['nope'])


def test_steps_merge_and_split():
    doc = triangle_doc()
    merged = native.steps_merge(doc, 'op:op_h')
    assert merged == [{'id': 's1', 'kind': 'group', 'operationIds': ['op_a', 'op_h']}]
    doc['steps'] = merged
    assert [s.id for s in native.steps(doc)] == ['given', 'op:op_T', 's1', 'op:op_o']
    merged = native.steps_merge(doc, 'op:op_T')                 # into the automatic «Дано»
    assert merged == [{'id': 's1', 'kind': 'group', 'operationIds': ['op_a', 'op_h']},
                      {'id': 'given', 'kind': 'given', 'operationIds': ['op_A', 'op_B', 'op_C', 'op_T']}]
    doc['steps'] = merged
    split = native.steps_split(doc, 'given', ['op_T'])
    assert split == [{'id': 's1', 'kind': 'group', 'operationIds': ['op_a', 'op_h']},
                     {'id': 'given', 'kind': 'given', 'operationIds': ['op_A', 'op_B', 'op_C']},
                     {'id': 's2', 'kind': 'group', 'operationIds': ['op_T']}]
    with pytest.raises(ValueError):
        native.steps_merge(doc, 'given')                        # the first step
    with pytest.raises(ValueError):
        native.steps_split(doc, 'op:op_o', ['op_o'])


def test_steps_split_refuses_a_cycle():
    doc = triangle_doc()
    doc['steps'] = [{'id': 'g', 'kind': 'group', 'operationIds': ['op_B', 'op_a', 'op_h']}]
    assert native.validate(doc) == []
    with pytest.raises(native.StepError) as err:
        native.steps_split(doc, 'g', ['op_a'])          # h (in g) needs a, a needs B (in g)
    assert [i.code for i in err.value.issues] == ['step_cycle', 'step_cycle']


# ── describe ─────────────────────────────────────────────────────────────

def test_describe_triangle_context_and_given_triangle():
    lines = native.describe(triangle_doc())
    assert lines == ['1. Строим треугольник ABC.',
                     '2. Строим отрезок BC.',
                     '3. Проводим высоту h треугольника ABC из вершины A.',
                     '4. Строим описанную окружность o треугольника ABC.']


def test_describe_without_a_triangle_polygon():
    lines = native.describe(triangle_doc(polygon=False))
    assert lines == ['1. Дано: точки A, B, C.',
                     '2. Строим отрезок BC.',
                     '3. Проводим высоту h из вершины A к стороне BC.',
                     '4. Строим окружность o через точки A, B, C.']


def test_describe_groups_titles_texts_and_overlay():
    doc = triangle_doc(polygon=False)
    doc['steps'] = [{'id': 'g', 'kind': 'group', 'title': 'Высота', 'operationIds': ['op_a', 'op_h']},
                    {'id': 'k', 'kind': 'group', 'text': 'Окружность через вершины', 'operationIds': ['op_o']}]
    lines = native.describe(doc, phrases={'steps': {'segment': {'text': 'Соединяем {a} и {b}'}}})
    assert lines == ['1. Дано: точки A, B, C.', '2. Высота.', '2.1. Соединяем B и C.',
                     '2.2. Проводим высоту h из вершины A к стороне BC.', '3. Окружность через вершины.']
    with pytest.raises(NotImplementedError):
        native.describe(doc, values=True)


def test_describe_names_hidden_lines_by_their_points():
    from animageo.native.commands import parse_commands
    data = parse_commands('A = (1, 3)\nB = (0, 0)\nC = (4, 0)\nh, H = Высота(A, BC)', document_id='d').document.data
    assert native.describe(data)[-1] == '3. Проводим высоту h из вершины A к стороне BC.'


def test_phrases_cover_registry():
    table = phrase_table()
    assert table['format'] == 'animageo-phrases/v1' and table['lang'] == 'ru'
    reg = registry()
    placeholder = re.compile(r'\{([^{}]+)\}')
    for name in sorted(reg.ops):
        record = reg.get(name)
        entry = table['steps'].get(record['stepKind'])
        assert entry is not None, record['stepKind']
        slots = {i['slot'] for i in record['inputs']} | {p['slot'] for p in record['params']} | \
            {o['slot'] for o in record['outputs']}
        templates = [(entry.get('ops') or {}).get(name) or entry['text']]
        templates += [c['text'] for c in entry.get('context') or ()]
        for i, template in enumerate(templates):
            if i > 0 and not _context_applies(entry['context'][i - 1]['when'], record):
                continue
            for key in placeholder.findall(template):
                keys = key[4:].split(',') if key.startswith('out:') else [key]
                extra = {'triangle', 'vertices'}
                assert all(k in slots or k in extra for k in keys), (name, template, key)
    for key in ('point', 'points', 'number', 'numbers', 'numbers_only', 'triangle'):
        assert key in table['given']
    assert PHRASES_PATH.name == 'ru.v1.json'


def _context_applies(when, record):
    slots = {i['slot'] for i in record['inputs']}
    if when == 'triangle_vertices':
        return {'a', 'b', 'c'} <= slots or {'vertex', 'side'} <= slots
    if when == 'three_vertices':
        return record['op'] == 'polygon.by_points'
    return record['op'] == 'locus.of_point'


def test_has_and_features():
    assert native.FEATURES[:7] == ('triangle', 'locus', 'steps', 'describe', 'render.eps', 'render.tikz', 'roles')
    assert native.has('locus') and not native.has('timeline')


# ── fixtures animageo-steps/v1 and the describe snapshots ────────────────

def test_steps_fixtures_cover_every_scene_and_verify():
    assert sorted(p.name for p in STEPS_DIR.glob('*.json')) == [p.name for p in SCENES]
    files, cases, mismatches = parity.verify([STEPS_DIR])
    assert mismatches == [] and files == len(SCENES) == cases
    fixture = read_json(STEPS_DIR / 'triangle_chain.json')
    assert list(fixture) == ['format', 'id', 'registry', 'generatedBy', 'document', 'expect']
    assert fixture['registry'] == native.__registry_version__
    assert list(fixture['expect']) == ['steps', 'describe', 'timeline']


def test_steps_fixture_reproduces():
    for path in SCENES:
        scene = read_json(path)
        fixture = read_json(STEPS_DIR / path.name)
        assert parity.steps_fixture(scene)['expect'] == fixture['expect'], path.stem


@pytest.mark.parametrize('path', SCENES, ids=lambda p: p.stem)
def test_describe_snapshots(path):
    text = '\n'.join(native.describe(read_json(path)['document'])) + '\n'
    snapshot = SNAPSHOTS / (path.stem + '.txt')
    if os.environ.get('ANIMAGEO_UPDATE_SNAPSHOTS'):
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(text, encoding='utf-8')
    assert snapshot.read_text(encoding='utf-8') == text


def test_steps_ignore_values_and_inputs():
    doc = triangle_doc()
    moved = copy.deepcopy(doc)
    moved['inputs']['A'] = {'kind': 'point', 'value': [2, 0]}         # collinear: the altitude is undefined
    assert native.describe(doc) == native.describe(moved)
    assert num(1) == {'kind': 'number', 'value': 1}
