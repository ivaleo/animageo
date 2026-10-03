"""Contract extensions of registry 1.2: the number input, op params, number literals, by_unit."""
import copy
import math

import pytest

from animageo import native
from animageo.native.kernel.evaluate import check_inputs, valid_input
from animageo.native.kernel.values import compare_values
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, num, number_input, point_input, ref


def codes(issues):
    return [i.code for i in issues]


def ev(doc, inputs=None):
    return native.evaluate(doc, inputs=inputs).elements


# ── the number input ─────────────────────────────────────────────────────

class TestNumberInput:
    def test_valid_input(self):
        assert valid_input('number', {'kind': 'number', 'value': 2.5})
        assert valid_input('number', {'kind': 'number', 'value': -3})
        for bad in ({'kind': 'number', 'value': math.inf}, {'kind': 'number', 'value': math.nan},
                    {'kind': 'number', 'value': True}, {'kind': 'number', 'value': '1'},
                    {'kind': 'number', 'value': 1, 'unit': 'length'}, {'kind': 'number'},
                    {'kind': 'point', 'value': [1, 2]}):
            assert not valid_input('number', bad), bad

    def test_check_inputs(self):
        doc = native.load(DocBuilder('n', registry_version='1.2').number('r', 2).doc)
        assert check_inputs(doc, {'r': number_input(7)}) == {'r': number_input(7)}
        with pytest.raises(ValueError, match='number'):
            check_inputs(doc, {'r': point_input(1, 2)})
        with pytest.raises(ValueError, match='number'):
            check_inputs(doc, {'r': {'kind': 'number', 'value': math.inf}})

    def test_validate_kind_must_match(self):
        b = DocBuilder('n', registry_version='1.2').number('r', 2).free('A', 0, 0)
        b.doc['inputs']['A'] = number_input(1)
        b.doc['inputs']['r'] = point_input(1, 2)
        assert sorted(codes(native.validate(b.doc))) == ['type_mismatch', 'type_mismatch']
        assert native.validate(DocBuilder('n', registry_version='1.2').number('r', 2).doc) == []

    def test_missing_input(self):
        doc = DocBuilder('n', registry_version='1.2').number('r').doc
        assert codes(native.validate(doc)) == ['missing_input']
        assert ev(doc)['r'] == {'state': 'error', 'type': 'number', 'reason': 'schema'}

    def test_number_inputs_do_not_count_in_scale(self):
        b = DocBuilder('n', registry_version='1.2', bounds=(-1, -1, 1, 1)).number('r', 1e6).free('A', 0, 0)
        assert native.evaluate(b.doc).scale == 2.0


# ── params ───────────────────────────────────────────────────────────────

class TestParams:
    def doc(self, strict=None):
        b = DocBuilder('p', registry_version='1.2').free('A', 1, 3).free('B', 0, 0).free('C', 4, 0)
        return b.segment('s', 'B', 'C').projection('H', 'A', 's', strict=strict)

    def test_optional_param_may_be_absent(self):
        assert native.validate(self.doc().doc) == []
        assert native.validate(self.doc(strict=1).doc) == []

    def test_param_must_be_a_number(self):
        b = self.doc()
        b.doc['operations']['op_H']['args']['strict'] = ref('A')
        assert codes(native.validate(b.doc)) == ['type_mismatch']
        assert ev(b.doc)['H'] == {'state': 'error', 'type': 'point', 'reason': 'type_mismatch'}

    def test_param_list_is_a_type_mismatch(self):
        b = self.doc()
        b.doc['operations']['op_H']['args']['strict'] = {'kind': 'list', 'items': [num(1)]}
        assert codes(native.validate(b.doc)) == ['type_mismatch']
        assert ev(b.doc)['H']['reason'] == 'type_mismatch'

    def test_required_param(self, monkeypatch):
        record = copy.deepcopy(registry().get('point.projection'))
        param = record['params'][0]
        param.pop('default')
        param['optional'] = False
        monkeypatch.setitem(registry().ops, 'point.projection', record)
        doc = self.doc().doc
        assert codes(native.validate(doc)) == ['missing_slot']
        assert ev(doc)['H'] == {'state': 'error', 'type': 'point', 'reason': 'schema'}
        assert ev(self.doc(strict=0).doc)['H']['state'] == 'defined'

    def test_param_values_reach_the_op(self):
        out = ev(self.doc(strict=1).doc, {'A': point_input(6, 3)})
        assert out['H'] == {'state': 'undefined', 'type': 'point', 'reason': 'outside_part',
                            'detail': {'slot': 'base'}}
        assert ev(self.doc().doc, {'A': point_input(6, 3)})['H']['state'] == 'defined'

    def test_params_do_not_make_dependencies(self):
        doc = native.load(self.doc(strict=1).doc)
        assert native.dependencies(doc, 'H') == ['A', 'B', 'C', 's']


# ── number literals in number inputs ─────────────────────────────────────

class TestLiterals:
    def test_literal_radius(self):
        b = DocBuilder('l', registry_version='1.2').free('O', 1, 2).circle_radius('c', 'O', 3)
        assert native.validate(b.doc) == []
        assert ev(b.doc)['c'] == {'state': 'defined', 'type': 'circle', 'value': {'c': [1.0, 2.0], 'r': 3.0}}

    def test_reference_radius(self):
        b = DocBuilder('l', registry_version='1.2').free('O', 1, 2).number('r', 2.5).circle_radius('c', 'O', 'r')
        assert ev(b.doc)['c']['value'] == {'c': [1.0, 2.0], 'r': 2.5}
        assert native.dependencies(native.load(b.doc), 'c') == ['O', 'r']

    def test_literal_in_a_point_slot(self):
        b = DocBuilder('l', registry_version='1.2').free('O', 1, 2).circle_radius('c', 'O', 3)
        b.doc['operations']['op_c']['args']['center'] = num(1)
        assert codes(native.validate(b.doc)) == ['type_mismatch']
        assert ev(b.doc)['c']['reason'] == 'type_mismatch'

    def test_point_in_a_number_slot(self):
        b = DocBuilder('l', registry_version='1.2').free('O', 1, 2).circle_radius('c', 'O', 'O')
        assert codes(native.validate(b.doc)) == ['type_mismatch']
        assert ev(b.doc)['c']['reason'] == 'type_mismatch'

    def test_upstream_through_a_number(self):
        b = DocBuilder('l', registry_version='1.2').free('O', 1, 2).number('r', 2, min=3, max=1)
        b.circle_radius('c', 'O', 'r')
        out = ev(b.doc)
        assert out['r'] == {'state': 'undefined', 'type': 'number', 'reason': 'invalid_parameter'}
        assert out['c'] == {'state': 'undefined', 'type': 'circle', 'reason': 'upstream', 'cause': 'r'}


# ── by_unit comparison ───────────────────────────────────────────────────

def test_compare_number_by_unit():
    info = registry().types['number']
    tolerance = {'length': 1e-8, 'area': 1e-4, 'scalar': 1e-12}.get

    def diff(expected, actual):
        return compare_values(info, expected, actual, tolerance, units=registry().number_units)

    assert diff({'value': 1.0, 'unit': 'area'}, {'value': 1.00001, 'unit': 'area'}) == []
    assert diff({'value': 1.0, 'unit': 'length'}, {'value': 1.00001, 'unit': 'length'}) != []
    assert diff({'value': 1.0, 'unit': 'angle'}, {'value': 1.0 + 1e-10, 'unit': 'angle'}) != []
    assert diff({'value': 1.0, 'unit': 'length'}, {'value': 1.0, 'unit': 'area'}) == [
        "value.unit: expected 'length', got 'area'"]
