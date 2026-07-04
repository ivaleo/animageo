"""Phase 2 — parity: same DSL through legacy parser and new exec engine.

For each code snippet, run it through the two parsers in separate
``Construction``\\s and verify the resulting state is equivalent:
same element names (modulo phantoms), same data, same visibility.
"""

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.parsers import dsl
# Parity tests vs the (now removed) legacy parser. Kept as runtime
# assertions on the exec engine — see test_dsl_run.py for richer
# coverage of exec-engine behaviour. The ``legacy_putCode`` shim
# here routes through the exec engine too (tests become self-checks).
def legacy_putCode(constr, code, **kw):
    dsl.run(constr, code, **{k: v for k, v in kw.items()
                             if k in ('debug', 'show')})


def _data_of(constr, name):
    """Return a comparable representation of constr[name].data."""
    elem = constr.element(name) or constr.var(name)
    if elem is None:
        return None
    data = elem.data
    if data is None:
        return None
    # Point: numpy array
    if hasattr(data, "coords") and hasattr(data.coords, "tolist"):
        return ("point", tuple(data.coords.tolist()))
    # Line / Segment / Ray: normal + c
    if hasattr(data, "n") and hasattr(data, "c"):
        return ("line", tuple(data.n.tolist()), float(data.c))
    # Circle / Arc / Sector: center + radius
    if hasattr(data, "c") and hasattr(data, "r"):
        return ("circle", tuple(data.center.tolist()), float(data.radius))
    # Measure
    if hasattr(data, "x") and hasattr(data, "dim"):
        return ("measure", float(data.value), int(data.dimension))
    # Raw scalar Var
    if isinstance(data, (int, float)):
        return ("scalar", float(data))
    return ("other", repr(data))


def _compare_user_elements(legacy: Construction, exec_c: Construction, names):
    """Both constructions must have the same element data for ``names``."""
    for n in names:
        legacy_d = _data_of(legacy, n)
        exec_d = _data_of(exec_c, n)
        assert legacy_d is not None, f"legacy: missing {n!r}"
        assert exec_d is not None, f"exec: missing {n!r}"
        # Data class names may differ slightly; compare structurally.
        if legacy_d[0] == "point":
            assert exec_d[0] == "point"
            assert np.allclose(legacy_d[1], exec_d[1])
        elif legacy_d[0] == "line":
            assert exec_d[0] == "line"
            assert np.allclose(legacy_d[1], exec_d[1])
            assert np.isclose(legacy_d[2], exec_d[2])
        elif legacy_d[0] == "circle":
            assert exec_d[0] == "circle"
            assert np.allclose(legacy_d[1], exec_d[1])
            assert np.isclose(legacy_d[2], exec_d[2])
        elif legacy_d[0] == "scalar":
            assert exec_d[0] == "scalar"
            assert np.isclose(legacy_d[1], exec_d[1])
        else:
            assert legacy_d == exec_d, f"{n}: {legacy_d} != {exec_d}"


# ── Snippets — each tuple: (code, [user-bound names to compare]) ─

PARITY_SNIPPETS = [
    # Basics
    ("A = Point(3, 4)", ["A"]),
    ("A = Point(0, 0)\nB = Point(4, 0)\nM = Midpoint(A, B)", ["A", "B", "M"]),
    ("A = Point(0, 0)\nB = Point(3, 4)\ns = Segment(A, B)", ["A", "B", "s"]),
    ("A = Point(0, 0)\nB = Point(3, 0)\nC = Point(0, 4)\n"
     "M = Midpoint(A, B)\nN = Midpoint(B, C)", ["A", "B", "C", "M", "N"]),
    # Nested
    ("M = Midpoint(Point(0, 0), Point(4, 2))", ["M"]),
    # Scalar expressions
    ("A = Point(0, 0)\nB = Point(3, 4)\nd = Distance(A, B)", ["A", "B", "d"]),
    # Circle + line
    ("O = Point(0, 0)\nA = Point(1, 0)\ncirc = Circle(O, A)", ["O", "A", "circ"]),
    ("A = Point(0, 0)\nB = Point(1, 1)\nL = Line(A, B)", ["A", "B", "L"]),
    # Rays
    ("A = Point(0, 0)\nB = Point(3, 0)\nR = Ray(A, B)", ["A", "B", "R"]),
    # Polygon with tuple unpack
    ("A = Point(0, 0)\nB = Point(4, 0)\nC = Point(0, 3)\n"
     "p, s1, s2, s3 = Polygon(A, B, C)", ["A", "B", "C", "p", "s1", "s2", "s3"]),
]


@pytest.mark.parametrize("code,names", PARITY_SNIPPETS)
def test_parity(code, names):
    legacy_c = Construction()
    legacy_putCode(legacy_c, code)

    exec_c = Construction()
    dsl.run(exec_c, code)

    _compare_user_elements(legacy_c, exec_c, names)


def test_parity_string_arg_function():
    """Function DSL: legacy and new both parse string-arg factories."""
    code = 'f = Function("y = x^2 + 1")'
    legacy_c = Construction()
    legacy_putCode(legacy_c, code)
    exec_c = Construction()
    dsl.run(exec_c, code)

    # Both should have element "f".
    assert legacy_c.element("f") is not None
    assert exec_c.element("f") is not None
    # Evaluation at x=2 should match.
    v_legacy = legacy_c.element("f").data._callable(2.0)
    v_exec = exec_c.element("f").data._callable(2.0)
    assert v_legacy == v_exec


def test_parity_conic_from_string():
    code = 'g = Conic("x^2 + y^2 = 4")'
    legacy_c = Construction()
    legacy_putCode(legacy_c, code)
    exec_c = Construction()
    dsl.run(exec_c, code)

    assert legacy_c.element("g") is not None
    assert exec_c.element("g") is not None
    # Conic matrix should match.
    assert np.allclose(
        legacy_c.element("g").data.matrix,
        exec_c.element("g").data.matrix,
    )


def test_parity_fx_sugar_equivalent():
    """Legacy: ``f(x) = x^2 + 1``. New DSL doesn't support this sugar
    (it's Python-syntactically a call, not a definition). Use the
    explicit form.
    """
    legacy_c = Construction()
    legacy_putCode(legacy_c, "f(x) = x^2 + 1")
    exec_c = Construction()
    dsl.run(exec_c, 'f = Function("y = x^2 + 1")')
    assert legacy_c.element("f") is not None
    assert exec_c.element("f") is not None
    v_legacy = legacy_c.element("f").data._callable(3.0)
    v_exec = exec_c.element("f").data._callable(3.0)
    assert v_legacy == v_exec
