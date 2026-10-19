"""The effects of a timeline at a time (1.11.0, ``native.timeline_effects``):
the enter and exit effects the video plays in the interval holding ``t``, by
the rule of the playback — a change of visibility at keyframe ``k+1`` plays in
``[t_k + at, t_k + at + duration]`` — and the presence of an element they
give, which ``resolve_paint`` draws at ``t``. Without manim."""
import pytest

from animageo import native
from animageo.native.paint import resolve_paint
from animageo.native.paint_fixtures import _Doc
from animageo.native.timeline import timeline_effects


def _doc():
    d = _Doc('effects').free('A', 0, 0).free('B', 5, 0).free('C', 1.5, 3.5)
    d.segment('a', 'B', 'C').segment('b', 'C', 'A').circle('k', 'A', 'B')
    d.op('number.free', {}, [('number', 'n', 'number')])
    d.doc['inputs']['n'] = {'kind': 'number', 'value': 1}
    return d.doc


LATE = {'version': 2, 'keyframes': [
    {'t': 0, 'visible': {'b': False, 'C': False}},
    {'t': 2, 'visible': {'b': True, 'C': True}, 'enter': {'C': {'effect': 'grow', 'duration': 1, 'at': 0.5}}},
    {'t': 3, 'visible': {'a': False}, 'exit': {'a': 'uncreate'}},
]}


def test_the_effects_at_a_time():
    doc = _doc()
    assert timeline_effects(doc, LATE, 0.1) == {
        'b': {'phase': 'enter', 'effect': 'fade', 'progress': pytest.approx(0.25), 'present': True},
        'C': {'phase': 'enter', 'effect': 'grow', 'progress': 0.0, 'present': False},
    }
    at_one = timeline_effects(doc, LATE, 1.0)
    assert at_one['b'] == {'phase': 'enter', 'effect': 'fade', 'progress': 1.0, 'present': True}
    assert at_one['C']['progress'] == pytest.approx(0.5) and at_one['C']['present']
    # at a keyframe: the interval that starts there, the video's frame
    assert timeline_effects(doc, LATE, 2.0) == {
        'a': {'phase': 'exit', 'effect': 'uncreate', 'progress': 0.0, 'present': True}}
    assert timeline_effects(doc, LATE, 2.2)['a']['progress'] == pytest.approx(0.5)
    # the end of the last interval
    assert timeline_effects(doc, LATE, 3.0) == {
        'a': {'phase': 'exit', 'effect': 'uncreate', 'progress': 1.0, 'present': False}}


def test_defaults_and_a_change_without_a_change():
    doc = _doc()
    timeline = {'version': 2, 'defaults': {'enter': {'effect': 'create', 'duration': 1.0}},
                'keyframes': [{'t': 0}, {'t': 1, 'visible': {'a': True, 'b': False}, 'show': ['k']},
                              {'t': 1.5, 'hide': ['k']}]}
    out = timeline_effects(doc, timeline, 0.5)
    # a and k are visible in the document: no change, no effect
    assert set(out) == {'b'} and out['b']['effect'] == 'fade'
    timeline['keyframes'][0]['visible'] = {'k': False}
    out = timeline_effects(doc, timeline, 0.5)
    assert out['k'] == {'phase': 'enter', 'effect': 'create', 'progress': 0.5, 'present': True}
    # the exit of the next interval, by the built-in default
    out = timeline_effects(doc, timeline, 1.25)
    assert out['k'] == {'phase': 'exit', 'effect': 'fade', 'progress': pytest.approx(0.625), 'present': True}
    # a window is cut at the end of its interval
    cut = {'version': 2, 'keyframes': [{'t': 0, 'visible': {'k': False}},
                                       {'t': 1, 'visible': {'k': True}, 'enter': {'k': {'duration': 3, 'at': 0.5}}}]}
    assert timeline_effects(doc, cut, 0.75)['k']['progress'] == pytest.approx(0.5)


def test_a_number_has_no_effect():
    timeline = {'version': 2, 'keyframes': [{'t': 0, 'visible': {'n': False}}, {'t': 1, 'visible': {'n': True}}]}
    assert timeline_effects(_doc(), timeline, 0.5) == {}


def test_resolve_paint_draws_the_presence():
    doc = _doc()
    els = resolve_paint(doc, None, 1.0, timeline=LATE)['elements']
    assert els['b']['drawn'] and els['b']['effect'] == {'phase': 'enter', 'effect': 'fade', 'progress': 1.0}
    assert els['C']['drawn'] and els['C']['effect']['progress'] == pytest.approx(0.5)
    els = resolve_paint(doc, None, 0.1, timeline=LATE)['elements']
    assert not els['C']['drawn'] and 'effect' not in els['C']
    assert els['a']['drawn'] and 'effect' not in els['a']
    els = resolve_paint(doc, None, 3.0, timeline=LATE)['elements']
    assert not els['a']['drawn']


def test_the_feature_is_announced():
    assert native.has('timeline.effects') and native.has('render.t.effects')
