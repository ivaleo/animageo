"""ClosestPoint of a conic and of a graph in the classic library
(``closest_point_Kp``, ``closest_point_Fp``): the projection of the kernel
(``animageo/native/kernel/paths.py``)."""
import math

import numpy as np
import pytest

from animageo.geo.lib_commands import COMMAND_REGISTRY, closest_point_Fp, closest_point_Kp
from animageo.geo.lib_conic import Conic
from animageo.geo.lib_elements import Point
from animageo.geo.lib_function import Function
from tests.native.ggb_synth import command, element, expression, ggb_bytes, point


def near(point, want):
    assert point is not None
    assert np.allclose(point.coords, want, atol=1e-9), (point.coords, want)


def test_the_signatures_are_commands():
    assert {'closest_point_Kp', 'closest_point_Fp'} <= set(COMMAND_REGISTRY)


def test_ellipse():
    k = Conic.from_string('x^2/25 + y^2/9 = 1')
    near(closest_point_Kp(k, Point([6, 0])), [5, 0])
    near(closest_point_Kp(k, Point([0, -7])), [0, -3])
    q = 5 / 16
    near(closest_point_Kp(k, Point([1, 0])), [5 * q, 3 * math.sqrt(1 - q * q)])


def test_a_turned_ellipse_and_a_circle():
    k = Conic.from_string('x^2/9 + y^2/25 = 1')        # the major axis along y
    near(closest_point_Kp(k, Point([0, 7])), [0, 5])
    c = Conic.from_string('x^2 + y^2 = 4')
    near(closest_point_Kp(c, Point([3, 4])), [1.2, 1.6])


def test_hyperbola_takes_the_nearest_branch():
    h = Conic.from_string('x^2/9 - y^2/16 = 1')
    near(closest_point_Kp(h, Point([5, 0])), [3, 0])
    near(closest_point_Kp(h, Point([-5, 0])), [-3, 0])


def test_parabola():
    q = Conic.from_string('y = x^2/4')
    near(closest_point_Kp(q, Point([0, -3])), [0, 0])
    p = closest_point_Kp(q, Point([0, 5]))
    assert abs(p.coords[1] - 3) < 1e-9 and abs(abs(p.coords[0]) - 2 * math.sqrt(3)) < 1e-9


def test_a_degenerate_conic_has_none():
    assert closest_point_Kp(Conic.from_string('x^2 - y^2 = 0'), Point([1, 2])) is None


def test_graph():
    f = Function.from_string('y = x^2')
    p = closest_point_Fp(f, Point([0, 3]))
    assert p.coords[1] == pytest.approx(2.5, abs=1e-7) and abs(p.coords[0]) == pytest.approx(math.sqrt(2.5), abs=1e-7)
    near(closest_point_Fp(f, Point([2, 4])), [2, 4])


def test_graph_stays_in_its_domain():
    f = Function('y = x^2', domain=(-1, 2))
    near(closest_point_Fp(f, Point([5, 5])), [2, 4])
    near(closest_point_Fp(f, Point([-5, 0])), [-1, 1])


def test_a_graph_without_a_value_has_none():
    f = Function('y = sqrt(x)', domain=(-5, -1))
    assert closest_point_Fp(f, Point([0, 0])) is None


# ── a classic render keeps going when the kernel gives nothing ─────────────
#
# ClosestPoint of a degenerate conic, or of a graph with no value in the
# window, has no point; a failure of the kernel call is the same. The output
# is left undefined, as the output of an unknown command, and the SVG and
# TikZ export of the rest of the file go on.

DEGENERATE = {
    'conic_pair_of_lines': (expression('q', 'x^2 - y^2 = 0', 'conic')
                            + element('conic', 'q', extra='<matrix A0="1" A1="-1" A2="0" A3="0" A4="0" A5="0"/>')
                            + point('A', 1., 3.) + command('ClosestPoint', ['q', 'A'], ['P']) + point('P', 2., 2.)),
    'graph_without_values': (expression('f', 'f(x) = sqrt(-x^2 - 1)') + element('function', 'f')
                             + point('A', 0., 0.) + command('ClosestPoint', ['f', 'A'], ['P']) + point('P', 0., 0.)),
    'graph_outside_the_window': (expression('f', 'f(x) = If(-5 ≤ x ≤ -1, sqrt(x))') + element('function', 'f')
                                 + point('A', 0., 0.) + command('ClosestPoint', ['f', 'A'], ['P'])
                                 + point('P', 0., 0.)),
}


def _render(tmp_path, name):
    from animageo import AnimaGeoScene
    path = tmp_path / f'{name}.ggb'
    path.write_bytes(ggb_bytes(DEGENERATE[name]))
    scene = AnimaGeoScene()
    scene.loadGGB(str(path), generate_stubs=False)
    svg, tex = tmp_path / f'{name}.svg', tmp_path / f'{name}.tex'
    scene.exportSVG(str(svg))
    scene.exportTikZ(str(tex))
    assert svg.stat().st_size > 0 and tex.stat().st_size > 0
    return scene


@pytest.mark.parametrize('name', sorted(DEGENERATE))
def test_a_degenerate_closest_point_is_skipped_and_the_file_renders(tmp_path, name):
    scene = _render(tmp_path, name)
    assert scene.geo.element('P').data is None          # undefined, as an unknown command leaves it
    assert isinstance(scene.geo.element('A').data, Point)


PROPER = {
    'locate': (expression('q', 'x^2/9 + y^2/4 = 1', 'conic')
               + element('conic', 'q', extra='<matrix A0="4" A1="9" A2="-36" A3="0" A4="0" A5="0"/>')
               + point('A', 1., 3.) + command('ClosestPoint', ['q', 'A'], ['P']) + point('P', 0., 2.)),
    'nearest_on_graph': (expression('f', 'f(x) = x^2') + element('function', 'f')
                         + point('A', 1., 3.) + command('ClosestPoint', ['f', 'A'], ['P']) + point('P', 1., 1.)),
}


@pytest.mark.parametrize('failing', sorted(PROPER))
def test_a_failing_kernel_call_is_skipped_and_the_file_renders(tmp_path, monkeypatch, failing):
    from animageo.native.kernel import paths
    monkeypatch.setitem(DEGENERATE, failing, PROPER[failing])
    assert isinstance(_render(tmp_path, failing).geo.element('P').data, Point)     # the kernel is reached

    def boom(*args, **kwargs):
        raise RuntimeError('kernel failure')

    monkeypatch.setattr(paths, failing, boom)
    scene = _render(tmp_path, failing)
    assert scene.geo.element('P').data is None
    assert isinstance(scene.geo.element('A').data, Point)
