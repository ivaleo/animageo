"""Classic geometry fixes of 1.8.0a2: tail outputs, circles without assert,
line_pp tolerance, seeded randomness."""
import logging
import math

import numpy as np
import pytest

from animageo.geo import lib_elements
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import (
    Command,
    circle_pi,
    circle_pm,
    circle_pp,
    circle_ps,
    line_pp,
    point_,
)
from animageo.geo.lib_elements import Circle, Element, Line, Point, Segment
from animageo.geo.lib_vars import Measure


def construction(points, *commands, seed=0):
    c = Construction(seed=seed)
    for name, xy in points.items():
        c.add(Element(name, Point(xy)))
    for cmd in commands:
        c.add_and_build(cmd)
    return c


def coords(c, name):
    data = c.element(name).data
    return None if data is None else tuple(float(v) for v in data.coords)


def move(c, name, xy):
    c.update(name, Point(xy))
    c.rebuild()


class TestTailOutputs:
    def scene(self):
        return construction(
            {'A': (-3, 1), 'B': (3, 1), 'O': (0, 0), 'R': (2, 0)},
            Command('Line', ['A', 'B'], ['l']),
            Command('Circle', ['O', 'R'], ['c']),
            Command('Intersect', ['l', 'c'], ['P', 'Q']),
        )

    def test_secant_gives_both(self):
        c = self.scene()
        assert coords(c, 'P') is not None and coords(c, 'Q') is not None

    def test_tangency_leaves_no_stale_second_point(self):
        c = self.scene()
        move(c, 'A', (-3, 2))
        move(c, 'B', (3, 2))
        assert coords(c, 'P') == pytest.approx((0.0, 2.0))
        assert c.element('Q').data is None            # was the old secant point

    def test_no_intersection_clears_both(self):
        c = self.scene()
        move(c, 'A', (-3, 5))
        move(c, 'B', (3, 5))
        assert c.element('P').data is None and c.element('Q').data is None

    def test_fixed_outputs_keep_their_value(self):
        c = self.scene()
        c.element('Q').fixed = True
        before = coords(c, 'Q')
        move(c, 'A', (-3, 2))
        move(c, 'B', (3, 2))
        assert coords(c, 'Q') == before


class TestCircles:
    def test_circle_without_assert(self):
        assert Circle((0, 0), 0).radius == 0

    @pytest.mark.parametrize('make', [
        lambda: circle_pp(Point((1, 1)), Point((1, 1))),
        lambda: circle_pi(Point((1, 1)), 0),
        lambda: circle_pi(Point((1, 1)), -2),
        lambda: circle_pi(Point((1, 1)), float('nan')),
        lambda: circle_pm(Point((1, 1)), Measure(0, 1)),
        lambda: circle_ps(Point((1, 1)), Segment(np.array((2.0, 2.0)), np.array((2.0, 2.0)))),
    ])
    def test_nonpositive_radius_is_undefined(self, make):
        assert make() is None

    def test_regular_radius(self):
        assert circle_pi(Point((1, 1)), 2).radius == 2
        assert circle_pp(Point((0, 0)), Point((3, 4))).radius == 5

    def test_zero_radius_in_a_construction_logs_nothing(self, caplog):
        with caplog.at_level(logging.WARNING):
            c = construction({'O': (1, 1), 'R': (1, 1)}, Command('Circle', ['O', 'R'], ['c']))
        assert c.element('c').data is None
        assert not [r for r in caplog.records if 'failed' in r.getMessage()]


class TestLinePP:
    def test_near_coincident_points(self):
        assert line_pp(Point((1.0, 2.0)), Point((1.0 + 1e-15, 2.0))) is None
        assert line_pp(Point((1e6, 0.0)), Point((1e6 + 1e-7, 0.0))) is None

    def test_close_but_distinct_points(self):
        line = line_pp(Point((0.0, 0.0)), Point((1e-9, 0.0)))
        assert line is not None and np.allclose(np.abs(line.normal), (0, 1))

    def test_zero_normal_has_a_direction(self):
        line = Line((0, 0), 0)
        assert tuple(line.direction) == (0.0, 0.0)


def on_circle(name='P', seed=0):
    return construction({'O': (0, 0), 'R': (2, 0)}, Command('Circle', ['O', 'R'], ['c']),
                        Command('Point', ['c'], [name]), seed=seed)


class TestSeededRandomness:
    def test_same_seed_same_point(self):
        a, b = on_circle(), on_circle()
        assert coords(a, 'P') == coords(b, 'P')
        assert a.seed == 0 and isinstance(a.rng, np.random.Generator)

    def test_other_seed_or_name_other_point(self):
        a = on_circle()
        assert coords(on_circle(seed=7), 'P') != coords(a, 'P')
        assert coords(on_circle('Q'), 'Q') != coords(a, 'P')

    def test_rebuild_does_not_move_a_random_point(self):
        c = on_circle()
        before = coords(c, 'P')
        c.rebuild(full=True)
        assert coords(c, 'P') == before
        assert math.hypot(*before) == pytest.approx(2)

    def test_points_on_paths(self):
        pts = {'A': (0, 0), 'B': (4, 0)}
        cmds = lambda: [Command('Segment', ['A', 'B'], ['s']), Command('Line', ['A', 'B'], ['l']),
                        Command('Ray', ['A', 'B'], ['r']),
                        Command('Point', ['s'], ['S']), Command('Point', ['l'], ['L']),
                        Command('Point', ['r'], ['T'])]
        first = construction(pts, *cmds())
        second = construction(pts, *cmds())
        for name in 'SLT':
            assert coords(first, name) is not None
            assert coords(first, name) == coords(second, name), name

    def test_outside_apply_the_module_generator_is_used(self):
        assert lib_elements.current_rng() is lib_elements.current_rng()
        p = point_()
        assert all(math.isfinite(v) for v in p.coords)

    def test_seed_none_is_unseeded(self):
        c = on_circle(seed=None)
        assert math.hypot(*coords(c, 'P')) == pytest.approx(2)
