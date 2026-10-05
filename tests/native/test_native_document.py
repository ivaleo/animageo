"""Document load/validate/dump, the JSON Schema mirror and closure."""
import copy
import json
import math

import pytest

from animageo import native
from animageo.native.canonical import canonical_json
from animageo.native.document import structure_issues
from tests.native.conftest import NATIVE_DIR, SCENES_DIR, DocBuilder, point_input, read_json, ref, ref_list

SCHEMA_PATH = NATIVE_DIR / 'schema' / 'construction.v1.schema.json'


def triangle_doc():
    b = DocBuilder('tri').free('A', 0, 0).free('B', 4, 0).free('C', 0, 3)
    b.midpoint('M', 'A', 'B').line('l', 'A', 'B').polygon('T', 'A', 'B', 'C', sides=[(1, 'sAB')])
    return b.doc


WORK_INTENT = {
    'condition': {'text': 'В треугольнике ABC проведена биссектриса AL.', 'source': 'photo',
                  'quote': 'биссектриса AL', 'mediaRef': 'media_17'},
    'forbid': ['solution', 'move_given'],
    'assumptions': ['AB = AC'],
    'briefRevision': 4,
}


def codes(issues):
    return sorted({i.code for i in issues})


# ── load / dump ──────────────────────────────────────────────────────────


class TestLoad:
    def test_sources(self, tmp_path):
        doc = triangle_doc()
        text = json.dumps(doc)
        path = tmp_path / 'doc.json'
        path.write_text(text, encoding='utf-8')
        for source in (doc, text, text.encode('utf-8'), path, str(path)):
            loaded = native.load(source)
            assert isinstance(loaded, native.NativeDocument)
            assert loaded.data == doc
        assert native.load(native.load(doc)).data == doc

    def test_load_copies(self):
        doc = triangle_doc()
        loaded = native.load(doc)
        doc['elements']['A']['displayName'] = 'changed'
        assert loaded.elements['A']['displayName'] == 'A'

    def test_properties(self):
        loaded = native.load(triangle_doc())
        assert loaded.document_id == 'tri'
        assert loaded.registry_version == '1.0'
        assert loaded.bounds == [-10, -10, 10, 10]
        assert set(loaded.operations) == {'op_A', 'op_B', 'op_C', 'op_M', 'op_l', 'op_T'}

    @pytest.mark.parametrize('text', [
        '{"format": NaN}', '{"a": 1, "a": 2}', '[1, 2]', '{"format": Infinity}', '{not json',
    ])
    def test_unreadable_json(self, text):
        with pytest.raises(native.LoadError) as info:
            native.load(text)
        assert info.value.issues and info.value.issues[0].code == 'schema'

    def test_strict_and_lenient(self):
        doc = triangle_doc()
        del doc['documentId']
        with pytest.raises(native.LoadError) as info:
            native.load(doc)
        assert any("'documentId'" in i.message for i in info.value.issues)
        lenient = native.load(doc, strict=False)
        assert codes(lenient.schema_issues) == ['schema']
        assert codes(native.validate(lenient)) == ['schema']
        with pytest.raises(native.LoadError):
            native.evaluate(lenient)

    def test_nan_in_python_dict_is_a_schema_issue(self):
        doc = triangle_doc()
        doc['inputs']['A'] = point_input(math.nan, 0)
        with pytest.raises(native.LoadError):
            native.load(doc)

    def test_type_error(self):
        with pytest.raises(TypeError):
            native.load(42)


class TestDump:
    def test_unknown_keys_and_no_defaults(self):
        doc = triangle_doc()
        doc['futureSection'] = {'x': [1, 2]}
        doc['appearance'] = {'A': {'visible': True, 'label': {'mode': 'name'}, 'overrides': {}}}
        doc['elements']['A']['origin'] = {'actionId': 'a1', 'source': 'tool'}
        del doc['viewDefaults']
        loaded = native.load(doc)
        assert native.dump(loaded) == doc
        assert 'viewDefaults' not in native.dump(loaded)

    def test_canonical_dump_of_canonical_input_is_identical(self):
        doc = triangle_doc()
        doc['inputs']['B'] = point_input(4.0, -0.0)
        canonical = canonical_json(doc)
        assert native.dumps(native.load(canonical)) == canonical
        assert native.dumps(canonical) == canonical
        assert native.dumps(native.load(json.dumps(doc, indent=3))) == canonical

    def test_content_hash(self):
        doc = triangle_doc()
        h = native.content_hash(native.load(doc))
        assert h.startswith('sha256:') and len(h) == len('sha256:') + 64
        assert native.content_hash(doc) == h
        assert native.content_hash(json.dumps(doc, indent=1)) == h
        doc['inputs']['A'] = point_input(0.5, 0)
        assert native.content_hash(doc) != h

    def test_work_intent_and_locked_round_trip(self):
        doc = triangle_doc()
        doc['workIntent'] = copy.deepcopy(WORK_INTENT)
        doc['appearance'] = {'A': {'locked': True}, 'B': {'locked': False, 'visible': True}}
        loaded = native.load(doc)
        assert native.validate(loaded) == []
        assert native.dump(loaded) == doc
        canonical = native.dumps(loaded)
        assert json.loads(canonical)['workIntent'] == WORK_INTENT
        assert native.dumps(native.load(canonical)) == canonical
        plain = triangle_doc()
        assert native.content_hash(doc) != native.content_hash(plain)
        changed = copy.deepcopy(doc)
        changed['workIntent']['briefRevision'] = 5
        assert native.content_hash(changed) != native.content_hash(doc)
        unlocked = copy.deepcopy(doc)
        unlocked['appearance']['A']['locked'] = False
        assert native.content_hash(unlocked) != native.content_hash(doc)

    def test_work_intent_and_locked_do_not_change_evaluation(self):
        doc = triangle_doc()
        plain = native.evaluate(doc)
        doc['workIntent'] = copy.deepcopy(WORK_INTENT)
        doc['appearance'] = {'A': {'locked': True}}
        result = native.evaluate(doc)
        assert result.elements == plain.elements and result.scale == plain.scale

    def test_bad_work_intent_is_a_schema_issue(self):
        doc = triangle_doc()
        doc['workIntent'] = {'forbid': ['answer']}
        with pytest.raises(native.LoadError):
            native.load(doc)
        assert codes(native.validate(doc)) == ['schema']

    def test_dump_is_a_copy(self):
        loaded = native.load(triangle_doc())
        dumped = native.dump(loaded)
        dumped['elements'].clear()
        assert loaded.elements


# ── validate ─────────────────────────────────────────────────────────────


class TestValidate:
    def test_valid(self):
        assert native.validate(triangle_doc()) == []

    def _issues(self, mutate):
        doc = triangle_doc()
        mutate(doc)
        return native.validate(native.load(doc))

    def test_id_mismatch(self):
        def m(doc):
            doc['elements']['A']['id'] = 'A2'
        assert 'id_mismatch' in codes(self._issues(m))

    def test_dangling_ref(self):
        def m(doc):
            doc['operations']['op_M']['args']['b'] = ref('ghost')
        issues = self._issues(m)
        assert codes(issues) == ['dangling_ref']
        assert issues[0].operationId == 'op_M'
        assert issues[0].path == '/operations/op_M/args/b/elementId'

    def test_type_mismatch_of_argument(self):
        def m(doc):
            doc['operations']['op_M']['args']['b'] = ref('l')
        assert codes(self._issues(m)) == ['type_mismatch']

    def test_type_mismatch_of_element(self):
        def m(doc):
            doc['elements']['M']['type'] = 'segment'
        assert codes(self._issues(m)) == ['type_mismatch']

    def test_list_minimum_and_kind(self):
        def short(doc):
            doc['operations']['op_T']['args']['vertices'] = ref_list('A', 'B')
            doc['operations']['op_T']['outputs'] = [{'slot': 'polygon', 'elementId': 'T'}]
            del doc['elements']['sAB']
        assert codes(self._issues(short)) == ['type_mismatch']

        def not_list(doc):
            doc['operations']['op_T']['args']['vertices'] = ref('A')
        assert 'type_mismatch' in codes(self._issues(not_list))

        def number(doc):
            doc['operations']['op_M']['args']['a'] = {'kind': 'number', 'value': 2}
        assert codes(self._issues(number)) == ['type_mismatch']

    def test_slots(self):
        def missing(doc):
            del doc['operations']['op_M']['args']['b']
        assert codes(self._issues(missing)) == ['missing_slot']

        def extra(doc):
            doc['operations']['op_M']['args']['c'] = ref('C')
        assert codes(self._issues(extra)) == ['unknown_slot']

        def out_slot(doc):
            doc['operations']['op_T']['outputs'][1]['slot'] = 'side.4'
            doc['elements']['sAB']['producer']['slot'] = 'side.4'
        assert codes(self._issues(out_slot)) == ['unknown_slot']

    def test_producer_and_outputs(self):
        def orphan(doc):
            doc['elements']['M']['producer'] = {'operationId': 'op_l', 'slot': 'line'}
        assert 'producer_mismatch' in codes(self._issues(orphan))

        def missing_element(doc):
            doc['operations']['op_M']['outputs'].append({'slot': 'point', 'elementId': 'Z'})
        assert codes(self._issues(missing_element)) == ['duplicate_output', 'producer_mismatch']

        def no_op(doc):
            doc['elements']['M']['producer']['operationId'] = 'op_none'
        assert 'producer_mismatch' in codes(self._issues(no_op))

    def test_cycle(self):
        b = DocBuilder('cyc').free('A', 0, 0).midpoint('P', 'A', 'Q').midpoint('Q', 'A', 'P').segment('s', 'P', 'A')
        issues = native.validate(b.doc)
        assert codes(issues) == ['cycle']
        assert sorted(i.operationId for i in issues) == ['op_P', 'op_Q']

    def test_self_cycle(self):
        b = DocBuilder('self').free('A', 0, 0).midpoint('P', 'A', 'P')
        assert [i.operationId for i in native.validate(b.doc)] == ['op_P']

    def test_inputs(self):
        def not_free(doc):
            doc['inputs']['M'] = point_input(1, 1)
        assert codes(self._issues(not_free)) == ['input_not_free']

        def unknown(doc):
            doc['inputs']['ghost'] = point_input(1, 1)
        assert codes(self._issues(unknown)) == ['dangling_ref']

        def missing(doc):
            del doc['inputs']['A']
        assert codes(self._issues(missing)) == ['missing_input']

    def test_unknown_op_is_a_warning(self):
        def m(doc):
            doc['operations']['op_M']['op'] = 'point.magic'
        issues = self._issues(m)
        assert codes(issues) == ['unknown_op']
        assert issues[0].severity == 'warning'

    def test_newer_registry(self):
        def m(doc):
            doc['operationRegistryVersion'] = '1.7'
            doc['operations']['op_M']['op'] = 'point.magic'
        issues = self._issues(m)
        assert codes(issues) == ['newer_registry']
        assert {i.severity for i in issues} == {'warning'}

    def test_graph_errors_scene(self):
        doc = read_json(SCENES_DIR / 'graph_errors.json')['document']
        assert codes(native.validate(doc)) == [
            'cycle', 'dangling_ref', 'missing_input', 'missing_slot', 'type_mismatch', 'unknown_op',
        ]

    def test_issue_to_dict(self):
        issue = native.Issue('cycle', '/operations/x', 'msg', operationId='x')
        assert issue.to_dict() == {'code': 'cycle', 'path': '/operations/x', 'message': 'msg',
                                   'severity': 'error', 'operationId': 'x'}


# ── structure vs JSON Schema ─────────────────────────────────────────────


def _invalid_documents():
    base = triangle_doc()

    def variant(fn):
        doc = copy.deepcopy(base)
        fn(doc)
        return doc

    yield 'missing format', variant(lambda d: d.pop('format'))
    yield 'wrong format', variant(lambda d: d.__setitem__('format', 'animageo-construction/v2'))
    yield 'bad document id', variant(lambda d: d.__setitem__('documentId', 'with space'))
    yield 'long id', variant(lambda d: d.__setitem__('documentId', 'x' * 65))
    yield 'registry version', variant(lambda d: d.__setitem__('operationRegistryVersion', '1'))
    yield 'operations not object', variant(lambda d: d.__setitem__('operations', []))
    yield 'bad operation key', variant(lambda d: d['operations'].__setitem__('bad key', d['operations']['op_M']))
    yield 'operation extra key', variant(lambda d: d['operations']['op_M'].__setitem__('extra', 1))
    yield 'operation without args', variant(lambda d: d['operations']['op_M'].pop('args'))
    yield 'bad op name', variant(lambda d: d['operations']['op_M'].__setitem__('op', 'Midpoint'))
    yield 'unknown argument kind', variant(
        lambda d: d['operations']['op_M']['args'].__setitem__('a', {'kind': 'text', 'value': 'x'}))
    yield 'ref without element', variant(lambda d: d['operations']['op_M']['args'].__setitem__('a', {'kind': 'ref'}))
    yield 'ref extra key', variant(
        lambda d: d['operations']['op_M']['args']['a'].__setitem__('extra', True))
    yield 'list items not array', variant(
        lambda d: d['operations']['op_T']['args'].__setitem__('vertices', {'kind': 'list', 'items': {}}))
    yield 'bad list item', variant(
        lambda d: d['operations']['op_T']['args']['vertices']['items'].append({'kind': 'ref', 'elementId': 7}))
    yield 'number not number', variant(
        lambda d: d['operations']['op_M']['args'].__setitem__('a', {'kind': 'number', 'value': '1'}))
    yield 'bool as number', variant(
        lambda d: d['operations']['op_M']['args'].__setitem__('a', {'kind': 'number', 'value': True}))
    yield 'expr without ast', variant(lambda d: d['operations']['op_M']['args'].__setitem__('a', {'kind': 'expr'}))
    yield 'expr ast not an object', variant(
        lambda d: d['operations']['op_M']['args'].__setitem__('a', {'kind': 'expr', 'ast': [1]}))
    yield 'expr extra key', variant(
        lambda d: d['operations']['op_M']['args'].__setitem__('a', {'kind': 'expr', 'ast': {'num': 1}, 'text': '1'}))
    yield 'bad output slot', variant(lambda d: d['operations']['op_M']['outputs'][0].__setitem__('slot', 'side.0'))
    yield 'output extra key', variant(lambda d: d['operations']['op_M']['outputs'][0].__setitem__('x', 1))
    yield 'outputs not array', variant(lambda d: d['operations']['op_M'].__setitem__('outputs', {}))
    yield 'bad branch', variant(lambda d: d['operations']['op_M'].__setitem__('branch', {'policy': 'x'}))
    yield 'element without displayName', variant(lambda d: d['elements']['M'].pop('displayName'))
    yield 'element bad type', variant(lambda d: d['elements']['M'].__setitem__('type', 'Point'))
    yield 'element extra key', variant(lambda d: d['elements']['M'].__setitem__('style', {}))
    yield 'producer extra key', variant(lambda d: d['elements']['M']['producer'].__setitem__('x', 1))
    yield 'origin not object', variant(lambda d: d['elements']['M'].__setitem__('origin', 'tool'))
    yield 'input kind', variant(lambda d: d['inputs'].__setitem__('A', {'kind': 'direction', 'value': 1}))
    yield 'number input bool', variant(lambda d: d['inputs'].__setitem__('A', {'kind': 'number', 'value': True}))
    yield 'number input array', variant(lambda d: d['inputs'].__setitem__('A', {'kind': 'number', 'value': [1]}))
    yield 'number input without value', variant(lambda d: d['inputs'].__setitem__('A', {'kind': 'number'}))
    yield 'number input extra key', variant(
        lambda d: d['inputs'].__setitem__('A', {'kind': 'number', 'value': 1, 'unit': 'length'}))
    yield 'input value length', variant(lambda d: d['inputs'].__setitem__('A', {'kind': 'point', 'value': [1]}))
    yield 'input value type', variant(lambda d: d['inputs'].__setitem__('A', {'kind': 'point', 'value': ['1', 2]}))
    yield 'input extra key', variant(lambda d: d['inputs']['A'].__setitem__('x', 1))
    yield 'path parameter not a number', variant(
        lambda d: d['inputs'].__setitem__('A', {'kind': 'pathParameter', 'value': [0.5]}))
    yield 'path parameter without value', variant(lambda d: d['inputs'].__setitem__('A', {'kind': 'pathParameter'}))
    yield 'path parameter bool', variant(
        lambda d: d['inputs'].__setitem__('A', {'kind': 'pathParameter', 'value': True}))
    yield 'path branch 0', variant(
        lambda d: d['inputs'].__setitem__('A', {'kind': 'pathParameter', 'value': 0.5, 'branch': 0}))
    yield 'path parameter extra key', variant(
        lambda d: d['inputs'].__setitem__('A', {'kind': 'pathParameter', 'value': 0.5, 'x': 1}))
    yield 'bounds length', variant(lambda d: d['viewDefaults'].__setitem__('bounds', [0, 0, 1]))
    yield 'timeline type', variant(lambda d: d.__setitem__('timeline', []))
    yield 'appearance type', variant(lambda d: d.__setitem__('appearance', []))
    yield 'locked not bool', variant(lambda d: d.__setitem__('appearance', {'A': {'locked': 1}}))
    yield 'locked string', variant(lambda d: d.__setitem__('appearance', {'A': {'locked': 'true'}}))

    def intent(value):
        return variant(lambda d: d.__setitem__('workIntent', value))

    yield 'work intent type', intent([])
    yield 'work intent extra key', intent({'purpose': 'lesson'})
    yield 'condition without text', intent({'condition': {'source': 'typed'}})
    yield 'condition text type', intent({'condition': {'text': 7}})
    yield 'condition text too long', intent({'condition': {'text': 'x' * 4001}})
    yield 'condition source', intent({'condition': {'text': 'a', 'source': 'scan'}})
    yield 'condition extra key', intent({'condition': {'text': 'a', 'sourceRef': 'm1'}})
    yield 'condition quote type', intent({'condition': {'text': 'a', 'quote': 1}})
    yield 'condition media type', intent({'condition': {'text': 'a', 'mediaRef': None}})
    yield 'forbid type', intent({'forbid': 'solution'})
    yield 'forbid item', intent({'forbid': ['answer']})
    yield 'forbid repeated', intent({'forbid': ['solution', 'solution']})
    yield 'assumptions type', intent({'assumptions': 'AB = BC'})
    yield 'assumption type', intent({'assumptions': [1]})
    yield 'assumption too long', intent({'assumptions': ['x' * 201]})
    yield 'too many assumptions', intent({'assumptions': ['a'] * 11})
    yield 'brief revision fraction', intent({'briefRevision': 1.5})
    yield 'brief revision negative', intent({'briefRevision': -1})
    yield 'brief revision bool', intent({'briefRevision': True})
    yield 'brief revision string', intent({'briefRevision': '2'})


def _valid_documents():
    base = triangle_doc()
    yield 'triangle', base
    doc = copy.deepcopy(base)
    doc.update({'timeline': None, 'appearance': {}, 'styleBinding': {'styleId': None}, 'exportDefaults': {},
                'bindings': {'legacyNames': {}}, 'futureKey': [1]})
    doc['operations']['op_M']['branch'] = None
    doc['elements']['M']['origin'] = {'source': 'tool'}
    yield 'all sections', doc
    doc = copy.deepcopy(base)
    del doc['inputs']
    del doc['viewDefaults']
    yield 'minimal', doc
    doc = copy.deepcopy(base)
    doc['operations']['op_M']['args']['a'] = {'kind': 'number', 'value': 2.5}
    yield 'number argument (graph issue, not schema)', doc
    doc = copy.deepcopy(base)
    doc['inputs']['A'] = {'kind': 'pathParameter', 'value': -2.5}
    yield 'path parameter (graph issue, not schema)', doc
    doc = copy.deepcopy(base)
    doc['inputs']['A'] = {'kind': 'pathParameter', 'value': 7, 'branch': -1}
    yield 'path parameter with branch', doc
    doc = copy.deepcopy(base)
    doc['inputs']['A'] = {'kind': 'number', 'value': -2.5}
    yield 'number input (graph issue, not schema)', doc
    doc = copy.deepcopy(base)
    doc['appearance'] = {'A': {'locked': True, 'color': 'red'}, 'B': {'locked': False}, 'ghost': 'kept as is'}
    yield 'appearance locked', doc
    doc = copy.deepcopy(base)
    doc['workIntent'] = WORK_INTENT
    yield 'work intent', doc
    for intent in ({}, None, {'condition': {'text': ''}}, {'forbid': [], 'assumptions': [], 'briefRevision': 0},
                   {'condition': {'text': 'x' * 4000}, 'assumptions': ['y' * 200] * 10, 'briefRevision': 3.0}):
        doc = copy.deepcopy(base)
        doc['workIntent'] = intent
        yield f'work intent {intent!r:.40}', doc
    for path in sorted(SCENES_DIR.glob('*.json')):
        yield path.stem, read_json(path)['document']


@pytest.mark.parametrize('name, doc', list(_invalid_documents()), ids=lambda v: v if isinstance(v, str) else '')
def test_structure_rejects(name, doc):
    assert structure_issues(doc), name


@pytest.mark.parametrize('name, doc', list(_valid_documents()), ids=lambda v: v if isinstance(v, str) else '')
def test_structure_accepts(name, doc):
    assert structure_issues(doc) == [], name


def test_inverted_bounds_are_checked_by_the_library_only():
    doc = triangle_doc()
    doc['viewDefaults']['bounds'] = [10, -10, -10, 10]
    assert codes(structure_issues(doc)) == ['schema']


def test_json_schema_agrees():
    jsonschema = pytest.importorskip('jsonschema')
    schema = read_json(SCHEMA_PATH)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    for name, doc in _valid_documents():
        assert list(validator.iter_errors(doc)) == [], name
    for name, doc in _invalid_documents():
        assert list(validator.iter_errors(doc)), name


# ── closure ──────────────────────────────────────────────────────────────


def test_closure():
    doc = native.load(triangle_doc())
    # topological order: operations in Kahn order (ties by ID: op_M, op_T, op_l), elements by ID
    assert native.closure(doc, 'A') == ['A', 'M', 'T', 'sAB', 'l']
    assert native.closure(doc, ['C']) == ['C', 'T', 'sAB']
    assert native.closure(doc, 'M', direction='up') == ['A', 'B', 'M']
    assert native.closure(doc, ['sAB', 'M'], direction='up') == ['A', 'B', 'C', 'M', 'sAB']
    with pytest.raises(ValueError):
        native.closure(doc, 'ghost')
    with pytest.raises(ValueError):
        native.closure(doc, 'A', direction='sideways')


def test_closure_terminates_on_cycles():
    doc = read_json(SCENES_DIR / 'graph_errors.json')['document']
    assert native.closure(doc, 'P') == ['P', 'Q', 'W', 'sPC']
    assert native.closure(doc, 'P', direction='up') == ['A', 'B', 'P', 'Q']
