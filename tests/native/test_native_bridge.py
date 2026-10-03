"""Bridge identity: a document built as a classic construction gives the
values of ``native.evaluate`` (no manim needed: ``animageo.geo`` is plain numpy)."""
import pytest

from animageo import native
from animageo.native.kernel import bridge
from animageo.native.kernel.numeric import tolerances
from animageo.native.registry import registry
from animageo.native.kernel.values import compare_values
from tests.native.conftest import EXPECTED_DIR, DocBuilder, path_input, point_input, read_json

FIXTURES = sorted(EXPECTED_DIR.glob('*.json'))


def bridge_values(doc, inputs=None):
    construction, names = bridge.build_construction(doc, inputs=inputs)
    construction.rebuild(full=True)
    return construction, names, values_of(construction, names, doc)


def values_of(construction, names, doc):
    doc = native.load(doc, strict=False)
    out = {}
    for el_id, el in doc.elements.items():
        data = construction.element(names.by_id[el_id]).data
        out[el_id] = None if data is None else bridge.from_classic(el['type'], data)
    return out


def evaluated_values(doc, inputs=None):
    ev = native.evaluate(doc, inputs=inputs)
    return {e: (r['value'] if r['state'] == 'defined' else None) for e, r in ev.elements.items()}


@pytest.mark.parametrize('path', FIXTURES, ids=[p.stem for p in FIXTURES])
def test_identity_on_every_fixture_case(path):
    fixture = read_json(path)
    doc = fixture['document']
    types = registry().types
    for case in fixture['cases']:
        _c, _n, got = bridge_values(doc, case.get('inputs'))
        # bit-equal to a fresh evaluation …
        assert native.canonical_json(got) == native.canonical_json(evaluated_values(doc, case.get('inputs'))), \
            case['name']
        # … and within the parity tolerance of the committed expectation
        tol = tolerances(case['scale'])
        for el_id, expected in case['expect'].items():
            where = f"{case['name']} {el_id}"
            if expected['state'] != 'defined':
                assert got[el_id] is None, where
                continue
            assert got[el_id] is not None, where
            assert compare_values(types[expected['type']], expected['value'], got[el_id], tol.parity) == [], where


def chain_doc():
    b = DocBuilder('bridge_chain', registry_version='1.1')
    b.free('O', 0, 0).free('R', 5, 0).free('A', -6, 0)
    b.circle('c', 'O', 'R').on_path('P', 'c', 1.0).segment('s', 'A', 'P').on_path('Q', 's', 0.5)
    b.midpoint('M', 'Q', 'O').line('l', 'A', 'P').line_circle('X1', 'X2', 'l', 'c')
    return b.doc


def same_as_evaluate(construction, names, doc, inputs):
    got = values_of(construction, names, doc)
    assert native.canonical_json(got) == native.canonical_json(evaluated_values(doc, inputs))


def test_moving_a_free_point_and_incremental_rebuild():
    from animageo.geo.lib_elements import Point
    doc = chain_doc()
    construction, names, _ = bridge_values(doc)
    construction.update(names.by_id['A'], Point([-7.0, 1.5]))
    construction.rebuild()
    same_as_evaluate(construction, names, doc, {'A': point_input(-7.0, 1.5)})


def test_animating_a_path_parameter():
    doc = chain_doc()
    construction, names, _ = bridge_values(doc)
    for t in (0.0, 2.5, -1.25, 7.0):
        construction.update_tparam(names.by_id['P'], t)
        construction.rebuild()
        same_as_evaluate(construction, names, doc, {'P': path_input(t)})
    construction.update_tparam(names.by_id['Q'], 0.9)
    construction.rebuild()
    same_as_evaluate(construction, names, doc, {'P': path_input(7.0), 'Q': path_input(0.9)})


def test_undefined_upstream_and_recovery():
    from animageo.geo.lib_elements import Point
    doc = chain_doc()
    construction, names, _ = bridge_values(doc)
    construction.update(names.by_id['R'], Point([0.0, 0.0]))       # zero radius
    construction.rebuild()
    assert construction.element(names.by_id['P']).data is None
    assert construction.element(names.by_id['M']).data is None
    same_as_evaluate(construction, names, doc, {'R': point_input(0, 0)})
    construction.update(names.by_id['R'], Point([3.0, 4.0]))
    construction.rebuild()
    same_as_evaluate(construction, names, doc, {'R': point_input(3, 4)})


def test_commands_survive_copy_and_name_the_operation():
    construction, _names, _ = bridge_values(chain_doc())
    commands = construction.commands
    assert {c.operation_id for c in commands} == {'op_c', 'op_P', 'op_s', 'op_Q', 'op_M', 'op_l', 'op_X1_X2'}
    for command in commands:
        copy = construction.copy(command)
        assert type(copy) is type(command) and copy.operation_id == command.operation_id
        assert copy.inputs == command.inputs and copy.inputs is not command.inputs
    assert {c.name for c in commands} >= {'circle.center_point', 'point.on_path', 'intersect.line_circle'}


def test_names():
    uid = '0f8fad5b-d9cb-469f-a165-70867728950e'
    names = bridge.build_names([uid, 'A', 'a-b', 'a_b', 'P₁'])
    assert names.by_id[uid] == 'e_0f8fad5bd9cb469fa16570867728950e'
    assert names.by_id['A'] == 'e_A'
    assert {names.by_id['a-b'], names.by_id['a_b']} == {'e_a_b', 'e_a_b_2'}
    assert names.by_id['P₁'] == 'e_P_'
    assert all(names.by_name[v] == k for k, v in names.by_id.items())


def test_broken_structure_gives_none():
    b = DocBuilder('bridge_broken', registry_version='1.1')
    b.free('A', 0, 0).free('B').midpoint('M', 'A', 'B').segment('s', 'A', 'A')
    b.op('op_U', 'point.future_op', {}, [('point', 'U', 'point')])
    b.op('op_X', 'point.midpoint', {'a': {'kind': 'ref', 'elementId': 'Y'},
                                    'b': {'kind': 'ref', 'elementId': 'A'}}, [('point', 'X', 'point')])
    b.op('op_Y', 'point.midpoint', {'a': {'kind': 'ref', 'elementId': 'X'},
                                    'b': {'kind': 'ref', 'elementId': 'A'}}, [('point', 'Y', 'point')])
    _c, _n, got = bridge_values(b.doc)
    assert got['A'] == {'x': 0.0, 'y': 0.0}
    assert got['s'] == {'a': [0.0, 0.0], 'b': [0.0, 0.0], 'length': 0.0}   # degenerate, still defined
    assert all(got[e] is None for e in ('B', 'M', 'U', 'X', 'Y'))
    assert native.canonical_json(got) == native.canonical_json(evaluated_values(b.doc))


def test_seed_is_passed():
    construction, _names = bridge.build_construction(chain_doc(), seed=7)
    assert construction.seed == 7


def test_value_round_trip_without_the_cache():
    values = {
        'point': {'x': 1.5, 'y': -2.0},
        'segment': {'a': [0.0, 0.0], 'b': [3.0, 4.0], 'length': 5.0},
        'line': {'p': [0.0, 1.0], 'dir': [1.0, 0.0]},
        'ray': {'origin': [1.0, 1.0], 'dir': [0.0, -1.0]},
        'circle': {'c': [1.0, 2.0], 'r': 3.0},
        'polygon': {'vertices': [[0.0, 0.0], [4.0, 0.0], [0.0, 3.0]], 'area': 6.0},
    }
    for type_, value in values.items():
        obj = bridge.to_classic(type_, value)
        assert bridge.from_classic(type_, obj) is value            # cached
        del obj._native
        assert native.canonical_json(bridge.from_classic(type_, obj)) == native.canonical_json(value), type_


def test_a_moved_object_is_read_from_its_fields():
    obj = bridge.to_classic('point', {'x': 1.0, 'y': 2.0})
    obj.translate([1.0, 1.0])
    assert bridge.from_classic('point', obj) == {'x': 2.0, 'y': 3.0}
