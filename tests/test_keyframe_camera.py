"""Keyframes v2 phase 5: @camera pseudo-element."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import KeyframeSequence, CameraInterpolator, EASING_FUNCTIONS, CAMERA_KEY


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes, **top):
    return {'version': 2, 'keyframes': keyframes, **top}


class TestCameraParsing:
    def test_camera_popped_from_values_not_validated_as_element(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'center': [0, 0], 'width': 14}}},
            {'t': 1, 'values': {'@camera': {'center': [2, 1], 'width': 8}}},
        ]), _construction())
        assert seq.keyframes[0].camera == {'center': [0.0, 0.0], 'width': 14.0}
        assert '@camera' not in seq.keyframes[0].values

    def test_camera_center_only(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'center': [0, 0]}}},
            {'t': 1, 'values': {'@camera': {'center': [3, 3]}}},
        ]), _construction())
        assert seq.keyframes[1].camera == {'center': [3.0, 3.0]}

    def test_camera_requires_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'values': {'@camera': {'width': 10}}}, {'t': 1},
            ]}, _construction())

    def test_bad_width_rejected(self):
        with pytest.raises(ValueError, match='width'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'values': {'@camera': {'width': -3}}}, {'t': 1},
            ]), _construction())

    def test_bad_center_rejected(self):
        with pytest.raises(ValueError, match='center'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'values': {'@camera': {'center': [1, 2, 3]}}}, {'t': 1},
            ]), _construction())

    def test_normal_values_still_work_alongside_camera(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0], '@camera': {'width': 14}}},
            {'t': 1, 'values': {'A': [1, 1], '@camera': {'width': 7}}},
        ]), _construction())
        assert 'A' in seq.keyframes[0].values
        assert seq.keyframes[0].camera == {'width': 14.0}


class TestCameraInterpolator:
    def test_center_and_width_lerp(self):
        ci = CameraInterpolator(
            start={'center': [0.0, 0.0], 'width': 14.0},
            end={'center': [4.0, 2.0], 'width': 6.0},
            easing=EASING_FUNCTIONS['linear'])
        mid = ci.at(0.5)
        assert mid['center'] == [2.0, 1.0]
        assert mid['width'] == pytest.approx(10.0)

    def test_absent_field_stays_absent(self):
        ci = CameraInterpolator(
            start={'width': 14.0}, end={'width': 6.0},
            easing=EASING_FUNCTIONS['linear'])
        mid = ci.at(0.5)
        assert 'center' not in mid
        assert mid['width'] == pytest.approx(10.0)


class TestCameraIntervalWiring:
    def test_interval_gets_camera_interp(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'width': 14}}},
            {'t': 1, 'values': {'@camera': {'width': 6}}},
        ]), _construction())
        assert seq.intervals[0].camera_interp is not None
        assert seq.intervals[0].camera_interp.at(1.0)['width'] == pytest.approx(6.0)

    def test_no_camera_no_interp(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}},
        ]), _construction())
        assert seq.intervals[0].camera_interp is None


from animageo.animageo import AnimaGeoScene


def _scene():
    s = AnimaGeoScene()
    s.geo = _construction()
    s.applyStyle()
    return s


class TestCameraPlayback:
    def test_apply_camera_sets_frame(self):
        s = _scene()
        s._apply_camera({'center': [2.0, 1.0], 'width': 6.0})
        c = s.camera.frame.get_center()
        assert abs(c[0] - 2.0) < 1e-6 and abs(c[1] - 1.0) < 1e-6
        assert abs(s.camera.frame.width - 6.0) < 1e-6

    def test_apply_camera_empty_noop(self):
        s = _scene()
        w0 = s.camera.frame.width
        s._apply_camera({})
        assert s.camera.frame.width == w0

    def test_apply_keyframe_state_applies_camera(self):
        s = _scene()
        s.updateGeoElements = lambda updates=None: None
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'@camera': {'width': 9}}},
            {'t': 1, 'values': {'@camera': {'width': 5}}},
        ]), s.geo)
        s._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        assert abs(s.camera.frame.width - 9.0) < 1e-6


class TestApplyKeyframesAt:
    def test_places_value_at_midpoint(self):
        import numpy as np
        s = _scene()
        s.apply_keyframes_at(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 2, 'values': {'A': [4, 0]}},
        ]), t=1.0)
        assert np.allclose(s.geo.element('A').data.coords, [2.0, 0.0], atol=1e-6)

    def test_camera_at_time(self):
        s = _scene()
        s.apply_keyframes_at(_v2([
            {'t': 0, 'values': {'@camera': {'width': 10}}},
            {'t': 2, 'values': {'@camera': {'width': 6}}},
        ]), t=1.0)
        assert abs(s.camera.frame.width - 8.0) < 1e-6

    def test_clamps_before_first_and_after_last(self):
        import numpy as np
        s = _scene()
        data = _v2([{'t': 1, 'values': {'A': [0, 0]}},
                    {'t': 3, 'values': {'A': [4, 0]}}])
        s.apply_keyframes_at(data, t=0.0)     # before first -> first state
        assert np.allclose(s.geo.element('A').data.coords, [0.0, 0.0], atol=1e-6)
        s.apply_keyframes_at(data, t=99.0)    # after last -> last state
        assert np.allclose(s.geo.element('A').data.coords, [4.0, 0.0], atol=1e-6)


class TestCameraOnlyIntervalAnimates:
    def test_camera_only_interval_runs_updater_not_wait(self, monkeypatch):
        # A camera-only interval must drive _play_keyframe_interval (so on_frame
        # animates the camera), NOT fall into the wait() short-circuit.
        s = _scene()
        calls = {'play_interval': 0, 'wait': 0}
        monkeypatch.setattr(s, '_play_keyframe_interval',
                            lambda *a, **k: calls.__setitem__('play_interval', calls['play_interval'] + 1))
        monkeypatch.setattr(s, '_play_keyframe_interval_v2',
                            lambda *a, **k: calls.__setitem__('play_interval', calls['play_interval'] + 1))
        monkeypatch.setattr(s, 'wait', lambda *a, **k: calls.__setitem__('wait', calls['wait'] + 1))
        monkeypatch.setattr(s, 'updateGeoElements', lambda updates=None: None)
        s.play_keyframes(_v2([
            {'t': 0, 'values': {'@camera': {'width': 12}}},
            {'t': 1, 'values': {'@camera': {'width': 6}}},
        ]))
        assert calls['play_interval'] >= 1     # updater ran (camera animates)
        assert calls['wait'] == 0              # did NOT short-circuit to wait
