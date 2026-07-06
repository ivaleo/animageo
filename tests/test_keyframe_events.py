"""Keyframes v2 phase 6: emphasis events (indicate/flash/circumscribe)."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import KeyframeSequence, EventSpec, EVENT_EFFECTS
from animageo.animageo import AnimaGeoScene


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes, **top):
    return {'version': 2, 'keyframes': keyframes, **top}


class TestEventParsing:
    def test_event_parsed_and_normalized(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 2, 'events': [{'effect': 'indicate', 'targets': ['B'],
                                 'at': 0.5, 'duration': 0.6, 'color': '#FF0000'}]},
        ]), _construction())
        (e,) = seq.keyframes[1].events
        assert e['effect'] == 'indicate' and e['targets'] == ['B']
        assert e['at'] == 0.5 and e['duration'] == 0.6 and e['color'] == '#ff0000'

    def test_events_require_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0}, {'t': 1, 'events': [{'effect': 'flash', 'targets': ['B']}]},
            ]}, _construction())

    def test_unknown_effect_rejected(self):
        with pytest.raises(ValueError, match='event'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'sparkle', 'targets': ['B']}]},
            ]), _construction())

    def test_passing_flash_rejected_as_unavailable(self):
        with pytest.raises(ValueError, match='not available'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'passing_flash', 'targets': ['B']}]},
            ]), _construction())

    def test_unknown_target_rejected(self):
        with pytest.raises(ValueError, match='GHOST'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'flash', 'targets': ['GHOST']}]},
            ]), _construction())

    def test_empty_targets_rejected(self):
        with pytest.raises(ValueError, match='target'):
            KeyframeSequence.from_json(_v2([
                {'t': 0}, {'t': 1, 'events': [{'effect': 'flash', 'targets': []}]},
            ]), _construction())

    def test_effect_set(self):
        assert EVENT_EFFECTS == ('indicate', 'flash', 'circumscribe')


class TestEventCompile:
    def test_interval_gets_eventspec(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 2, 'events': [{'effect': 'indicate', 'targets': ['A', 'B'],
                                 'at': 0.5, 'duration': 1.0}]},
        ]), _construction())
        (e,) = seq.intervals[0].events
        assert isinstance(e, EventSpec)
        assert e.effect == 'indicate' and e.targets == ['A', 'B']
        assert e.start == 0.5 and e.duration == pytest.approx(1.0)
        assert seq.has_events() is True

    def test_duration_clamped(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'events': [{'effect': 'flash', 'targets': ['B'],
                                 'at': 0.5, 'duration': 5.0}]},
        ]), _construction())
        (e,) = seq.intervals[0].events
        assert e.duration == pytest.approx(0.5)

    def test_no_events_empty(self):
        seq = KeyframeSequence.from_json(_v2([{'t': 0}, {'t': 1}]), _construction())
        assert seq.intervals[0].events == []
        assert seq.has_events() is False


def _scene():
    s = AnimaGeoScene()
    c = _construction()
    s.geo = c
    s.applyStyle()
    return s


class TestEventEnvelope:
    def test_bump_zero_at_ends_one_at_mid(self):
        s = AnimaGeoScene()
        spec = EventSpec('indicate', ['B'], start=0.0, duration=1.0)
        assert s._event_envelope(spec, 0.0) == pytest.approx(0.0)
        assert s._event_envelope(spec, 0.5) == pytest.approx(1.0)
        assert s._event_envelope(spec, 1.0) == pytest.approx(0.0, abs=1e-9)

    def test_zero_outside_window(self):
        s = AnimaGeoScene()
        spec = EventSpec('indicate', ['B'], start=0.5, duration=0.5)
        assert s._event_envelope(spec, 0.4) == 0.0
        assert s._event_envelope(spec, 1.1) == 0.0


class TestIndicateAdapter:
    def test_identity_at_envelope_zero(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        mobj = s.mobject('B')
        w0 = mobj.width
        spec = EventSpec('indicate', ['B'], start=0.0, duration=1.0, scale=1.5)
        s._event_indicate(mobj, 0.0, spec)
        assert mobj.width == pytest.approx(w0)      # no change at env 0

    def test_scales_up_at_envelope_one(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        mobj = s.mobject('B')
        w0 = mobj.width
        spec = EventSpec('indicate', ['B'], start=0.0, duration=1.0, scale=1.5)
        s._event_indicate(mobj, 1.0, spec)
        assert mobj.width > w0

    def test_apply_events_does_not_touch_elem_style(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        interval_events = [EventSpec('indicate', ['B'], start=0.0, duration=1.0)]
        class _IV:
            events = interval_events
        before = dict(elem.style)
        s._apply_events(_IV(), 0.5, {})
        assert dict(elem.style) == before


from manim import ValueTracker


def _drive_interval(scene, progresses, on_step=None):
    """Drive the sentinel updater installed by ``_play_keyframe_interval`` /
    ``_play_keyframe_interval_v2`` directly at each of *progresses* (repeats
    allowed), without running a real manim animation.

    Adapted from the precedent in
    ``test_keyframe_initial_state.py::test_keyframe_interval_redraws_interpolated_independent_point``
    (grab the ValueTracker + sentinel Mobject the interval just
    ``self.add()``ed, then invoke the updater by hand) the same way
    ``test_keyframe_visibility.py::_drive_v2_interval`` does — but, like that
    helper and unlike the original precedent, ``scene.add``/``scene.remove``/
    ``updateGeoElements`` are left wired to their REAL implementations, so
    ``become()`` actually mutates mobject geometry. That is required here:
    the bug under test is that a static event target is never re-become'd,
    so only real ``become()`` calls can reveal the scale/colour compounding.
    Only ``scene.play`` is replaced (each real interval still calls it once,
    so this same function is installed for the whole ``play_keyframes`` run
    and re-resolves the *current* tracker/sentinel via ``scene.mobjects``
    each time it fires).
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


class TestEventSelfRestoration:
    """Phase 6 Task 2 review bugs, driven through the REAL ``play_keyframes``
    path (not just the isolated adapter unit tests above):

    Bug 1 — an interval whose ONLY content is an emphasis event (no
    interpolators/labels/styles/camera) must still run the frame updater; the
    legacy 'no work' gate in ``play_keyframes`` didn't check ``interval.events``
    and took the ``wait()`` short-circuit instead, so the event never applied.

    Bug 2 — an event target that isn't otherwise touched (not an
    interpolator/label/style/enter-exit target) is never re-``become()``'d by
    ``updateGeoElements``, so ``_event_indicate``'s ``mobj.scale(...)``
    mutates the SAME mobject every frame: the pulse compounds and never
    actually self-restores once the envelope closes back to 0.
    """

    def test_indicate_only_interval_runs_and_self_restores(self):
        s = _scene()
        elem_b = s.geo.element('B')
        elem_b.visible = True
        s.addGeoElement(elem_b)
        base_width = s.mobject('B').width
        assert base_width > 0

        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [-2, 0]}},
            {'t': 1, 'values': {'A': [2, 0]},
             'events': [{'effect': 'indicate', 'targets': ['B'],
                         'at': 0.0, 'duration': 1.0, 'scale': 1.6}]},
            # Indicate-ONLY interval: no values/labels/styles/camera change,
            # just an emphasis event. This is the exact shape bug 1 broke.
            {'t': 2, 'events': [{'effect': 'indicate', 'targets': ['B'],
                                 'at': 0.0, 'duration': 1.0, 'scale': 1.6}]},
        ]), s.geo)

        wait_calls = []
        s.wait = lambda *a, **k: wait_calls.append(a)

        widths = []
        s.play = _drive_interval(
            s, [0.0, 0.5, 1.0],
            on_step=lambda p: widths.append(s.mobject('B').width),
        )

        s.play_keyframes(seq)

        # Bug 1: the indicate-only second interval must not have taken the
        # legacy wait() short-circuit.
        assert wait_calls == [], (
            f"indicate-only interval called wait{wait_calls!r} instead of "
            f"running the frame updater"
        )
        # ... and both intervals (3 progress samples each) must have run the
        # updater for real.
        assert len(widths) == 6, (
            f"expected 6 width samples (2 intervals x 3 progress steps), got "
            f"{len(widths)} -- an interval likely short-circuited to wait()"
        )

        # Sanity: the pulse actually scales B up mid-envelope.
        assert widths[1] > base_width * 1.1

        # Bug 2: at the very last sample (end of the second, indicate-only
        # interval; envelope back at 0), B must be back to its original
        # width -- not compounded from repeated un-reset scale() calls.
        assert widths[-1] == pytest.approx(base_width, rel=1e-3), (
            f"B did not self-restore: {widths[-1]} != {base_width} "
            f"(indicate scale likely compounded across frames)"
        )

    def test_v2_loop_indicate_target_also_self_restores(self):
        # Same bug 2, but through _play_keyframe_interval_v2 (the interval
        # takes the v2 lifecycle path because M has an enter effect); B is a
        # separate static indicate target untouched by that lifecycle.
        s = _scene()
        elem_b = s.geo.element('B')
        elem_b.visible = True
        s.addGeoElement(elem_b)
        base_width = s.mobject('B').width

        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True},
             'enter': {'M': {'effect': 'create', 'duration': 1.0, 'at': 0.0}},
             'events': [{'effect': 'indicate', 'targets': ['B'],
                         'at': 0.0, 'duration': 1.0, 'scale': 1.6}]},
        ]), s.geo)
        seq.bind_visibility(get_element=s.geo.element)
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)

        widths = []
        s.play = _drive_interval(
            s, [0.0, 0.5, 1.0],
            on_step=lambda p: widths.append(s.mobject('B').width),
        )
        s._play_keyframe_interval_v2(seq.intervals[0])

        assert widths[1] > base_width * 1.1
        assert widths[-1] == pytest.approx(base_width, rel=1e-3), (
            f"B did not self-restore in the v2 loop: {widths[-1]} != {base_width}"
        )


class TestAdditiveEvents:
    def test_flash_adds_and_removes_temp_mobject(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        spec = EventSpec('flash', ['B'], start=0.0, duration=1.0)
        active = {}
        n0 = len(s.mobjects)
        s._event_additive(spec, 0.5, 0.5, active)      # mid-window -> temp added
        assert len(active) == 1
        assert len(s.mobjects) == n0 + 1
        s._event_additive(spec, 0.0, 1.01, active)     # past window -> removed
        assert len(active) == 0
        assert len(s.mobjects) == n0

    def test_circumscribe_adds_box_around_target(self):
        s = _scene()
        elem = s.geo.element('B'); elem.visible = True; s.addGeoElement(elem)
        spec = EventSpec('circumscribe', ['B'], start=0.0, duration=1.0)
        active = {}
        s._event_additive(spec, 0.5, 0.5, active)
        assert len(active) == 1
        temp = next(iter(active.values()))
        # the box encloses the target
        assert temp.width >= s.mobject('B').width
