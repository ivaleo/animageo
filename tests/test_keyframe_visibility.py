"""Keyframes v2 phase 2: visibility maps + entrance/exit effects."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import (
    Keyframe, KeyframeSequence, ENTER_EFFECTS, EXIT_EFFECTS,
    DEFAULT_EFFECT_DURATION,
)


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes, **top):
    return {'version': 2, 'keyframes': keyframes, **top}


class TestVisibilityParsing:
    def test_visible_map_parsed(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ]), _construction())
        assert seq.keyframes[0].visible == {'M': False}
        assert seq.keyframes[1].visible == {'M': True}

    def test_show_hide_fold_into_visible(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'show': ['M'], 'hide': ['B']},
        ]), _construction())
        assert seq.keyframes[1].visible == {'M': True, 'B': False}

    def test_enter_exit_specs_parsed_with_defaults_filled(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True},
             'enter': {'M': {'effect': 'create', 'duration': 0.8, 'at': 0.1}}},
        ]), _construction())
        assert seq.keyframes[1].enter['M'] == {
            'effect': 'create', 'duration': 0.8, 'at': 0.1}

    def test_enter_effect_shorthand_string(self):
        # "enter": {"M": "grow"} is shorthand for {"effect": "grow"}
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'grow'}},
        ]), _construction())
        assert seq.keyframes[1].enter['M']['effect'] == 'grow'
        assert seq.keyframes[1].enter['M']['duration'] == DEFAULT_EFFECT_DURATION
        assert seq.keyframes[1].enter['M']['at'] == 0.0

    def test_top_level_defaults_parsed(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0}, {'t': 1},
        ], defaults={'easing': 'linear',
                     'enter': {'effect': 'create', 'duration': 0.6}}), _construction())
        assert seq.defaults['easing'] == 'linear'
        assert seq.defaults['enter'] == {'effect': 'create', 'duration': 0.6}

    def test_visible_requires_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'visible': {'M': False}}, {'t': 1},
            ]}, _construction())

    def test_enter_requires_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0}, {'t': 1, 'enter': {'M': 'fade'}},
            ]}, _construction())

    def test_unknown_effect_rejected(self):
        with pytest.raises(ValueError, match='effect'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'M': False}},
                {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'sparkle'}},
            ]), _construction())

    def test_write_effect_accepted_for_enter_in_phase3(self):
        # Phase 3 Task 2 lifted the 'write' rejection for enter effects; see
        # tests/test_keyframe_labels_v3.py::TestWriteEffect for full coverage.
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'write'}},
        ]), _construction())
        assert seq.keyframes[1].enter['M']['effect'] == 'write'

    def test_exit_effect_validated_against_exit_set(self):
        # 'create' is an entrance effect, not valid for exit
        with pytest.raises(ValueError, match='exit'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'M': True}},
                {'t': 1, 'visible': {'M': False}, 'exit': {'M': 'create'}},
            ]), _construction())

    def test_visible_unknown_element_rejected(self):
        with pytest.raises(ValueError, match='GHOST'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'GHOST': False}}, {'t': 1},
            ]), _construction())

    def test_effect_sets_membership(self):
        # 'write' was added to ENTER_EFFECTS in phase 3 Task 2 (still absent
        # from EXIT_EFFECTS -- write remains enter-only).
        assert ENTER_EFFECTS == ('fade', 'none', 'create', 'grow', 'write')
        assert EXIT_EFFECTS == ('fade', 'none', 'uncreate', 'shrink')

    def test_defaults_effect_key_always_present(self):
        # defaults.enter without an explicit 'effect' must still carry a
        # resolved 'effect' (downstream reads spec['effect'] directly).
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0}, {'t': 1},
        ], defaults={'enter': {'duration': 0.6}}), _construction())
        assert seq.defaults['enter']['effect'] == 'fade'   # default effect
        assert seq.defaults['enter']['duration'] == 0.6

    def test_defaults_effect_still_validated_when_key_absent(self):
        # a bad explicit effect in defaults still rejected
        with pytest.raises(ValueError):
            KeyframeSequence.from_json(_v2([{'t': 0}, {'t': 1}],
                defaults={'enter': {'effect': 'bogus'}}), _construction())

    def test_write_allowed_in_defaults_enter(self):
        # 'write' is a valid ENTER_EFFECTS member (phase 3); defaults.enter
        # must accept it the same way per-keyframe 'enter' does -- no special
        # "phase 3" rejection.
        seq = KeyframeSequence.from_json(_v2([{'t': 0}, {'t': 1}],
            defaults={'enter': {'effect': 'write'}}), _construction())
        assert seq.defaults['enter']['effect'] == 'write'

    def test_write_still_rejected_in_defaults_exit(self):
        # 'write' is enter-only -- absent from EXIT_EFFECTS -- so
        # defaults.exit must still reject it (normal unknown-effect error).
        with pytest.raises(ValueError, match='exit'):
            KeyframeSequence.from_json(_v2([{'t': 0}, {'t': 1}],
                defaults={'exit': {'effect': 'write'}}), _construction())

    def test_defaults_requires_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [{'t': 0}, {'t': 1}],
                'defaults': {'enter': 'fade'}}, _construction())


from animageo.keyframes import EffectSpec


class TestBindVisibility:
    def _seq(self, kfs, **top):
        return KeyframeSequence.from_json(_v2(kfs, **top), _construction())

    def test_enter_effect_created_on_false_to_true(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert (e.name, e.kind, e.direction) == ('M', 'fade', 'in')
        assert e.start == 0.0 and e.duration == pytest.approx(0.4)
        assert seq.intervals[0].exit_effects == []

    def test_exit_effect_created_on_true_to_false(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': True}},
            {'t': 1, 'visible': {'M': False}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].exit_effects
        assert (e.name, e.kind, e.direction) == ('M', 'fade', 'out')

    def test_no_change_no_effect(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': True}},
            {'t': 1, 'visible': {'M': True}},
        ])
        seq.bind_visibility()
        assert seq.intervals[0].enter_effects == []
        assert seq.intervals[0].exit_effects == []

    def test_explicit_effect_and_timing_used(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 2, 'visible': {'M': True},
             'enter': {'M': {'effect': 'grow', 'duration': 0.8, 'at': 0.3}}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert e.kind == 'grow' and e.start == 0.3 and e.duration == pytest.approx(0.8)

    def test_duration_clamped_to_interval(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 0.5, 'visible': {'M': True},
             'enter': {'M': {'effect': 'fade', 'duration': 2.0, 'at': 0.0}}},
        ])
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert e.duration == pytest.approx(0.5)   # clamped to interval

    def test_defaults_enter_used_when_no_per_kf_effect(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ], defaults={'enter': {'effect': 'create', 'duration': 0.6}})
        seq.bind_visibility()
        (e,) = seq.intervals[0].enter_effects
        assert e.kind == 'create' and e.duration == pytest.approx(0.6)

    def test_initial_visibility_recorded(self):
        seq = self._seq([
            {'t': 0, 'visible': {'M': False, 'B': True}},
            {'t': 1, 'visible': {'M': True}},
        ])
        seq.bind_visibility()
        assert seq.initial_visibility.get('M') is False
        assert seq.initial_visibility.get('B') is True

    def test_has_visibility_effects(self):
        seq = self._seq([{'t': 0, 'visible': {'M': False}},
                         {'t': 1, 'visible': {'M': True}}])
        seq.bind_visibility()
        assert seq.has_visibility_effects() is True
        seq2 = self._seq([{'t': 0}, {'t': 1}])
        seq2.bind_visibility()
        assert seq2.has_visibility_effects() is False

    def test_redeclaring_already_visible_element_makes_no_effect(self):
        # M is visible in the construction and NOT listed in keyframe 0.
        # Re-declaring it True at kf1 must NOT create a spurious enter effect.
        c = _construction()
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},                       # kf0 does not mention M
            {'t': 1, 'visible': {'M': True}},
        ]), c)
        seq.bind_visibility(get_element=c.element)
        assert seq.intervals[0].enter_effects == []
        assert seq.intervals[0].exit_effects == []

    def test_hiding_construction_visible_element_makes_exit(self):
        # M visible in construction, not in kf0; kf1 hides it -> exit effect.
        c = _construction()
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'visible': {'M': False}},
        ]), c)
        seq.bind_visibility(get_element=c.element)
        (e,) = seq.intervals[0].exit_effects
        assert e.name == 'M' and e.direction == 'out'

    def test_seed_defaults_true_without_get_element(self):
        # Backwards-compat: without get_element, unlisted element seeds True,
        # so re-declaring True is a no-op (no spurious enter).
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'visible': {'M': True}},
        ]), _construction())
        seq.bind_visibility()   # no get_element
        assert seq.intervals[0].enter_effects == []


from animageo.animageo import AnimaGeoScene


def _scene():
    s = AnimaGeoScene()
    c = s.geo
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return s


class TestEffectAlpha:
    def test_in_ramps_up(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'fade', start=0.0, duration=1.0, direction='in')
        assert s._effect_alpha(spec, 0.0) == 0.0
        assert s._effect_alpha(spec, 0.5) == pytest.approx(0.5)
        assert s._effect_alpha(spec, 1.0) == 1.0

    def test_out_ramps_down(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'fade', start=0.0, duration=1.0, direction='out')
        assert s._effect_alpha(spec, 0.0) == 1.0
        assert s._effect_alpha(spec, 1.0) == 0.0

    def test_start_offset_respected(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'fade', start=0.5, duration=0.5, direction='in')
        assert s._effect_alpha(spec, 0.4) == 0.0     # before start
        assert s._effect_alpha(spec, 0.75) == pytest.approx(0.5)
        assert s._effect_alpha(spec, 1.0) == 1.0

    def test_zero_duration_steps(self):
        s = AnimaGeoScene()
        spec = EffectSpec('M', 'none', start=0.5, duration=0.0, direction='in')
        assert s._effect_alpha(spec, 0.49) == 0.0
        assert s._effect_alpha(spec, 0.5) == 1.0


class TestFadeAdapter:
    def test_fade_multiplies_opacity(self):
        s = _scene()
        elem = s.geo.element('M')
        elem.visible = True
        s.addGeoElement(elem)
        mobj = s.mobject('M')
        assert mobj is not None
        subs = mobj.family_members_with_points()
        # Capture pre-fade opacities before mutating — _effect_fade multiplies
        # both channels, so both must shrink wherever they started non-zero.
        pre = [(sub.get_fill_opacity(), sub.get_stroke_opacity()) for sub in subs]
        s._effect_fade(mobj, 0.25)
        for sub, (fill0, stroke0) in zip(subs, pre):
            if fill0 > 0:
                assert sub.get_fill_opacity() <= 0.25 + 1e-6
            if stroke0 > 0:
                assert sub.get_stroke_opacity() <= 0.25 + 1e-6


class TestV2VisibilityWiring:
    def test_kf0_visible_applied(self):
        s = _scene()
        s.updateGeoElements = lambda updates=None: None
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}},
        ]), s.geo)
        seq.bind_visibility()
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        assert s.geo.element('M').visible is False

    def test_v1_path_unchanged_uses_show_hide(self, monkeypatch):
        # A v1 sequence must still go through the legacy Show/Hide 0.4s path.
        s = _scene()
        calls = {'show': 0, 'hide': 0, 'v2': 0}
        monkeypatch.setattr(s, 'Show', lambda names, *a, **k: (calls.__setitem__('show', calls['show'] + 1) or []))
        monkeypatch.setattr(s, 'Hide', lambda names, *a, **k: (calls.__setitem__('hide', calls['hide'] + 1) or []))
        monkeypatch.setattr(s, '_play_keyframe_interval_v2', lambda *a, **k: calls.__setitem__('v2', calls['v2'] + 1))
        monkeypatch.setattr(s, '_play_keyframe_interval', lambda *a, **k: None)
        monkeypatch.setattr(s, 'wait', lambda *a, **k: None)
        s.play_keyframes({'keyframes': [
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}, 'show': ['M']},
        ]})
        assert calls['v2'] == 0            # v2 path never taken for v1
        assert calls['show'] >= 1          # legacy Show used


from manim import Mobject, ValueTracker


def _drive_v2_interval(scene, progresses, on_step=None):
    """Build a ``scene.play`` stub that drives the sentinel updater installed
    by ``_play_keyframe_interval_v2`` directly at each of *progresses*
    (repeats allowed), without running a real manim animation.

    Mirrors the precedent in
    ``test_keyframe_initial_state.py::test_keyframe_interval_redraws_interpolated_independent_point``
    (grab the ValueTracker + sentinel Mobject the interval just
    ``self.add()``ed, then invoke the updater by hand) — but unlike that
    precedent, which also stubs ``updateGeoElements`` to a no-op recorder,
    this leaves ``scene.add`` / ``scene.remove`` / ``updateGeoElements``
    wired to their real implementations, so mobject identity (``become()``)
    and opacity are exercised for real. *on_step(p)*, if given, is called
    after each progress value has been driven through the updater once.
    """
    def fake_play(*_args, **_kwargs):
        tracker = next(m for m in reversed(scene.mobjects) if isinstance(m, ValueTracker))
        sentinel = next(m for m in reversed(scene.mobjects) if getattr(m, 'updaters', None))
        for p in progresses:
            tracker.set_value(p)
            for updater in list(sentinel.updaters):
                updater(sentinel)
            if on_step is not None:
                on_step(p)
    return fake_play


class TestV2IntervalPlayback:
    """Scene-level coverage for ``_play_keyframe_interval_v2`` itself.

    ``test_v1_path_unchanged_uses_show_hide`` above monkeypatches this
    method to a no-op, so nothing previously drove its ``on_frame`` sentinel
    updater for real; these tests exercise the integrated behavior:
    entering elements are revealed + faded, the effect alpha is applied
    AFTER ``updateGeoElements`` (become), and exiting elements are removed
    at interval end.
    """

    def test_v2_interval_enter_fade_reveals_and_fades(self):
        s = _scene()
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True},
             'enter': {'M': {'effect': 'fade', 'duration': 1.0, 'at': 0.0}}},
        ]), s.geo)
        seq.bind_visibility(get_element=s.geo.element)
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        assert s.geo.element('M').visible is False
        assert s.mobject('M') is None

        snapshots = {}

        def on_step(p):
            elem = s.geo.element('M')
            assert elem.visible is True
            mobj = s.mobject('M')
            assert mobj is not None
            snapshots[p] = (
                tuple(sub.get_fill_opacity() for sub in mobj.family_members_with_points()),
                tuple(sub.get_stroke_opacity() for sub in mobj.family_members_with_points()),
            )

        s.play = _drive_v2_interval(s, [0.5, 1.0], on_step=on_step)
        s._play_keyframe_interval_v2(seq.intervals[0])

        # Enter completed: M stays fully visible past the interval end.
        assert s.geo.element('M').visible is True
        assert s.mobject('M') is not None

        mid_fill, mid_stroke = snapshots[0.5]
        end_fill, end_stroke = snapshots[1.0]
        # At progress 0.5 the fade adapter multiplied a freshly-become'd,
        # full-opacity mobject by alpha=0.5 — some channel must read lower
        # than its (fully-restored, alpha=1) end-of-interval value.
        assert (any(m < e - 1e-6 for m, e in zip(mid_fill, end_fill)) or
                any(m < e - 1e-6 for m, e in zip(mid_stroke, end_stroke)))

    def test_v2_interval_exit_fade_removes_at_end(self):
        s = _scene()
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': True}},
            {'t': 1, 'visible': {'M': False},
             'exit': {'M': {'effect': 'fade', 'duration': 1.0, 'at': 0.0}}},
        ]), s.geo)
        seq.bind_visibility(get_element=s.geo.element)
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        assert s.geo.element('M').visible is True
        assert s.mobject('M') is not None

        removed = []
        real_remove = s.remove

        def spy_remove(*mobjects):
            removed.extend(mobjects)
            return real_remove(*mobjects)

        s.remove = spy_remove
        s.play = _drive_v2_interval(s, [0.5, 1.0])
        s._play_keyframe_interval_v2(seq.intervals[0])

        assert s.geo.element('M').visible is False
        assert any(getattr(m, 'name', None) == 'M' for m in removed)

    def test_effect_applied_after_become_not_wiped(self):
        # Ordering guarantee: each frame's updateGeoElements() (become) must
        # run BEFORE the fade adapter multiplies opacity. Re-invoking the
        # sentinel updater at the SAME progress twice must re-fade from a
        # fresh full-opacity mobject each time, not compound onto the
        # already-faded value from the previous call.
        s = _scene()
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True},
             'enter': {'M': {'effect': 'fade', 'duration': 1.0, 'at': 0.0}}},
        ]), s.geo)
        seq.bind_visibility(get_element=s.geo.element)
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)

        snapshots = []

        def on_step(p):
            mobj = s.mobject('M')
            snapshots.append((
                tuple(sub.get_fill_opacity() for sub in mobj.family_members_with_points()),
                tuple(sub.get_stroke_opacity() for sub in mobj.family_members_with_points()),
            ))

        s.play = _drive_v2_interval(s, [0.5, 0.5], on_step=on_step)
        s._play_keyframe_interval_v2(seq.intervals[0])

        assert len(snapshots) == 2
        assert snapshots[0] == snapshots[1]


class TestPartialAdapter:
    def test_partial_zero_hides_all_points(self):
        s = _scene()
        # a segment is a pure-stroke VMobject — good for partial draw
        s.geo.add(Command('Segment', ['A', 'B'], ['seg']))
        s.geo.rebuild()
        elem = s.geo.element('seg')
        elem.visible = True
        s.addGeoElement(elem)
        mobj = s.mobject('seg')
        assert mobj is not None
        import numpy as np
        subs = mobj.family_members_with_points()
        full_pts = sum(sm.get_num_points() for sm in subs)
        assert full_pts > 0
        s._effect_partial(mobj, 0.0)
        # manim's pointwise_become_partial (the same primitive manim's own
        # Create/ShowPartial use) keeps the points array length fixed and
        # instead collapses every point onto the curve's start — so at
        # alpha 0 the drawn stroke collapses to (near) nothing rather than
        # shrinking the array. Assert that collapse directly.
        for sm in mobj.family_members_with_points():
            pts = np.asarray(sm.points)
            spread = pts.max(axis=0) - pts.min(axis=0)
            assert np.all(np.abs(spread) < 1e-6)

    def test_apply_effect_alpha_routes_create(self):
        s = _scene()
        called = {}
        s._effect_partial = lambda m, a: called.setdefault('partial', a)
        elem = s.geo.element('M'); elem.visible = True; s.addGeoElement(elem)
        s._apply_effect_alpha('M', 'create', 0.5)
        assert called.get('partial') == 0.5


class TestScaleAdapter:
    def test_scale_shrinks_bbox(self):
        s = _scene()
        s.geo.add(Command('Segment', ['A', 'B'], ['seg']))
        s.geo.rebuild()
        elem = s.geo.element('seg'); elem.visible = True; s.addGeoElement(elem)
        mobj = s.mobject('seg')
        w_full = mobj.width
        s._effect_scale(mobj, 0.25)
        assert mobj.width < w_full * 0.5

    @staticmethod
    def _labelled_point():
        """An element mobject shaped like ``_render_point``'s output:
        ``VGroup(dot, label)`` with the label tagged by ``ui.create_label``."""
        from manim import Circle, Square, VGroup
        dot = Circle(radius=0.1).move_to([1.0, 1.0, 0]).set_fill(opacity=1)
        label = Square(side_length=0.2).move_to([1.5, 1.4, 0])
        label.set_fill(opacity=1).set_stroke(opacity=1)
        label._animageo_is_label = True
        return VGroup(dot, label), dot, label

    def test_grow_keeps_a_labelled_point_in_place(self):
        # Scaling the whole VGroup about its bbox centre dragged the dot
        # towards its label: the point slid into place while growing.
        s = _scene()
        mobj, dot, _label = self._labelled_point()
        s._effect_scale(mobj, 0.25)
        assert dot.get_center()[:2] == pytest.approx([1.0, 1.0])
        assert dot.width == pytest.approx(0.05)

    def test_grow_fades_the_label_where_it_stands(self):
        s = _scene()
        mobj, _dot, label = self._labelled_point()
        center, width = label.get_center().copy(), label.width
        s._effect_scale(mobj, 0.25)
        assert label.get_center()[:2] == pytest.approx(center[:2])
        assert label.width == pytest.approx(width)
        assert label.get_fill_opacity() == pytest.approx(0.25)

    def test_apply_effect_alpha_routes_grow(self):
        s = _scene()
        called = {}
        s._effect_scale = lambda m, a: called.setdefault('scale', a)
        elem = s.geo.element('M'); elem.visible = True; s.addGeoElement(elem)
        s._apply_effect_alpha('M', 'grow', 0.3)
        assert called.get('scale') == 0.3


class TestDefaultsEasing:
    def test_defaults_easing_used_as_fallback(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}},          # no explicit easing
        ], defaults={'easing': 'linear'}), _construction())
        # the interval ending at kf1 should use the default 'linear'
        assert seq.intervals[0].easing_name == 'linear'

    def test_explicit_keyframe_easing_overrides_default(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}, 'easing': 'in'},
        ], defaults={'easing': 'linear'}), _construction())
        assert seq.intervals[0].easing_name == 'in'

    def test_no_default_still_smooth(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}},
        ]), _construction())
        assert seq.intervals[0].easing_name == 'smooth'

    def test_bad_defaults_easing_rejected(self):
        with pytest.raises(ValueError, match='easing'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1},
            ], defaults={'easing': 'bogus'}), _construction())
