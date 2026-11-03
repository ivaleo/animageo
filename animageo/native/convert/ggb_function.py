"""Safe source definitions of GeoGebra functions, independent of classic parsing."""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from .ggb_expr import ExprError, MAX_CHARS, _NAME, _Reader, _tokens


@dataclass
class FunctionSpec:
    """Source AST, ordered source labels and explicit literal domain only."""

    ast: dict
    refs: list
    domain: list = field(default_factory=lambda: [None, None])


class _FunctionReader(_Reader):
    def __init__(self, tokens, kinds, formal):
        super().__init__(tokens, kinds, variables=(formal,))
        self.in_condition = False

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
