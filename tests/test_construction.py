"""Tests for Construction state management (construction.py).

Covers: add/update elements, command execution, dependency tracking, rebuild.
"""
import numpy as np
import pytest

from animageo.geo.lib_elements import (
    Point, Line, Segment, Circle, Angle, Polygon, Element,
)
from animageo.geo.lib_vars import Var, Measure, AngleSize
from animageo.geo.lib_commands import Command
from animageo.geo.construction import Construction, normalize_name


# ── normalize_name ────────────────────────────────────────────────────

class TestNormalizeName:
    def test_simple(self):
        assert normalize_name('A') == 'A'
        assert normalize_name('point1') == 'point1'

    def test_html_entities(self):
        assert normalize_name("A&apos;B") == 'A_primeB'

    def test_subscript_braces(self):
        assert normalize_name('M_{1}') == 'M_1'

    def test_prime(self):
        assert normalize_name("A'") == 'A_Prime'

    def test_digit_prefix(self):
        assert normalize_name('1abc') == 'var_1abc'

    def test_empty_string(self):
        """normalize_name should raise ValueError on empty strings."""
        with pytest.raises(ValueError):
            normalize_name('')


# ── Construction basics ────────────────────────────────────────────────

class TestConstructionBasics:
    def test_init(self):
        c = Construction()
        # starts with xAxis and yAxis
        assert len(c.elements) == 2
        assert c.element('xAxis') is not None
        assert c.element('yAxis') is not None

    def test_add_element(self):
        c = Construction()
        c.add(Element('A', Point([1, 2])))
        assert c.element('A') is not None
        assert np.allclose(c.element('A').data.coords, [1, 2])

    def test_add_var(self):
        c = Construction()
        c.add(Var('d', Measure(5, 1)))
        assert c.var('d') is not None
        assert c.var('d').data.value == 5

    def test_add_command(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        cmd = Command('Midpoint', ['A', 'B'], ['M'])
        c.add(cmd)
        assert len(c.commands) == 1

    def test_element_not_found(self):
        c = Construction()
        assert c.element('Z') is None

    def test_var_not_found(self):
        c = Construction()
        assert c.var('z') is None


# ── Construction update ────────────────────────────────────────────────

class TestConstructionUpdate:
    def test_update_existing(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.update('A', Point([5, 5]))
        assert np.allclose(c.element('A').data.coords, [5, 5])

    def test_update_creates_new(self):
        c = Construction()
        c.update('B', Point([3, 4]))
        assert c.element('B') is not None

    def test_update_var(self):
        c = Construction()
        c.add(Var('x', 10.0))
        c.update('x', 20.0)
        assert c.var('x').data == 20.0


# ── Construction rebuild ──────────────────────────────────────────────

class TestConstructionRebuild:
    def test_simple_rebuild(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.rebuild(full=True)
        assert c.element('M') is not None
        assert np.allclose(c.element('M').data.coords, [2, 0])

    def test_chain_rebuild(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([6, 0])))
        c.add(Element('C', Point([0, 8])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.add(Command('Segment', ['A', 'B'], ['s']))
        c.add(Command('Distance', ['A', 'B'], ['d']))
        c.add(Command('Circle', ['A', 'B', 'C'], ['circ']))
        c.rebuild(full=True)

        assert np.allclose(c.element('M').data.coords, [3, 0])
        assert isinstance(c.element('s').data, Segment)
        assert np.isclose(c.var('d').data.value, 6)
        assert isinstance(c.element('circ').data, Circle)

    def test_dependency_levels(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.add(Command('Segment', ['A', 'M'], ['s']))

        assert c.state['A']['level'] == 0
        assert c.state['B']['level'] == 0
        assert c.state['M']['level'] == 1
        assert c.state['s']['level'] == 2

    def test_incremental_rebuild(self):
        """Only unbuilt elements should be recomputed."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.rebuild(full=True)

        # Mark M as needing rebuild
        c.update('A', Point([2, 0]))
        log = c.rebuild()
        assert 'M' in log


# ── State tracking ─────────────────────────────────────────────────────

class TestStateTracking:
    def test_outputs_tracked(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        assert 'M' in c.state['A']['outputs']
        assert 'M' in c.state['B']['outputs']

    def test_inputs_tracked(self):
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        assert 'A' in c.state['M']['inputs']
        assert 'B' in c.state['M']['inputs']

    def test_phantom_variables(self):
        c = Construction()
        key1 = c.add_new_phantom()
        key2 = c.add_new_phantom()
        assert key1 == '_1'
        assert key2 == '_2'
        assert key1 in c.phantoms


# ── Intersect ordering ────────────────────────────────────────────────

class TestIntersectOrdering:
    def test_circle_circle_multi_output_uses_index_order(self):
        c = Construction()

        expected_m = np.array([-0.52, -1.76])
        expected_n = np.array([-0.3399427812, -2.4858094529])

        points = {
            'N9': [0.46171494, -2.03287612],
            'N1': expected_m,
            'N2': [-0.06706666, -1.50409452],
            'H7': [-0.26409452, -2.21293334],
            'N7': [-0.79287612, -1.68415174],
            'H1': [1.17626866, 0.24724438],
            'H6': [-2.95810549, 1.39501133],
        }
        for name, coords in points.items():
            c.add(Element(name, Point(coords)))

        c.add(Command('Circle', ['N9', 'N1', 'N2'], ['q']))
        c.add(Command('Circle', ['N1', 'H7', 'N7'], ['r']))
        c.add(Command('Intersect', ['q', 'r'], ['M', 'N']))
        c.add(Command('Intersect', ['q', 'r', '1'], ['I1']))
        c.add(Command('Intersect', ['q', 'r', '2'], ['I2']))
        c.add(Command('Circle', ['H1', 'H6', 'N'], ['t']))

        c.rebuild(full=True)

        assert np.allclose(c.element('M').data.coords, expected_m, atol=1e-6)
        assert np.allclose(c.element('N').data.coords, expected_n, atol=1e-6)
        assert np.allclose(c.element('M').data.coords, c.element('I1').data.coords, atol=1e-9)
        assert np.allclose(c.element('N').data.coords, c.element('I2').data.coords, atol=1e-9)
        assert np.allclose(c.element('t').data.center, [-1.1830068002, -0.2310044332], atol=1e-6)
        assert np.isclose(c.element('t').data.radius, 2.4072603966, atol=1e-6)


# ── Error recovery ─────────────────────────────────────────────────────

class TestApplyErrorRecovery:
    def test_failing_command_sets_outputs_to_none(self):
        """When a command result is None (e.g. concentric circles), outputs degrade gracefully."""
        c = Construction()
        c.add(Element('c1', Circle([0, 0], 5)))
        c.add(Element('c2', Circle([0, 0], 3)))
        c.add(Command('Intersect', ['c1', 'c2', '1'], ['P']))
        c.rebuild(full=True)
        p = c.element('P')
        assert p is not None
        assert p.data is None

    def test_rebuild_continues_after_failure(self):
        """A failing command should not prevent subsequent commands."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Element('c1', Circle([0, 0], 5)))
        c.add(Element('c2', Circle([0, 0], 3)))
        c.add(Command('Intersect', ['c1', 'c2', '1'], ['P']))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.rebuild(full=True)
        assert c.element('M') is not None
        assert np.allclose(c.element('M').data.coords, [2, 0])


# ── Cycle detection ────────────────────────────────────────────────────

class TestCycleDetection:
    def test_no_cycle_sorts_correctly(self):
        """Commands without cycles should be sorted in dependency order."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        # Add commands in reverse dependency order
        c.add(Command('Segment', ['A', 'M'], ['s']))
        c.add(Command('Midpoint', ['A', 'B'], ['M']))
        c.sortCommands()
        names = [cmd.name for cmd in c.commands]
        assert names.index('Midpoint') < names.index('Segment')

    def test_cycle_raises_error(self):
        """Circular dependencies should raise ValueError."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        cmd1 = Command('Midpoint', ['A', 'C'], ['B'])
        cmd2 = Command('Midpoint', ['B', 'A'], ['C'])
        c.commands = [cmd1, cmd2]
        with pytest.raises(ValueError, match="cycle"):
            c.sortCommands()

    def test_independent_commands_preserve_order(self):
        """Commands without dependencies should maintain original order."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Element('C', Point([0, 4])))
        c.add(Element('D', Point([4, 4])))
        c.add(Command('Midpoint', ['A', 'B'], ['M1']))
        c.add(Command('Midpoint', ['C', 'D'], ['M2']))
        original = [cmd.outputs[0] for cmd in c.commands]
        c.sortCommands()
        after = [cmd.outputs[0] for cmd in c.commands]
        assert original == after


# ── Batch style API ────────────────────────────────────────────────────

class TestBatchStyleAPI:
    def test_set_style_multiple_elements(self):
        """setElementStyle equivalent at construction level."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        c.add(Element('C', Point([0, 4])))
        for name in ['A', 'B', 'C']:
            elem = c.element(name)
            elem.style['stroke'] = '#ff0000'
            elem.style['fill_opacity'] = 0.5
        for name in ['A', 'B', 'C']:
            assert c.element(name).style['stroke'] == '#ff0000'
            assert c.element(name).style['fill_opacity'] == 0.5

    def test_set_visible_multiple_elements(self):
        """setVisible equivalent at construction level."""
        c = Construction()
        c.add(Element('A', Point([0, 0])))
        c.add(Element('B', Point([4, 0])))
        for name in ['A', 'B']:
            c.element(name).visible = False
        assert not c.element('A').visible
        assert not c.element('B').visible
        for name in ['A', 'B']:
            c.element(name).visible = True
        assert c.element('A').visible


class TestSceneBatchAPI:
    """Scene-level setElementStyle / setVisible auto-rebuild by default.

    Regression: previously both methods mutated ``elem.style`` / ``elem.visible``
    but never called ``updateGeoElements``, so the change was invisible
    until the next render pass. Users had to know to chain ``updateAllGeometry()``.
    """

    def _scene(self):
        from animageo.animageo import AnimaGeoScene
        s = AnimaGeoScene()
        s.putCode("A = Point(0, 0)\nB = Point(1, 1)\n")
        s.applyStyle(export={'size': [400, 300]})
        s.addAllGeometry(show=True)
        return s

    def test_setElementStyle_auto_rerenders(self):
        s = self._scene()
        old_mobj = s.mobject('A')
        assert old_mobj is not None
        s.setElementStyle(['A'], stroke='#ff0000')
        new_mobj = s.mobject('A')
        assert s.element('A').style['stroke'] == '#ff0000'
        # With auto-update, the mobject was replaced by a fresh render.
        assert new_mobj is not None

    def test_setElementStyle_update_false_defers(self):
        s = self._scene()
        s.setElementStyle(['A'], stroke='#00ff00', update=False)
        assert s.element('A').style['stroke'] == '#00ff00'

    def test_setVisible_auto_rerenders(self):
        s = self._scene()
        s.setVisible(['A'], False)
        assert s.element('A').visible is False
        # Idempotent: flipping back is fine.
        s.setVisible(['A'], True)
        assert s.element('A').visible is True


class TestTparamConstraintClassification:
    """Path-type classification for tparam points (conic/locus/function)."""

    def _constr_with_path(self, path_name, path_data, point_coords, tparam):
        from animageo.geo.lib_commands import Command
        c = Construction()
        c.add(Element(path_name, path_data, fixed=True))
        c.add(Element('D', Point(point_coords), tparam=tparam))
        c.add(Command('Point', [path_name], ['D']))
        return c

    def test_ellipse_constraint(self):
        from animageo.geo.lib_conic import Conic
        ell = Conic.from_coeffs(a=1/9, c=1/4, f=-1.0)
        c = self._constr_with_path('c', ell, [0.0, 2.0], np.pi / 2)
        info = c.get_independents()['D']
        assert info['type'] == 'tparam_point'
        assert info['constraint'] == 'ellipse'
        assert np.isclose(info['tparam'], np.pi / 2)

    def test_hyperbola_constraint_tuple_tparam(self):
        from animageo.geo.lib_conic import Conic
        hyp = Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0)
        c = self._constr_with_path('h', hyp, [-2.0, 0.0], (-1.0, 0.0))
        info = c.get_independents()['D']
        assert info['constraint'] == 'hyperbola'
        assert list(info['tparam']) == [-1.0, 0.0]   # JSON-safe list

    def test_parabola_constraint(self):
        from animageo.geo.lib_conic import Conic
        # y^2 = 4x  ->  -4x + y^2 = 0
        par = Conic.from_coeffs(c=1.0, d=-4.0)
        c = self._constr_with_path('p', par, [1.0, 2.0], 2.0)
        assert c.get_independents()['D']['constraint'] == 'parabola'

    def test_locus_constraint(self):
        from animageo.geo.lib_elements import LocusCurve
        loc = LocusCurve([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        c = self._constr_with_path('loc', loc, [1.0, 0.0], 0.5)
        assert c.get_independents()['D']['constraint'] == 'locus'

    def test_function_constraint(self):
        from animageo.geo.lib_function import Function
        f = Function("y = x^2")
        c = self._constr_with_path('f', f, [1.5, 2.25], 1.5)
        assert c.get_independents()['D']['constraint'] == 'function'

    def test_circle_constraint_unchanged(self):
        from animageo.geo.lib_elements import Circle
        circ = Circle([0.0, 0.0], 2.0)
        c = self._constr_with_path('k', circ, [0.0, 2.0], np.pi / 2)
        assert c.get_independents()['D']['constraint'] == 'circle'


class TestTparamFromCoords:
    def _ellipse_constr(self):
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        ell = Conic.from_coeffs(a=1/9, c=1/4, f=-1.0)   # x^2/9 + y^2/4 = 1
        c.add(Element('c', ell, fixed=True))
        c.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        c.add(Command('Point', ['c'], ['D']))
        return c

    def test_ellipse_coords_roundtrip(self):
        c = self._ellipse_constr()
        t = c.tparam_from_coords('D', [0.0, 2.0])
        assert np.isclose(t, np.pi / 2)
        # slightly off-curve coords still project sanely
        t2 = c.tparam_from_coords('D', [0.0, 2.05])
        assert np.isclose(t2, np.pi / 2)

    def test_hyperbola_returns_tuple(self):
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        hyp = Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0)
        c.add(Element('h', hyp, fixed=True))
        c.add(Element('D', Point([2.0, 0.0]), tparam=(1.0, 0.0)))
        c.add(Command('Point', ['h'], ['D']))
        bt = c.tparam_from_coords('D', [-2.0, 0.0])
        assert isinstance(bt, tuple) and bt[0] == -1.0

    def test_free_point_returns_none(self):
        c = Construction()
        c.add(Element('A', Point([1.0, 1.0])))
        assert c.tparam_from_coords('A', [2.0, 2.0]) is None

    def test_unknown_name_returns_none(self):
        c = Construction()
        assert c.tparam_from_coords('nope', [0.0, 0.0]) is None


class TestLateBuiltElementStyle:
    """An element the parser created while undefined (GGB saved NaN coords —
    e.g. an intersection of a circle that does not exist in the saved state)
    got an empty style: no z_index, no label defaults. When a later rebuild
    defined it, it rendered on the fill tier — a point UNDER the segments
    through it (repro: «Хроматические числа», D and E under q, n, p)."""

    def test_gets_its_type_defaults_when_first_built(self):
        from animageo.constants import Z_POINT

        c = Construction()
        c.update('D', None)
        c.update('D', Point([1, 2]))
        style = c.element('D').style
        assert style.get('z_index') == Z_POINT
        assert style.get('label_visible') is False
        assert not style.is_explicit('z_index')

    def test_keeps_writes_made_while_undefined(self):
        c = Construction()
        c.update('D', None)
        c.element('D').style['z_index'] = 7
        c.update('D', Point([1, 2]))
        style = c.element('D').style
        assert style['z_index'] == 7
        assert style.is_explicit('z_index')
