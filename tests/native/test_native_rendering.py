"""``native.render`` without manim: source view, appearance plan, overlaps,
argument errors (the drawing itself is in ``test_native_render_manim.py``)."""
import subprocess
import sys

import pytest

from animageo import native
from animageo.native import rendering
from tests.native.conftest import REPO_ROOT, DocBuilder, point_input


def doc(bounds=(-10, -10, 10, 10)):
    b = DocBuilder('rendering', registry_version='1.1', bounds=bounds)
    b.free('A', 0, 0).free('B', 3, 4).segment('s', 'A', 'B').circle('c', 'A', 'B')
    return b.doc


class TestSourceView:
    def test_from_bounds(self):
        view = native.source_view(doc((-6, -4, 10, 8)))
        assert view == {'ptWidth': 800.0, 'ptHeight': 600.0, 'ptUnit': 50.0,
                        'ptXZero': 300.0, 'ptYZero': 400.0}

    def test_default_bounds(self):
        d = doc()
        del d['viewDefaults']
        assert native.source_view(d) == {'ptWidth': 800.0, 'ptHeight': 800.0, 'ptUnit': 40.0,
                                         'ptXZero': 400.0, 'ptYZero': 400.0}

    def test_a_broken_document_is_refused(self):
        with pytest.raises(native.LoadError):
            native.source_view({'format': 'animageo-construction/v1'})


class TestAppearancePlan:
    def plan(self, appearance, **elements):
        d = doc()
        for el_id, name in elements.items():
            d['elements'][el_id]['displayName'] = name
        d['appearance'] = appearance
        return rendering.appearance_plan(d, 40.0)

    def test_defaults(self):
        plan, diagnostics = self.plan({})
        assert diagnostics == []
        assert plan['A'] == {'visible': True, 'style': {'display_name': 'A', 'label_visible': True,
                                                        'label_mode': 'label'}}
        assert plan['s'] == {'visible': True, 'style': {'display_name': 's', 'label_visible': False}}

    def test_modes(self):
        plan, _ = self.plan({'s': {'label': {'mode': 'value'}}, 'c': {'label': {'mode': 'name_value'}},
                             'B': {'label': {'mode': 'caption', 'text': 'вершина'}},
                             'A': {'visible': False, 'label': {'mode': 'none'}}})
        assert plan['s']['style']['label_mode'] == 'value'
        assert plan['c']['style']['label_mode'] == 'label_value'
        assert plan['B']['style'] == {'display_name': 'B', 'label_visible': True, 'label_mode': 'label',
                                      'label_text': 'вершина'}
        assert plan['A'] == {'visible': False, 'style': {'display_name': 'A', 'label_visible': False}}

    def test_locked_is_ignored(self):
        locked, diagnostics = self.plan({'A': {'locked': True}, 's': {'locked': False}})
        assert diagnostics == []
        assert locked == self.plan({})[0]

    def test_a_name_label_needs_a_name(self):
        d = doc()
        d['elements']['A']['displayName'] = ''
        plan, _ = rendering.appearance_plan(d, 40.0)
        assert plan['A']['style'] == {'label_visible': False}

    def test_offset_and_overrides(self):
        plan, diagnostics = self.plan({'A': {'label': {'mode': 'name', 'offsetWorld': [0.5, -0.25]},
                                             'overrides': {'stroke': '#cc3333', 'size_px': 7, 'bogus': 1}}})
        style = plan['A']['style']
        assert style['label_offset_px'] == [20.0, -10.0]
        assert style['label_placement_locked'] is True
        assert style['stroke'] == '#cc3333' and style['size_px'] == 7 and 'bogus' not in style
        assert diagnostics == [{'code': 'unknown_style_key', 'elementId': 'A', 'key': 'bogus'}]

    def test_bad_entries_are_reported(self):
        _, diagnostics = self.plan({'X': {}, 'A': {'label': {'mode': 'shout', 'offsetWorld': [1, 'a']}}})
        assert diagnostics == [
            {'code': 'unknown_element', 'elementId': 'X'},
            {'code': 'bad_label_mode', 'elementId': 'A', 'mode': 'shout'},
            {'code': 'bad_label_offset', 'elementId': 'A'},
        ]


class TestMarksInThePlan:
    def doc(self):
        b = DocBuilder('marks', registry_version='1.3')
        b.free('A', 0, 0).free('B', 4, 0).free('C', 0, 3).free('D', 4, 3)
        b.segment('s', 'A', 'B').segment('t', 'C', 'D').segment('u', 'A', 'C')
        b.angle('g', 'B', 'A', 'C').angle('h', 'C', 'D', 'B')
        b.equal_segments('m1', 's', 't', count=2).equal_segments('m2', 't', 'u', count=3)
        b.equal_angles('ma', 'g', 'h').right_mark('r', 'B', 'A', 'C')
        return b.doc

    def test_targets(self):
        assert rendering.mark_targets(self.doc()) == {'m1': ['s', 't'], 'm2': ['t', 'u'], 'ma': ['g', 'h']}

    def test_tick_counts_and_the_right_marker(self):
        plan, diagnostics = rendering.appearance_plan(self.doc(), 40.0)
        assert diagnostics == []
        ticks = {e: plan[e]['style'].get('tick_count') for e in ('s', 't', 'u', 'g', 'h')}
        assert ticks == {'s': 2, 't': 2, 'u': 3, 'g': 1, 'h': 1}      # t: the first mark in ID order wins
        assert plan['r']['style']['right_angle_marker'] is True
        for mark in ('m1', 'm2', 'ma', 'r'):
            assert plan[mark]['style']['label_visible'] is False
        assert 'tick_count' not in plan['m1']['style']

    def test_an_override_wins_and_a_hidden_mark_draws_nothing(self):
        d = self.doc()
        d['appearance'] = {'t': {'overrides': {'tick_count': 0}}, 'm2': {'visible': False},
                           'r': {'overrides': {'right_angle_marker': False}}}
        plan, _ = rendering.appearance_plan(d, 40.0)
        assert plan['t']['style']['tick_count'] == 0
        assert 'tick_count' not in plan['u']['style']
        assert plan['r']['style']['right_angle_marker'] is False

    def test_an_undefined_mark_draws_nothing(self):
        d = self.doc()
        plan, _ = rendering.appearance_plan(d, 40.0, inputs={'B': point_input(0, 0)})
        # B = A: the angle g and the right mark are undefined, m1 still marks s and t
        assert 'right_angle_marker' not in plan['r']['style']
        assert 'tick_count' not in plan['g']['style'] and 'tick_count' not in plan['h']['style']
        assert plan['s']['style']['tick_count'] == 2
        ev = native.evaluate(d, inputs={'B': point_input(0, 0)})
        assert rendering.appearance_plan(d, 40.0, evaluated=ev) == (plan, [])


def test_label_overlaps():
    boxes = {'A': [0, 0, 10, 10], 'B': [8, 8, 18, 18], 'C': [5, 5, 15, 15], 'D': [100, 0, 101, 1]}
    # A∩B = 4 < 0.15·100; A∩C = 25; B∩C = 49
    assert rendering.label_overlaps(boxes) == [['A', 'C'], ['B', 'C']]
    assert rendering.label_overlaps(boxes, share=0.04) == [['A', 'B'], ['A', 'C'], ['B', 'C']]


class TestArguments:
    @pytest.mark.parametrize('kwargs, error', [
        ({'fmt': 'mp4'}, NotImplementedError),
        ({'fmt': 'eps'}, NotImplementedError),
        ({'t': 1.0}, NotImplementedError),
        ({'timeline': {}}, NotImplementedError),
        ({'export_layout': {'export': {}, 'size': [1, 1]}}, ValueError),
        ({'export_layout': [1]}, ValueError),
        ({'inputs': {'A': point_input('x', 0)}}, ValueError),
        ({'inputs': {'s': point_input(0, 0)}}, ValueError),
    ])
    def test_refused_before_drawing(self, kwargs, error):
        with pytest.raises(error):
            native.render(doc(), **kwargs)

    def test_a_broken_document(self):
        with pytest.raises(native.LoadError):
            native.render({'format': 'animageo-construction/v1'})


BLOCKED = 'man' + 'im'


def test_without_the_renderer_a_clear_error():
    code = f"""
import importlib.abc, sys
class _Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == {BLOCKED!r} or name.startswith({BLOCKED!r} + '.'):
            raise ModuleNotFoundError('blocked: ' + name, name=name)
sys.meta_path.insert(0, _Block())
from animageo import native
from tests.native.test_native_rendering import doc
try:
    native.render(doc())
except RuntimeError as exc:
    print('ERR', exc)
"""
    proc = subprocess.run([sys.executable, '-c', code], cwd=REPO_ROOT, capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert 'ERR native.render needs ' + BLOCKED in proc.stdout
