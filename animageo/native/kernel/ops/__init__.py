"""Op implementations: ``@op("point.midpoint")`` pure functions.

An implementation takes ``(args, ctx)``: ``args`` maps each input slot to an
:class:`~animageo.native.kernel.values.Input` (a list of them for a list
slot); ``ctx`` is an :class:`OpContext`. It returns ``{slot: value}`` for every
output slot, a value being an encoded value or
:class:`~animageo.native.kernel.values.Undefined`.
"""
from __future__ import annotations

__all__ = ['IMPLEMENTATIONS', 'OpContext', 'op']

IMPLEMENTATIONS: dict = {}


def op(name: str):
    """Register the implementation of registry operation ``name``."""
    def register(fn):
        if name in IMPLEMENTATIONS:
            raise ValueError(f'operation {name!r} is implemented twice')
        IMPLEMENTATIONS[name] = fn
        return fn
    return register


class OpContext:
    """What an implementation sees besides its arguments.

    ``tol`` — :class:`~animageo.native.kernel.numeric.Tolerances` of the case;
    ``input`` — the input value of a free operation's element (else ``None``).
    ``decide(name, value, tol)`` reports a degeneracy decision: ``value`` is
    the decision value measured from the exact mathematical boundary (a
    length, a cross product, a segment parameter minus an end) and ``tol``
    the decide tolerance it is compared with. Evaluation ignores the reports;
    the fixture generator uses them to refuse near-degenerate cases.
    """

    __slots__ = ('tol', 'input', 'operation_id', 'decisions')

    def __init__(self, tol, *, input=None, operation_id=None, decisions=None):
        self.tol = tol
        self.input = input
        self.operation_id = operation_id
        self.decisions = decisions

    def decide(self, name: str, value: float, tol: float) -> None:
        if self.decisions is not None:
            self.decisions.append((self.operation_id, name, value, tol))


from . import angle, arc, circle, intersect, line, mark, measure, number, point, polygon, text, transform  # noqa: E402,F401,E501  (registration)
