"""point.expression and vector.expression (registry 1.10, docs/native/ops/point.expression.md,
docs/native/ops/vector.expression.md): kernel, validate, describe, «Команды», bridge, labels, drag."""
import math

import pytest

from animageo import native
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, ref, ref_list

REG = '1.10'
X = {'var': 'x'}


def N(v):
    return {'num': v}


def R(k):
    return {'ref': k}


def O(o, *args):
    return {'op': o, 'args': list(args)}


def F(name, *args):
    return {'fn': name, 'args': list(args)}


def expression(b, el_id, ast, *refs, kind='point'):
    b.op(f'op_{el_id}', f'{kind}.expression',
         {'expr': {'kind': 'expr', 'ast': ast}, 'refs': ref_list(*refs)}, [(kind, el_id, kind)])
    return b


def base(registry_version=REG):
    """Free A(1, 2), U(1, 1), V(4, 5); u = UV, t = 0.25, f(x) = x²."""
    b = DocBuilder('expr_points', registry_version=registry_version).free('A', 1, 2).free('U', 1, 1).free('V', 4, 5)
    b.vector('u', 'U', 'V').number('t', 0.25)
    b.op('op_f', 'function.expr', {'expr': {'kind': 'expr', 'ast': O('*', X, X)}, 'refs': ref_list()},
         [('function', 'f', 'function')])
    return b


def element(doc, el_id, inputs=None):
    return native.evaluate(doc, inputs=inputs).elements[el_id]


class TestKernel:
    def test_point_from_a_sum(self):
        b = expression(base(), 'M', O('+', R(0), R(1)), 'A', 'u')
        assert native.validate(b.doc) == []
        assert element(b.doc, 'M')['value'] == {'x': 4.0, 'y': 6.0}

    def test_point_from_a_pair_and_a_call(self):
        b = expression(base(), 'M', {'pair': [O('*', N(2), R(0)), {'call': 1, 'args': [N(3)]}]}, 't', 'f')
        assert element(b.doc, 'M')['value'] == {'x': 0.5, 'y': 9.0}

    def test_vector_from_the_origin(self):
        b = expression(base(), 'w', O('*', N(2), O('-', R(0), R(1))), 'A', 'u', kind='vector')
        rec = element(b.doc, 'w')
        assert rec['type'] == 'vector'
        assert rec['value'] == {'a': [0.0, 0.0], 'b': [-4.0, -4.0], 'length': math.hypot(4.0, 4.0)}

    def test_affine_combination_moves_with_its_inputs(self):
        b = expression(base(), 'M', O('+', O('*', R(0), R(1)), O('*', O('-', N(1), R(0)), R(2))), 't', 'A', 'V')
        assert element(b.doc, 'M')['value'] == {'x': 0.25 + 0.75 * 4, 'y': 0.5 + 0.75 * 5}
        moved = element(b.doc, 'M', inputs={'A': {'kind': 'point', 'value': [5, 6]}})['value']
        assert moved == {'x': 0.25 * 5 + 3.0, 'y': 0.25 * 6 + 3.75}

    def test_reasons(self):
        b = expression(base(), 'M', O('/', R(0), O('-', R(1), N(0.25))), 'A', 't')
        assert (element(b.doc, 'M')['state'], element(b.doc, 'M')['reason']) == ('undefined', 'out_of_domain')
        b = expression(base(), 'M', {'pair': [N(0), O('*', O('*', R(0), N(1e308)), N(10))]}, 't')
        assert element(b.doc, 'M')['reason'] == 'non_finite'
        b = expression(base(), 'M', {'pair': [N(0), {'call': 0, 'args': [N(1e200)]}]}, 'f')
        assert element(b.doc, 'M')['reason'] == 'out_of_domain'         # f has no value there
        b = base().free('C', 0, 0).free('D', 1, 0).free('E', 0, 1).free('G', 1, 1)
        b.line('l', 'C', 'D').line('m', 'E', 'G').intersect('P', 'l', 'm')          # parallel lines
        expression(b, 'M', O('+', R(0), R(1)), 'P', 'u')
        assert (element(b.doc, 'M')['state'], element(b.doc, 'M')['reason']) == ('undefined', 'upstream')

    def test_negative_zero_is_zero(self):
        b = expression(base(), 'M', O('neg', {'pair': [N(0), N(0)]}), kind='point')
        value = element(b.doc, 'M')['value']
        assert math.copysign(1.0, value['x']) == 1.0 and math.copysign(1.0, value['y']) == 1.0
        b = expression(base(), 'w', O('*', N(-1), {'pair': [N(0), N(1)]}), kind='vector')
        assert math.copysign(1.0, element(b.doc, 'w')['value']['b'][0]) == 1.0


class TestValidate:
    def test_a_type_mistake_is_formula_at_its_node(self):
        b = expression(base(), 'M', O('*', O('+', R(0), N(1)), N(2)), 'A')
        issues = native.validate(b.doc)
        assert [(i.code, i.path, i.severity) for i in issues] == \
            [('formula', '/operations/op_M/args/expr/ast/args/0', 'error')]
        assert 'vec + num' in issues[0].message
        assert (element(b.doc, 'M')['state'], element(b.doc, 'M')['reason']) == ('error', 'formula')

    def test_the_root_against_the_result(self):
        b = expression(base(), 'M', O('*', R(0), R(1)), 'A', 'u')            # a dot product is a number
        assert [(i.code, i.path) for i in native.validate(b.doc)] == [('formula', '/operations/op_M/args/expr/ast')]
        assert element(b.doc, 'M')['reason'] == 'formula'
        b = expression(base(), 'M', R(0), 'f')                                 # a bare function
        assert [(i.code, i.path) for i in native.validate(b.doc)] == [('formula', '/operations/op_M/args/expr/ast')]

    def test_no_cascade_from_refs(self):
        b = base().free('C', 0, 0).free('D', 1, 0).line('l', 'C', 'D')
        expression(b, 'M', O('+', R(0), N(1)), 'l')
        assert [i.code for i in native.validate(b.doc)] == ['type_mismatch']
        b = expression(base(), 'M', O('+', R(0), N(1)), 'nobody')
        assert [i.code for i in native.validate(b.doc)] == ['dangling_ref']
        assert element(b.doc, 'M')['reason'] == 'dangling_ref'

    def test_old_slots_refuse_the_typed_nodes(self):
        b = base()
        b.op('op_n', 'number.expression', {'expr': {'kind': 'expr', 'ast': {'pair': [N(1), N(2)]}},
                                            'refs': ref_list()}, [('number', 'n', 'number')])
        assert [i.code for i in native.validate(b.doc)] == ['formula']
        assert element(b.doc, 'n')['reason'] == 'formula'

    def test_needs_registry_1_10(self):
        b = expression(base('1.9'), 'M', O('+', R(0), R(1)), 'A', 'u')
        assert [(i.code, i.path) for i in native.validate(b.doc)] == \
            [('needs_newer_registry', '/operations/op_M/op')]

    def test_records(self):
        reg = registry()
        for kind in ('point', 'vector'):
            record = reg.get(f'{kind}.expression')
            assert record['since'] == '1.10' and record['status'] == 'beta'
            assert record['inputs'] == [{'slot': 'expr', 'type': 'expr', 'result': 'vec'},
                                        {'slot': 'refs', 'type': 'operand', 'list': True, 'min': 0}]
            assert record['undefined'] == ['out_of_domain', 'non_finite', 'upstream']
            assert record['stepKind'] == f'{kind}_expression'
            assert record['phrases'] == {'ru': f'{{{kind}}} = {{expr}}'}
        assert native.has('typed_expressions')


class TestText:
    def test_describe_prints_the_formula(self):
        b = expression(base(), 'M', O('+', R(0), O('*', R(1), R(2))), 'A', 't', 'u')
        expression(b, 'w', {'pair': [N(1), {'call': 0, 'args': [N(2)]}]}, 'f', kind='vector')
        lines = native.describe(b.doc)
        assert any(line.endswith('Отмечаем точку M = A + t·u.') for line in lines), lines
        assert any(line.endswith('Строим вектор w = (1, f(2)).') for line in lines), lines

    def test_commands_print_a_warning_and_keep_the_operation(self):
        from animageo.native.commands import parse_commands, print_commands
        b = expression(base(), 'M', O('+', R(0), R(1)), 'A', 'u')
        printed = print_commands(b.doc)
        line = next(i for i in printed.issues if i.code == 'unprintable_operation' and 'выражения' in i.message)
        assert printed.text.splitlines()[line.line - 1].startswith('M = point.expression(')
        assert line.message == 'выражения в «Командах» будут позже'
        result = parse_commands(printed.text, base=b.doc)          # an edit keeps it, as a function
        assert native.canonical_json(result.document.data) == native.canonical_json(b.doc)
        alone = parse_commands(printed.text)                          # without the base it is not read
        assert alone.document is None or 'op_M' not in alone.document.data.get('operations', {})


class TestDrawing:
    def doc(self):
        b = expression(base(), 'M', O('+', R(0), R(1)), 'A', 'u')
        expression(b, 'w', O('-', R(0), R(1)), 'V', 'A', kind='vector')
        b.segment('s', 'A', 'M')
        return b

    def test_the_bridge_builds_the_kernel_values(self):
        from animageo.native.kernel import bridge
        b = self.doc()
        for inputs in (None, {'A': {'kind': 'point', 'value': [-2, 3]}}):
            constr, names = bridge.build_construction(b.doc, inputs=inputs)
            constr.rebuild(full=True)
            ev = native.evaluate(b.doc, inputs=inputs).elements
            for el_id in ('M', 'w', 's'):
                data = constr.objectByName(names.by_id[el_id]).data
                got = bridge.from_classic(ev[el_id]['type'], data)
                assert native.canonical_json(got) == native.canonical_json(ev[el_id]['value']), el_id

    def test_a_label_like_a_free_point(self):
        b = self.doc()
        layout = native.layout_labels(b.doc, backend='metrics')
        m, a = layout['M'], layout['A']
        assert m['text'] == '$M$'
        assert (m['anchor'], m['offsetPx']) == (a['anchor'], a['offsetPx'])
        # A(1, 2) and M(4, 6): the label sits at its own point, 3 and 4 units away
        scale = (m['point'][0] - a['point'][0]) / 3
        assert scale > 0 and m['point'][1] - a['point'][1] == pytest.approx(-4 * scale)

    @pytest.mark.manim
    def test_drawn(self, tmp_path):
        pytest.importorskip('manim')
        b = self.doc()
        plain = base().segment('s', 'A', 'V')
        native.render(b.doc, out=tmp_path / 'expr.svg', fmt='svg', report=False)
        native.render(plain.doc, out=tmp_path / 'plain.svg', fmt='svg', report=False)
        svg = (tmp_path / 'expr.svg').read_bytes()
        assert svg.count(b'<path') > (tmp_path / 'plain.svg').read_bytes().count(b'<path')

    def test_drag_through_its_inputs(self):
        b = self.doc()
        b.doc.setdefault('appearance', {})['M'] = {'drag': {'via': 'A'}}
        assert native.validate(b.doc) == []
        result = native.drag(b.doc, {}, 'M', (7.0, -1.0))
        assert result['status'] == 'ok'
        inputs = result['inputs']
        moved = element(b.doc, 'M', inputs=inputs)['value']
        assert moved['x'] == pytest.approx(7.0, abs=1e-9) and moved['y'] == pytest.approx(-1.0, abs=1e-9)
        assert inputs['A']['value'] == pytest.approx([4.0, -5.0], abs=1e-9)
