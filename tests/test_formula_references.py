"""Formulas that refer to points and to other functions.

GeoGebra formulas read point coordinates — ``x(A)``, ``y(A)`` — name their
own variable (``g(t) = t²``) and call other functions (``f(t) = g(t) + k``).
Such a curve is a command on everything it refers to, re-read on every
rebuild, so it follows a dragged or animated point like it does in the applet.
"""
import os
import re
import tempfile
import zipfile

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.geo.formula_params import formula_parameters, parametric_inputs
from animageo.geo.lib_conic import Conic
from animageo.geo.lib_function import Function, parse_function_expression
from animageo.geo.lib_implicit import ImplicitCurve
from animageo.keyframes import apply_parsed_value
from animageo.parsers import dsl, ggb_parser


ST = ('<show object="true" label="false"/><objColor r="0" g="0" b="0" alpha="0"/>'
      '<lineStyle thickness="5" type="0"/>')


def num(name, val):
    return (f'<element type="numeric" label="{name}"><value val="{val}"/>'
            '<show object="false" label="true"/></element>')


def pt(name, x, y):
    return (f'<element type="point" label="{name}"><show object="true" label="true"/>'
            f'<coords x="{x}" y="{y}" z="1"/></element>')


def fn(name, exp, color='r="0" g="0" b="0"'):
    return (f'<expression label="{name}" exp="{exp}"/>'
            f'<element type="function" label="{name}"><show object="true" label="false"/>'
            f'<objColor {color} alpha="0"/><lineStyle thickness="5" type="0"/></element>')


def make_ggb(body):
    xml = ('<?xml version="1.0" encoding="utf-8"?><geogebra format="5.0"><euclidianView>'
           '<size width="600" height="400"/>'
           '<coordSystem xZero="300" yZero="200" scale="50" yscale="50"/>'
           '<evSettings axes="false" grid="false"/><bgColor r="255" g="255" b="255"/>'
           f'</euclidianView><construction>{body}</construction></geogebra>')
    fd, path = tempfile.mkstemp(suffix='.ggb')
    os.close(fd)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('geogebra.xml', xml)
    return path


def load(body):
    path = make_ggb(body)
    try:
        c = Construction()
        ggb_parser.load(c, {}, path)
        return c
    finally:
        os.remove(path)


def move(c, name, xy):
    apply_parsed_value(c, name, 'point', list(xy))
    c.rebuild()


# The owner's drawing: a Lagrange polynomial through A, B, C and a cubic
# family through the same points (formulas verbatim from the saved file).
POINTS = {'A': (-1.526984126984127, -1.1450793650793651),
          'B': (-0.35492063492063497, -2.6142857142857143),
          'C': (1.4114285714285715, -2.498730158730159)}
LAGRANGE = ('g(t) = ((y(A) * (t - x(B))) * (t - x(C)) / (((x(A) - x(B)) * (x(A) - x(C))))) '
            '+ ((y(B) * (t - x(A))) * (t - x(C)) / (((x(B) - x(A)) * (x(B) - x(C))))) '
            '+ ((y(C) * (t - x(A))) * (t - x(B)) / (((x(C) - x(A)) * (x(C) - x(B)))))')
FAMILY = 'f(t) = g(t) + (((k * (t - x(A))) * (t - x(B))) * (t - x(C)))'
LAGRANGE_BODY = (''.join(pt(n, *xy) for n, xy in POINTS.items())
                 + fn('g', LAGRANGE) + num('k', 1)
                 + fn('f', FAMILY, color='r="208" g="84" b="86"'))


def passes_through(func, points):
    return all(abs(float(func(x)) - y) < 1e-9 for x, y in points)


# ── Parsing ─────────────────────────────────────────────────────────────

class TestParsing:
    def test_variable_comes_from_the_left_side(self):
        expr, var = parse_function_expression('g(t) = t^2')
        assert str(var) == 'x' and str(expr) == 'x**2'

    def test_coordinate_calls_are_not_the_variable(self):
        assert formula_parameters('f(x) = x(A) + x', 'function') == ['A']
        assert formula_parameters('y = y(A) * x', 'function') == ['A']

    def test_parameters_name_points_numbers_and_functions(self):
        assert formula_parameters(FAMILY, 'function') == ['A', 'B', 'C', 'g', 'k']

    def test_point_named_like_a_sympy_object(self):
        # O, E, N, S, I, Q are sympy names; as a point they are still a point.
        assert formula_parameters('f(x) = x(O) + y(E) * x', 'function') == ['E', 'O']

    def test_coordinate_of_an_expression_is_not_supported(self):
        assert formula_parameters('f(x) = x(A + B)', 'function') is None

    def test_conic_and_implicit_coordinates(self):
        eq = '(x - x(A))^(2) + (y - y(A))^(2) = 4'
        assert formula_parameters(eq, 'conic') == ['A']
        assert formula_parameters(eq, 'implicit') == ['A']

    def test_parametric_inputs_need_every_name_in_the_construction(self):
        c = load(pt('A', 1, 2))
        assert parametric_inputs(c, 'f(x) = x(A) + x', 'function') == ['A']
        assert parametric_inputs(c, 'f(x) = x(Z) + x', 'function') is None

    def test_geogebra_and_numpy_function_names(self):
        assert Function.from_string('y = arctan(x)')(1.0) == pytest.approx(np.pi / 4)
        assert Function.from_string('y = sgn(x)')(-2.0) == pytest.approx(-1.0)
        assert Function.from_string('y = lg(x)')(100.0) == pytest.approx(2.0)
        assert Function.from_string('y = hypot(x, 1)')(0.0) == pytest.approx(1.0)

    def test_unbound_names_are_refused(self):
        with pytest.raises(ValueError):
            Function.from_string('f(x) = x(A) + x')
        with pytest.raises(ValueError):
            Function.from_string('f(x) = q(x) + 1')
        with pytest.raises(ValueError):
            Conic.from_string('(x - x(A))^2 + y^2 = 4')
        with pytest.raises(ValueError):
            ImplicitCurve.from_string('x^3 + y^3 = x(A)')


# ── GGB import ──────────────────────────────────────────────────────────

class TestGGBImport:
    def test_lagrange_functions_are_built_through_the_points(self):
        c = load(LAGRANGE_BODY)
        g, f = c.element('g').data, c.element('f').data
        assert isinstance(g, Function) and isinstance(f, Function)
        assert passes_through(g, POINTS.values())
        assert passes_through(f, POINTS.values())
        assert c.command_diagnostics == []

    def test_family_differs_from_the_polynomial_by_k(self):
        c = load(LAGRANGE_BODY)
        g, f = c.element('g').data, c.element('f').data
        xa, xb, xc = (POINTS[n][0] for n in 'ABC')
        x = 0.25
        assert float(f(x)) - float(g(x)) == pytest.approx((x - xa) * (x - xb) * (x - xc))

    def test_curves_follow_a_moved_point(self):
        c = load(LAGRANGE_BODY)
        move(c, 'A', (-2.0, 1.0))
        moved = [(-2.0, 1.0), POINTS['B'], POINTS['C']]
        assert passes_through(c.element('g').data, moved)
        assert passes_through(c.element('f').data, moved)

    def test_family_follows_its_number(self):
        c = load(LAGRANGE_BODY)
        apply_parsed_value(c, 'k', 'var', 3.0)
        c.rebuild()
        g, f = c.element('g').data, c.element('f').data
        xa, xb, xc = (POINTS[n][0] for n in 'ABC')
        x = 0.25
        assert float(f(x)) - float(g(x)) == pytest.approx(3 * (x - xa) * (x - xb) * (x - xc))

    def test_function_of_t(self):
        c = load(fn('g', 'g(t) = t^(2)'))
        assert c.element('g').data(2.0) == pytest.approx(4.0)
        assert c.command_diagnostics == []

    def test_function_of_t_with_a_slider_named_t(self):
        # The variable shadows the number, as in GeoGebra.
        c = load(num('t', 5) + fn('g', 'g(t) = t^(2)'))
        assert c.element('g').data(2.0) == pytest.approx(4.0)
        assert c.command_diagnostics == []

    def test_coordinate_plus_variable(self):
        c = load(pt('A', 3, 1) + fn('f', 'f(x) = x(A) + x'))
        assert c.element('f').data(1.0) == pytest.approx(4.0)
        move(c, 'A', (5, 1))
        assert c.element('f').data(1.0) == pytest.approx(6.0)

    def test_vector_coordinates(self):
        body = (pt('A', 0, 0) + pt('B', 2, 3)
                + '<command name="Vector"><input a0="A" a1="B"/><output a0="u"/></command>'
                  '<element type="vector" label="u">' + ST + '<coords x="2" y="3" z="0"/></element>'
                + fn('f', 'f(x) = y(u) * x + x(u)'))
        c = load(body)
        assert c.element('f').data(1.0) == pytest.approx(5.0)
        move(c, 'B', (1, 1))
        assert c.element('f').data(1.0) == pytest.approx(2.0)

    def test_function_calling_a_fixed_function(self):
        c = load(fn('g', 'g(x) = x^(2)') + fn('f', 'f(x) = g(x + 1) - 1'))
        assert c.element('f').data(2.0) == pytest.approx(8.0)

    def test_unrecognisable_function_is_diagnosed(self):
        c = load(fn('f', 'f(x) = q(x) + 1'))
        assert c.element('f') is None or c.element('f').data is None
        diags = [d for d in c.command_diagnostics if d['outputs'] == ['f']]
        assert diags and diags[0]['reason'] == 'expression_parse_error'
        assert diags[0]['expression'] == 'f(x) = q(x) + 1'

    def test_function_of_a_missing_point_is_diagnosed(self):
        c = load(fn('f', 'f(x) = x(Z) + x'))
        assert any(d['outputs'] == ['f'] for d in c.command_diagnostics)

    def test_circle_equation_follows_its_centre(self):
        body = (pt('A', 1, 2)
                + '<expression label="c" exp="(x - x(A))^(2) + (y - y(A))^(2) = 4" type="conic"/>'
                  '<element type="conic" label="c">' + ST +
                  '<matrix A0="1" A1="1" A2="1" A3="0" A4="-1" A5="-2"/></element>')
        c = load(body)
        assert not c.element('c').fixed
        move(c, 'A', (3, -1))
        conic = c.element('c').data
        assert isinstance(conic, Conic)
        assert conic.equivalent(Conic.from_string('(x - 3)^2 + (y + 1)^2 = 4'))

    def test_line_equation_follows_a_point(self):
        body = (pt('A', 1, 2)
                + '<expression label="g" exp="y = y(A)" type="line"/>'
                  '<element type="line" label="g">' + ST + '<coords x="0" y="1" z="-2"/></element>')
        c = load(body)
        move(c, 'A', (1, 5))
        line = c.element('g').data
        assert abs(np.dot(line.normal, [0.0, 5.0]) - line.offset) < 1e-9
        assert abs(np.dot(line.normal, [7.0, 5.0]) - line.offset) < 1e-9

    def test_graph_between_two_points(self):
        body = (pt('A', -1, 0) + pt('B', 2, 0)
                + fn('f', 'f(x) = If(x(A) ≤ x ≤ x(B), x^(2))'))
        c = load(body)
        f = c.element('f').data
        assert f(1.0) == pytest.approx(1.0) and np.isnan(f(3.0))
        move(c, 'B', (4, 0))
        assert c.element('f').data(3.0) == pytest.approx(9.0)

    def test_point_named_like_a_constant(self):
        c = load(pt('e', 3, 1) + fn('f', 'f(x) = x(e) + x'))
        assert c.element('f').data(1.0) == pytest.approx(4.0)

    def test_nested_calls_are_bounded(self):
        # Each level doubles the inlined expression: past the limit the
        # function is refused with a diagnostic instead of hanging the load.
        import time
        body = fn('h', 'h(x) = x^(2)') + ''.join(
            fn(f'h{k}', f'h{k}(x) = {f"h{k - 1}" if k > 1 else "h"}(sin(x)) '
                        f'+ {f"h{k - 1}" if k > 1 else "h"}(cos(x))')
            for k in range(1, 31))
        start = time.perf_counter()
        c = load(body)
        assert time.perf_counter() - start < 5
        assert c.element('h1').data(0.0) == pytest.approx(1.0)
        assert c.element('h30') is None
        assert any(d['outputs'] == ['h30'] for d in c.command_diagnostics)

    def test_unbound_implicit_curve_is_diagnosed(self):
        body = ('<expression label="h" exp="x^(3) + y^(3) = x(Z)" type="implicitpoly"/>'
                '<element type="implicitpoly" label="h">' + ST + '</element>')
        c = load(body)
        assert c.element('h') is None
        assert any(d['outputs'] == ['h'] and d['reason'] == 'expression_parse_error'
                   for d in c.command_diagnostics)

    def test_implicit_curve_follows_a_point(self):
        body = (pt('A', 1, 0)
                + '<expression label="h" exp="x^(3) + y^(3) = x(A)" type="implicitpoly"/>'
                  '<element type="implicitpoly" label="h">' + ST + '</element>')
        c = load(body)
        move(c, 'A', (8, 0))
        h = c.element('h').data
        assert isinstance(h, ImplicitCurve)
        assert abs(float(h(2.0, 0.0))) < 1e-9


# ── DSL ─────────────────────────────────────────────────────────────────

class TestDSL:
    def test_function_factory_follows_a_point(self):
        c = Construction()
        dsl.run(c, 'A = Point(2, 0)\nf = Function("y = x(A) * x")\n')
        assert c.element('f').data(1.0) == pytest.approx(2.0)
        move(c, 'A', (5, 0))
        assert c.element('f').data(1.0) == pytest.approx(5.0)

    def test_redefining_a_function_from_itself_raises(self):
        # A dependency cycle used to hang the construction forever.
        c = Construction()
        with pytest.raises(ValueError, match='cycle'):
            dsl.run(c, 'f = Function("y = x^2")\nf = Function("y = f(x) + 1")\n')

    def test_sugar_with_coordinates_and_a_function_call(self):
        c = Construction()
        dsl.run(c, 'A = Point(2, 3)\ng(t) = y(A)*t + x(A)\nk = 1\n'
                   'f(x) = g(x) + k*x^2\n')
        assert c.element('g').data(1.0) == pytest.approx(5.0)
        assert c.element('f').data(1.0) == pytest.approx(6.0)
        move(c, 'A', (5, 1))
        assert c.element('g').data(1.0) == pytest.approx(6.0)
        assert c.element('f').data(1.0) == pytest.approx(7.0)


# ── Rendering ───────────────────────────────────────────────────────────

def _stroke_colours(body, tmp_path, stem):
    """Stroke colours of the unfilled paths (curves) in the exported SVG."""
    from animageo.animageo import AnimaGeoScene
    path = make_ggb(body)
    try:
        scene = AnimaGeoScene()
        scene.loadGGB(path, generate_stubs=False)
        out = tmp_path / f'{stem}.svg'
        scene.exportSVG(str(out))
    finally:
        os.remove(path)
    return set(re.findall(r'<path fill="none"[^>]*?stroke="([^"]*)"', out.read_text()))


def test_both_curves_are_drawn_in_the_svg(tmp_path):
    black, red = 'rgb(0%, 0%, 0%)', 'rgb(81.568627%, 32.941176%, 33.72549%)'
    hidden = LAGRANGE_BODY.replace('<show object="true" label="false"/>',
                                   '<show object="false" label="false"/>')
    assert hidden.count('<show object="false" label="false"/>') == 2   # g, f
    assert {black, red} <= _stroke_colours(LAGRANGE_BODY, tmp_path, 'shown')
    assert not {black, red} & _stroke_colours(hidden, tmp_path, 'hidden')


# ── 1.7.12: implicit products, sympy-named numbers, domains, conic degree ──

class TestImplicitProducts:
    @pytest.mark.parametrize('text, x, expected', [
        ('y = 2x + 1', 3.0, 7.0),
        ('y = 2 x', 3.0, 6.0),
        ('y = 2(x + 1)', 1.0, 4.0),
        ('y = (x + 1)(x - 1)', 3.0, 8.0),
        ('y = x (x + 1)', 2.0, 6.0),
        ('y = (x + 1) x', 2.0, 6.0),
        ('y = 2.5x', 2.0, 5.0),
        ('y = 1e2x', 2.0, 200.0),
        ('y = sqrt(4)x', 3.0, 6.0),
        ('g(t) = 3t^(2)', 2.0, 12.0),
    ])
    def test_function_text(self, text, x, expected):
        assert Function.from_string(text)(x) == pytest.approx(expected)

    def test_number_times_variable(self):
        assert Function.from_string('y = k x', parameters={'k': 3})(2.0) == pytest.approx(6.0)

    def test_number_before_a_bracket_is_a_product(self):
        assert formula_parameters('y = k(x + 1)', 'function') == ['k']
        f = Function.from_string('y = k(x + 1)', parameters={'k': 3})
        assert f(1.0) == pytest.approx(6.0)

    def test_coordinate_after_a_number(self):
        f = Function.from_string('y = 2x(A) + x', parameters={'A': (3.0, 4.0)})
        assert f(1.0) == pytest.approx(7.0)

    def test_a_called_function_stays_a_call(self):
        g = Function.from_string('y = x^2')
        assert Function.from_string('y = g(x) + 1', parameters={'g': g})(3.0) == pytest.approx(10.0)
        assert Function.from_string('y = sin(x)')(0.0) == pytest.approx(0.0)

    def test_conic_and_implicit(self):
        assert Conic.from_string('x^2 + 4y^2 = 4').equivalent(
            Conic.from_string('x^2 + 4*y^2 = 4'))
        h = ImplicitCurve.from_string('x^3 + 2x y = 1')
        assert float(h(1.0, 0.0)) == pytest.approx(0.0)

    def test_ggb_formula_follows_its_number_and_point(self):
        c = load(num('k', 2) + pt('A', 1, 0) + fn('f', 'f(x) = k (x - x(A))'))
        assert c.element('f').data(3.0) == pytest.approx(4.0)
        move(c, 'A', (2, 0))
        assert c.element('f').data(3.0) == pytest.approx(2.0)

    def test_dsl_sugar(self):
        c = Construction()
        dsl.run(c, 'f(x) = 2x + 1\ng(t) = 2t + 1\nh(t) = t(t + 1)\n')
        assert c.element('f').data(3.0) == pytest.approx(7.0)
        assert c.element('g').data(3.0) == pytest.approx(7.0)
        assert c.element('h').data(2.0) == pytest.approx(6.0)

    def test_constant_before_a_bracket(self):
        assert Function.from_string('y = pi(x + 1)')(0.0) == pytest.approx(np.pi)
        assert Function.from_string('y = 2e(x + 1)')(0.0) == pytest.approx(2 * np.e)

    def test_coordinate_of_an_expression_is_named_in_the_error(self):
        with pytest.raises(ValueError, match=r"x\(x \+ 1\)"):
            Function.from_string('y = 3x(x + 1)')


class TestSympyNamedNumbers:
    def test_parameters(self):
        assert formula_parameters('y = E*x + gamma', 'function') == ['E', 'gamma']
        assert formula_parameters('x^2 + y^2 = N', 'conic') == ['N']
        assert formula_parameters('x^3 + S*y = 1', 'implicit') == ['S']
        assert formula_parameters('y = 2gamma x', 'function') == ['gamma']

    def test_ggb_numbers_named_like_sympy_objects(self):
        c = load(num('E', 2) + num('gamma', 3) + fn('f', 'f(x) = E * x + gamma'))
        assert c.element('f').data(1.0) == pytest.approx(5.0)
        apply_parsed_value(c, 'E', 'var', 4.0)
        c.rebuild()
        assert c.element('f').data(1.0) == pytest.approx(7.0)

    def test_number_named_like_a_sympy_function_before_a_bracket(self):
        for name in ('N', 'S', 'O', 'Q', 'E'):
            text = f'y = {name}(x + 1)'
            assert formula_parameters(text, 'function') == [name]
            f = Function.from_string(text, parameters={name: 3})
            assert f(1.0) == pytest.approx(6.0), name

    def test_conic_number_named_e(self):
        c = load(num('e', 4) + '<expression label="c" exp="x^(2) + y^(2) = e" type="conic"/>'
                 '<element type="conic" label="c">' + ST +
                 '<matrix A0="1" A1="1" A2="-4" A3="0" A4="0" A5="0"/></element>')
        assert c.element('c').data.equivalent(Conic.from_string('x^2 + y^2 = 4'))
        apply_parsed_value(c, 'e', 'var', 9.0)
        c.rebuild()
        assert c.element('c').data.equivalent(Conic.from_string('x^2 + y^2 = 9'))

    def test_constants_keep_their_meaning(self):
        assert Function.from_string('y = pi + e*x')(1.0) == pytest.approx(np.pi + np.e)
        assert Function.from_string('y = If(true, x, -x)')(2.0) == pytest.approx(2.0)
        assert Conic.from_string('x^2 + y^2 = pi').equivalent(
            Conic.from_string('x^2 + y^2 = 3.141592653589793'))


class TestCalledFunctionDomain:
    def test_domain_carries_over(self):
        from animageo.geo.lib_commands import function_Tn
        g = Function('y = x^2', domain=(-1.0, 1.0))
        f = function_Tn('f(x) = g(x) + 1', g)
        assert f(0.5) == pytest.approx(1.25)
        assert np.isnan(f(2.0))

    def test_nested_call_of_a_function_with_a_domain(self):
        from animageo.geo.lib_commands import function_Tn
        g = Function('y = x^2', domain=(-1.0, 1.0))
        f = function_Tn('f(x) = g(g(x))', g)
        assert f(0.5) == pytest.approx(0.0625)
        assert np.isnan(f(2.0))

    def test_domain_of_a_transformed_argument(self):
        from animageo.geo.lib_commands import function_Tn
        g = Function('y = x', domain=(0.0, 1.0))
        f = function_Tn('f(x) = g(x - 5)', g)
        assert f(5.5) == pytest.approx(0.5)
        assert np.isnan(f(0.5))


class TestConicDegreeBound:
    def test_huge_power_is_refused_before_expanding(self):
        import time
        start = time.perf_counter()
        with pytest.raises(ValueError, match='degree'):
            Conic.from_string('(x + y)^(10000) = 1')
        with pytest.raises(ValueError, match='degree'):
            Conic.from_string('(x + y)^(10^400) = 1')
        assert time.perf_counter() - start < 1

    def test_cancelling_terms_still_make_a_conic(self):
        conic = Conic.from_string('(x + 1)^(3) - x^(3) = y')
        assert conic.equivalent(Conic.from_string('3x^2 + 3x + 1 = y'))

    def test_not_polynomial(self):
        with pytest.raises(ValueError, match='not polynomial'):
            Conic.from_string('sin(x) = y')


class TestEvaluationBounds:
    """Parsing evaluates exactly; nothing in a formula may make it run long."""

    @pytest.mark.parametrize('text', [
        'y = x + 7^(9^9)',
        'y = x + 7**(9**9)',
        'y = x + pow(7, 9^9)',
        'y = x + sqrt(10^9999)^(10^4)',
        'y = x + (10^7)!',
        'y = x + gamma(10^7)',
        'y = x + root(7, 1/10^9)',
        'y = x + real_root(7, 10^(-9))',
        'y = x + exp(10^9 log(7))',
        'y = x + E^(10^9 log(7))',
        'y = x + floor(exp(10^9))',
        'y = x + round(10^(10^4) sqrt(2))',
        'y = x + frac(10^(10^4) sqrt(2))',
        'y = x + re((sqrt(2) + I)^(10^4))',
        'y = x + re((sqrt(2) + I)^(900) (sqrt(2) + I)^(900))',
        'y = x + sqrt(7^11000 + 1)',
        'y = x + (7^11000 + 1)^(1/2)',
        'y = x + Float(1, 10^9)',
        'y = x + factorial(10^7)',
        'y = x + fibonacci(10^8)',
        'y = x + binomial(10^8, 10^7)',
        'y = x + ' + '1 + ' * 1200 + '1',
    ])
    def test_refused_fast(self, text):
        import time
        start = time.perf_counter()
        with pytest.raises(ValueError):
            Function.from_string(text)
        assert time.perf_counter() - start < 1

    def test_conic_power_refused_fast(self):
        import time
        start = time.perf_counter()
        with pytest.raises(ValueError):
            Conic.from_string('x^2 + y^2 = 7^(9^9)')
        with pytest.raises(ValueError):
            Conic.from_string('x^2 + y^2 = (1 + sqrt(2))^(900) (1 + sqrt(2))^(900)')
        assert time.perf_counter() - start < 1

    @pytest.mark.parametrize('text, x, expected', [
        ('y = 2^10 x', 1.0, 1024.0),
        ('y = 10^(-6) + x', 0.0, 1e-6),
        ('y = pi^500 * 0 + x', 1.0, 1.0),
        ('y = sqrt(2) x + exp(2) * 0', 1.0, np.sqrt(2)),
        ('y = floor(7.5) + round(2.4) + abs(-3) + x', 0.0, 12.0),
        ('y = gamma(x)', 5.0, 24.0),
        ('y = pow(2, 3) x', 1.0, 8.0),
        ('y = root(8, 3) x', 1.0, 2.0),
        ('y = 3! x', 1.0, 6.0),
    ])
    def test_ordinary_powers_and_factorials(self, text, x, expected):
        assert Function.from_string(text)(x) == pytest.approx(expected)
