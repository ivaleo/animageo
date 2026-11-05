"""The visible part of a line or a ray (1.12.0, ``native.line_display``):
the points on a line by the graph, the rules of the part, ``visible_range``,
the paint ``stroke.visibleWorld`` and its fixtures. Manim-free."""
import math

import pytest

from animageo import native
from animageo.native import line_display as ld
from animageo.native import paint_fixtures
from animageo.native.paint import resolve_paint
from animageo.native.paint_fixtures import _Doc, _ref

H = ld.DEFAULT_OVERHANG_PX / 100        # the default overhang in world units at ptUnitStyle 100


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for p, q in zip(a, b) for x, y in zip(p, q))


def on_line(b=(2, 0), c=1.5):
    d = _Doc('t').free('A', 0, 0).free('B', *b).line('l', 'A', 'B')
    d.op('point.on_path', {'path': _ref('l')}, [('point', 'C', 'point')])
    d.doc['inputs']['C'] = {'kind': 'pathParameter', 'value': c}
    return d


# ── the points on a line by the graph ───────────────────────────────────

class TestIncidentPoints:
    def test_defining_points_and_a_point_on_it(self):
        assert ld.incident_points(on_line().doc, 'l') == ['A', 'B', 'C']

    def test_a_point_that_only_lies_on_it_does_not_count(self):
        d = on_line().free('R', 5, 0)           # numerically on l, not by the graph
        assert ld.incident_points(d.doc, 'l') == ['A', 'B', 'C']

    def test_intersections_and_feet(self):
        d = _Doc('t').free('A', 0, 1).free('B', 2, 1).line('l', 'A', 'B').free('C', 5, 0).free('D', 5, 4)
        d.line('k', 'C', 'D').free('O', 4, 3).free('R', 4, 4.5).circle('c', 'O', 'R')
        d.op('intersect.line_line', {'first': _ref('l'), 'second': _ref('k')}, [('point', 'X', 'point')])
        d.op('intersect.line_circle', {'line': _ref('k'), 'circle': _ref('c')},
             [('first', 'Y1', 'point'), ('second', 'Y2', 'point')])
        d.free('P', 2, 4.6).op('point.projection', {'point': _ref('P'), 'base': _ref('k')}, [('foot', 'F', 'point')])
        assert ld.incident_points(d.doc, 'l') == ['A', 'B', 'X']
        assert ld.incident_points(d.doc, 'k') == ['C', 'D', 'F', 'X', 'Y1', 'Y2']

    def test_one_point_lines_and_siblings(self):
        d = _Doc('t').free('P', 0, 3).free('O', 0, 0).free('R', 1, 0).circle('c', 'O', 'R').free('A', 1, 1)
        d.free('B', 2, 1).line('m', 'A', 'B')
        d.op('line.parallel', {'point': _ref('P'), 'base': _ref('m')}, [('line', 'p', 'line')])
        d.op('line.tangents_from_point', {'point': _ref('P'), 'circle': _ref('c')},
             [('tangent.1', 't1', 'line'), ('tangent.2', 't2', 'line'), ('touch.1', 'T1', 'point'),
              ('touch.2', 'T2', 'point')])
        d.op('ray.at_angle', {'vertex': _ref('A'), 'a': _ref('B'), 'size': {'kind': 'number', 'value': 1.0}},
             [('ray', 'r', 'ray'), ('point', 'Q', 'point')])
        assert ld.incident_points(d.doc, 'p') == ['P']
        assert ld.incident_points(d.doc, 't1') == ['P', 'T1']
        assert ld.incident_points(d.doc, 't2') == ['P', 'T2']
        assert ld.incident_points(d.doc, 'r') == ['A', 'Q']
        spec = ld.line_spec(d.doc, 'p')
        assert spec.length_from == ('m', 'line') and spec.args == (('point', 'P', 'point'),)
        assert ld.line_spec(d.doc, 'r').origin == 'A'

    def test_on_conditions_by_ref_and_by_pair(self):
        d = _Doc('t').free('A', 0, 0).free('B', 2, 0).line('l', 'A', 'B').ray('r', 'A', 'B')
        d.free('P', 5, 0).free('Q', -2, 0).free('S', 7, 0)
        d.doc['conditions'] = [
            {'id': 'c1', 'mode': 'check', 'statement': {'kind': 'on', 'point': {'ref': 'P'}, 'object': {'ref': 'l'}}},
            {'id': 'c2', 'mode': 'check', 'statement': {'kind': 'on', 'point': {'ref': 'Q'},
                                                        'object': {'pair': ['B', 'A']}}},
            {'id': 'c3', 'mode': 'check', 'statement': {'kind': 'on', 'point': {'ref': 'S'},
                                                        'object': {'ref': 'r'}}}]
        assert ld.incident_points(d.doc, 'l') == ['A', 'B', 'P', 'Q']
        assert ld.incident_points(d.doc, 'r') == ['A', 'B', 'S']       # a pair is a line, not a ray

    def test_not_a_line(self):
        d = on_line().segment('s', 'A', 'B')
        assert ld.incident_points(d.doc, 's') == [] and ld.line_spec(d.doc, 's') is None
        assert ld.line_spec(d.doc, 'nope') is None


# ── the part ────────────────────────────────────────────────────────────

class TestVisibleSegment:
    def test_frame_by_default(self):
        assert ld.visible_segment(on_line().doc, 'l') is None

    def test_hull_and_overhang(self):
        d = on_line().overrides('l', line_display='incident')
        assert _close(ld.visible_segment(d.doc, 'l'), ((-H, 0), (3 + H, 0)))
        d.overrides('l', line_overhang_px=50)
        assert _close(ld.visible_segment(d.doc, 'l'), ((-0.5, 0), (3.5, 0)))
        assert _close(ld.visible_segment(d.doc, 'l', pt_unit_style=50), ((-1, 0), (4, 0)))

    def test_recomputed_for_other_inputs(self):
        d = on_line().overrides('l', line_display='incident')
        moved = {'B': {'kind': 'point', 'value': [0, 2]}}
        assert _close(ld.visible_segment(d.doc, 'l', inputs=moved), ((0, -H), (0, 3 + H)))
        ev = native.evaluate(d.doc, inputs=moved)
        assert ld.visible_segment(d.doc, 'l', evaluated=ev) == ld.visible_segment(d.doc, 'l', inputs=moved)

    def test_style_mapping_and_callable(self):
        d = on_line()
        keys = {'l': {'line_display': 'incident', 'line_overhang_px': 0}}
        assert _close(ld.visible_segment(d.doc, 'l', keys), ((0, 0), (3, 0)))
        assert ld.visible_segment(d.doc, 'l', lambda key: keys.get(key)) == ld.visible_segment(d.doc, 'l', keys)
        assert ld.visible_segment(d.doc, 'l', {'l': {'line_display': 'nope'}}) is None

    def test_a_ray_from_its_origin(self):
        d = _Doc('t').free('O', 1, 1).free('T', 3, 1).ray('r', 'O', 'T').free('C', 5, 0).free('D', 5, 4)
        d.line('k', 'C', 'D').op('intersect.line_line', {'first': _ref('r'), 'second': _ref('k')},
                                 [('point', 'X', 'point')])
        d.vector('w', 'C', 'D').op('ray.by_vector', {'origin': _ref('O'), 'vector': _ref('w')}, [('ray', 'v', 'ray')])
        d.overrides('r', line_display='incident').overrides('v', line_display='incident')
        assert _close(ld.visible_segment(d.doc, 'r'), ((1, 1), (5 + H, 1)))
        assert ld.visible_segment(d.doc, 'v') is None        # its origin only

    def test_one_point_takes_the_length_of_its_base(self):
        d = _Doc('t').free('D', 1, 0).free('E', 4, 0).line('m', 'D', 'E').segment('s', 'D', 'E').free('P', 2, 3)
        d.op('line.parallel', {'point': _ref('P'), 'base': _ref('m')}, [('line', 'p', 'line')])
        d.op('line.perpendicular', {'point': _ref('P'), 'base': _ref('s')}, [('line', 'q', 'line')])
        d.op('line.perpendicular_bisector', {'a': _ref('D'), 'b': _ref('E')}, [('line', 'b', 'line')])
        for el_id in ('p', 'q', 'b'):
            d.overrides(el_id, line_display='incident')
        # the base drawn to the frame: its part inside the frame
        assert _close(ld.visible_segment(d.doc, 'p', frame=(-1, -1, 7, 5)), ((-2, 3), (6, 3)))
        assert ld.visible_segment(d.doc, 'p', frame=None) == ld.visible_segment(d.doc, 'p')   # viewDefaults
        d.overrides('m', line_display='incident')
        assert _close(ld.visible_segment(d.doc, 'p'), ((0.5 - H, 3), (3.5 + H, 3)))
        (x0, y0), (x1, y1) = ld.visible_segment(d.doc, 'q')
        assert (x0, x1) == pytest.approx((2, 2)) and abs(y1 - y0) == pytest.approx(3)
        assert (y0 + y1) / 2 == pytest.approx(3)
        assert ld.visible_segment(d.doc, 'b') is None        # no point on it: the frame

    def test_visible_range(self):
        d = _Doc('t').free('A', 1, 1).free('B', 3, 2).line('l', 'A', 'B').ray('r', 'A', 'B')
        d.overrides('l', visible_range=[-0.5, 1.5]).overrides('r', visible_range=[2, -1])
        assert _close(ld.visible_segment(d.doc, 'l'), ((0, 0.5), (4, 2.5)))
        assert _close(ld.visible_segment(d.doc, 'r'), ((1, 1), (5, 3)))      # sorted, clamped to t >= 0
        d.overrides('l', visible_range=[0, 'x'], line_display='incident', line_overhang_px=0)
        assert _close(ld.visible_segment(d.doc, 'l'), ((1, 1), (3, 2)))      # not a range: the display

    def test_undefined_points_and_lines(self):
        d = on_line(b=(0, 0)).overrides('l', line_display='incident')       # A = B: no line
        assert ld.visible_segment(d.doc, 'l') is None

    def test_clip_segment(self):
        frame = (0, 0, 4, 4)
        assert ld.clip_segment(((1, 1), (3, 3)), frame) == ((1, 1), (3, 3), 0.0)
        start, end, offset = ld.clip_segment(((-1, 2), (6, 2)), frame)
        assert (start, end) == ((0, 2), (4, 2)) and offset == pytest.approx(1)
        assert ld.clip_segment(((5, 5), (6, 6)), frame) is None
        assert ld.clip_segment(((1, 1), (1, 1)), frame) is None


# ── the paint ───────────────────────────────────────────────────────────

class TestPaint:
    def test_visible_world_only_with_a_part(self):
        d = on_line().line('k', 'A', 'C').overrides('l', line_display='incident')
        out = resolve_paint(d.doc)['elements']
        assert _close(out['l']['stroke']['visibleWorld'], ((-H, 0), (3 + H, 0)))
        assert 'visibleWorld' not in out['k']['stroke']

    def test_a_style_sets_the_display(self):
        d = on_line()
        style = {'defaults': {'line': {'line_display': 'incident', 'line_overhang_px': 20}}}
        assert _close(resolve_paint(d.doc, style)['elements']['l']['stroke']['visibleWorld'], ((-0.2, 0), (3.2, 0)))

    def test_the_label_hangs_from_the_middle_of_the_part(self):
        """The label spot (``_get_anchor`` of the classic graph) is the middle
        of the drawn part, the same part as ``visibleWorld``."""
        d = on_line().overrides('l', line_display='incident').label('l')
        stroke = resolve_paint(d.doc)['elements']['l']
        (x0, y0), (x1, y1) = stroke['stroke']['visibleWorld']
        assert stroke['label']['spotWorld'] == pytest.approx([(x0 + x1) / 2, (y0 + y1) / 2])

    def test_the_label_of_a_clipped_part(self):
        d = on_line(c=10).overrides('l', line_display='incident').label('l')      # C at x = 20, far outside
        out = resolve_paint(d.doc)['elements']['l']
        (x0, _), (x1, _) = out['stroke']['visibleWorld']
        assert x1 == pytest.approx(20 + H)
        right = 2 * out['label']['spotWorld'][0] - x0       # the right end of the drawn part: the frame's
        assert 7 < right < 10

    def test_paint_agrees_with_the_pure_function(self):
        for case in _line_cases():
            if case['name'] == 'one_point':
                continue        # a base drawn to the frame: the frame of the export
            expect = case['expect']
            for el_id, entry in expect['elements'].items():
                world = (entry.get('stroke') or {}).get('visibleWorld')
                if world is None:
                    continue
                part = ld.visible_segment(case['document'], el_id, _resolved(case),
                                          pt_unit_style=expect['ptUnitStyle'])
                assert _close(part, world), (case['name'], el_id)

    def test_ineffective_on_a_segment(self):
        from animageo.native.rendering import appearance_plan
        d = on_line().segment('s', 'A', 'B').overrides('s', line_display='incident')
        _plan, diagnostics = appearance_plan(d.doc, 100.0)
        assert [(x['elementId'], x['key'], x['reason']) for x in diagnostics
                if x['code'] == 'style_key_ineffective'] == [('s', 'line_display', 'not_read')]

    def test_the_keys_of_the_contract(self):
        keys = native.style_keys()['types']
        for type_ in ('line', 'ray'):
            assert keys[type_]['keys']['line_display'] == {'unit': 'enum', 'default': 'frame',
                                                           'values': ['frame', 'incident']}
            assert keys[type_]['keys']['line_overhang_px'] == {'unit': 'px', 'default': ld.DEFAULT_OVERHANG_PX}
            assert keys[type_]['keys']['visible_range'] == {'unit': 'number[]', 'default': None}
        assert 'line_display' not in keys['segment']['keys']


_CASES = []


def _line_cases():
    """The cases of ``paint_lines`` (built once)."""
    if not _CASES:
        _CASES.extend(paint_fixtures._rows(paint_fixtures._lines()))
    return _CASES


def _resolved(case):
    """The keys of ``line_display`` of every element of the case: the
    document's overrides over the ``defaults`` of the case's style."""
    defaults = ((case['style'] or {}).get('defaults') or {})
    doc = case['document']

    def keys(key):
        type_ = doc['elements'][key]['type']
        out = dict(defaults.get(type_) or {})
        out.update(((doc.get('appearance') or {}).get(key) or {}).get('overrides') or {})
        return out
    return keys


def test_the_line_fixtures():
    cases = _line_cases()
    names = [c['name'] for c in cases]
    assert names == ['by_points', 'by_points_dragged', 'one_point', 'intersections', 'ray', 'visible_range',
                     'conditions', 'style_defaults']
    by_name = {c['name']: c['expect']['elements'] for c in cases}
    # the same document with another input: the part follows the points
    assert by_name['by_points']['l']['stroke']['visibleWorld'] != by_name['by_points_dragged']['l']['stroke'][
        'visibleWorld']
    for case, el_id in (('one_point', 'b'), ('ray', 'v'), ('ray', 'k'), ('style_defaults', 'b')):
        assert 'visibleWorld' not in by_name[case][el_id]['stroke'], (case, el_id)
    world = by_name['one_point']['g']['stroke']['visibleWorld']       # the frame length of f, centred at Q
    assert ((world[0][0] + world[1][0]) / 2, (world[0][1] + world[1][1]) / 2) == pytest.approx((5, 2))
    assert math.hypot(world[1][0] - world[0][0], world[1][1] - world[0][1]) == pytest.approx(
        math.hypot(6.2 / 3, 6.2))
