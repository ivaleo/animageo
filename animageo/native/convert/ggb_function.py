"""Safe source definitions of GeoGebra functions, independent of classic parsing."""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import math
import re

from .ggb_expr import ExprError, MAX_CHARS, _NAME, _Reader, _tokens
from ..expr.validate import MAX_INTEGER_POWER


@dataclass
class FunctionSpec:
    """Source AST, ordered source labels and explicit literal domain only."""

    ast: dict
    refs: list
    domain: list = field(default_factory=lambda: [None, None])


class _BoundedReader(_Reader):
    """Function-only source guards; the legacy number reader stays unchanged."""

    def __init__(self, tokens, kinds, variables=()):
        super().__init__(tokens, kinds, variables=variables)
        # postfix() converts superscript integers to float before AST validation.
        # Check the integer first, including values too large for a finite float.
        if any(kind == 'sup' and abs(value) > MAX_INTEGER_POWER for kind, value in tokens):
            raise ExprError('formula_unsupported', 'superscript exceeds the integer power limit')

    def unary(self):
        # The base number reader's unary + does not contribute to AST depth.
        # Bound source recursion too, including long runs of redundant +.
        if self.is_op('+'):
            self.take()
            self.deeper()
            node = self.unary()
            self.depth -= 1
            return node
        return super().unary()

    def exponent(self):
        if self.is_op('+'):
            self.take()
            self.deeper()
            node = self.exponent()
            self.depth -= 1
            return node
        return super().exponent()


class _FunctionReader(_BoundedReader):
    def __init__(self, tokens, kinds, formal):
        super().__init__(tokens, kinds, variables=(formal,))
        self.in_condition = False

    def primary(self):
        if self.in_condition and self.is_op('('):
            self.take()
            self.deeper()
            node = self.condition_or()
            self.expect(')')
            self.depth -= 1
            return node
        return super().primary()

    def name(self, name):
        if name in self.variables:
            return {'var': 'x'}
        if name != 'If' or not self.is_op('(', '['):
            return super().name(name)
        close = ')' if self.take()[1] == '(' else ']'
        self.deeper()
        previous = self.in_condition
        self.in_condition = True
        cond = self.condition_or()
        self.in_condition = False
        self.expect(',')
        items = [cond, self.sum()]
        if self.is_op(','):
            self.take()
            items.append(self.sum())
        self.expect(close)
        self.in_condition = previous
        self.depth -= 1
        return {'if': items}

    def condition_or(self):
        node = self.condition_and()
        while self.is_op('||'):
            self.take()
            node = {'or': [node, self.condition_and()]}
        return node

    def condition_and(self):
        node = self.condition_not()
        while self.is_op('&&'):
            self.take()
            node = {'and': [node, self.condition_not()]}
        return node

    def condition_not(self):
        if self.is_op('!'):
            self.take()
            self.deeper()
            node = {'not': [self.condition_not()]}
            self.depth -= 1
            return node
        left = self.sum()
        node = None
        while self.is_op('<', '<=', '>', '>='):
            sign = self.take()[1]
            right = self.sum()
            comparison = {'cmp': sign, 'args': [left, right]}
            node = comparison if node is None else {'and': [node, comparison]}
            left = right
        return left if node is None else node


_HEADER = re.compile(r'^\s*(.*?)\s*\(([^()]*)\)\s*=(?!=)(.*)$', re.DOTALL)
_Y_HEADER = re.compile(r'^\s*y\s*=(?!=)(.*)$', re.DOTALL)


def parse_function(text, kinds, *, label) -> FunctionSpec:
    """Read a bare body, matching ``f(x)=``/``f(t)=``, or ``y=`` graph.

    If and comparisons are opt-in here; parse_number retains its language.
    Only variable nodes normalize to x. Source object names remain unchanged.
    Parsing never evaluates the function or executes source text.
    """
    from ..expr.validate import problems

    text = str(text)
    if len(text) > MAX_CHARS:
        raise ExprError('formula_unsupported', 'function definition exceeds expression limits')
    formal = 'x'
    header = _HEADER.match(text)
    if header:
        name, formal, text = (p.strip() for p in header.groups())
        if name != label or not _NAME.fullmatch(formal):
            raise ExprError('formula_unsupported', 'function header must match its source label and one variable')
    else:
        header = _Y_HEADER.match(text)
        if header:
            text = header.group(1)
    reader = _FunctionReader(_tokens(text, conditions=True), kinds, formal)
    ast = reader.read()
    if problems(ast, len(reader.labels), vars=('x',)):
        raise ExprError('formula_unsupported', 'function exceeds expression limits or condition grammar')
    return FunctionSpec(ast, reader.labels)


def source_ref_names(spec, ctx):
    """Translate source labels by identity, never by their current values."""
    normalized = {source: name for name, source in ctx.display.items()}
    return [normalized.get(source, source) for source in spec.refs]


def source_ref_values(spec, ctx):
    """Original XML numbers, independently of emitted or evaluated operations."""
    out = []
    for name in source_ref_names(spec, ctx):
        expected = ctx.expected.get(name)
        if not expected or expected.get('kind') not in ('number', 'angle'):
            return None
        value = expected.get('value')
        if not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value):
            return None
        out.append(float(value))
    return out


def source_report_value(spec, ctx):
    values = source_ref_values(spec, ctx)
    if values is None:
        return None
    return {'kind': 'function', 'value': {'expr': copy.deepcopy(spec.ast), 'refs': values,
                                         'domain': list(spec.domain)}}


def _parse_domain(text, kinds):
    """The number-expression language with bounded source recursion/conversion."""
    from ..expr.validate import problems

    text = str(text)
    if len(text) > MAX_CHARS:
        raise ExprError('formula_unsupported', 'function domain exceeds expression limits')
    reader = _BoundedReader(_tokens(text), kinds)
    ast = reader.read()
    if problems(ast, len(reader.labels)):
        raise ExprError('formula_unsupported', 'function domain exceeds expression limits')
    return ast, reader.labels


def read_functions(infos, norm, ctx) -> None:
    """Read source definitions even when classic parsing made no object."""
    from ..expr import evaluate
    from ..expr.evaluate import ExprError as EvaluationError

    kinds = {info['label']: info['type'] for info in infos}
    for info in infos:
        if info['type'] != 'function':
            continue
        name = norm[info['label']]
        forced = ctx.forced.get(name)
        if forced and forced[0] not in ('parse_error', 'unsupported_signature', 'no_registry_op'):
            continue
        command, inputs = info.get('command'), info.get('inputs', [])
        if command not in ('Expression', 'Function'):
            continue
        try:
            if command == 'Expression' and len(inputs) == 1:
                spec = parse_function(inputs[0], kinds, label=info['label'])
            elif command == 'Function' and len(inputs) == 3:
                if inputs[0].strip() in kinds:
                    raise ExprError('formula_unsupported', 'Function of a source object is not an inline definition')
                spec = parse_function(inputs[0], kinds, label=info['label'])
                domain = []
                for text in inputs[1:]:
                    ast, refs = _parse_domain(text, kinds)
                    if refs:
                        raise ExprError('unsupported_signature', 'function domain depends on source objects')
                    domain.append(evaluate(ast))
                spec.domain = domain
            else:
                raise ExprError('unsupported_signature', 'unsupported source function definition')
        except (ExprError, EvaluationError) as exc:
            reason = exc.reason if isinstance(exc, ExprError) else 'formula_unsupported'
            ctx.forced[name] = (reason, str(exc))
            continue
        ctx.forced.pop(name, None)
        ctx.functions[name] = spec
        expected = source_report_value(spec, ctx)
        if expected is not None:
            ctx.expected[name] = expected
    _read_graph_points(infos, norm, ctx)


def _read_graph_points(infos, norm, ctx):
    """Only XML Point(f): saved x is its free input, saved y is a check.

    A domain clamps x and a piecewise ``If`` has no value in its gaps, in
    GeoGebra as in ``point.on_function`` (registry 1.9): the saved point
    checks the branch it is on."""
    for info in infos:
        inputs = info.get('inputs', [])
        if info['type'] != 'point' or info.get('command') != 'Point' or len(inputs) != 1:
            continue
        function = norm.get(inputs[0])
        spec = ctx.functions.get(function)
        if spec is None:
            continue
        name = norm[info['label']]
        forced = ctx.forced.get(name)
        if forced and forced[0] not in ('parse_error', 'unsupported_signature', 'no_registry_op'):
            continue
        coords = info.get('coords') or {}
        x, z = coords.get('x'), coords.get('z')
        if x is None or z is None or not math.isfinite(x) or not math.isfinite(z) or z == 0:
            ctx.forced[name] = ('unsupported_signature', 'нет конечной исходной абсциссы свободной точки графика')
            continue
        x = x / z
        if not math.isfinite(x):
            ctx.forced[name] = ('unsupported_signature', 'нет конечной исходной абсциссы свободной точки графика')
            continue
        ctx.forced.pop(name, None)
        ctx.function_points[name] = function, x


def verify_function(spec, native_value, actual_ref_ids, expected_ref_ids, expected_ref_values, scale):
    """Verify the definition and bindings against source, not successful evaluation.

    Structure, variable normalization, ordered object IDs and domain must match
    exactly. Ref values use the existing import comparison, with no new tolerance.
    Missing independent source evidence leaves the definition unchecked.
    """
    from .values import compare

    if spec is None or expected_ref_ids is None or expected_ref_values is None:
        return 'not_checked', None
    if len(expected_ref_ids) != len(spec.refs) or len(expected_ref_values) != len(spec.refs) or any(
            value is None or not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) for value in expected_ref_values):
        return 'not_checked', None
    if not isinstance(native_value, dict) or actual_ref_ids != expected_ref_ids:
        return 'failed', None
    if native_value.get('expr') != spec.ast or native_value.get('domain') != list(spec.domain):
        return 'failed', None
    actual = native_value.get('refs')
    if not isinstance(actual, list) or len(actual) != len(expected_ref_values):
        return 'failed', None
    delta = 0.0
    for expected, value in zip(expected_ref_values, actual):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            return 'failed', None
        status, difference = compare({'kind': 'number', 'value': expected},
                                     {'kind': 'number', 'value': value}, scale)
        if status != 'passed':
            return status, difference
        delta = max(delta, difference)
    return 'passed', delta
