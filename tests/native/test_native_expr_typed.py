"""Typed expressions (registry 1.10, docs/native/expr.md §6): the nodes pair,
call and x/y, the overloads for pairs, the type pass and the typed interpreter."""
import math

import pytest

from animageo.native.expr import (ExprError, MAX_DEPTH, MAX_NODES, evaluate_typed, problems, to_text,
                                  type_problems)


def N(v):
    return {'num': v}


def R(k):
    return {'ref': k}


def O(o, *args):
    return {'op': o, 'args': list(args)}


def F(name, *args):
    return {'fn': name, 'args': list(args)}


def PAIR(a, b):
    return {'pair': [a, b]}


def CALL(k, a):
    return {'call': k, 'args': [a]}


PI = {'const': 'pi'}
P = ('point', {'x': 1.0, 'y': 2.0})
Q = ('point', {'x': 4.0, 'y': -2.0})
U = ('vector', {'a': [1.0, 1.0], 'b': [4.0, 5.0], 'length': 5.0})
K = ('number', {'value': 2.0, 'unit': 'scalar'})
SQUARE = ('function', {'expr': O('*', {'var': 'x'}, {'var': 'x'}), 'refs': [], 'domain': [None, None]})


def types(*operands):
    return [t for t, _ in operands]


def pointers(ast, operands, result):
    return [p for p, _ in problems(ast, len(operands), (), types(*operands), result)]


def value(ast, operands, result):
    return evaluate_typed(ast, list(operands), result)


def reason(ast, operands, result):
    with pytest.raises(ExprError) as info:
        evaluate_typed(ast, list(operands), result)
    return info.value.reason


class TestStructure:
    def test_old_slots_refuse_the_typed_nodes(self):
        assert problems(PAIR(N(1), N(2)), 0) == [('', 'a node must have exactly one of num, const, ref, op, fn')]
        assert problems(CALL(0, N(1)), 1)[0][0] == ''
        assert problems(F('x', R(0)), 1) == [('', "unknown function 'x'")]
        assert problems(F('y', R(0)), 1, ('x',)) == [('', "unknown function 'y'")]

    def test_typed_slot_takes_them(self):
        for ast in (PAIR(N(1), N(2)), CALL(0, N(1)), F('x', R(0)), F('y', R(0)), F('abs', R(0))):
            assert problems(ast, 1, result='vec') == []
            assert problems(ast, 1, result='num') == []

    @pytest.mark.parametrize('ast, message', [
        ({'pair': [N(1)]}, 'pair takes 2 values'),
        ({'pair': [N(1), N(2), N(3)]}, 'pair takes 2 values'),
        ({'pair': N(1)}, 'pair takes 2 values'),
        ({'pair': [N(1), N(2)], 'num': 1}, 'a node must have exactly one of num, const, ref, op, fn, pair, call'),
        ({'call': 0, 'args': [N(1), N(2)]}, 'call takes 1 argument, not 2'),
        ({'call': 0, 'args': []}, 'call takes 1 argument, not 0'),
        ({'call': 0}, "a call node misses key 'args'"),
        ({'call': 0, 'args': [N(1)], 'x': 1}, "a call node does not allow key 'x'"),
        ({'call': 1.5, 'args': [N(1)]}, 'call must be an integer >= 0'),
        ({'call': 3, 'args': [N(1)]}, 'call 3 is outside refs (1 items)'),
        (F('x', R(0), R(0)), 'x takes 1 argument, not 2'),
        ({'if': [N(1), N(2), N(3)]}, "node 'if' is not in AST v1"),
        ({'var': 'x'}, "node 'var' is not in AST v1"),
    ])
    def test_shapes(self, ast, message):
        assert problems(ast, 1, result='vec') == [('', message)]

    def test_children_have_pointers(self):
        ast = PAIR(N(1), CALL(0, {'pair': []}))
        assert problems(ast, 1, result='vec') == [('/pair/1/args/0', 'pair takes 2 values')]

    def test_limits_are_the_same(self):
        deep = N(1)
        for _ in range(MAX_DEPTH):
            deep = PAIR(deep, N(0))
        assert problems(deep, 0, result='vec')[0][1] == f'deeper than {MAX_DEPTH} levels'
        wide = PAIR(N(1), N(1))
        for _ in range(7):                         # a balanced tree of 2^9 - 1 nodes, 9 levels
            wide = O('+', wide, wide)
        assert problems(wide, 0, result='vec') == [('', f'more than {MAX_NODES} nodes')]

    def test_vars_and_result_do_not_mix(self):
        with pytest.raises(ValueError):
            problems(N(1), 0, ('x',), result='num')


class TestTypes:
    @pytest.mark.parametrize('ast, operands, result', [
        (O('+', R(0), R(1)), (P, U), 'vec'),
        (O('-', R(0), R(1)), (P, Q), 'vec'),
        (O('*', R(0), R(1)), (K, U), 'vec'),
        (O('*', R(1), R(0)), (K, U), 'vec'),
        (O('/', R(0), N(2)), (U,), 'vec'),
        (O('*', R(0), R(1)), (U, P), 'num'),
        (O('neg', R(0)), (U,), 'vec'),
        (F('x', R(0)), (P,), 'num'),
        (F('y', O('-', R(0), R(1))), (P, Q), 'num'),
        (F('abs', R(0)), (U,), 'num'),
        (F('abs', R(0)), (K,), 'num'),
        (PAIR(R(0), O('*', N(2), PI)), (K,), 'vec'),
        (CALL(0, N(2)), (SQUARE,), 'num'),
        (PAIR(N(2), CALL(0, N(2))), (SQUARE,), 'vec'),
        (O('+', R(0), O('*', N(0.5), O('-', R(1), R(0)))), (P, Q), 'vec'),
        (F('sin', O('^', R(0), N(2))), (K,), 'num'),
        (F('max', F('x', R(0)), N(0)), (P,), 'num'),
    ])
    def test_well_typed(self, ast, operands, result):
        assert pointers(ast, operands, result) == []

    @pytest.mark.parametrize('ast, operands, result, where', [
        (O('+', R(0), N(1)), (P,), 'vec', ''),                    # GGB A + 1
        (O('-', N(1), R(0)), (U,), 'vec', ''),
        (O('/', N(1), R(0)), (U,), 'num', ''),
        (O('/', R(0), R(1)), (P, U), 'vec', ''),                  # complex division in GGB
        (O('^', R(0), N(2)), (U,), 'vec', ''),
        (O('^', N(2), R(0)), (U,), 'num', ''),
        (F('sin', R(0)), (P,), 'num', ''),
        (F('min', R(0), N(1)), (P,), 'num', ''),
        (F('x', N(1)), (), 'num', ''),
        (F('x', R(0)), (K,), 'num', ''),
        (PAIR(R(0), N(1)), (P,), 'vec', ''),
        (CALL(0, N(1)), (P,), 'num', ''),                          # a call of a point
        (CALL(0, R(1)), (SQUARE, P), 'num', ''),
        (R(0), (SQUARE,), 'num', ''),                              # a bare function
        (O('+', R(0), R(1)), (P, U), 'num', ''),                   # the root against the result
        (N(1), (), 'vec', ''),
        (O('+', R(0), O('*', R(1), N(1))), (P, SQUARE), 'vec', '/args/1/args/0'),
        (PAIR(N(1), O('+', R(0), N(1))), (U,), 'vec', '/pair/1'),
    ])
    def test_errors_point_at_their_node(self, ast, operands, result, where):
        assert pointers(ast, operands, result) == [where]

    def test_one_problem_per_mistake(self):
        # (A + 1)·2 in a vec slot: the sum is wrong; its product and the root are not reported again
        ast = O('*', O('+', R(0), N(1)), N(2))
        assert problems(ast, 1, (), ['point'], 'vec') == [('/args/0', 'type: vec + num')]

    def test_siblings_in_pre_order(self):
        ast = O('*', PAIR(R(0), N(1)), F('sin', R(0)))
        assert pointers(ast, (P,), 'vec') == ['/args/0', '/args/1']
        ast = PAIR(F('cos', R(0)), O('/', N(1), R(0)))
        assert pointers(ast, (P,), 'vec') == ['/pair/0', '/pair/1']

    def test_messages(self):
        assert problems(O('/', R(0), R(0)), 1, (), ['vector'], 'vec') == [('', 'type: vec / vec')]
        assert problems(F('sin', R(0)), 1, (), ['point'], 'num') == [('', 'type: sin(vec)')]
        assert problems(N(1), 0, (), [], 'vec') == [('', 'type: the formula gives num, the slot needs vec')]

    def test_without_operands_only_the_structure(self):
        assert problems(O('+', R(0), N(1)), 1, result='vec') == []
        assert problems(O('+', R(0), N(1)), 1, (), ['circle'], 'vec') == []
        assert problems(O('+', R(0), N(1)), None, (), ['point'], 'vec') == [('', 'type: vec + num')]

    def test_type_problems_without_a_result(self):
        assert type_problems(O('+', R(0), R(1)), ['point', 'vector']) == []
        assert type_problems(O('+', R(0), N(1)), ['point']) == [('', 'type: vec + num')]

    def test_type_pass_has_no_recursion(self):
        ast = R(0)
        for _ in range(MAX_DEPTH - 1):
            ast = O('neg', ast)
        assert problems(ast, 1, (), ['vector'], 'vec') == []
        assert type_problems(ast, ['vector'], 'num') == [('', 'type: the formula gives vec, the slot needs num')]


class TestEvaluate:
    def test_values(self):
        assert value(O('+', R(0), R(1)), (P, U), 'vec') == (4.0, 6.0)
        assert value(O('-', R(0), R(1)), (P, Q), 'vec') == (-3.0, 4.0)
        assert value(O('*', R(0), R(1)), (K, U), 'vec') == (6.0, 8.0)
        assert value(O('*', R(1), R(0)), (K, U), 'vec') == (6.0, 8.0)
        assert value(O('/', R(0), N(4)), (U,), 'vec') == (0.75, 1.0)
        assert value(O('*', R(0), R(1)), (U, P), 'num') == 11.0
        assert value(O('neg', R(0)), (U,), 'vec') == (-3.0, -4.0)
        assert value(F('x', R(0)), (P,), 'num') == 1.0
        assert value(F('y', R(0)), (U,), 'num') == 4.0
        assert value(F('abs', R(0)), (U,), 'num') == 5.0
        assert value(F('abs', R(0)), (('number', {'value': -2.0, 'unit': 'scalar'}),), 'num') == 2.0
        assert value(PAIR(R(0), N(3)), (K,), 'vec') == (2.0, 3.0)
        assert value(CALL(0, N(3)), (SQUARE,), 'num') == 9.0
        assert value(PAIR(N(2), CALL(0, N(2))), (SQUARE,), 'vec') == (2.0, 4.0)

    def test_affine_combination(self):
        t = ('number', {'value': 0.25, 'unit': 'scalar'})
        ast = O('+', O('*', R(0), R(1)), O('*', O('-', N(1), R(0)), R(2)))
        x, y = value(ast, (t, P, Q), 'vec')
        assert (x, y) == (0.25 * 1.0 + 0.75 * 4.0, 0.25 * 2.0 + 0.75 * -2.0)

    def test_degrees_are_radians(self):
        alpha = ('number', {'value': 0.5, 'unit': 'angle'})
        ast = O('+', R(0), O('*', N(30), O('/', PI, N(180))))
        assert value(ast, (alpha,), 'num') == 0.5 + 30 * (math.pi / 180)

    def test_division_by_zero(self):
        assert reason(O('/', R(0), N(0)), (U,), 'vec') == 'out_of_domain'
        assert reason(O('/', R(0), O('-', R(1), R(1))), (U, K), 'vec') == 'out_of_domain'

    def test_call_without_a_value(self):
        f = ('function', {'expr': O('*', {'var': 'x'}, {'var': 'x'}), 'refs': [], 'domain': [0.0, 1.0]})
        assert reason(CALL(0, N(2)), (f,), 'num') == 'out_of_domain'
        assert value(CALL(0, N(1)), (f,), 'num') == 1.0
        branch = ('function', {'expr': {'if': [{'cmp': '<', 'args': [{'var': 'x'}, N(0)]}, N(-1)]},
                               'refs': [], 'domain': [None, None]})
        assert value(CALL(0, N(-3)), (branch,), 'num') == -1.0
        assert reason(CALL(0, N(3)), (branch,), 'num') == 'out_of_domain'
        root = ('function', {'expr': F('sqrt', {'var': 'x'}), 'refs': [], 'domain': [None, None]})
        assert reason(PAIR(N(1), CALL(0, N(-1))), (root,), 'vec') == 'out_of_domain'

    def test_non_finite_by_component(self):
        big = ('point', {'x': 1e308, 'y': 1.0})
        assert reason(O('*', N(10), R(0)), (big,), 'vec') == 'non_finite'
        assert reason(O('+', R(0), R(0)), (big,), 'vec') == 'non_finite'
        assert reason(O('*', R(0), R(0)), (big,), 'num') == 'non_finite'
        tall = ('point', {'x': 1.0, 'y': 1e308})
        assert reason(O('*', R(0), N(10)), (tall,), 'vec') == 'non_finite'

    def test_x_before_y(self):
        assert reason(PAIR(F('sqrt', N(-1)), O('*', N(1e308), N(10))), (), 'vec') == 'out_of_domain'
        assert reason(PAIR(O('*', N(1e308), N(10)), F('sqrt', N(-1))), (), 'vec') == 'non_finite'

    def test_abs_of_large_components(self):
        huge = ('vector', {'a': [0.0, 0.0], 'b': [1e200, 1e200], 'length': math.hypot(1e200, 1e200)})
        assert value(F('abs', R(0)), (huge,), 'num') == math.hypot(1e200, 1e200)
        top = ('vector', {'a': [0.0, 0.0], 'b': [1.7e308, 1.7e308], 'length': math.inf})
        assert reason(F('abs', R(0)), (top,), 'num') == 'non_finite'

    def test_negative_zero(self):
        x, y = value(O('neg', PAIR(N(0), N(1))), (), 'vec')
        assert (x, y) == (0.0, -1.0) and math.copysign(1.0, x) == 1.0
        x, y = value(O('*', N(-1), PAIR(N(0), N(0))), (), 'vec')
        assert math.copysign(1.0, x) == 1.0 and math.copysign(1.0, y) == 1.0
        v = value(O('*', F('x', PAIR(N(0), N(0))), N(-1)), (), 'num')
        assert v == 0.0 and math.copysign(1.0, v) == 1.0

    def test_a_badly_typed_tree_is_formula(self):
        assert reason(O('+', R(0), N(1)), (P,), 'vec') == 'formula'
        assert reason(N(1), (), 'vec') == 'formula'
        assert reason(R(0), (('circle', {}),), 'vec') == 'formula'


class TestText:
    @pytest.mark.parametrize('ast, names, text', [
        (PAIR(N(1), N(2)), [], '(1, 2)'),
        (PAIR(R(0), O('+', R(0), N(4))), ['c_x'], '(c_x, c_x + 4)'),
        (CALL(0, N(1)), ['f'], 'f(1)'),
        (CALL(0, O('+', R(1), N(1))), ['f', 't'], 'f(t + 1)'),
        (CALL(2, N(1)), ['f'], 'refs[2](1)'),
        (F('x', R(0)), ['P'], 'x(P)'),
        (F('y', O('-', R(0), R(1))), ['A', 'B'], 'y(A - B)'),
        (F('abs', R(0)), ['u'], 'abs(u)'),
        (O('+', R(0), R(1)), ['M', 'v'], 'M + v'),
        (O('neg', R(0)), ['u'], '-u'),
        (O('neg', PAIR(N(1), N(2))), [], '-(1, 2)'),
        (O('*', N(2), PAIR(N(1), N(2))), [], '2·(1, 2)'),
        (O('^', CALL(0, N(2)), N(2)), ['f'], 'f(2)^2'),
        (O('/', O('-', R(0), R(1)), N(2)), ['A', 'B'], '(A - B)/2'),
        (O('+', O('*', R(0), R(1)), O('*', O('-', N(1), R(0)), R(2))), ['t', 'A', 'M'], 't·A + (1 - t)·M'),
    ])
    def test_text(self, ast, names, text):
        assert to_text(ast, names) == text
