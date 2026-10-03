"""point.on_path, path frames (kernel/paths.py) and native.project."""
import math

import pytest

from animageo import native
from animageo.native.kernel import paths
from animageo.native.kernel.paths import Frame, point_at, project
from tests.native.conftest import DocBuilder, path_input, point_input

TOL = 2e-9


def xy(p):
    return (p['x'], p['y'])


def segment(a, b):
    return Frame('affine', a, (b[0] - a[0], b[1] - a[1]), 0, 1)


SQUARE = Frame('perimeter', vertices=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))


class TestPointAt:
    def test_segment_and_clamp(self):
        f = segment((1.0, 2.0), (5.0, 4.0))
        assert xy(point_at(f, 0)) == (1.0, 2.0)
        assert xy(point_at(f, 1)) == (5.0, 4.0)
        assert xy(point_at(f, 0.5)) == (3.0, 3.0)
        assert xy(point_at(f, -0.5)) == (1.0, 2.0)
        assert xy(point_at(f, 1.5)) == (5.0, 4.0)

    def test_line_and_ray(self):
        line = Frame('affine', (1.0, 1.0), (2.0, 0.0))
        assert xy(point_at(line, 2)) == (5.0, 1.0)
        assert xy(point_at(line, -1)) == (-1.0, 1.0)
        ray = Frame('affine', (1.0, 1.0), (2.0, 0.0), 0, None)
        assert xy(point_at(ray, 2)) == (5.0, 1.0)
        assert xy(point_at(ray, -1)) == (1.0, 1.0)

    def test_circle(self):
        f = Frame('angle', (1.0, -1.0), radius=2.0)
        assert xy(point_at(f, 0)) == (3.0, -1.0)
        p = point_at(f, math.pi / 4)
        assert p == {'x': 1 + 2 * math.cos(math.pi / 4), 'y': -1 + 2 * math.sin(math.pi / 4)}
        assert point_at(f, 7) == {'x': 1 + 2 * math.cos(7), 'y': -1 + 2 * math.sin(7)}

    def test_polygon_sides_and_wrap(self):
        assert xy(point_at(SQUARE, 0)) == (0.0, 0.0)
        assert xy(point_at(SQUARE, 0.5)) == (0.5, 0.0)
        assert xy(point_at(SQUARE, 1.25)) == (1.0, 0.25)
        assert xy(point_at(SQUARE, 3.5)) == (0.0, 0.5)
        assert xy(point_at(SQUARE, 4)) == (0.0, 0.0)
        assert xy(point_at(SQUARE, 4.5)) == (0.5, 0.0)
        assert xy(point_at(SQUARE, -0.5)) == (0.0, 0.5)
        assert xy(point_at(SQUARE, -4)) == (0.0, 0.0)

    def test_polygon_wrap_never_leaves_the_range(self):
        # t / n rounds to an integer although t is just below it: t' < 0 is
        # moved into [0, n), and t' = n becomes 0.
        tri = Frame('perimeter', vertices=((0.0, 0.0), (3.0, 0.0), (0.0, 3.0)))
        for t in (3 - 2 ** -51, -2 ** -60, 6 - 2 ** -50, -3 - 2 ** -51, 1e-300, -1e-300):
            p = point_at(tri, t)
            assert all(math.isfinite(v) for v in xy(p)), t
            assert paths.distance_to_path(p['x'], p['y'], 'polygon',
                                          {'vertices': [[0, 0], [3, 0], [0, 3]]}) < 1e-12

    def test_degenerate_parts_still_give_a_point(self):
        assert xy(point_at(segment((2.0, 2.0), (2.0, 2.0)), 0.7)) == (2.0, 2.0)
        same = Frame('perimeter', vertices=((1.0, 1.0),) * 3)
        assert xy(point_at(same, 1.5)) == (1.0, 1.0)


class TestProject:
    @pytest.mark.parametrize('t', [0, 0.1, 0.25, 0.5, 0.9, 1])
    def test_segment_round_trip(self, t):
        f = segment((1.0, 2.0), (5.0, -4.0))
        assert project(f, *xy(point_at(f, t)), TOL) == pytest.approx(t, abs=1e-12)

    @pytest.mark.parametrize('t', [-3, -0.5, 0, 0.5, 2, 10])
    def test_line_round_trip(self, t):
        f = Frame('affine', (1.0, 2.0), (3.0, -1.0))
        assert project(f, *xy(point_at(f, t)), TOL) == pytest.approx(t, abs=1e-12)

    @pytest.mark.parametrize('t', [0, 0.5, 1, 2.5, 6.25])
    def test_angle_round_trip(self, t):
        f = Frame('angle', (1.0, -1.0), radius=2.0)
        assert project(f, *xy(point_at(f, t)), TOL) == pytest.approx(t, abs=1e-12)

    @pytest.mark.parametrize('t', [0, 0.25, 1, 1.75, 2.5, 3.9])
    def test_perimeter_round_trip(self, t):
        assert project(SQUARE, *xy(point_at(SQUARE, t)), TOL) == pytest.approx(t, abs=1e-12)

    def test_clamps(self):
        assert project(segment((0.0, 0.0), (2.0, 0.0)), -5, 1, TOL) == 0
        assert project(segment((0.0, 0.0), (2.0, 0.0)), 5, 1, TOL) == 1
        assert project(Frame('affine', (0.0, 0.0), (2.0, 0.0), 0, None), -5, 1, TOL) == 0
        assert project(Frame('affine', (0.0, 0.0), (2.0, 0.0)), -5, 1, TOL) == -2.5

    def test_ties_go_to_the_smallest_parameter(self):
        assert project(Frame('angle', (1.0, 1.0), radius=2.0), 1, 1, TOL) == 0
        assert project(SQUARE, 0.5, 0.5, TOL) == 0.5          # equidistant from every side
        assert project(SQUARE, -1, -1, TOL) == 0              # corner V0: 0, not 4
        assert project(SQUARE, 2, -1, TOL) == 1               # corner V1
        assert project(segment((2.0, 2.0), (2.0, 2.0)), 5, 5, TOL) == 0

    def test_angle_range(self):
        f = Frame('angle', (0.0, 0.0), radius=1.0)
        assert project(f, 1, -1e-300, TOL) == 0            # -1e-300 + 2π rounds to 2π
        assert project(f, 0, -1, TOL) == pytest.approx(1.5 * math.pi)


def on_path_doc(path_kind='segment', t=0.5):
    b = DocBuilder('on_path', registry_version='1.1')
    b.free('A', 1, 2).free('B', 5, 4).free('C', 1, 6)
    {'segment': lambda: b.segment('p', 'A', 'B'),
     'line': lambda: b.line('p', 'A', 'B'),
     'ray': lambda: b.ray('p', 'A', 'B'),
     'circle': lambda: b.circle('p', 'A', 'B'),
     'polygon': lambda: b.polygon('p', 'A', 'B', 'C')}[path_kind]()
    return b.on_path('P', 'p', t)


class TestEvaluate:
    @pytest.mark.parametrize('kind, t, expected', [
        ('segment', 0.5, (3.0, 3.0)),
        ('segment', 2, (5.0, 4.0)),
        ('line', 2, (9.0, 6.0)),
        ('line', -1, (-3.0, 0.0)),
        ('ray', 2, (9.0, 6.0)),
        ('ray', -1, (1.0, 2.0)),
        ('polygon', 1.5, (3.0, 5.0)),
        ('polygon', 3, (1.0, 2.0)),
    ])
    def test_values_in_the_producer_frame(self, kind, t, expected):
        ev = native.evaluate(on_path_doc(kind, t).doc)
        assert ev.elements['P'] == {'state': 'defined', 'type': 'point',
                                    'value': {'x': expected[0], 'y': expected[1]}}
        assert native.check(on_path_doc(kind, t).doc).results['op_P:on_path'] == 'passed'

    def test_circle(self):
        ev = native.evaluate(on_path_doc('circle', 0).doc)
        r = math.hypot(4, 2)
        assert ev.elements['P']['value'] == {'x': 1 + r, 'y': 2.0}

    def test_the_point_moves_with_the_line_points(self):
        doc = on_path_doc('line', 0.25).doc
        moved = native.evaluate(doc, inputs={'A': point_input(-3, 0), 'B': point_input(5, 4)})
        assert moved.elements['P']['value'] == {'x': -1.0, 'y': 1.0}

    def test_upstream(self):
        doc = on_path_doc('circle', 1).doc
        ev = native.evaluate(doc, inputs={'B': point_input(1, 2)})
        assert ev.elements['P'] == {'state': 'undefined', 'type': 'point', 'reason': 'upstream', 'cause': 'p'}

    @pytest.mark.parametrize('value', [None, point_input(1, 2)])
    def test_a_missing_or_foreign_input_is_a_schema_error(self, value):
        b = on_path_doc('segment')
        if value is None:
            del b.doc['inputs']['P']
        else:
            b.doc['inputs']['P'] = value
        assert native.evaluate(b.doc).elements['P']['reason'] == 'schema'

    @pytest.mark.parametrize('value', [
        {'kind': 'pathParameter', 'value': float('nan')},
        {'kind': 'pathParameter', 'value': True},
        {'kind': 'pathParameter', 'value': '0.5'},
        {'kind': 'pathParameter', 'value': 0.5, 'branch': 0},
        {'kind': 'pathParameter', 'value': 0.5, 'extra': 1},
    ])
    def test_a_broken_input_value(self, value):
        b = on_path_doc('segment')
        with pytest.raises(ValueError, match='pathParameter'):
            native.evaluate(b.doc, inputs={'P': value})
        b.doc['inputs']['P'] = value
        with pytest.raises(native.LoadError):
            native.evaluate(b.doc)

    def test_branch_is_read_and_ignored(self):
        b = on_path_doc('segment')
        b.doc['inputs']['P'] = {'kind': 'pathParameter', 'value': 0.5, 'branch': -1}
        assert native.evaluate(b.doc).elements['P']['value'] == {'x': 3.0, 'y': 3.0}

    def test_a_point_is_not_a_path(self):
        b = DocBuilder('np', registry_version='1.1').free('A', 1, 2).on_path('P', 'A', 0.5)
        assert native.evaluate(b.doc).elements['P']['reason'] == 'type_mismatch'

    def test_case_inputs_by_kind(self):
        doc = on_path_doc('segment').doc
        assert native.evaluate(doc, inputs={'P': path_input(1)}).elements['P']['value'] == {'x': 5.0, 'y': 4.0}
        with pytest.raises(ValueError, match='pathParameter'):
            native.evaluate(doc, inputs={'P': point_input(1, 1)})
        with pytest.raises(ValueError, match='point'):
            native.evaluate(doc, inputs={'A': path_input(1)})

    def test_path_parameters_do_not_change_the_scale(self):
        doc = on_path_doc('line', 0.5).doc
        assert native.evaluate(doc, inputs={'P': path_input(1e6)}).scale == native.evaluate(doc).scale

    def test_validate(self):
        b = on_path_doc('segment')
        assert native.validate(b.doc) == []
        b.doc['inputs']['P'] = point_input(1, 1)
        assert [i.code for i in native.validate(b.doc)] == ['type_mismatch']
        del b.doc['inputs']['P']
        assert [i.code for i in native.validate(b.doc)] == ['missing_input']

    def test_a_point_on_a_path_feeds_further_ops(self):
        b = on_path_doc('segment', 0.5)
        b.midpoint('M', 'P', 'C')
        assert native.evaluate(b.doc).elements['M']['value'] == {'x': 2.0, 'y': 4.5}


class TestNativeProject:
    def test_by_path_and_by_point(self):
        doc = on_path_doc('segment').doc
        assert native.project(doc, 'p', (3, 3)) == 0.5
        assert native.project(doc, 'P', (5, 4)) == 1.0
        assert native.project(doc, 'P', (100, 100)) == 1.0

    def test_line_frame_of_the_producer(self):
        doc = on_path_doc('line').doc
        assert native.project(doc, 'P', (9, 6)) == 2.0
        assert native.project(doc, 'P', (9, 6), inputs={'B': point_input(3, 3)}) == 4.0

    def test_round_trip_through_evaluate(self):
        for kind in ('segment', 'line', 'ray', 'circle', 'polygon'):
            doc = on_path_doc(kind, 0.3).doc
            x, y = xy(native.evaluate(doc).elements['P']['value'])
            assert native.project(doc, 'P', (x, y)) == pytest.approx(0.3, abs=1e-12), kind

    def test_undefined_and_errors(self):
        doc = on_path_doc('circle').doc
        assert native.project(doc, 'P', (0, 0), inputs={'B': point_input(1, 2)}) is None
        with pytest.raises(ValueError, match='not a path'):
            native.project(doc, 'A', (0, 0))
        with pytest.raises(ValueError, match='unknown'):
            native.project(doc, 'ghost', (0, 0))
