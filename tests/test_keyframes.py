"""Tests for keyframe animation system (keyframes.py, construction extensions).

Covers: interpolators, angular interpolation, KeyframeSequence parsing,
validation, Construction.update_tparam(), Construction.get_independents(),
interval building.
"""
import sys
import types
import importlib

# Prevent animageo.__init__ from importing animageo.animageo (which needs manim).
# We only need the geo subpackage and keyframes module for these tests.
_pkg = types.ModuleType('animageo')
_pkg.__path__ = [__import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'animageo')]
_pkg.__package__ = 'animageo'
sys.modules.setdefault('animageo', _pkg)

import numpy as np
import pytest

# Import construction first — it resolves the lib_vars/lib_elements circular import
from animageo.geo.construction import Construction
from animageo.geo.lib_elements import (
    Point, Line, Segment, Circle, Text, Element,
)
from animageo.geo.lib_vars import Var, Measure, AngleSize, Boolean
from animageo.geo.lib_commands import Command

from animageo.keyframes import (
    Interpolator,
    KeyframeSequence,
    apply_parsed_value,
    _parse_value,
    _interpolate_angle,
    _ease_linear,
    _ease_smooth,
    EASING_FUNCTIONS,
)


# ── Interpolator basics ──────────────────────────────────────────────────

class TestInterpolator:
    def test_linear_scalar(self):
        interp = Interpolator('x', 'var', 0.0, 10.0, easing=_ease_linear)
        assert interp.at(0) == 0.0
        assert interp.at(0.5) == 5.0
        assert interp.at(1.0) == 10.0

    def test_smooth_scalar(self):
        interp = Interpolator('x', 'var', 0.0, 10.0, easing=_ease_smooth)
        assert interp.at(0) == 0.0
        assert interp.at(1.0) == 10.0
        # smooth should be slower at edges than linear
        assert interp.at(0.1) < 1.0
        assert interp.at(0.9) > 9.0

    def test_point_interpolation(self):
        start = np.array([0.0, 0.0])
        end = np.array([4.0, 6.0])
        interp = Interpolator('A', 'point', start, end, easing=_ease_linear)
        mid = interp.at(0.5)
        assert np.allclose(mid, [2.0, 3.0])

    def test_bool_interpolation(self):
        interp = Interpolator('flag', 'bool', False, True, easing=_ease_linear)
        assert interp.at(0.0) == False
        assert interp.at(0.4) == False
        assert interp.at(0.5) == True
        assert interp.at(1.0) == True

    def test_tparam_linear_interpolation(self):
        interp = Interpolator('D', 'tparam_linear', 0.2, 0.8, easing=_ease_linear)
        assert np.isclose(interp.at(0), 0.2)
        assert np.isclose(interp.at(0.5), 0.5)
        assert np.isclose(interp.at(1.0), 0.8)


# ── Angular interpolation ────────────────────────────────────────────────

class TestAngularInterpolation:
    def test_short_path_same_half(self):
        # 0 -> pi/2: short path is +pi/2
        result = _interpolate_angle(0, np.pi / 2, 0.5, 'short')
        assert np.isclose(result, np.pi / 4)

    def test_short_path_wraps(self):
        # 0.1 -> 6.0 (close to 2*pi): short path should go backward
        result = _interpolate_angle(0.1, 6.0, 1.0, 'short')
        expected = 0.1 + (6.0 - 0.1 - 2 * np.pi)  # negative diff
        assert np.isclose(result, expected)

    def test_ccw_direction(self):
        # ccw from 0 to pi/2: goes +pi/2
        result = _interpolate_angle(0, np.pi / 2, 0.5, 'ccw')
        assert np.isclose(result, np.pi / 4)

    def test_ccw_long_way(self):
        # ccw from pi/2 to 0: goes +3*pi/2 (the long way around)
        result = _interpolate_angle(np.pi / 2, 0, 1.0, 'ccw')
        assert np.isclose(result, np.pi / 2 + 3 * np.pi / 2)

    def test_cw_direction(self):
        # cw from pi/2 to 0: goes -pi/2
        result = _interpolate_angle(np.pi / 2, 0, 1.0, 'cw')
        assert np.isclose(result, 0)

    def test_tparam_circle_via_interpolator(self):
        interp = Interpolator('P', 'tparam_circle', 0, np.pi, easing=_ease_linear, angle_direction='short')
        assert np.isclose(interp.at(0.5), np.pi / 2)


# ── Construction.update_tparam ────────────────────────────────────────────

class TestUpdateTparam:
    def test_update_tparam_basic(self):
        c = Construction()
        c.add(Element('center', Point([0, 0])))
        c.add(Element('c1', Circle([0, 0], 5)))
        c.add(Element('P', Point([5, 0]), tparam=0.0))
        c.add(Command('Point', ['c1'], ['P']))
        c.rebuild(full=True)

        # Update tparam
        c.update_tparam('P', np.pi / 2)
        assert c.element('P').tparam == np.pi / 2
        assert not c.state['P']['built']

    def test_update_tparam_marks_dependents(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('c1', Circle([0, 0], 5)))
        c.add(Element('P', Point([5, 0]), tparam=0.0))
        c.add(Command('Point', ['c1'], ['P']))
        c.add(Element('Q', Point([2.5, 0])))
        c.add(Command('Midpoint', ['A', 'P'], ['Q']))
        c.rebuild(full=True)

        # Update tparam on P — Q (midpoint of A,P) should be marked unbuilt
        c.update_tparam('P', np.pi)
        assert not c.state['P']['built']
        assert not c.state['Q']['built']

    def test_update_tparam_and_rebuild(self):
        c = Construction()
        c.add(Element('c1', Circle([0, 0], 5)))
        c.add(Element('P', Point([5, 0]), tparam=0.0))
        c.add(Command('Point', ['c1'], ['P']))
        c.rebuild(full=True)
        assert np.allclose(c.element('P').data.coords, [5, 0], atol=0.01)

        c.update_tparam('P', np.pi / 2)
        c.rebuild()
        # Point should now be at top of circle (0, 5)
        assert np.allclose(c.element('P').data.coords, [0, 5], atol=0.01)


# ── Construction.get_independents ─────────────────────────────────────────

class TestGetIndependents:
    def test_free_points(self):
        c = Construction()
        c.add(Element('A', Point([1, 2])))
        c.add(Element('B', Point([3, 4])))
        indeps = c.get_independents()
        assert 'A' in indeps
        assert indeps['A']['type'] == 'free_point'
        assert indeps['A']['coords'] == [1.0, 2.0]

    def test_free_text(self):
        c = Construction()
        c.add(Element('txt1', Text([('str', 'hello')], position=[1, 2])))
        c.add(Element('A', Point([0, 0])))
        c.add(Element('anchored', Text([('str', 'anchored')], anchor_point='A')))
        indeps = c.get_independents()
        assert indeps['txt1']['type'] == 'free_text'
        assert indeps['txt1']['position'] == [1.0, 2.0]
        assert 'anchored' not in indeps

    def test_excludes_dependent(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.rebuild(full=True)
        indeps = c.get_independents()
        assert 'A' in indeps
        assert 'B' in indeps
        assert 'M' not in indeps

    def test_free_var(self):
        c = Construction()
        c.add(Var('x', Measure(5, 1)))
        c.add(Var('angle', AngleSize(1.57)))
        c.add(Var('flag', Boolean(True)))
        c.add(Var('num', 42.0))
        indeps = c.get_independents()
        assert indeps['x']['type'] == 'measure'
        assert indeps['x']['value'] == 5
        assert indeps['angle']['type'] == 'angle'
        assert indeps['flag']['type'] == 'boolean'
        assert indeps['num']['type'] == 'number'

    def test_tparam_point_on_circle(self):
        c = Construction()
        c.add(Element('c1', Circle([0, 0], 5)))
        c.add(Element('P', Point([5, 0]), tparam=0.0))
        c.add(Command('Point', ['c1'], ['P']))
        c.rebuild(full=True)
        indeps = c.get_independents()
        assert 'P' in indeps
        assert indeps['P']['type'] == 'tparam_point'
        assert indeps['P']['constraint'] == 'circle'
        assert indeps['P']['tparam'] == 0.0

    def test_tparam_point_on_segment(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Segment', ['A', 'B'], ['s']))
        c.rebuild(full=True)
        c.add(Element('P', Point([2, 0]), tparam=0.5))
        c.add(Command('Point', ['s'], ['P']))
        c.rebuild(full=True)
        indeps = c.get_independents()
        assert 'P' in indeps
        assert indeps['P']['type'] == 'tparam_point'
        assert indeps['P']['constraint'] == 'segment'
        assert indeps['P']['tparam'] == 0.5

    def test_excludes_axes(self):
        """xAxis and yAxis should not show up (they have no Point data)."""
        c = Construction()
        indeps = c.get_independents()
        assert 'xAxis' not in indeps
        assert 'yAxis' not in indeps


# ── KeyframeSequence parsing ──────────────────────────────────────────────

def _make_test_construction():
    """Helper: construction with 2 free points, 1 var, 1 tparam point."""
    c = Construction()
    c.add(Element('A', Point([0, 0])))
    c.add(Element('B', Point([4, 0])))
    c.add(Var('x', 35.0))
    c.add(Element('c1', Circle([0, 0], 5)))
    c.add(Element('D', Point([5, 0]), tparam=0.0))
    c.add(Command('Point', ['c1'], ['D']))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


class TestKeyframeSequenceParsing:
    def test_basic_parsing(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'A': [0, 0], 'x': 35}},
                {'t': 2, 'values': {'A': [4, 4], 'x': 110}},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        assert len(seq.keyframes) == 2
        assert len(seq.intervals) == 1
        assert seq.intervals[0].duration == 2.0

    def test_three_keyframes(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'x': 35}},
                {'t': 1, 'values': {'x': 110}},
                {'t': 3, 'values': {'x': 35}},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        assert len(seq.intervals) == 2
        assert np.isclose(seq.intervals[0].duration, 1.0)
        assert np.isclose(seq.intervals[1].duration, 2.0)

    def test_tparam_point_parsing(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'D': {'tparam': 0.0}}},
                {'t': 2, 'values': {'D': {'tparam': 3.14, 'direction': 'ccw'}}},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        interps = seq.intervals[0].interpolators
        assert len(interps) == 1
        assert interps[0].kind == 'tparam_circle'
        assert interps[0].angle_direction == 'ccw'

    def test_free_text_position_parsing(self):
        c = _make_test_construction()
        c.add(Element('txt1', Text([('str', 'hello')], position=[1, 2])))
        data = {
            'keyframes': [
                {'t': 0, 'values': {'txt1': [1, 2]}},
                {'t': 2, 'values': {'txt1': [5, 6]}},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        interps = seq.intervals[0].interpolators
        assert len(interps) == 1
        assert interps[0].kind == 'text_position'
        assert np.allclose(interps[0].at(0.5), [3, 4])

    def test_visibility_changes(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'x': 35}},
                {'t': 2, 'values': {'x': 110}, 'show': ['M'], 'hide': ['B']},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        assert seq.intervals[0].show == ['M']
        assert seq.intervals[0].hide == ['B']

    def test_easing_selection(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'x': 35}},
                {'t': 2, 'values': {'x': 110}, 'easing': 'linear'},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        interp = seq.intervals[0].interpolators[0]
        assert interp.easing is _ease_linear

    def test_skips_unchanged_values(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'x': 35, 'A': [0, 0]}},
                {'t': 2, 'values': {'x': 35, 'A': [0, 0]}},  # same values
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        assert len(seq.intervals[0].interpolators) == 0

    def test_sorted_by_time(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 3, 'values': {'x': 35}},
                {'t': 0, 'values': {'x': 0}},
                {'t': 1, 'values': {'x': 110}},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        times = [kf.t for kf in seq.keyframes]
        assert times == [0, 1, 3]


class TestKeyframeSequenceValidation:
    def test_too_few_keyframes(self):
        c = _make_test_construction()
        with pytest.raises(ValueError, match="At least 2"):
            KeyframeSequence.from_json({'keyframes': [{'t': 0}]}, c)

    def test_unknown_element(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'NONEXISTENT': [0, 0]}},
                {'t': 1, 'values': {'NONEXISTENT': [1, 1]}},
            ]
        }
        with pytest.raises(ValueError, match="not an independent"):
            KeyframeSequence.from_json(data, c)

    def test_dependent_element_rejected(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'M': [0, 0]}},
                {'t': 1, 'values': {'M': [1, 1]}},
            ]
        }
        with pytest.raises(ValueError, match="not an independent"):
            KeyframeSequence.from_json(data, c)

    def test_unknown_easing(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'x': 0}},
                {'t': 1, 'values': {'x': 1}, 'easing': 'bounce_crazy'},
            ]
        }
        with pytest.raises(ValueError, match="unknown easing"):
            KeyframeSequence.from_json(data, c)

    def test_duplicate_times(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'x': 0}},
                {'t': 0, 'values': {'x': 1}},
            ]
        }
        with pytest.raises(ValueError, match="strictly increasing"):
            KeyframeSequence.from_json(data, c)

    def test_bad_point_value(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'A': [0, 0]}},
                {'t': 1, 'values': {'A': 42}},  # not [x,y]
            ]
        }
        with pytest.raises(ValueError, match="free_point requires"):
            KeyframeSequence.from_json(data, c)

    def test_bad_tparam_value(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'D': {'tparam': 0}}},
                {'t': 1, 'values': {'D': 42}},  # not {"tparam": ...}
            ]
        }
        with pytest.raises(ValueError, match="tparam_point requires"):
            KeyframeSequence.from_json(data, c)

    def test_unknown_show_element(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {}},
                {'t': 1, 'values': {}, 'show': ['GHOST']},
            ]
        }
        with pytest.raises(ValueError, match="not found"):
            KeyframeSequence.from_json(data, c)


# ── Interval interpolator values ──────────────────────────────────────────

class TestIntervalInterpolation:
    def test_point_moves(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'A': [0, 0]}, 'easing': 'linear'},
                {'t': 1, 'values': {'A': [10, 0]}, 'easing': 'linear'},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        interp = seq.intervals[0].interpolators[0]
        assert np.allclose(interp.at(0.5), [5, 0])

    def test_var_changes(self):
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'x': 0}, 'easing': 'linear'},
                {'t': 1, 'values': {'x': 100}, 'easing': 'linear'},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        interp = seq.intervals[0].interpolators[0]
        assert np.isclose(interp.at(0.25), 25.0)

    def test_value_carried_forward(self):
        """When a value is set in kf0 but not kf1, it should carry forward to kf2."""
        c = _make_test_construction()
        data = {
            'keyframes': [
                {'t': 0, 'values': {'A': [0, 0], 'x': 0}},
                {'t': 1, 'values': {'x': 50}},           # A not mentioned
                {'t': 2, 'values': {'A': [10, 0], 'x': 100}},
            ]
        }
        seq = KeyframeSequence.from_json(data, c)
        # Interval 0: only x changes (A stays same)
        interp_names_0 = {i.name for i in seq.intervals[0].interpolators}
        assert 'x' in interp_names_0
        # A shouldn't have an interpolator in interval 0 since it isn't in kf1.values

        # Interval 1: A should interpolate from [0,0] to [10,0]
        interp_names_1 = {i.name for i in seq.intervals[1].interpolators}
        assert 'A' in interp_names_1
        assert 'x' in interp_names_1


# ── Integration: full construction cycle ──────────────────────────────────

class TestIntegrationConstruction:
    def test_apply_parsed_value_updates_measure_value_and_marks_dependents(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Var('r', Measure(5, 1)))
        c.add(Command('Circle', ['A', 'r'], ['c1']))
        c.rebuild(full=True)
        assert c.state['c1']['built'] is True

        apply_parsed_value(c, 'r', 'var', 10.0)

        assert c.var('r').data.value == 10.0
        assert c.state['r']['built'] is True
        assert c.state['c1']['built'] is False

    def test_apply_parsed_value_updates_boolean_wrapper(self):
        c = Construction()
        c.add(Var('flag', Boolean(False)))

        apply_parsed_value(c, 'flag', 'bool', True)

        assert c.var('flag').data.value is True

    def test_apply_parsed_value_updates_free_text_position(self):
        c = Construction()
        c.add(Element('txt1', Text([('str', 'hello')], position=[1, 2])))

        apply_parsed_value(c, 'txt1', 'text_position', np.array([5.0, 6.0]))

        assert np.allclose(c.element('txt1').data.position, [5, 6])

    def test_parse_and_apply_first_keyframe_value_to_construction(self):
        c = _make_test_construction()
        seq = KeyframeSequence.from_json({
            'keyframes': [
                {'t': 0, 'values': {'A': [2, 1]}},
                {'t': 1, 'values': {'A': [3, 1]}},
            ],
        }, c)
        first = seq.keyframes[0]
        kind, val, _dir = _parse_value('A', first.values['A'], seq.element_info['A'])

        apply_parsed_value(c, 'A', kind, val)
        c.rebuild()

        assert np.allclose(c.element('A').data.coords, [2, 1])
        assert np.allclose(c.element('M').data.coords, [3, 0.5])

    def test_animate_free_point_rebuilds_midpoint(self):
        """Simulates what play_keyframes does: update free point, rebuild, check dependent."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.rebuild(full=True)
        assert np.allclose(c.element('M').data.coords, [2, 0])

        # Simulate keyframe: move A to (2, 0)
        c.update('A', Point([2, 0]))
        log = c.rebuild()
        assert 'M' in log
        assert np.allclose(c.element('M').data.coords, [3, 0])

    def test_animate_tparam_rebuilds_dependent(self):
        """Moving a constrained point via tparam updates its dependents."""
        c = Construction()
        c.add(Element('O', Point([0, 0])))
        c.add(Element('c1', Circle([0, 0], 5)))
        c.add(Element('P', Point([5, 0]), tparam=0.0))
        c.add(Command('Point', ['c1'], ['P']))
        c.add(Command('Segment', ['O', 'P'], ['s']))
        c.rebuild(full=True)

        # Move P to top of circle
        c.update_tparam('P', np.pi / 2)
        log = c.rebuild()
        assert 'P' in log
        assert 's' in log
        assert np.allclose(c.element('P').data.coords, [0, 5], atol=0.01)

    def test_simultaneous_point_and_var(self):
        """Simulate updating both a free point and a variable."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Var('r', 5.0))
        c.add(Command('Circle', ['A', 'r'], ['c1']))
        c.rebuild(full=True)
        assert isinstance(c.element('c1').data, Circle)
        assert c.element('c1').data.radius == 5.0

        # Move center and change radius simultaneously
        c.update('A', Point([1, 1]))
        c.update('r', 10.0)
        log = c.rebuild()
        assert 'c1' in log
        assert np.allclose(c.element('c1').data.center, [1, 1])
        assert c.element('c1').data.radius == 10.0


# ── _parse_value: [x,y] values, constraint-aware kinds, hyperbola ────────

class TestTparamPathParseValue:
    """[x,y] values + constraint-aware interpolation kinds (conic/locus/function)."""

    def _ellipse_constr(self):
        from animageo.geo.construction import Construction
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        c.add(Element('c', Conic.from_coeffs(a=1/9, c=1/4, f=-1.0), fixed=True))
        c.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        c.add(Command('Point', ['c'], ['D']))
        return c

    def test_kind_by_constraint(self):
        from animageo.keyframes import _parse_value
        cases = {
            'circle': 'tparam_circle',
            'ellipse': 'tparam_circle',
            'hyperbola': 'tparam_hyperbola',
            'parabola': 'tparam_linear',
            'segment': 'tparam_linear',
            'ray': 'tparam_linear',
            'line': 'tparam_linear',
            'locus': 'tparam_linear',
            'function': 'tparam_linear',
            'unknown': 'tparam_linear',
        }
        for constraint, expected in cases.items():
            info = {'type': 'tparam_point', 'constraint': constraint}
            value = {'tparam': [1.0, 0.5]} if constraint == 'hyperbola' \
                else {'tparam': 0.5}
            kind, _, _ = _parse_value('D', value, info)
            assert kind == expected, constraint

    def test_dict_tparam_still_works(self):
        from animageo.keyframes import _parse_value
        info = {'type': 'tparam_point', 'constraint': 'circle'}
        kind, val, direction = _parse_value(
            'D', {'tparam': 1.25, 'direction': 'ccw'}, info)
        assert (kind, val, direction) == ('tparam_circle', 1.25, 'ccw')

    def test_hyperbola_dict_list_value(self):
        from animageo.keyframes import _parse_value
        info = {'type': 'tparam_point', 'constraint': 'hyperbola'}
        kind, val, _ = _parse_value('D', {'tparam': [-1.0, 0.7]}, info)
        assert kind == 'tparam_hyperbola'
        assert val == (-1.0, 0.7)

    def test_xy_value_projects_via_construction(self):
        import numpy as np
        from animageo.keyframes import _parse_value
        c = self._ellipse_constr()
        info = c.get_independents()['D']
        kind, val, _ = _parse_value('D', [0.0, 2.0], info, c)
        assert kind == 'tparam_circle'
        assert np.isclose(val, np.pi / 2)

    def test_xy_without_construction_raises(self):
        import pytest
        from animageo.keyframes import _parse_value
        info = {'type': 'tparam_point', 'constraint': 'ellipse'}
        with pytest.raises(ValueError, match='construction'):
            _parse_value('D', [0.0, 2.0], info)

    def test_get_current_value_hyperbola_tuple(self):
        from animageo.keyframes import _get_current_value
        info = {'type': 'tparam_point', 'tparam': [-1.0, 0.5]}
        assert _get_current_value(info) == (-1.0, 0.5)


class TestHyperbolaInterpolatorAndPipeline:
    def test_interpolator_lerps_scalar_keeps_branch(self):
        from animageo.keyframes import Interpolator
        interp = Interpolator('D', 'tparam_hyperbola',
                              start=(1.0, 0.0), end=(1.0, 2.0),
                              easing=lambda t: t)
        b, t = interp.at(0.5)
        assert b == 1.0 and abs(t - 1.0) < 1e-12

    def test_interpolator_branch_snaps_at_half(self):
        from animageo.keyframes import Interpolator
        interp = Interpolator('D', 'tparam_hyperbola',
                              start=(1.0, 0.5), end=(-1.0, 0.5),
                              easing=lambda t: t)
        assert interp.at(0.25)[0] == 1.0
        assert interp.at(0.75)[0] == -1.0

    def _ellipse_constr(self):
        from animageo.geo.construction import Construction
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        c.add(Element('c', Conic.from_coeffs(a=1/9, c=1/4, f=-1.0), fixed=True))
        c.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        c.add(Command('Point', ['c'], ['D']))
        return c

    def test_from_json_with_xy_values_end_to_end(self):
        import numpy as np
        from animageo.keyframes import KeyframeSequence, apply_parsed_value
        c = self._ellipse_constr()
        seq = KeyframeSequence.from_json({
            "keyframes": [
                {"t": 0, "values": {"D": [3.0, 0.0]}},
                {"t": 2, "values": {"D": [0.0, 2.0]}, "easing": "linear"},
            ]
        }, c)
        interval = seq.intervals[0]
        assert len(interval.interpolators) == 1
        interp = interval.interpolators[0]
        assert interp.kind == 'tparam_circle'          # ellipse -> cyclic
        assert np.isclose(interp.at(0.0), 0.0)
        assert np.isclose(interp.at(1.0), np.pi / 2)
        # mid-interval: apply + rebuild moves D along the ellipse
        apply_parsed_value(c, 'D', interp.kind, interp.at(0.5))
        c.rebuild()
        x, y = c.element('D').data.coords
        assert np.isclose(x**2 / 9 + y**2 / 4, 1.0, atol=1e-9)
        assert x > 0 and y > 0                          # first quadrant


class TestSceneSnapshotTparamPaths:
    def _scene_with_hyperbola_point(self):
        from animageo.animageo import AnimaGeoScene
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        scene = AnimaGeoScene()
        scene.geo.add(Element(
            'h', Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0), fixed=True))
        scene.geo.add(Element('D', Point([2.0, 0.0]), tparam=(1.0, 0.0)))
        scene.geo.add(Command('Point', ['h'], ['D']))
        return scene

    def test_snapshot_keeps_hyperbola_tuple(self):
        scene = self._scene_with_hyperbola_point()
        raw, info_map = scene._snapshot_independents()
        assert raw['D'] == {'tparam': [1.0, 0.0]}
        assert info_map['D']['constraint'] == 'hyperbola'

    def test_apply_keyframe_state_accepts_xy(self):
        import numpy as np
        from animageo.animageo import AnimaGeoScene
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        from animageo.keyframes import Keyframe
        scene = AnimaGeoScene()
        scene.geo.add(Element(
            'c', Conic.from_coeffs(a=1/9, c=1/4, f=-1.0), fixed=True))
        scene.geo.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        scene.geo.add(Command('Point', ['c'], ['D']))
        kf = Keyframe(t=0, values={'D': [0.0, 2.0]}, show=[], hide=[],
                      easing_name='smooth')
        scene._apply_keyframe_state(kf, scene.geo.get_independents(),
                                    update_scene=False)
        assert np.allclose(scene.geo.element('D').data.coords, [0.0, 2.0],
                           atol=1e-9)
