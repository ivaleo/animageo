"""number.expression and AST v1 (docs/native/expr.md, registry 1.4, 1.8.1a5)."""
import ast as pyast
import math
from pathlib import Path

import pytest

import animageo.native as native
from animageo.native import expr
from animageo.native.commands import parse_commands, print_commands
from animageo.native.expr import ExprError, evaluate, problems, to_text
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, number_input, ref, ref_list


def N(v):
    return {'num': v}


def R(k):
    return {'ref': k}


def O(o, *args):
    return {'op': o, 'args': list(args)}


def F(name, *args):
    return {'fn': name, 'args': list(args)}


PI = {'const': 'pi'}


def reason(ast, refs=()):
    with pytest.raises(ExprError) as info:
        evaluate(ast, refs)
    return info.value.reason


def chain(depth):
    """A tree of ``depth`` levels: neg(neg(… num 1))."""
    node = N(1)
    for _ in range(depth - 1):
        node = O('neg', node)
    return node


# ── the rules ────────────────────────────────────────────────────────────


class TestProblems:
    def test_a_valid_tree(self):
        tree = O('+', F('sqrt', R(0)), O('^', R(1), N(3)))
        assert problems(tree, 2) == []
        assert problems(F('min', PI, F('max', N(-1), N(2.5))), 0) == []
        assert problems(R(1.0), 2) == []                      # an integral float is an integer

    @pytest.mark.parametrize('tree, pointer, text', [
        ([1], '', 'must be an object'),
        ({'num': 1, 'const': 'pi'}, '', 'exactly one'),
        ({}, '', 'exactly one'),
        ({'num': 1, 'unit': 'length'}, '', "does not allow key 'unit'"),
        ({'op': '+'}, '', "misses key 'args'"),
        ({'num': '1'}, '', 'finite number'),
        ({'num': True}, '', 'finite number'),
        ({'num': math.inf}, '', 'finite number'),
        ({'const': 'e'}, '', 'unknown constant'),
        ({'ref': -1}, '', 'integer >= 0'),
        ({'ref': 0.5}, '', 'integer >= 0'),
        ({'ref': 2}, '', 'outside refs'),
        (O('%', N(1), N(2)), '', 'unknown operator'),
        (F('atan2', N(1), N(2)), '', 'unknown function'),
        (F('log10', N(1)), '', 'unknown function'),
        (F('cbrt', N(1)), '', 'unknown function'),
        ({'var': 'x'}, '', "'var' is not in AST v1"),
        ({'if': [{'cmp': '<', 'args': [N(1), N(2)]}, N(1)]}, '', "'if' is not in AST v1"),
        (O('+', N(1)), '', 'takes 2 arguments, not 1'),
        (O('neg', N(1), N(2)), '', 'takes 1 argument, not 2'),
        (F('sqrt'), '', 'takes 1 argument, not 0'),
        ({'fn': 'sqrt', 'args': {}}, '', 'args must be an array'),
        (O('^', R(0), N(65)), '', 'integer power above 64'),
        (O('^', R(0), N(-65.0)), '', 'integer power above 64'),
        (O('+', N(1), F('sqrt', {'ref': 3})), '/args/1/args/0', 'outside refs'),
    ])
    def test_a_rule(self, tree, pointer, text):
        found = problems(tree, 2)
        assert len(found) == 1 and found[0][0] == pointer and text in found[0][1], found

    def test_problems_in_pre_order(self):
        tree = O('+', F('nope', N(1)), O('*', {'const': 'e'}, {'ref': 9}))
        assert [p for p, _m in problems(tree, 1)] == ['/args/0', '/args/1/args/0', '/args/1/args/1']

    def test_powers_inside_the_limit(self):
        assert problems(O('^', R(0), N(64)), 1) == []
        assert problems(O('^', R(0), N(-64)), 1) == []
        assert problems(O('^', R(0), N(100.5)), 1) == []      # not an integer: pow
        assert problems(O('^', R(0), O('neg', N(100))), 1) == []   # not a literal: pow

    def test_ref_count_none_skips_the_range(self):
        assert problems(R(7)) == []

    def test_depth(self):
        assert expr.MAX_DEPTH == 32
        assert problems(chain(32)) == []
        found = problems(chain(33))
        assert found == [('/args/0' * 32, 'deeper than 32 levels')]

    def test_nodes(self):
        assert expr.MAX_NODES == 256

        def full(depth):
            return N(0) if depth == 1 else O('+', full(depth - 1), full(depth - 1))

        tree = full(8)                                    # 255 nodes
        assert sum(1 for _ in _walk(tree)) == 255 and problems(tree) == []
        assert problems(F('min', tree, N(1))) == [('', 'more than 256 nodes')]          # 257
        assert problems(O('neg', tree)) == []                                           # 256

    def test_a_deep_tree_does_not_recurse(self):
        found = problems(chain(20000))
        assert found == [('/args/0' * 32, 'deeper than 32 levels')]
        with pytest.raises(ExprError) as info:
            evaluate(chain(20000))
        assert info.value.reason == 'formula'

    def test_limits_are_in_the_registry(self):
        limits = registry().numeric['expr']
        assert (limits['maxDepth'], limits['maxNodes'], limits['maxIntegerPower']) == \
            (expr.MAX_DEPTH, expr.MAX_NODES, expr.MAX_INTEGER_POWER)
        info = registry().types['expr']
        assert info['value'] == {} and info['argument'] is True

    def test_whitelist(self):
        assert set(expr.FUNCTIONS) == {'sqrt', 'abs', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'exp',
                                       'ln', 'lg', 'min', 'max'}
        assert set(expr.OPERATORS) == {'+', '-', '*', '/', '^', 'neg'}
        assert expr.CONSTANTS == ('pi',)


def _walk(node):
    yield node
    for child in node.get('args', ()):
        yield from _walk(child)


# ── evaluation ───────────────────────────────────────────────────────────


class TestEvaluate:
    @pytest.mark.parametrize('tree, refs, value', [
        (O('+', F('sqrt', R(0)), O('^', R(1), N(3))), (4, 2), 10.0),
        (O('-', N(1), N(3)), (), -2.0),
        (O('*', PI, N(2)), (), 2 * math.pi),
        (O('/', N(1), N(4)), (), 0.25),
        (O('neg', R(0)), (3,), -3.0),
        (O('^', N(2), N(-3)), (), 0.125),
        (O('^', N(-2), N(3)), (), -8.0),
        (O('^', N(2), N(0)), (), 1.0),
        (O('^', N(-8), N(2.0)), (), 64.0),
        (O('^', N(4), N(0.5)), (), 2.0),
        (O('^', N(-2), O('+', N(1), N(1))), (), 4.0),        # pow with an integral value
        (F('abs', N(-2.5)), (), 2.5),
        (F('sin', N(0)), (), 0.0),
        (F('cos', N(0)), (), 1.0),
        (F('tan', N(0)), (), 0.0),
        (F('asin', N(1)), (), math.pi / 2),
        (F('acos', N(-1)), (), math.pi),
        (F('atan', N(1)), (), math.atan(1)),
        (F('exp', N(0)), (), 1.0),
        (F('ln', N(1)), (), 0.0),
        (F('lg', N(1000)), (), 3.0),
        (F('min', N(2), N(-1)), (), -1.0),
        (F('max', N(2), N(-1)), (), 2.0),
        (R(0), (1.5,), 1.5),
    ])
    def test_value(self, tree, refs, value):
        assert evaluate(tree, refs) == value

    @pytest.mark.parametrize('tree, refs, why', [
        (O('/', N(1), N(0)), (), 'out_of_domain'),
        (O('/', N(0), O('-', N(1), N(1))), (), 'out_of_domain'),
        (F('sqrt', N(-1e-300)), (), 'out_of_domain'),
        (F('ln', N(0)), (), 'out_of_domain'),
        (F('lg', N(-1)), (), 'out_of_domain'),
        (F('asin', N(1.0000001)), (), 'out_of_domain'),
        (F('acos', N(-2)), (), 'out_of_domain'),
        (O('^', N(-8), N(1 / 3)), (), 'out_of_domain'),
        (O('^', N(0), N(-2)), (), 'non_finite'),
        (O('^', N(0), N(-0.5)), (), 'non_finite'),
        (O('^', N(10), N(400.5)), (), 'non_finite'),
        (O('^', N(1e300), N(2)), (), 'non_finite'),
        (F('exp', N(1000)), (), 'non_finite'),
        (O('*', N(1e200), N(1e200)), (), 'non_finite'),
        (O('+', R(0), R(0)), (1.7e308,), 'non_finite'),
    ])
    def test_undefined(self, tree, refs, why):
        assert reason(tree, refs) == why

    def test_the_first_failing_node_decides(self):
        assert reason(O('+', F('sqrt', N(-1)), F('exp', N(1000)))) == 'out_of_domain'
        assert reason(O('+', F('exp', N(1000)), F('sqrt', N(-1)))) == 'non_finite'
        # an overflow is caught at its node, before a later domain check sees an infinity
        assert reason(F('sqrt', O('neg', F('exp', N(1000))))) == 'non_finite'

    def test_integer_powers_are_binary_powering(self):
        def power(b, n):
            r, m = 1.0, abs(n)
            while m:
                if m & 1:
                    r = r * b
                b = b * b
                m >>= 1
            return 1.0 / r if n < 0 else r

        for base in (1.1, -0.7, 3.3, 1e-3):
            for n in (1, 2, 5, 7, 13, 31, 64, -1, -7, -64):
                assert evaluate(O('^', N(base), N(n))) == power(base, n), (base, n)

    def test_signed_zero(self):
        assert math.copysign(1, evaluate(O('neg', N(0)))) == 1          # -0 comes out as 0
        assert math.copysign(1, evaluate(O('*', N(-1), N(0)))) == 1
        # min/max take the second argument only when strictly smaller/greater
        from animageo.native.expr.evaluate import _eval

        zero, minus_zero = N(0.0), O('neg', N(0))
        assert math.copysign(1, _eval(F('min', zero, minus_zero), [])) == 1
        assert math.copysign(1, _eval(F('min', minus_zero, zero), [])) == -1
        assert math.copysign(1, _eval(F('max', minus_zero, zero), [])) == -1

    def test_refs_and_formula(self):
        assert evaluate(O('+', R(0), R(1)), [1, 2]) == 3.0
        assert reason(R(2), [1, 2]) == 'formula'
        assert reason({'fn': 'eval', 'args': [N(1)]}) == 'formula'


# ── text ─────────────────────────────────────────────────────────────────


class TestText:
    @pytest.mark.parametrize('tree, text', [
        (O('+', F('sqrt', R(0)), O('^', R(1), N(3))), 'sqrt(a) + b^3'),
        (O('-', R(0), O('-', R(1), N(1))), 'a - (b - 1)'),
        (O('-', O('-', R(0), R(1)), N(1)), 'a - b - 1'),
        (O('*', O('+', R(0), N(1)), R(1)), '(a + 1)·b'),
        (O('/', R(0), O('*', R(1), N(2))), 'a/(b·2)'),
        (O('^', R(0), O('^', R(1), N(2))), 'a^b^2'),
        (O('^', O('^', R(0), R(1)), N(2)), '(a^b)^2'),
        (O('^', O('neg', R(0)), N(2)), '(-a)^2'),
        (O('neg', O('^', R(0), N(2))), '-a^2'),
        (O('^', R(0), N(-2)), 'a^(-2)'),
        (O('+', R(0), O('neg', R(1))), 'a + (-b)'),
        (O('neg', O('neg', R(0))), '-(-a)'),
        (F('max', PI, N(1.5e-7)), 'max(pi, 1.5e-7)'),
    ])
    def test_text(self, tree, text):
        assert to_text(tree, ['a', 'b']) == text


# ── documents ────────────────────────────────────────────────────────────


def expression_doc(tree, refs=('a', 'b'), *, kind='expr'):
    b = DocBuilder('expr_doc', registry_version='1.4')
    b.number('a', 4).number('b', 2)
    arg = {'kind': kind, 'ast': tree} if kind == 'expr' else {'kind': 'number', 'value': 1}
    b.op('op_e', 'number.expression', {'expr': arg, 'refs': ref_list(*refs)}, [('number', 'e', 'number')])
    return b


class TestDocument:
    def test_evaluate(self):
        doc = expression_doc(O('+', F('sqrt', R(0)), O('^', R(1), N(3)))).doc
        assert native.validate(doc) == []
        assert native.evaluate(doc).elements['e']['value'] == {'value': 10.0, 'unit': 'scalar'}
        e = native.evaluate(doc, inputs={'a': number_input(-1)}).elements['e']
        assert (e['state'], e['reason']) == ('undefined', 'out_of_domain')

    def test_a_refused_tree(self):
        doc = expression_doc(O('+', R(0), F('sqrt', R(2)))).doc
        issues = native.validate(doc)
        assert [(i.code, i.path, i.severity) for i in issues] == \
            [('formula', '/operations/op_e/args/expr/ast/args/1/args/0', 'error')]
        e = native.evaluate(doc).elements['e']
        assert (e['state'], e['reason']) == ('error', 'formula')

    def test_kinds(self):
        doc = expression_doc(None, kind='number').doc
        assert [i.code for i in native.validate(doc)] == ['type_mismatch']
        assert native.evaluate(doc).elements['e']['reason'] == 'type_mismatch'
        b = DocBuilder('expr_elsewhere', registry_version='1.4')
        b.free('O', 0, 0).free('A', 3, 0)
        b.op('op_c', 'circle.center_radius', {'center': ref('O'), 'radius': {'kind': 'expr', 'ast': N(2)}},
             [('circle', 'c', 'circle')])
        assert [i.code for i in native.validate(b.doc)] == ['type_mismatch']
        assert native.evaluate(b.doc).elements['c']['reason'] == 'type_mismatch'

    def test_empty_refs_and_upstream(self):
        b = expression_doc(O('*', N(2), PI), refs=())
        assert native.evaluate(b.doc).elements['e']['value']['value'] == 2 * math.pi
        b = expression_doc(F('sqrt', R(0)), refs=('L',))
        b.free('A', 0, 0).free('Q', 3, 4).segment('s', 'A', 'Q')
        b.op('op_L', 'measure.length', {'of': ref('s')}, [('number', 'L', 'number')])
        assert native.evaluate(b.doc).elements['e']['value']['value'] == math.sqrt(5)
        e = native.evaluate(b.doc, inputs={'Q': {'kind': 'point', 'value': [0, 0]}}).elements['e']
        assert e['value']['value'] == 0.0                  # a zero segment is defined, length 0
        b.doc['elements']['L']['type'] = 'point'
        assert native.evaluate(b.doc).elements['e']['reason'] == 'type_mismatch'

    def test_commands_print_and_keep(self):
        doc = expression_doc(O('+', F('sqrt', R(0)), O('^', R(1), N(3)))).doc
        printed = print_commands(doc)
        assert printed.text.splitlines()[-1] == 'e = sqrt(a) + b^3'
        assert [(i.code, i.line) for i in printed.issues] == [('unprintable_operation', 3)]
        result = parse_commands(printed.text, base=doc)
        assert [(i.code, i.line) for i in result.issues] == [('forbidden', 3)]
        assert native.canonical_json(result.document.data) == native.canonical_json(doc)


# ── no eval, stdlib only ─────────────────────────────────────────────────


def test_the_package_has_no_eval_and_imports_only_the_stdlib():
    root = Path(expr.__file__).parent
    for path in sorted(root.glob('*.py')):
        tree = pyast.parse(path.read_text(encoding='utf-8'))
        for node in pyast.walk(tree):
            if isinstance(node, pyast.Call) and isinstance(node.func, pyast.Name):
                assert node.func.id not in ('eval', 'exec', 'compile', '__import__'), path.name
            if isinstance(node, pyast.Import):
                assert all(a.name in ('math',) for a in node.names), path.name
            if isinstance(node, pyast.ImportFrom) and node.level == 0:
                assert node.module in ('__future__', 'math'), path.name
