"""Objects that depend on a free number follow it after import.

In GeoGebra an object built from a number (a slider) is recomputed when the number changes.
After ``ggb_parser.load`` → ``apply_parsed_value(var)`` → ``rebuild()`` the
same object must change in animageo too — otherwise the exact frame and the
video stand still while the applet moves.
"""
import os
import tempfile
import zipfile

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_conic import Conic
from animageo.keyframes import apply_parsed_value
from animageo.parsers import ggb_parser


ST = ('<show object="true" label="false"/><objColor r="0" g="0" b="0" alpha="0"/>'
      '<lineStyle thickness="5" type="0"/>')


def num(name, val):
    return (f'<element type="numeric" label="{name}"><value val="{val}"/>'
            '<show object="false" label="true"/></element>')


def pt(name, x, y):
    return (f'<element type="point" label="{name}"><show object="true" label="true"/>'
            f'<coords x="{x}" y="{y}" z="1"/></element>')


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


def data_at(c, var, value, target):
    apply_parsed_value(c, var, 'var', value)
    c.rebuild()
    e = c.element(target)
    return None if e is None else e.data


FUNC_A = ('<expression label="f" exp="f(x) = (a * x^(2))"/>'
          '<element type="function" label="f">' + ST + '</element>')
CONIC_A = ('<expression label="p" exp="y = (a * x^(2))" type="conic"/>'
           '<element type="conic" label="p">' + ST +
           '<matrix A0="-1" A1="0" A2="0" A3="0" A4="0" A5="0.5"/></element>')
LINE_A = ('<expression label="g" exp="y = (a * x) + 1" type="line"/>'
          '<element type="line" label="g">' + ST + '<coords x="-1" y="1" z="-1"/></element>')


# ── Cases 1–2: formulas with a parameter ───────────────────────────────

def test_case1_function_follows_parameter():
    c = load(num('a', 1) + FUNC_A)
    for v in (1.0, 3.0):
        assert data_at(c, 'a', v, 'f')(2.0) == pytest.approx(4 * v)
    assert not c.element('f').fixed


def test_case2_conic_follows_parameter():
    c = load(num('a', 1) + CONIC_A)
    for v in (1.0, 3.0):
        k = data_at(c, 'a', v, 'p')
        assert k.evaluate(2.0, 4 * v) == pytest.approx(0.0)


def test_line_equation_follows_parameter():
    c = load(num('a', 1) + LINE_A)
    g = data_at(c, 'a', 3.0, 'g')
    assert np.dot(g.normal, [1.0, 4.0]) == pytest.approx(g.offset)


def test_implicit_equation_follows_parameter():
    body = num('a', 1) + ('<expression label="h" exp="x^(3) + a * y = 1" type="implicitpoly"/>'
                          '<element type="implicitpoly" label="h">' + ST + '</element>')
    c = load(body)
    assert data_at(c, 'a', 2.0, 'h')(1.0, 0.0) == pytest.approx(0.0)


def test_conic_load_time_curve_equals_saved():
    c = load(num('a', 1) + CONIC_A)
    saved = Conic.from_ggb_matrix(-1, 0, 0, 0, 0, 0.5)
    assert c.element('p').data.equivalent(saved)


def test_conic_equation_mismatch_keeps_saved_matrix():
    # The saved matrix says y = 2x², the equation with a = 1 says y = x²:
    # trust GeoGebra's curve and say so.
    body = num('a', 1) + CONIC_A.replace('A0="-1"', 'A0="-2"')
    c = load(body)
    p = c.element('p')
    assert p.fixed
    assert p.data.equivalent(Conic.from_ggb_matrix(-2, 0, 0, 0, 0, 0.5))
    assert any(d['reason'] == 'parametric_dependency_frozen' and d['outputs'] == ['p']
               for d in c.command_diagnostics)


def test_parametric_conic_survives_degenerate_value():
    c = load(num('a', 1) + CONIC_A)
    k = data_at(c, 'a', 0.0, 'p')
    assert k is not None and k.is_degenerate()


def test_function_calling_other_function_follows_the_number():
    body = (num('a', 1) + '<expression label="f" exp="f(x) = x^(2)"/>'
            '<element type="function" label="f">' + ST + '</element>'
            '<expression label="g" exp="g(x) = f(x) + a"/>'
            '<element type="function" label="g">' + ST + '</element>')
    c = load(body)
    assert c.command_diagnostics == []
    for v in (1.0, 3.0):
        assert data_at(c, 'a', v, 'g')(2.0) == pytest.approx(4 + v)


def test_function_without_parameters_unchanged():
    body = ('<expression label="f" exp="f(x) = x^(2)"/>'
            '<element type="function" label="f">' + ST + '</element>')
    c = load(body)
    assert c.element('f').fixed and c.command_diagnostics == []


# ── Case 4: coordinates with nested parentheses ────────────────────────

def test_case4_point_with_nested_parentheses_exists_and_moves():
    body = (num('a', 1) + '<expression label="F" exp="(0, 1 / ((4 * a)))" type="point"/>'
            + pt('F', 0, 0.25))
    c = load(body)
    assert c.element('F') is not None
    assert data_at(c, 'a', 1.0, 'F').coords[1] == pytest.approx(0.25)
    assert data_at(c, 'a', 2.0, 'F').coords[1] == pytest.approx(0.125)


def test_expression_parse_error_is_diagnosed():
    body = '<expression label="P" exp="(1, q(1))" type="point"/>' + pt('P', 1, 1)
    c = load(body)
    assert c.element('P') is not None           # kept at its saved position
    assert any(d['reason'] == 'expression_parse_error' and d['outputs'] == ['P']
               for d in c.command_diagnostics)


# ── Case 5: a vector expression as a command input ─────────────────────

TRANSLATE_AU = (pt('A', 0, 0) + pt('B', 1, 0)
                + '<command name="Vector"><input a0="A" a1="B"/><output a0="u"/></command>'
                  '<element type="vector" label="u">' + ST + '<coords x="1" y="0" z="0"/></element>'
                + pt('P', 0, 1)
                + '<command name="Translate"><input a0="P" a1="Vector[(a * u)]"/>'
                  '<output a0="Q"/></command>'
                + pt('Q', 1, 1))


def test_case5_translate_by_scaled_vector():
    c = load(num('a', 1) + TRANSLATE_AU)
    assert np.allclose(data_at(c, 'a', 1.0, 'Q').coords, [1, 1])
    assert np.allclose(data_at(c, 'a', 3.0, 'Q').coords, [3, 1])


# ── Case 3: a function call inside an expression ───────────────────────

def test_case3_point_on_graph_by_function_value():
    body = (num('a', 1) + FUNC_A
            + '<expression label="P" exp="(1, f(1))" type="point"/>' + pt('P', 1, 1))
    c = load(body)
    assert np.allclose(data_at(c, 'a', 1.0, 'P').coords, [1, 1])
    assert np.allclose(data_at(c, 'a', 3.0, 'P').coords, [1, 3])


# ── Cases 6–7: transformations of curves ───────────────────────────────

def test_case6_dilate_function():
    body = (num('a', 1) + pt('O', 0, 0) + '<expression label="f" exp="f(x) = x^(2)"/>'
            '<element type="function" label="f">' + ST + '</element>'
            '<command name="Dilate"><input a0="f" a1="a" a2="O"/><output a0="g"/></command>'
            '<element type="function" label="g">' + ST + '</element>')
    c = load(body)
    assert data_at(c, 'a', 1.0, 'g')(2.0) == pytest.approx(4.0)
    assert data_at(c, 'a', 2.0, 'g')(2.0) == pytest.approx(2.0)


def test_case7_dilate_conic():
    body = (num('a', 1) + pt('O', 0, 0)
            + '<expression label="p" exp="y = x^(2)" type="conic"/>'
              '<element type="conic" label="p">' + ST
            + '<matrix A0="-1" A1="0" A2="0" A3="0" A4="0" A5="0.5"/></element>'
            + '<command name="Dilate"><input a0="p" a1="a" a2="O"/><output a0="q"/></command>'
            + '<element type="conic" label="q">' + ST
            + '<matrix A0="-1" A1="0" A2="0" A3="0" A4="0" A5="0.5"/></element>')
    c = load(body)
    assert data_at(c, 'a', 2.0, 'q').evaluate(2.0, 2.0) == pytest.approx(0.0)


# ── Case 8: a point on a path at a numeric parameter ───────────────────
# GeoGebra's Point(path, t): t is a normalised path parameter clamped to
# [0, 1] (PathNormalizer); a circle maps it onto the angle −π … π.

def test_point_on_circle_normalised_parameter():
    from animageo.geo.lib_commands import point_ci, point_cm
    from animageo.geo.lib_elements import Circle
    from animageo.geo.lib_vars import Measure
    c = Circle([0, 0], 3)
    assert np.allclose(point_ci(c, 0.0).coords, [-3, 0])     # angle −π
    assert np.allclose(point_ci(c, 0.25).coords, [0, -3])    # angle −π/2
    assert np.allclose(point_ci(c, 0.5).coords, [3, 0])      # angle 0
    assert np.allclose(point_cm(c, Measure(0.75, 0)).coords, [0, 3])


def test_point_on_circle_clamps_parameter():
    from animageo.geo.lib_commands import point_ci
    from animageo.geo.lib_elements import Circle
    c = Circle([0, 0], 3)
    assert np.allclose(point_ci(c, 1.2).coords, point_ci(c, 1.0).coords)
    assert np.allclose(point_ci(c, -0.5).coords, point_ci(c, 0.0).coords)


def test_point_on_segment_and_conic_circle():
    from animageo.geo.lib_commands import point_si, point_Ki
    from animageo.geo.lib_elements import Segment
    assert np.allclose(point_si(Segment(np.array([0.0, 0.0]), np.array([4.0, 2.0])), 0.25).coords,
                       [1, 0.5])
    k = Conic.from_string('x^2 + y^2 = 4')
    assert np.allclose(point_Ki(k, 0.5).coords, [2, 0])


POINT_ON_CIRCLE = (pt('O', 0, 0) + pt('A', 3, 0)
                   + '<command name="Circle"><input a0="O" a1="A"/><output a0="c"/></command>'
                   + '<element type="conic" label="c">' + ST
                   + '<matrix A0="1" A1="1" A2="-9" A3="0" A4="0" A5="0"/></element>'
                   + '<command name="Point"><input a0="c" a1="t"/><output a0="C"/></command>'
                   + pt('C', -3, 0))


def test_case8_point_on_circle_follows_number():
    c = load(num('t', 0) + POINT_ON_CIRCLE)
    assert np.allclose(data_at(c, 't', 0.0, 'C').coords, [-3, 0])
    assert np.allclose(data_at(c, 't', 0.5, 'C').coords, [3, 0])


# ── Scene level: exact frames at the two keyframes differ (TZ criterion 2) ──

SCENE_CASES = {
    # key: (var, value at t=0, value at t=4, frame times, body)
    'function': ('a', 1, 3, (0, 4), num('a', 1) + FUNC_A),
    'conic': ('a', 1, 3, (0, 4), num('a', 1) + CONIC_A),
    'point_f1': ('a', 1, 3, (0, 4), num('a', 1) + FUNC_A
                 + '<expression label="P" exp="(1, f(1))" type="point"/>' + pt('P', 1, 1)),
    'nested': ('a', 1, 3, (0, 4), num('a', 1)
               + '<expression label="F" exp="(0, 1 / ((4 * a)))" type="point"/>'
               + pt('F', 0, 0.25)),
    'translate': ('a', 1, 3, (0, 4), num('a', 1) + TRANSLATE_AU),
    # t: 0 → 1.2 is clamped at 1 — the full turn ends where it started,
    # so compare the start with the middle of the interval.
    'point_on_circle': ('t', 0, 1.2, (0, 2), num('t', 0) + POINT_ON_CIRCLE),
    'control_circle': ('a', 1, 3, (0, 4), num('a', 1) + pt('O', 0, 0)
                       + '<command name="Circle"><input a0="O" a1="a"/><output a0="k"/></command>'
                       + '<element type="conic" label="k">' + ST
                       + '<matrix A0="1" A1="1" A2="-1" A3="0" A4="0" A5="0"/></element>'),
}


@pytest.mark.parametrize('key', sorted(SCENE_CASES))
def test_exact_frames_differ(key, tmp_path):
    pytest.importorskip('manim')
    import hashlib
    from animageo.animageo import AnimaGeoScene

    var, v0, v1, times, body = SCENE_CASES[key]
    path = make_ggb(body)
    try:
        scene = AnimaGeoScene()
        scene.loadGGB(path, generate_stubs=False)
        kf = {"version": 2, "keyframes": [
            {"t": 0, "values": {var: v0}},
            {"t": 4, "values": {var: v1}, "easing": "linear"},
        ]}
        digests = []
        for t in times:
            scene.apply_keyframes_at(kf, t)
            out = tmp_path / f'{t}.svg'
            scene.exportSVG(str(out))
            digests.append(hashlib.md5(out.read_bytes()).hexdigest())
        assert digests[0] != digests[1]
    finally:
        os.remove(path)


# ── Point(conic, t) / Point(f, t) in GeoGebra's path parametrisation ───
# A conic's parameter is measured in GeoGebra's own frame of the conic: the
# first "eigenvector" it picks (GeoConicND.classifyConic, non-continuous
# mode). Real frames saved by GeoGebra in example files pin the port.

GGB_SAVED_FRAMES = [
    # (A0, A1, A2, A3, A4, A5) as saved in <matrix>, then <eigenvectors> e0, e1
    ((31.59891921540665, -120.74182073819247, 462.0264445450647,
      -2.1924931381587944e-14, -148.19893112025727, -238.59541929743122),
     (0, 1), (-1, 0)),                                   # hyperbola, axes swapped
    ((74.20917306787533, 322.57237306787533, 2145.5256003860013,
      -1.8911999999999947, -490.64967717069226, -345.4977661053416),
     (0.999971013139094, 0.007613992485830642),
     (-0.007613992485830642, 0.999971013139094)),        # slightly rotated ellipse
    ((-1, 0, 1, 0, 0, 0.5), (0, 1), (-1, 0)),            # parabola y = x² − 1
]


@pytest.mark.parametrize('matrix, e0, e1', GGB_SAVED_FRAMES)
def test_ggb_frame_matches_saved_eigenvectors(matrix, e0, e1):
    frame = Conic.from_ggb_matrix(*matrix).ggb_frame()
    assert np.allclose(frame['e0'], e0, atol=1e-9)
    assert np.allclose(frame['e1'], e1, atol=1e-9)


def test_point_on_ellipse():
    from animageo.geo.lib_commands import point_Ki
    wide = Conic.from_string('x^2/4 + y^2 = 1')
    assert np.allclose(point_Ki(wide, 0.5).coords, [2, 0])      # angle 0 on the major axis
    assert np.allclose(point_Ki(wide, 0.75).coords, [0, 1])
    tall = Conic.from_string('x^2 + y^2/4 = 1')                  # GeoGebra's first axis is (0, 1)
    assert np.allclose(point_Ki(tall, 0.5).coords, [0, 2])
    assert np.allclose(point_Ki(tall, 0.75).coords, [-1, 0])


def test_point_on_hyperbola_branches():
    from animageo.geo.lib_commands import point_Ki
    h = Conic.from_string('x^2/4 - y^2 = 1')
    assert np.allclose(point_Ki(h, 0.25).coords, [2, 0])        # right branch vertex
    assert np.allclose(point_Ki(h, 0.75).coords, [-2, 0])       # left branch vertex
    assert point_Ki(h, 0.0) is None                              # at infinity


def test_point_on_parabola():
    from animageo.geo.lib_commands import point_Ki
    p = Conic.from_ggb_matrix(-1, 0, 0, 0, 0, 0.5)                # y = x²
    assert np.allclose(point_Ki(p, 0.5).coords, [0, 0])          # vertex
    assert np.allclose(point_Ki(p, 0.75).coords, [-0.5, 0.25])   # GeoGebra runs towards −x
    assert point_Ki(p, 1.0) is None


def test_parabola_from_focus_and_directrix_follows_directrix_orientation():
    # GeoGebra orients a Parabola(F, d) by the directrix normal, so reversing
    # the directrix reverses the direction a Point(parabola, t) travels.
    from animageo.geo.lib_commands import point_Ki, parabola_pl, line_pp
    from animageo.geo.lib_elements import Point
    F = Point([0, 0.25])
    d = line_pp(Point([0, -0.25]), Point([1, -0.25]))
    d_rev = line_pp(Point([1, -0.25]), Point([0, -0.25]))
    assert np.allclose(point_Ki(parabola_pl(F, d), 0.75).coords, [-0.5, 0.25])
    assert np.allclose(point_Ki(parabola_pl(F, d_rev), 0.75).coords, [0.5, 0.25])


def test_point_on_degenerate_conic_is_undefined():
    from animageo.geo.lib_commands import point_Ki
    assert point_Ki(Conic.from_string('x^2 - y^2 = 0'), 0.3) is None


POINT_ON_GRAPH = ('<expression label="f" exp="f(x) = x^(2)"/>'
                  '<element type="function" label="f">' + ST + '</element>'
                  '<command name="Point"><input a0="f" a1="t"/><output a0="P"/></command>'
                  + pt('P', 0, 0))


def test_point_on_graph_uses_saved_view_range():
    # The saved view spans x ∈ [−6, 6] (xZero 300 px, 50 px per unit, 600 px wide):
    # GeoGebra maps t ∈ [0, 1] onto it.
    c = load(num('t', 0.5) + POINT_ON_GRAPH)
    assert np.allclose(data_at(c, 't', 0.5, 'P').coords, [0, 0])
    assert np.allclose(data_at(c, 't', 0.75, 'P').coords, [3, 9])
    assert np.allclose(data_at(c, 't', 2.0, 'P').coords, [6, 36])   # clamped


def test_point_on_graph_respects_explicit_domain():
    from animageo.geo.lib_commands import point_Fiii
    from animageo.geo.lib_function import Function
    f = Function('x**2', domain=(0.0, 2.0))
    assert np.allclose(point_Fiii(f, 0.5, -6.0, 6.0).coords, [1, 1])


# ── Review fixes ───────────────────────────────────────────────────────

CIRCLE_OA = (pt('O', 0, 0) + pt('A', 3, 0)
             + '<command name="Circle"><input a0="O" a1="A"/><output a0="c"/></command>'
             + '<element type="conic" label="c">' + ST
             + '<matrix A0="1" A1="1" A2="-9" A3="0" A4="0" A5="0"/></element>')


def move_point(c, name, xy):
    apply_parsed_value(c, name, 'point', xy)
    c.rebuild()


def test_function_follows_a_length():
    # Radius(c) is a length (Measure of dimension 1), not a plain number.
    body = (CIRCLE_OA + '<command name="Radius"><input a0="c"/><output a0="r"/></command>'
            + num('r', 3) + '<expression label="f" exp="f(x) = (r * x^(2))"/>'
              '<element type="function" label="f">' + ST + '</element>')
    c = load(body)
    assert c.element('f').data(1.0) == pytest.approx(3.0)
    move_point(c, 'A', [2, 0])
    assert c.element('f').data(1.0) == pytest.approx(2.0)


def test_conic_follows_a_distance():
    body = (pt('O', 0, 0) + pt('A', 3, 0)
            + '<command name="Distance"><input a0="O" a1="A"/><output a0="d"/></command>' + num('d', 3)
            + '<expression label="p" exp="y = (d * x^(2))" type="conic"/>'
              '<element type="conic" label="p">' + ST
            + '<matrix A0="-3" A1="0" A2="0" A3="0" A4="0" A5="0.5"/></element>')
    c = load(body)
    move_point(c, 'A', [2, 0])
    assert c.element('p').data.evaluate(1.0, 2.0) == pytest.approx(0.0)


def test_formula_follows_an_angle_object():
    body = (pt('A', 1, 0) + pt('B', 0, 0) + pt('C', 0, 1)
            + '<command name="Angle"><input a0="A" a1="B" a2="C"/><output a0="α"/></command>'
              '<element type="angle" label="α">' + ST + '</element>'
            + '<expression label="f" exp="f(x) = sin(α) x"/>'.replace('sin(α) x', 'sin(α) * x')
            + '<element type="function" label="f">' + ST + '</element>')
    c = load(body)
    assert c.element('f').data(1.0) == pytest.approx(1.0)          # sin(90°)
    move_point(c, 'C', [1, 1])
    assert c.element('f').data(1.0) == pytest.approx(np.sin(np.pi / 4))


def test_boolean_in_if_formula():
    body = ('<element type="boolean" label="b"><value val="true"/><show object="false" label="true"/></element>'
            '<expression label="f" exp="f(x) = If(b, x, -x)"/>'
            '<element type="function" label="f">' + ST + '</element>')
    c = load(body)
    assert c.element('f').data(2.0) == pytest.approx(2.0)
    apply_parsed_value(c, 'b', 'bool', False)
    c.rebuild()
    assert c.element('f').data(2.0) == pytest.approx(-2.0)


def test_point_from_number_and_length():
    body = CIRCLE_OA + '<expression label="P" exp="(0, -Radius(c))" type="point"/>' + pt('P', 0, -3)
    c = load(body)
    assert np.allclose(c.element('P').data.coords, [0, -3])
    move_point(c, 'A', [2, 0])
    assert np.allclose(c.element('P').data.coords, [0, -2])


@pytest.mark.parametrize('kind, exp', [
    ('function', 'f(x) = (a + (__import__(&quot;os&quot;).environ.__setitem__(&quot;ANIMAGEO_PWNED&quot;, &quot;1&quot;) or 0)) * x'),
    ('line', 'y = (a + (__import__(&quot;os&quot;).environ.__setitem__(&quot;ANIMAGEO_PWNED&quot;, &quot;1&quot;) or 0)) * x'),
    ('line', 'y = (__import__(&quot;os&quot;).environ.__setitem__(&quot;ANIMAGEO_PWNED&quot;, &quot;1&quot;) or 1) * x'),
    ('conic', 'y = (a + (__import__(&quot;os&quot;).environ.__setitem__(&quot;ANIMAGEO_PWNED&quot;, &quot;1&quot;) or 0)) * x^(2)'),
    ('implicitpoly', 'x^(3) + (a + (__import__(&quot;os&quot;).environ.__setitem__(&quot;ANIMAGEO_PWNED&quot;, &quot;1&quot;) or 0)) * y = 1'),
])
def test_formula_text_from_a_file_is_not_run_as_code(kind, exp, monkeypatch):
    monkeypatch.delenv('ANIMAGEO_PWNED', raising=False)
    saved = {'line': '<coords x="-1" y="1" z="0"/>',
             'conic': '<matrix A0="-1" A1="0" A2="0" A3="0" A4="0" A5="0.5"/>'}.get(kind, '')
    type_attr = '' if kind == 'function' else f' type="{kind}"'
    body = (num('a', 1) + f'<expression label="g" exp="{exp}"{type_attr}/>'
            f'<element type="{kind}" label="g">' + ST + saved + '</element>')
    load(body)
    assert 'ANIMAGEO_PWNED' not in os.environ


def test_formula_command_failure_keeps_saved_curve(monkeypatch):
    from animageo.geo import lib_commands

    def boom(*args):
        raise RuntimeError('unexpected sympy failure')
    monkeypatch.setitem(lib_commands.COMMAND_REGISTRY, 'conic_Tn', boom)
    c = load(num('a', 1) + CONIC_A)
    assert c.element('p').fixed
    assert any(d['reason'] == 'parametric_dependency_frozen' for d in c.command_diagnostics)


def test_point_on_path_mismatch_keeps_saved_position():
    # The file says C is at (0, 3), but Point(c, 0) is (−3, 0) by GeoGebra's
    # rule: trust the file and say so.
    body = num('t', 0) + POINT_ON_CIRCLE.replace(pt('C', -3, 0), pt('C', 0, 3))
    c = load(body)
    assert np.allclose(c.element('C').data.coords, [0, 3])
    assert c.element('C').fixed
    assert any(d['reason'] == 'parametric_dependency_frozen' and d['outputs'] == ['C']
               for d in c.command_diagnostics)


def test_saved_curve_guard_normalises_tiny_matrices():
    from animageo.parsers.ggb_parser import _same_curve
    a = Conic.from_ggb_matrix(-1e-9, 0, 0, 0, 0, 0.5e-9)     # y = x²
    b = Conic.from_ggb_matrix(-2e-9, 0, 0, 0, 0, 0.5e-9)     # y = 2x²
    assert not _same_curve(a, b)
    assert _same_curve(a, Conic.from_ggb_matrix(-1, 0, 0, 0, 0, 0.5))
