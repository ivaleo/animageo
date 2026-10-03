"""Evaluation: states, reasons, upstream/cause, graph errors, inputs, robustness."""
import copy
import json

import pytest

from animageo import native
from animageo.native.kernel import ops as kernel_ops
from tests.native.conftest import DocBuilder, point_input, ref, ref_list


def states(ev):
    out = {}
    for el_id, rec in ev.elements.items():
        if rec['state'] == 'defined':
            out[el_id] = 'defined'
        else:
            out[el_id] = '/'.join(x for x in (rec['state'], rec['reason'], rec.get('cause')) if x)
    return out


def chain_doc():
    b = DocBuilder('chain').free('A', -4, -1).free('B', 4, 3).free('C', -3, 4).free('D', 3, -4).free('E', 5, 5)
    b.line('l', 'A', 'B').line('m', 'C', 'D').intersect('X', 'l', 'm').midpoint('M', 'X', 'E')
    b.circle('c', 'M', 'A').segment('k', 'X', 'E')
    return b.doc


def test_result_format():
    ev = native.evaluate(chain_doc())
    data = ev.to_dict()
    assert list(data) == ['format', 'documentId', 'kernel', 'scale', 'elements', 'diagnostics']
    assert data['format'] == 'animageo-evaluated/v1'
    assert data['documentId'] == 'chain'
    assert data['kernel'] == {'library': native_version(), 'registry': '1.2'}
    assert data['scale'] == 20.0
    assert list(data['elements']) == sorted(data['elements'])
    assert data['elements']['A'] == {'state': 'defined', 'type': 'point', 'value': {'x': -4.0, 'y': -1.0}}
    assert set(data['elements']['c']['value']) == {'c', 'r'}
    assert data['diagnostics'] == []
    json.dumps(data)
    native.canonical_json(data)


def native_version():
    import animageo
    return animageo.__version__


def test_sources():
    doc = chain_doc()
    expected = native.evaluate(doc).to_dict()
    assert native.evaluate(json.dumps(doc)).to_dict() == expected
    assert native.evaluate(native.load(doc)).to_dict() == expected


class TestUpstream:
    def test_cause_through_three_levels(self):
        ev = native.evaluate(chain_doc(), inputs={'A': point_input(1, 1), 'B': point_input(1, 1)})
        s = states(ev)
        assert s['l'] == 'undefined/coincident_points'
        assert s['X'] == s['M'] == s['c'] == s['k'] == 'undefined/upstream/l'
        assert s['m'] == 'defined'

    def test_tie_goes_to_the_first_slot(self):
        inputs = {'A': point_input(1, 1), 'B': point_input(1, 1), 'C': point_input(2, 2), 'D': point_input(2, 2)}
        assert states(native.evaluate(chain_doc(), inputs=inputs))['X'] == 'undefined/upstream/l'

    def test_root_in_the_middle(self):
        inputs = {'A': point_input(0, 0), 'B': point_input(2, 0), 'C': point_input(0, 3), 'D': point_input(5, 3)}
        s = states(native.evaluate(chain_doc(), inputs=inputs))
        assert s['X'] == 'undefined/parallel'
        assert s['M'] == s['c'] == s['k'] == 'undefined/upstream/X'

    def test_worst_state_wins(self):
        b = DocBuilder('worst').free('A', 0, 0).free('B', 0, 0).free('C', 3, 1)
        b.line('u', 'A', 'B')                                     # undefined
        b.op('op_R', 'point.magic', {'p': ref('A')}, [('point', 'R', 'point')])   # unsupported
        b.midpoint('P', 'A', 'Q').midpoint('Q', 'A', 'P')         # error (cycle)
        b.intersect('X', 'u', 'u')                                # undefined/upstream u
        b.polygon('W', 'X', 'R', 'P').polygon('W2', 'X', 'R', 'C').polygon('W3', 'C', 'X', 'C')
        b.polygon('W4', 'C', 'P', 'Q')
        s = states(native.evaluate(b.doc))
        assert s['W'] == 'error/upstream/P'
        assert s['W2'] == 'unsupported/upstream/R'
        assert s['W3'] == 'undefined/upstream/u'
        assert s['W4'] == 'error/upstream/P'


class TestGraphErrors:
    def test_cycle(self):
        b = DocBuilder('cyc').free('A', 0, 0).free('C', 1, 1)
        b.midpoint('P', 'A', 'Q').midpoint('Q', 'A', 'P').segment('s', 'P', 'C')
        b.midpoint('R', 'R', 'A')   # self cycle
        s = states(native.evaluate(b.doc))
        assert s['P'] == s['Q'] == s['R'] == 'error/cycle'
        assert s['s'] == 'error/upstream/P'

    def test_op_between_two_cycles_is_upstream(self):
        b = DocBuilder('two').free('A', 0, 0)
        b.midpoint('P', 'A', 'Q').midpoint('Q', 'A', 'P').midpoint('o', 'P', 'A')
        b.midpoint('R', 'o', 'S').midpoint('S', 'A', 'R')
        s = states(native.evaluate(b.doc))
        assert s['o'] == 'error/upstream/P'
        assert s['R'] == s['S'] == 'error/cycle'

    def test_unknown_op(self):
        b = DocBuilder('unk').free('A', 0, 0).free('C', 1, 1)
        b.op('op_R', 'point.magic', {'p': ref('A'), 'q': ref('ghost')}, [('point', 'R', 'point')])
        b.segment('s', 'R', 'C')
        s = states(native.evaluate(b.doc))
        assert s['R'] == 'unsupported/unknown_op'
        assert s['s'] == 'unsupported/upstream/R'

    def test_newer_registry(self):
        b = DocBuilder('new').free('A', 0, 0).free('B', 1, 1)
        b.op('op_R', 'point.magic', {'p': ref('A')}, [('point', 'R', 'point')]).midpoint('M', 'A', 'B')
        b.doc['operationRegistryVersion'] = '1.4'
        s = states(native.evaluate(b.doc))
        assert s['R'] == 'unsupported/newer_registry'
        assert s['M'] == 'defined'

    def test_argument_errors(self):
        b = DocBuilder('args').free('A', 0, 0).free('B', 1, 1).line('l', 'A', 'B')
        b.op('op_d', 'point.midpoint', {'a': ref('A'), 'b': ref('ghost')}, [('point', 'd', 'point')])
        b.op('op_t', 'circle.center_point', {'center': ref('l'), 'through': ref('A')}, [('circle', 't', 'circle')])
        b.op('op_m', 'point.midpoint', {'a': ref('A')}, [('point', 'm', 'point')])
        b.op('op_x', 'point.midpoint', {'a': ref('A'), 'b': ref('B'), 'c': ref('B')}, [('point', 'x', 'point')])
        b.op('op_k', 'point.midpoint', {'a': ref_list('A', 'B'), 'b': ref('B')}, [('point', 'k', 'point')])
        b.op('op_n', 'point.midpoint', {'a': {'kind': 'number', 'value': 1}, 'b': ref('B')}, [('point', 'n', 'point')])
        b.op('op_p', 'polygon.by_points', {'vertices': ref_list('A', 'B')}, [('polygon', 'p', 'polygon')])
        b.op('op_q', 'polygon.by_points', {'vertices': ref('A')}, [('polygon', 'q', 'polygon')])
        b.op('op_v', 'polygon.by_points', {'vertices': ref_list('A', 'l', 'B')}, [('polygon', 'v', 'polygon')])
        b.op('op_o', 'point.midpoint', {'b': ref('ghost'), 'a': ref('l')}, [('point', 'o', 'point')])
        s = states(native.evaluate(b.doc))
        assert s['d'] == 'error/dangling_ref'
        assert s['t'] == 'error/type_mismatch'
        assert s['m'] == 'error/schema'
        assert s['x'] == 'error/schema'
        assert s['k'] == 'error/type_mismatch'
        assert s['n'] == 'error/type_mismatch'
        assert s['p'] == 'error/type_mismatch'
        assert s['q'] == 'error/type_mismatch'
        assert s['v'] == 'error/type_mismatch'
        # registry slot order decides: slot a (type mismatch) before slot b (dangling)
        assert s['o'] == 'error/type_mismatch'

    def test_element_errors(self):
        b = DocBuilder('els').free('A', 0, 0).free('B', 1, 1).free('C', 2, 0).free('F')
        b.op('op_s', 'segment.by_points', {'a': ref('A'), 'b': ref('B')}, [('segment', 's', 'line')])
        b.polygon('T', 'A', 'B', 'C', sides=[(4, 's4')])
        b.midpoint('M', 'A', 'B')
        b.doc['elements']['M']['producer']['slot'] = 'other'
        b.doc['elements']['orphan'] = {'id': 'orphan', 'type': 'point', 'displayName': 'o',
                                      'producer': {'operationId': 'op_none', 'slot': 'point'}}
        b.segment('sF', 'F', 'A')
        s = states(native.evaluate(b.doc))
        assert s['s'] == 'error/type_mismatch'
        assert s['s4'] == 'error/schema'
        assert s['M'] == 'error/schema'
        assert s['orphan'] == 'error/schema'
        assert s['F'] == 'error/schema'
        assert s['sF'] == 'error/upstream/F'
        assert s['T'] == 'defined'


class TestInputs:
    def test_override(self):
        doc = DocBuilder('in').free('A', 0, 0).free('B', 2, 0).midpoint('M', 'A', 'B').doc
        ev = native.evaluate(doc, inputs={'B': point_input(4, 6)})
        assert ev.elements['M']['value'] == {'x': 2.0, 'y': 3.0}
        assert native.evaluate(doc).elements['M']['value'] == {'x': 1.0, 'y': 0.0}

    def test_override_gives_a_missing_input(self):
        doc = DocBuilder('in').free('A', 0, 0).free('B').midpoint('M', 'A', 'B').doc
        assert states(native.evaluate(doc))['M'] == 'error/upstream/B'
        assert states(native.evaluate(doc, inputs={'B': point_input(1, 1)}))['M'] == 'defined'

    @pytest.mark.parametrize('inputs', [
        {'ghost': point_input(0, 0)},
        {'M': point_input(0, 0)},
        {'A': point_input(float('nan'), 0)},
        {'A': point_input(True, 0)},
        {'A': {'kind': 'number', 'value': 1}},
        {'A': {'kind': 'point', 'value': [1, 2, 3]}},
        [('A', point_input(0, 0))],
    ])
    def test_bad_overrides(self, inputs):
        doc = DocBuilder('in').free('A', 0, 0).free('B', 2, 0).midpoint('M', 'A', 'B').doc
        with pytest.raises(ValueError):
            native.evaluate(doc, inputs=inputs)


class TestRobustness:
    def test_non_finite(self):
        doc = DocBuilder('big').free('A', 1.7e308, 0).free('B', 1.7e308, 0).midpoint('M', 'A', 'B').doc
        assert states(native.evaluate(doc))['M'] == 'undefined/non_finite'

    def test_exception_is_internal(self, monkeypatch):
        def broken(args, ctx):
            raise ZeroDivisionError('boom')
        monkeypatch.setitem(kernel_ops.IMPLEMENTATIONS, 'point.midpoint', broken)
        doc = DocBuilder('x').free('A', 0, 0).free('B', 2, 0).midpoint('M', 'A', 'B').segment('s', 'M', 'A').doc
        ev = native.evaluate(doc)
        assert states(ev)['M'] == 'error/internal'
        assert states(ev)['s'] == 'error/upstream/M'
        assert ev.diagnostics == [{'code': 'internal', 'operationId': 'op_M', 'op': 'point.midpoint',
                                   'message': 'ZeroDivisionError: boom'}]

    def test_missing_slot_in_result_is_internal(self, monkeypatch):
        monkeypatch.setitem(kernel_ops.IMPLEMENTATIONS, 'point.midpoint', lambda args, ctx: {})
        doc = DocBuilder('x').free('A', 0, 0).free('B', 2, 0).midpoint('M', 'A', 'B').doc
        ev = native.evaluate(doc)
        assert states(ev)['M'] == 'error/internal'
        assert ev.diagnostics[0]['code'] == 'internal'

    def test_order_independence(self):
        doc = chain_doc()
        doc['inputs']['A'] = point_input(1, 1)
        doc['inputs']['B'] = point_input(1, 1)
        reordered = copy.deepcopy(doc)
        reordered['operations'] = dict(reversed(list(doc['operations'].items())))
        reordered['elements'] = dict(reversed(list(doc['elements'].items())))
        assert native.evaluate(reordered).to_dict() == native.evaluate(doc).to_dict()

    def test_partial_and_shared_outputs(self):
        b = DocBuilder('poly').free('A', 0, 0).free('B', 4, 0).free('C', 0, 3)
        b.polygon('T', 'A', 'B', 'C', sides=[(2, 'sBC')])
        ev = native.evaluate(b.doc)
        assert ev.elements['sBC']['value'] == {'a': [4.0, 0.0], 'b': [0.0, 3.0], 'length': 5.0}
        assert native.check(b.doc).results == {'op_T:sides_match': 'passed'}

    def test_large_chain_without_recursion(self):
        b = DocBuilder('long').free('A', 0, 0).free('B', 1, 0)
        prev = 'B'
        for i in range(3000):
            b.midpoint(f'M{i}', 'A', prev)
            prev = f'M{i}'
        ev = native.evaluate(b.doc)
        assert ev.elements['M2999']['state'] == 'defined'
