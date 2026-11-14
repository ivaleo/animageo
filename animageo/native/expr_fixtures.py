"""Parity fixtures of typed expressions (registry 1.10, docs/native/expr.md §6).

``python -m animageo.native fixtures expr [--check]`` writes (or checks)
``parity/v1/expr/typed.json`` in the format ``animageo-expr-cases/v1``:

    {format, registry, generatedBy, tolerance, cases: [
        {name, ast, operands: [{name, type, value}], result,
         expect: {value, text, exact} | {reason} | {problems: [pointer]}}]}

``operands`` are the items of ``refs`` (``name`` — the name ``text`` prints
for them); ``value`` is a number for ``result: "num"`` and ``[x, y]`` for
``"vec"``. ``exact: true`` — the value is bit-exact in both kernels (the
arithmetic, ``sqrt``, the integer power, ``pair``, ``x``, ``y``, the dot
product); otherwise a component may differ by ``tolerance · max(1, |v|)``
(``hypot``, the libm functions, ``call``). A case with ``problems`` lists
the pointers of :func:`~animageo.native.expr.problems` with the operand
types and the result (messages are not compared); a case with ``reason``
is the reason of :class:`~animageo.native.expr.ExprError`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from ._fixture_registry import BASELINE_VERSION as FIXTURE_REGISTRY_VERSION

__all__ = ['DEFAULT_DIR', 'EXPR_CASES_FORMAT', 'TOLERANCE', 'build_fixtures', 'case_expect', 'check_fixtures',
           'verify_fixture', 'verify_fixtures', 'write_fixtures']

DEFAULT_DIR = Path(__file__).resolve().parent / 'parity' / 'v1' / 'expr'
EXPR_CASES_FORMAT = 'animageo-expr-cases/v1'
TOLERANCE = 1e-9            # tol.parity of a scalar at scale 1 (_numeric.json), relative above 1

X = {'var': 'x'}
PI = {'const': 'pi'}


def N(v):
    return {'num': v}


def R(k):
    return {'ref': k}


def O(name, *args):
    return {'op': name, 'args': list(args)}


def F(name, *args):
    return {'fn': name, 'args': list(args)}


def PAIR(a, b):
    return {'pair': [a, b]}


def CALL(k, a):
    return {'call': k, 'args': [a]}


def DEG(v):
    """``v°`` as the writers of 1.10 write it: ``v·(pi/180)``."""
    return O('*', N(v), O('/', PI, N(180)))


# operands: (name, type, value)
A = ('A', 'point', {'x': 1.0, 'y': 2.0})
B = ('B', 'point', {'x': 4.0, 'y': -2.0})
M = ('M', 'point', {'x': -0.5, 'y': 0.25})
U = ('u', 'vector', {'a': [1.0, 1.0], 'b': [4.0, 5.0], 'length': 5.0})
V = ('v', 'vector', {'a': [0.0, 0.0], 'b': [-2.0, 1.0], 'length': math.hypot(-2.0, 1.0)})
K = ('k', 'number', {'value': 2.0, 'unit': 'scalar'})
T = ('t', 'number', {'value': 0.25, 'unit': 'scalar'})
ZERO = ('z', 'number', {'value': 0.0, 'unit': 'scalar'})
ALPHA = ('α', 'number', {'value': 0.5, 'unit': 'angle'})
CX = ('c_x', 'number', {'value': -1.5, 'unit': 'length'})
SQUARE = ('f', 'function', {'expr': O('*', X, X), 'refs': [], 'domain': [None, None]})
UNIT_SQUARE = ('g', 'function', {'expr': O('*', X, X), 'refs': [], 'domain': [0.0, 1.0]})
STEP = ('h', 'function', {'expr': {'if': [{'cmp': '<', 'args': [X, N(0)]}, N(-1)]}, 'refs': [],
                          'domain': [None, None]})
SINE = ('s', 'function', {'expr': F('sin', X), 'refs': [], 'domain': [None, None]})
ROOT = ('r', 'function', {'expr': F('sqrt', X), 'refs': [], 'domain': [None, None]})
SCALED = ('p', 'function', {'expr': O('*', {'ref': 0}, X), 'refs': [3.0], 'domain': [None, None]})
BIG = ('W', 'point', {'x': 1e308, 'y': 1.0})
HUGE = ('w', 'vector', {'a': [0.0, 0.0], 'b': [1e200, 1e200], 'length': math.hypot(1e200, 1e200)})
FAR = ('Q', 'point', {'x': 1.7e308, 'y': 1.7e308})
ON_Y = ('O', 'point', {'x': 0.0, 'y': 3.0})

_INEXACT_FNS = {'sin', 'cos', 'tan', 'atan', 'asin', 'acos', 'exp', 'ln', 'lg'}


def _deep(depth):
    """``-(-(…(1, 0)))`` whose numbers stand at ``depth`` (the root at depth 1)."""
    ast = PAIR(N(1), N(0))
    for _ in range(depth - 2):
        ast = O('neg', ast)
    return ast


def _wide():
    ast = PAIR(N(1), N(1))
    for _ in range(7):                          # 2^9 - 1 nodes
        ast = O('+', ast, ast)
    return ast


def _cases():
    """``[(name, ast, operands, result)]`` — every row of the typing table,
    every type error with its pointer, the limits, ``−0``, overflow, ``/0``,
    ``call`` outside its domain and in a branch of ``If``, ``abs`` of large
    components."""
    return [
        # values: every node and overload
        ('point_plus_vector', O('+', R(0), R(1)), [A, U], 'vec'),
        ('point_minus_vector', O('-', R(0), R(1)), [A, U], 'vec'),
        ('point_minus_point', O('-', R(0), R(1)), [B, A], 'vec'),
        ('point_plus_point', O('+', R(0), R(1)), [A, B], 'vec'),
        ('vector_plus_vector', O('+', R(0), R(1)), [U, V], 'vec'),
        ('number_times_vector', O('*', R(0), R(1)), [K, U], 'vec'),
        ('vector_times_number', O('*', R(0), R(1)), [U, K], 'vec'),
        ('literal_times_point', O('*', N(0.5), R(0)), [B], 'vec'),
        ('vector_over_number', O('/', R(0), N(4)), [U], 'vec'),
        ('point_over_number', O('/', R(0), R(1)), [A, K], 'vec'),
        ('dot_product', O('*', R(0), R(1)), [U, V], 'num'),
        ('dot_point_vector', O('*', R(0), R(1)), [A, U], 'num'),
        ('neg_vector', O('neg', R(0)), [U], 'vec'),
        ('neg_pair', O('neg', PAIR(N(1), N(2))), [], 'vec'),
        ('x_of_point', F('x', R(0)), [A], 'num'),
        ('y_of_point', F('y', R(0)), [B], 'num'),
        ('x_of_vector', F('x', R(0)), [U], 'num'),
        ('y_of_difference', F('y', O('-', R(0), R(1))), [A, B], 'num'),
        ('abs_of_vector', F('abs', R(0)), [U], 'num'),
        ('abs_of_difference', F('abs', O('-', R(0), R(1))), [B, A], 'num'),
        ('abs_of_number', F('abs', O('-', N(1), R(0))), [K], 'num'),
        ('pair_literal', PAIR(N(2), N(3)), [], 'vec'),
        ('pair_of_numbers', PAIR(R(0), N(4)), [CX], 'vec'),
        ('pair_of_coordinates', PAIR(F('y', R(0)), F('x', R(0))), [A], 'vec'),
        ('pair_plus_point', O('+', PAIR(N(1), N(-1)), R(0)), [A], 'vec'),
        ('call_value', CALL(0, N(3)), [SQUARE], 'num'),
        ('call_in_pair', PAIR(N(2), CALL(0, N(2))), [SQUARE], 'vec'),
        ('call_of_coordinate', PAIR(F('x', R(1)), CALL(0, F('x', R(1)))), [SQUARE, A], 'vec'),
        ('call_with_refs', CALL(0, O('+', R(1), N(1))), [SCALED, T], 'num'),
        ('call_libm', PAIR(R(1), CALL(0, R(1))), [SINE, ALPHA], 'vec'),
        ('call_power', O('^', CALL(0, N(2)), N(2)), [SQUARE], 'num'),
        ('call_branch', CALL(0, N(-3)), [STEP], 'num'),
        ('affine_combination', O('+', O('*', R(0), R(1)), O('*', O('-', N(1), R(0)), R(2))), [T, A, B], 'vec'),
        ('midpoint_formula', O('/', O('+', R(0), R(1)), N(2)), [A, B], 'vec'),
        ('point_and_twice_vector', O('+', R(0), O('*', N(2), O('-', R(1), R(0)))), [A, B], 'vec'),
        ('rotated_by_degrees', PAIR(F('cos', O('+', R(0), DEG(30))), F('sin', O('+', R(0), DEG(30)))),
         [ALPHA], 'vec'),
        ('scaled_angle', O('*', N(4), O('-', R(0), DEG(90))), [ALPHA], 'num'),
        ('number_slot_with_pi', O('*', N(2), PI), [], 'num'),
        ('sqrt_component', PAIR(F('sqrt', F('x', R(0))), N(0)), [B], 'vec'),
        ('integer_power_of_component', O('^', F('x', R(0)), N(3)), [U], 'num'),
        ('min_max_of_components', PAIR(F('min', F('x', R(0)), F('y', R(0))), F('max', F('x', R(0)), F('y', R(0)))),
         [B], 'vec'),
        ('nested_refs', O('-', O('*', F('abs', R(0)), R(1)), R(2)), [U, V, M], 'vec'),
        # −0
        ('negative_zero_x', O('neg', PAIR(N(0), N(1))), [], 'vec'),
        ('negative_zero_both', O('*', N(-1), PAIR(N(0), N(0))), [], 'vec'),
        ('negative_zero_num', O('*', F('x', R(0)), N(-1)), [ON_Y], 'num'),
        ('negative_zero_divided', O('/', PAIR(N(0), N(-0.0)), N(-2)), [], 'vec'),
        # reasons
        ('divide_vector_by_zero', O('/', R(0), N(0)), [U], 'vec'),
        ('divide_by_zero_number', O('/', R(0), R(1)), [A, ZERO], 'vec'),
        ('sqrt_of_negative_component', PAIR(F('sqrt', F('y', R(0))), N(0)), [B], 'vec'),
        ('call_outside_domain', CALL(0, N(2)), [UNIT_SQUARE], 'num'),
        ('call_inside_domain', CALL(0, N(0.5)), [UNIT_SQUARE], 'num'),
        ('call_branch_without_value', CALL(0, N(3)), [STEP], 'num'),
        ('call_root_of_negative', PAIR(N(1), CALL(0, N(-1))), [ROOT], 'vec'),
        ('call_overflow', CALL(0, N(1e200)), [SQUARE], 'num'),
        ('overflow_x', O('*', N(10), R(0)), [BIG], 'vec'),
        ('overflow_sum', O('+', R(0), R(0)), [BIG], 'vec'),
        ('overflow_dot', O('*', R(0), R(0)), [BIG], 'num'),
        ('x_before_y_domain', PAIR(F('sqrt', N(-1)), O('*', N(1e308), N(10))), [], 'vec'),
        ('x_before_y_overflow', PAIR(O('*', N(1e308), N(10)), F('sqrt', N(-1))), [], 'vec'),
        ('abs_of_large_components', F('abs', R(0)), [HUGE], 'num'),
        ('abs_overflow', F('abs', R(0)), [FAR], 'num'),
        ('vector_components_overflow', O('-', R(0), R(1)),
         [('E', 'point', {'x': 1e308, 'y': 0.0}), ('G', 'point', {'x': -1e308, 'y': 0.0})], 'vec'),
        # type errors (pointers)
        ('point_plus_number', O('+', R(0), N(1)), [A], 'vec'),
        ('number_minus_vector', O('-', N(1), R(0)), [U], 'vec'),
        ('number_over_vector', O('/', N(1), R(0)), [U], 'num'),
        ('vector_over_vector', O('/', R(0), R(1)), [U, V], 'vec'),
        ('vector_power', O('^', R(0), N(2)), [U], 'vec'),
        ('number_to_vector_power', O('^', N(2), R(0)), [U], 'num'),
        ('sin_of_point', F('sin', R(0)), [A], 'num'),
        ('min_of_point', F('min', R(0), N(1)), [A], 'num'),
        ('x_of_number', F('x', R(0)), [K], 'num'),
        ('pair_of_vector', PAIR(R(0), N(1)), [A], 'vec'),
        ('call_of_point', CALL(0, N(1)), [A], 'num'),
        ('call_of_vector_argument', CALL(0, R(1)), [SQUARE, A], 'num'),
        ('bare_function', R(0), [SQUARE], 'num'),
        ('bare_function_in_sum', O('+', R(0), N(1)), [SQUARE], 'num'),
        ('root_gives_vec_for_num', O('+', R(0), R(1)), [A, U], 'num'),
        ('root_gives_num_for_vec', O('*', R(0), R(1)), [U, V], 'vec'),
        ('literal_for_vec', N(1), [], 'vec'),
        ('nested_mistake_once', O('*', O('+', R(0), N(1)), N(2)), [A], 'vec'),
        ('deep_mistake', O('+', R(0), O('*', R(1), N(1))), [A, SQUARE], 'vec'),
        ('two_mistakes_in_pre_order', O('*', PAIR(R(0), N(1)), F('sin', R(0))), [A], 'vec'),
        ('mistakes_in_pair', PAIR(F('cos', R(0)), O('/', N(1), R(0))), [A], 'vec'),
        # structure and limits
        ('call_with_two_arguments', {'call': 0, 'args': [N(1), N(2)]}, [SQUARE], 'num'),
        ('call_outside_refs', CALL(3, N(1)), [SQUARE], 'num'),
        ('pair_of_three', {'pair': [N(1), N(2), N(3)]}, [], 'vec'),
        ('pair_with_extra_key', {'pair': [N(1), N(2)], 'num': 1}, [], 'vec'),
        ('condition_in_typed_slot', {'if': [{'cmp': '<', 'args': [N(0), N(1)]}, PAIR(N(1), N(1))]}, [], 'vec'),
        ('deeper_than_32', _deep(33), [], 'vec'),
        ('depth_32', _deep(32), [], 'vec'),
        ('more_than_256_nodes', _wide(), [], 'vec'),
        ('power_above_64', O('*', O('^', R(0), N(65)), R(1)), [K, U], 'vec'),
        ('power_64', O('*', O('^', R(0), N(-64)), R(1)), [K, U], 'vec'),
    ]


def _exact(ast) -> bool:
    """Whether the value of a valid typed tree is bit-exact in both kernels."""
    stack = [ast]
    while stack:
        node = stack.pop()
        if 'call' in node:
            return False
        if 'fn' in node and node['fn'] in _INEXACT_FNS:
            return False
        if 'op' in node and node['op'] == '^' and not ('num' in node['args'][1]
                                                        and float(node['args'][1]['num']).is_integer()):
            return False
        stack.extend(node.get('args') or ())
        stack.extend(node.get('pair') or ())
    return True


def _is_vec(node, types) -> bool:
    """Whether a node of a valid typed tree is a pair (the trees of the cases are shallow)."""
    from .expr import OPERAND_TYPES
    if 'pair' in node:
        return True
    if 'ref' in node:
        return OPERAND_TYPES[types[int(node['ref'])]] == 'vec'
    if 'op' in node:
        args = node['args']
        if node['op'] == '*':
            return _is_vec(args[0], types) != _is_vec(args[1], types)
        return node['op'] != '^' and _is_vec(args[0], types)
    return False


def _abs_of_pair(ast, types) -> bool:
    """Whether the tree takes ``abs`` of a pair (``hypot``: within the tolerance)."""
    stack = [ast]
    while stack:
        node = stack.pop()
        if node.get('fn') == 'abs' and _is_vec(node['args'][0], types):
            return True
        stack.extend(node.get('args') or ())
        stack.extend(node.get('pair') or ())
    return False


def case_expect(ast, operands, result) -> dict:
    """The ``expect`` of a case by this library."""
    from .expr import ExprError, evaluate_typed, problems, to_text
    types = [item['type'] for item in operands]
    found = problems(ast, len(types), (), types, result)
    if found:
        return {'problems': [pointer for pointer, _message in found]}
    try:
        value = evaluate_typed(ast, [(item['type'], item['value']) for item in operands], result)
    except ExprError as exc:
        return {'reason': exc.reason}
    exact = _exact(ast) and not _abs_of_pair(ast, types)
    return {'value': list(value) if isinstance(value, tuple) else value,
            'text': to_text(ast, [item['name'] for item in operands]), 'exact': exact}


def build_fixtures() -> dict:
    """``{file name: fixture}``."""
    from .. import __version__
    cases = []
    for name, ast, operands, result in _cases():
        items = [{'name': n, 'type': t, 'value': v} for n, t, v in operands]
        cases.append({'name': name, 'ast': ast, 'operands': items, 'result': result,
                      'expect': case_expect(ast, items, result)})
    fixture = {'format': EXPR_CASES_FORMAT, 'registry': FIXTURE_REGISTRY_VERSION, 'generatedBy': f'animageo {__version__}',
               'tolerance': TOLERANCE, 'cases': cases}
    return {'typed.json': json.loads(json.dumps(fixture))}


def _dump(fixture) -> str:
    return json.dumps(fixture, ensure_ascii=False, indent=1) + '\n'


def write_fixtures(directory=DEFAULT_DIR) -> list:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fixture in sorted(build_fixtures().items()):
        path = directory / name
        path.write_text(_dump(fixture), encoding='utf-8')
        written.append(path)
    return written


def _unlabelled(fixture: dict) -> dict:
    out = dict(fixture)
    out.pop('generatedBy', None)
    return out


def check_fixtures(directory=DEFAULT_DIR) -> list:
    """Files that differ from a fresh build (the version label aside; real
    numbers within the libm comparison of ``_fixture_compare``)."""
    from ._fixture_compare import same_fixture
    directory = Path(directory)
    problems = []
    built = build_fixtures()
    for name, fixture in sorted(built.items()):
        path = directory / name
        if not path.exists():
            problems.append(f'{path}: missing')
            continue
        if not same_fixture(_unlabelled(json.loads(path.read_text(encoding='utf-8'))), _unlabelled(fixture)):
            problems.append(f'{path}: out of date')
    for path in sorted(directory.glob('*.json')):
        if path.name not in built:
            problems.append(f'{path}: not built here')
    return problems


def _same_number(want, have, exact, tol) -> bool:
    if exact:
        return want == have and math.copysign(1.0, want) == math.copysign(1.0, have)
    return abs(want - have) <= tol * max(1.0, abs(want))


def verify_fixture(fixture: dict, label: str = '') -> list:
    """Mismatches between the cases of a fixture and this library."""
    label = label or 'typed'
    if fixture.get('format') != EXPR_CASES_FORMAT:
        return [f'{label}: not {EXPR_CASES_FORMAT}']
    tol = float(fixture.get('tolerance', TOLERANCE))
    out = []
    for case in fixture['cases']:
        where = f"{label} [{case['name']}]"
        want = case['expect']
        have = case_expect(case['ast'], case['operands'], case['result'])
        if set(want) != set(have):
            out.append(f'{where}: expected {want!r}, got {have!r}')
            continue
        if 'value' not in want:
            if want != have:
                out.append(f'{where}: expected {want!r}, got {have!r}')
            continue
        if want['text'] != have['text'] or want['exact'] != have['exact']:
            out.append(f"{where}: expected text {want['text']!r}, got {have['text']!r}")
            continue
        a = want['value'] if isinstance(want['value'], list) else [want['value']]
        b = have['value'] if isinstance(have['value'], list) else [have['value']]
        if len(a) != len(b) or not all(_same_number(x, y, want['exact'], tol) for x, y in zip(a, b)):
            out.append(f"{where} value: expected {want['value']!r}, got {have['value']!r}")
    return out


def verify_fixtures(directory=DEFAULT_DIR) -> tuple:
    """``(files, cases, mismatches)`` of the fixtures in ``directory``."""
    directory = Path(directory)
    files = cases = 0
    mismatches = []
    for path in sorted(directory.glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        files += 1
        cases += len(fixture['cases'])
        mismatches.extend(verify_fixture(fixture, path.name))
    return files, cases, mismatches
