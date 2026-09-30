"""Tests for PR 7 — Piecewise parsing + asymptote-aware rendering.

Covers:
- ``If[cond, then]`` / ``If[cond, then, else]`` / nested If.
- Unicode comparators ``≤``, ``≥``.
- Piecewise evaluation returns NaN outside condition.
- 1/x renders as two separate polylines (split at x=0 singularity).
- tan(x) rendering terminates (no hang at asymptotes).
- ``func5.ggb``'s function ``m(x) = If[-1 ≤ x ≤ 1, x²]`` loads.
"""
import logging
import os

import numpy as np
import pytest

from animageo.geo.lib_function import (
    Function, _translate_if_to_piecewise, _split_top_level_commas,
    parse_function_expression,
)
from animageo.geo.lib_elements import Element


# ── Helpers ──────────────────────────────────────────────────────────

class TestSplitTopCommas:
    def test_flat(self):
        assert _split_top_level_commas("a, b, c") == ["a", " b", " c"]

    def test_nested_brackets(self):
        assert _split_top_level_commas("[a,b], c") == ["[a,b]", " c"]

    def test_nested_parens(self):
        assert _split_top_level_commas("f(a,b), g") == ["f(a,b)", " g"]


# ── If → Piecewise translation ──────────────────────────────────────

class TestTranslateIf:
    def test_two_arg(self):
        r = _translate_if_to_piecewise("If[x > 0, x**2]")
        assert 'Piecewise' in r and 'x**2' in r and 'x > 0' in r

    def test_three_arg(self):
        r = _translate_if_to_piecewise("If[x > 0, x, -x]")
        assert 'Piecewise' in r
        assert '(x, x > 0)' in r
        assert '(-x, True)' in r

    def test_parenthesis_form_from_xml_converter(self):
        r = _translate_if_to_piecewise("If(-1 <= x <= 1, x**(2))")
        assert 'Piecewise' in r and 'x**(2)' in r

    def test_nested(self):
        r = _translate_if_to_piecewise("If[x > 0, If[x < 10, x, 10], 0]")
        assert r.count('Piecewise') == 2

    def test_non_if_unchanged(self):
        s = "x**2 + sin(x)"
        assert _translate_if_to_piecewise(s) == s

    def test_boundary_word(self):
        # "if" inside an identifier should not trigger.
        s = "midpoint + 5"
        assert _translate_if_to_piecewise(s) == s


# ── Parsing + evaluation ─────────────────────────────────────────────

class TestPiecewiseParse:
    def test_basic_piecewise(self):
        f = Function.from_string('y = If[-1 <= x <= 1, x**2]')
        # Inside condition.
        assert f(0) == pytest.approx(0.0)
        assert f(0.5) == pytest.approx(0.25)
        assert f(-1) == pytest.approx(1.0)
        assert f(1) == pytest.approx(1.0)
        # Outside — NaN.
        assert np.isnan(f(2.0))
        assert np.isnan(f(-2.0))

    def test_if_else(self):
        f = Function.from_string('y = If[x >= 0, x, -x]')
        # Absolute value.
        assert f(3) == pytest.approx(3.0)
        assert f(-3) == pytest.approx(3.0)

    def test_unicode_comparators(self):
        # GGB writes ≤ and ≥ directly.
        f = Function.from_string('y = If[-1 ≤ x ≤ 1, x**2]')
        assert f(0.5) == pytest.approx(0.25)
        assert np.isnan(f(2))

    def test_ggb_style_m(self):
        # Exact form from func5.ggb.
        f = Function.from_string('m(x) = If[-1 ≤ x ≤ 1, x^(2)]')
        assert f(0) == pytest.approx(0.0)
        assert f(1) == pytest.approx(1.0)
        assert np.isnan(f(5))

    def test_if_parenthesis_form(self):
        f = Function.from_string('m(x) = If(-1 <= x <= 1, x**(2))')
        assert f(0.5) == pytest.approx(0.25)
        assert np.isnan(f(2))


# ── Asymptote rendering ───────────────────────────────────────────────

class TestAsymptotes:
    @pytest.fixture
    def scene(self, caplog):
        from animageo.animageo import AnimaGeoScene
        caplog.set_level(logging.WARNING, logger='animageo.animageo')
        s = AnimaGeoScene()
        s.camera.frame.set(width=10)
        return s

    def test_one_over_x_splits(self, scene, caplog):
        # y = 1/x has asymptote at x=0 → two polylines, one each side.
        f = Function.from_string('y = 1/x')
        # Singularities should include 0.
        assert any(abs(s) < 1e-9 for s in f.natural_singularities)

        elem = Element('h', f)
        mobj = scene.CreateMObject(elem, z_auto=True)
        assert mobj is not None
        # Expect at least 2 disjoint polylines.
        assert len(mobj.submobjects) >= 2
        assert len(caplog.records) == 0

    def test_log_renders(self, scene, caplog):
        # y = log(x) defined only for x > 0.
        f = Function.from_string('y = log(x)')
        elem = Element('l', f)
        mobj = scene.CreateMObject(elem, z_auto=True)
        # Either renders a right-half polyline or returns None — must not crash.
        assert len(caplog.records) == 0

    def test_piecewise_renders(self, scene, caplog):
        # Bounded piecewise from func5.
        f = Function.from_string('m(x) = If[-1 ≤ x ≤ 1, x^(2)]')
        elem = Element('m', f)
        mobj = scene.CreateMObject(elem, z_auto=True)
        assert mobj is not None
        assert len(mobj.submobjects) >= 1
        assert len(caplog.records) == 0


# ── func5.ggb fixture: function m ────────────────────────────────────

FUNC5 = os.path.join(
    os.path.dirname(__file__), '..', 'examples', 'func', 'func5.ggb',
)


@pytest.mark.skipif(not os.path.isfile(FUNC5), reason='func5.ggb not available')
class TestFunc5Piecewise:
    def test_function_m_loads(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser

        constr = Construction()
        ggb_parser.load(constr, {}, FUNC5)
        m = constr.element('m')
        assert m is not None
        assert isinstance(m.data, Function)
        # m(x) = If[-1 ≤ x ≤ 1, x²]
        assert m.data(0) == pytest.approx(0.0)
        assert m.data(0.5) == pytest.approx(0.25)
        assert m.data(1) == pytest.approx(1.0)
        # Outside the condition — NaN.
        assert np.isnan(m.data(2.0))


# ── 1.7.13: periodic singularities ───────────────────────────────────

from animageo.geo.safe_sympify import MATH_FUNCTIONS

_CALLS = {
    'atan2': 'atan2(x, 1)', 'root': 'root(x, 3)', 'real_root': 'real_root(x, 3)',
    'pow': 'pow(x, 2)', 'Max': 'Max(x, 1)', 'Min': 'Min(x, 1)',
    'max': 'max(x, 1)', 'min': 'min(x, 1)',
    'Piecewise': 'Piecewise((x, x > 0), (0, True))',
}


@pytest.mark.parametrize('name', sorted(MATH_FUNCTIONS))
def test_every_math_function_of_x_parses_fast(name):
    # tan, cot, sec, csc and their hyperbolic twins used to hang: sympy
    # gives their singularities as an infinite set, which was iterated.
    import time
    start = time.perf_counter()
    f = Function.from_string('y = ' + _CALLS.get(name, f'{name}(x)'))
    assert time.perf_counter() - start < 1
    assert all(np.isfinite(s) for s in f.natural_singularities)


@pytest.mark.parametrize('text, x, expected', [
    ('y = round(x)', 2.5, 3.0), ('y = round(x)', -2.5, -3.0),
    ('y = round(x)', 2.4, 2.0), ('y = round(x, 1)', -0.25, -0.3),
    ('y = round(2.5) + round(-0.5) + 0*x', 0.0, 2.0),
])
def test_round_is_a_graph_with_halves_away_from_zero(text, x, expected):
    assert Function.from_string(text)(x) == pytest.approx(expected)


@pytest.mark.parametrize('text, expected', [
    ('y = tan(x)', [-3 * np.pi / 2, -np.pi / 2, np.pi / 2, 3 * np.pi / 2]),
    ('y = cot(x)', [-np.pi, 0.0, np.pi]),
    ('y = sec(x)', [-3 * np.pi / 2, -np.pi / 2, np.pi / 2, 3 * np.pi / 2]),
    ('y = csc(x)', [-np.pi, 0.0, np.pi]),
    ('y = coth(x)', [0.0]),
    ('y = csch(2x + 1)', [-0.5]),
    ('y = tanh(x) + sech(x)', []),
    ('y = tan(x)/x', [-3 * np.pi / 2, -np.pi / 2, 0.0, np.pi / 2, 3 * np.pi / 2]),
    ('y = tan(πx)', [-4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5]),
])
def test_periodic_singularities(text, expected):
    sings = Function.from_string(text).natural_singularities
    near = [s for s in sings if -5 < s < 5]
    assert near == pytest.approx(expected, abs=1e-9)
    assert sings == sorted(sings) and len(sings) < 5000


class TestPeriodicAsymptotes:
    @pytest.fixture
    def scene(self, caplog):
        from animageo.animageo import AnimaGeoScene
        caplog.set_level(logging.WARNING, logger='animageo.animageo')
        s = AnimaGeoScene()
        s.camera.frame.set(width=10)
        return s

    @pytest.mark.parametrize('name', ['tan', 'cot', 'sec', 'csc'])
    def test_split_at_every_asymptote(self, scene, caplog, name):
        f = Function.from_string(f'y = {name}(x)')
        mobj = scene.CreateMObject(Element('f', f), z_auto=True)
        assert mobj is not None and len(mobj.submobjects) >= 3
        inside = [s for s in f.natural_singularities if -4.9 < s < 4.9]
        assert inside
        for piece in mobj.submobjects:
            xs = piece.points[:, 0]
            assert not any(xs.min() < s < xs.max() for s in inside)
        assert len(caplog.records) == 0
