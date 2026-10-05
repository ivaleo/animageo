"""Graph queries and pure edits (native/edit.py)."""
import copy
import random

import pytest

from animageo import native
from animageo.native.edit import element_order, name_key, valid_name
from tests.native.conftest import DocBuilder, path_input, point_input, ref


def scene():
    b = DocBuilder('edit', registry_version='1.1')
    b.free('A', -4, 0).free('B', 4, 0).free('C', 0, 5).free('D', 1, -3)
    b.segment('s', 'A', 'B').line('l', 'A', 'C').midpoint('M', 'A', 'B')
    b.circle('c', 'M', 'C').line_circle('P1', 'P2', 'l', 'c')
    b.polygon('T', 'A', 'B', 'C', sides=[(1, 'tAB'), (2, 'tBC')])
    b.on_path('Q', 's', 0.25).segment('q', 'Q', 'D')
    b.doc['appearance'] = {'P2': {'visible': False}, 'A': {'label': True}}
    b.doc['timeline'] = None
    return b.doc


def ids(effects, group, key):
    return effects[group][key]


class TestQueries:
    def test_closure_is_topological(self):
        doc = scene()
        down = native.closure(doc, 'A')
        assert set(down) == {'A', 's', 'l', 'M', 'c', 'P1', 'P2', 'T', 'tAB', 'tBC', 'Q', 'q'}
        assert down.index('M') < down.index('c') < down.index('P1')
        assert down.index('s') < down.index('Q') < down.index('q')
        assert native.closure(doc, 'P2', direction='up') == ['A', 'B', 'C', 'M', 'c', 'l', 'P2']

    def test_element_order_ties(self):
        order = element_order(scene())
        assert order[:4] == ['A', 'B', 'C', 'D']
        assert order.index('P1') + 1 == order.index('P2')   # one operation, by ID

    def test_dependencies_and_free_inputs(self):
        doc = scene()
        assert native.dependencies(doc, 'q') == ['A', 'B', 'D', 's', 'Q']
        assert native.dependencies(doc, 'A') == []
        assert native.free_inputs(doc, ['q']) == ['A', 'B', 'D', 'Q']
        assert native.free_inputs(doc, 'P1') == ['A', 'B', 'C']
        with pytest.raises(ValueError):
            native.dependencies(doc, 'ghost')


class TestDelete:
    def test_element_mode(self):
        doc = scene()
        before = copy.deepcopy(doc)
        new, eff = native.delete(doc, ['P2'])
        assert doc == before                                   # pure
        assert set(new.elements) == set(doc['elements']) - {'P2'}
        assert new.operations['op_P1_P2']['outputs'] == [{'slot': 'first', 'elementId': 'P1'}]
        assert eff['removed'] == {'operations': [], 'elements': ['P2'], 'inputs': [], 'appearance': ['P2']}
        assert eff['modified']['operations'] == ['op_P1_P2']
        assert native.validate(new) == []

    def test_operation_mode_takes_the_siblings(self):
        new, eff = native.delete(scene(), 'P2', mode='operation')
        assert eff['removed']['elements'] == ['P1', 'P2']
        assert eff['removed']['operations'] == ['op_P1_P2']
        assert eff['modified']['operations'] == []

    def test_a_free_point_takes_its_dependents_and_inputs(self):
        new, eff = native.delete(scene(), ['B'])
        assert eff['removed']['elements'] == ['B', 'M', 'P1', 'P2', 'Q', 'T', 'c', 'q', 's', 'tAB', 'tBC']
        assert eff['removed']['inputs'] == ['B', 'Q']
        assert eff['removed']['appearance'] == ['P2']
        assert set(new.elements) == {'A', 'C', 'D', 'l'}
        assert new.data['timeline'] is None and new.data['appearance'] == {'A': {'label': True}}
        assert native.validate(new) == []

    def test_a_polygon_side(self):
        new, eff = native.delete(scene(), 'tBC')
        assert eff['removed']['elements'] == ['tBC']
        assert [o['elementId'] for o in new.operations['op_T']['outputs']] == ['T', 'tAB']

    def test_unknown(self):
        with pytest.raises(native.EditError) as info:
            native.delete(scene(), ['A', 'ghost'])
        assert [i.code for i in info.value.issues] == ['unknown_element']

    def test_steps_and_legacy_names_follow(self):
        """1.10.0a2: a removed operation leaves its step (an empty step goes), a
        removed element its legacy name; the effects name the steps."""
        doc = scene()
        doc['steps'] = [{'id': 'given', 'kind': 'group', 'operationIds': ['op_A', 'op_B', 'op_C', 'op_D']},
                        {'id': 's2', 'kind': 'group', 'operationIds': ['op_s', 'op_l', 'op_M']},
                        {'id': 's3', 'kind': 'group', 'operationIds': ['op_c', 'op_P1_P2']}]
        doc['bindings'] = {'legacyNames': {'A': 'A', 'M': 'M', 'c': 'c', 'P2': 'P_2'}}
        assert native.validate(doc) == []
        new, eff = native.delete(doc, ['M'])
        assert native.validate(new) == []
        assert new.data['steps'] == [doc['steps'][0], {'id': 's2', 'kind': 'group', 'operationIds': ['op_s', 'op_l']}]
        assert new.data['bindings'] == {'legacyNames': {'A': 'A'}}
        assert eff['removed']['steps'] == ['s3'] and eff['modified']['steps'] == ['s2']
        # the last step goes: no steps left
        new, eff = native.delete(doc, ['A', 'B'])
        assert new.data['steps'] == [{'id': 'given', 'kind': 'group', 'operationIds': ['op_C', 'op_D']}]
        assert eff['removed']['steps'] == ['s2', 's3'] and eff['modified']['steps'] == ['given']
        assert native.validate(new) == []
        new, _ = native.delete(new, ['C', 'D'])
        assert 'steps' not in new.data and new.data['bindings'] == {'legacyNames': {}}
        # a document without steps keeps the effects of before
        _, eff = native.delete(scene(), ['P2'])
        assert 'steps' not in eff['removed'] and 'steps' not in eff['modified']
        assert native.has('delete.cleanup')


class TestRedefine:
    def test_make_a_point_free(self):
        new, eff = native.redefine(scene(), 'op_M', {'op': 'point.free', 'args': {}},
                                   inputs={'M': point_input(0, 1)})
        assert new.operations['op_M'] == {'id': 'op_M', 'op': 'point.free', 'args': {},
                                          'outputs': [{'slot': 'point', 'elementId': 'M'}]}
        assert new.inputs['M'] == point_input(0, 1)
        assert eff['added']['inputs'] == ['M'] and eff['modified']['operations'] == ['op_M']
        assert native.evaluate(new).elements['c']['value']['c'] == [0.0, 1.0]

    def test_free_point_becomes_a_midpoint(self):
        new, eff = native.redefine(scene(), 'op_D', {'op': 'point.midpoint', 'args': {'a': ref('B'), 'b': ref('C')}})
        assert 'D' not in new.inputs and eff['removed']['inputs'] == ['D']
        assert native.evaluate(new).elements['D']['value'] == {'x': 2.0, 'y': 2.5}

    def test_point_moves_onto_a_path(self):
        new, eff = native.redefine(scene(), 'op_D', {'op': 'point.on_path', 'args': {'path': ref('l')}},
                                   inputs={'D': path_input(0.5)})
        assert eff['modified']['inputs'] == ['D']
        assert native.evaluate(new).elements['D']['value'] == {'x': -2.0, 'y': 2.5}

    def test_a_free_op_needs_an_input_of_its_kind(self):
        with pytest.raises(native.EditError) as info:
            native.redefine(scene(), 'op_D', {'op': 'point.on_path', 'args': {'path': ref('l')}})
        assert info.value.issues[0].code == 'missing_input'

    def test_slot_map_and_output_removed(self):
        new, eff = native.redefine(scene(), 'op_P1_P2',
                                   {'op': 'intersect.other_than', 'args': {'first': ref('l'), 'second': ref('c'),
                                                                           'known': ref('A')}},
                                   slot_map={'second': 'point'})
        assert new.operations['op_P1_P2']['outputs'] == [{'slot': 'point', 'elementId': 'P2'}]
        assert new.elements['P2']['producer'] == {'operationId': 'op_P1_P2', 'slot': 'point'}
        assert eff['removed']['elements'] == ['P1']
        assert [w['code'] for w in eff['warnings']] == ['output_removed']
        assert eff['modified']['elements'] == ['P2']

    def test_slot_conflict(self):
        with pytest.raises(native.EditError) as info:
            native.redefine(scene(), 'op_P1_P2',
                            {'op': 'intersect.other_than', 'args': {'first': ref('l'), 'second': ref('c'),
                                                                    'known': ref('A')}},
                            slot_map={'first': 'point', 'second': 'point'})
        assert info.value.issues[0].code == 'slot_conflict'

    def test_type_change_must_fit_the_users(self):
        # s is used by point.on_path (path accepts a ray) — fine; a ray cannot be a segment for others.
        new, _ = native.redefine(scene(), 'op_s', {'op': 'ray.by_points', 'args': {'origin': ref('A'), 'through': ref('B')}},
                                 slot_map={'segment': 'ray'})
        assert new.elements['s']['type'] == 'ray'
        doc = scene()
        doc['operations']['op_X'] = {'id': 'op_X', 'op': 'circle.center_point',
                                     'args': {'center': ref('M'), 'through': ref('B')},
                                     'outputs': [{'slot': 'circle', 'elementId': 'X'}]}
        doc['elements']['X'] = {'id': 'X', 'type': 'circle', 'displayName': 'X',
                                'producer': {'operationId': 'op_X', 'slot': 'circle'}}
        with pytest.raises(native.EditError) as info:
            native.redefine(doc, 'op_M', {'op': 'segment.by_points', 'args': {'a': ref('A'), 'b': ref('B')}},
                            slot_map={'point': 'segment'})
        assert info.value.issues[0].code == 'type_mismatch'

    def test_cycle(self):
        with pytest.raises(native.EditError) as info:
            native.redefine(scene(), 'op_M', {'op': 'point.midpoint', 'args': {'a': ref('A'), 'b': ref('P1')}})
        assert info.value.issues[0].code == 'cycle'

    def test_unknown_operation_and_op(self):
        with pytest.raises(native.EditError) as info:
            native.redefine(scene(), 'op_zz', {'op': 'point.free', 'args': {}})
        assert info.value.issues[0].code == 'unknown_operation'
        with pytest.raises(native.EditError) as info:
            native.redefine(scene(), 'op_M', {'op': 'point.bogus', 'args': {}})
        assert info.value.issues[0].code == 'unknown_op'

    def test_new_validation_errors_are_refused(self):
        with pytest.raises(native.EditError) as info:
            native.redefine(scene(), 'op_M', {'op': 'point.midpoint', 'args': {'a': ref('A'), 'b': ref('ghost')}})
        assert info.value.issues[0].code == 'dangling_ref'
        with pytest.raises(native.EditError) as info:
            native.redefine(scene(), 'op_M', {'op': 'point.midpoint', 'args': {'a': ref('A')}})
        assert info.value.issues[0].code == 'missing_slot'

    def test_pure(self):
        doc = scene()
        before = copy.deepcopy(doc)
        native.redefine(doc, 'op_M', {'op': 'point.free', 'args': {}}, inputs={'M': point_input(0, 1)})
        assert doc == before


class TestRename:
    @pytest.mark.parametrize('name', ['A', 'AB', 'Ж', 'α', 'A1', 'A12', 'A₁', 'A_1', 'A_{12}', 'A_{ab}',
                                      "A'", "A''", "m_a'", 'Ω_{Ж1}', 'x' * 32])
    def test_valid(self, name):
        assert valid_name(name)

    @pytest.mark.parametrize('name', ['', '1A', '_A', '__A', 'A_', 'A_{}', 'A_{a', 'A1B', 'A_1_2', 'A 1',
                                      "'A", 'A-1', 'A₁1', 'x' * 33, 'A_{a_b}', 'A__1', 'A.1'])
    def test_invalid(self, name):
        assert not valid_name(name)

    def test_name_key(self):
        assert name_key('A_{1}') == name_key('A_1') == 'A_1'
        assert name_key("A_{ab}'") == "A_ab'"
        assert name_key('A₁') != name_key('A_1')

    def test_rename(self):
        doc = scene()
        new, eff = native.rename(doc, 'P1', 'K_{1}')
        assert new.elements['P1']['displayName'] == 'K_{1}'
        assert eff['modified']['elements'] == ['P1']
        assert new.operations == doc['operations']
        _, eff = native.rename(doc, 'P1', 'P1')
        assert eff['modified']['elements'] == []

    def test_refusals(self):
        doc = scene()
        doc['elements']['P2']['displayName'] = 'K_1'
        for name, code in (('K_{1}', 'duplicate_name'), ('A', 'duplicate_name'), ('1x', 'invalid_name')):
            with pytest.raises(native.EditError) as info:
                native.rename(doc, 'P1', name)
            assert info.value.issues[0].code == code, name
        with pytest.raises(native.EditError) as info:
            native.rename(doc, 'ghost', 'Z')
        assert info.value.issues[0].code == 'unknown_element'


# ── property tests on random documents ───────────────────────────────────


def random_doc(rng: random.Random, n_ops=14):
    b = DocBuilder(f'rand{rng.randrange(10 ** 6)}', registry_version='1.1')
    kinds = {'point': [], 'linear': [], 'circle': [], 'path': []}

    def coord():
        return rng.randint(-8, 8) + rng.random()

    for i in range(rng.randint(2, 4)):
        el = f'F{i}'
        b.free(el, coord(), coord())
        kinds['point'].append(el)
    for i in range(n_ops):
        pts = kinds['point']
        choice = rng.choice(['mid', 'seg', 'line', 'ray', 'circle', 'xll', 'xlc', 'xcc', 'poly', 'path'])
        el = f'E{i}'
        if choice in ('mid', 'seg', 'line', 'ray', 'circle'):
            a, c = rng.sample(pts, 2) if len(pts) > 1 else (pts[0], pts[0])
            if choice == 'mid':
                b.midpoint(el, a, c)
                kinds['point'].append(el)
            elif choice == 'seg':
                b.segment(el, a, c)
                kinds['linear'].append(el)
                kinds['path'].append(el)
            elif choice == 'line':
                b.line(el, a, c)
                kinds['linear'].append(el)
                kinds['path'].append(el)
            elif choice == 'ray':
                b.ray(el, a, c)
                kinds['linear'].append(el)
                kinds['path'].append(el)
            else:
                b.circle(el, a, c)
                kinds['circle'].append(el)
                kinds['path'].append(el)
        elif choice == 'xll' and len(kinds['linear']) >= 2:
            f, s = rng.sample(kinds['linear'], 2)
            b.intersect(el, f, s)
            kinds['point'].append(el)
        elif choice == 'xlc' and kinds['linear'] and kinds['circle']:
            b.line_circle(el + 'a', el + 'b', rng.choice(kinds['linear']), rng.choice(kinds['circle']), op_id='op_' + el)
            kinds['point'] += [el + 'a', el + 'b']
        elif choice == 'xcc' and len(kinds['circle']) >= 2:
            f, s = rng.sample(kinds['circle'], 2)
            b.circle_circle(el + 'a', el + 'b', f, s, op_id='op_' + el)
            kinds['point'] += [el + 'a', el + 'b']
        elif choice == 'poly' and len(pts) >= 3:
            verts = rng.sample(pts, 3)
            b.polygon(el, *verts, sides=[(1, el + 's1')])
            kinds['path'].append(el)
            kinds['linear'].append(el + 's1')
        elif choice == 'path' and kinds['path']:
            b.on_path(el, rng.choice(kinds['path']), rng.random() * 3)
            kinds['point'].append(el)
    return b.doc


SEEDS = range(200)


def _is_topological(doc, order):
    pos = {e: i for i, e in enumerate(order)}
    for el_id in order:
        for dep in native.dependencies(doc, el_id):
            if dep in pos and pos[dep] > pos[el_id]:
                return False
    return True


@pytest.mark.parametrize('seed', SEEDS)
def test_properties(seed):
    rng = random.Random(seed)
    doc = random_doc(rng)
    assert native.validate(doc) == []
    elements = sorted(doc['elements'])
    target = rng.choice(elements)

    down = native.closure(doc, target)
    up = native.closure(doc, target, direction='up')
    assert down[0] == target or target in down
    # closed: every user of a member is a member; every ancestor of a member is a member
    for el_id in down:
        assert set(native.closure(doc, el_id)) <= set(down)
    for el_id in up:
        assert set(native.dependencies(doc, el_id)) <= set(up)
    assert _is_topological(doc, down) and _is_topological(doc, up)
    assert _is_topological(doc, element_order(doc))

    new, eff = native.delete(doc, [target])
    assert set(eff['removed']['elements']) == set(down)
    assert set(new.elements) == set(elements) - set(down)
    assert native.validate(new) == []
    for el_id in new.elements:
        assert new.elements[el_id] == doc['elements'][el_id]

    # redefining a midpoint to depend on its own dependents is a cycle
    producer = doc['elements'][target]['producer']['operationId']
    op = doc['operations'][producer]
    dependent = next((e for e in down if e != target and doc['elements'][e]['type'] == 'point'), None)
    if op['op'] == 'point.midpoint' and dependent is not None:
        with pytest.raises(native.EditError) as info:
            native.redefine(doc, producer, {'op': 'point.midpoint',
                                            'args': {'a': op['args']['a'], 'b': ref(dependent)}})
        assert info.value.issues[0].code == 'cycle'
    if op['op'] == 'point.free':
        new, eff = native.redefine(doc, producer, {'op': 'point.free', 'args': {}},
                                   inputs={target: point_input(1.5, -2.5)})
        assert [o['elementId'] for o in new.operations[producer]['outputs']] == [target]
        assert eff['modified']['inputs'] == [target]
        assert native.validate(new) == []

    new, _ = native.rename(doc, target, 'Zz_{9}')
    assert new.operations == doc['operations']
    other = next(e for e in elements if e != target)
    with pytest.raises(native.EditError) as info:
        native.rename(new, other, 'Zz_9')
    assert info.value.issues[0].code == 'duplicate_name'
