"""A timeline of one keyframe is legal (1.11.0rc7): ``render(t)`` is the
state of that keyframe for any ``t``, the video is a still of
``video.duration`` seconds (1 s by default)."""
import tempfile

import numpy as np
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import native  # noqa: E402
from animageo.native.paint_fixtures import _Doc  # noqa: E402

from .test_native_frame_equals_video import FPS, _psnr, _still, _video_frames  # noqa: E402

ONE = {'version': 2, 'keyframes': [
    {'t': 0.5, 'values': {'C': [2.0, 3.0]}, 'visible': {'b': False},
     'styles': {'c': {'stroke': '#ff0000', 'stroke_width_px': 4}}},
]}
# the same state held for a second by a second keyframe (the reference)
TWO = {'version': 2, 'keyframes': [
    ONE['keyframes'][0],
    {'t': 1.5, 'values': {'C': [2.0, 3.0]}, 'visible': {'b': False},
     'styles': {'c': {'stroke': '#ff0000', 'stroke_width_px': 4}}},
]}


def _doc():
    d = _Doc('one').free('A', 0, 0).free('B', 5, 0).free('C', 1.5, 3.5)
    d.segment('a', 'B', 'C').segment('b', 'C', 'A').segment('c', 'A', 'B')
    d.angle('alpha', 'B', 'A', 'C').label('a').label('alpha', 'value')
    return d.doc


def _svg(doc, timeline, t):
    with tempfile.NamedTemporaryFile(suffix='.svg') as f:
        result = native.render(doc, fmt='svg', out=f.name, t=t, timeline=timeline)
        return open(f.name, encoding='utf-8').read(), result.report


def test_the_still_of_one_keyframe_is_its_state_at_any_t():
    doc = _doc()
    reference, _ = _svg(doc, TWO, 0.5)
    assert 'rgb(100%, 0%, 0%)' in reference      # the style of the keyframe is drawn
    for t in (-1.0, 0.5, 0.9, 7.0):
        svg, report = _svg(doc, ONE, t)
        assert svg == reference, t
        assert report['t'] == 0.5
        assert report['visible']['b'] is False
        assert report['elements']['b']['visible'] is False
        assert report['effects'] == {}


def test_the_video_frame_of_one_keyframe_at_any_t():
    doc = _doc()
    reference, _ = _still(doc, TWO, 0.5)
    for t in (0.0, 0.5, 3.0):
        frame, report = _still(doc, ONE, t)
        assert _psnr(frame, reference) == float('inf'), t
        assert report['t'] == 0.5


def test_the_video_of_one_keyframe_is_a_still_of_its_duration():
    doc = _doc()
    frames, count, times = _video_frames(doc, ONE, set(range(FPS)))
    assert count == FPS                       # 1 s by default
    assert times == pytest.approx([0.5 + k / FPS for k in range(FPS)])
    still, _ = _still(doc, ONE, 0.5)
    for n in (0, FPS // 2, FPS - 1):
        assert _psnr(frames[n], still) >= 60, n


def test_the_duration_of_the_video_of_one_keyframe():
    doc = _doc()
    with tempfile.NamedTemporaryFile(suffix='.mp4') as f:
        result = native.render(doc, fmt='mp4', out=f.name, timeline=ONE,
                               video={'fps': FPS, 'quality': 'low', 'duration': 0.5})
        assert result.report['video']['duration'] == 0.5
        assert result.report['t'] == 0.5
        assert result.report['visible']['b'] is False
        import subprocess
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', f.name],
                               capture_output=True, text=True)
        if probe.returncode == 0:
            assert int(probe.stdout.strip()) == 5


@pytest.mark.parametrize('duration', [0, -1, float('inf'), 'long', True, 601])
def test_a_bad_duration(duration):
    with pytest.raises(ValueError, match='video.duration'):
        native.render(_doc(), fmt='mp4', timeline=ONE, video={'duration': duration})


def test_a_duration_with_two_keyframes_is_refused():
    with pytest.raises(ValueError, match='video.duration'):
        native.render(_doc(), fmt='mp4', timeline=TWO, video={'duration': 2.0})
