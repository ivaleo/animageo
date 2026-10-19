"""``native.render(t=…)`` is the frame of the video at ``t`` (1.11.0): one
function draws the frame of the playback and the still (``seek_keyframes``),
so the video-camera PNG at ``t`` equals the frame the video writes, before the
codec, inside the windows of the effects and the events too; the vector still
draws the same state (its value labels in TeX, the video's with cached
digits)."""
import tempfile

import numpy as np
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import native  # noqa: E402
from animageo.native.paint_fixtures import _Doc  # noqa: E402

FPS = 10


def _frame_times(scene, bridge):
    """The playhead time of each frame of the video (the rule of manim and
    ``play_keyframes``): an interval plays ``len(arange(0, duration, 1/fps))``
    frames, frame ``k`` at ``start + k/fps``; one that changes nothing is a
    still of ``int(duration·fps)`` frames."""
    from animageo.keyframes import KeyframeSequence
    seq = KeyframeSequence.from_json(bridge, scene.geo)
    seq.bind_visibility(get_element=scene.geo.element)
    times = []
    for iv in seq.intervals:
        if not (iv.enter_effects or iv.exit_effects) and scene._interval_holds_still(iv):
            count = int(iv.duration / (1 / FPS))
        else:
            count = len(np.arange(0, iv.duration, 1 / FPS))
        times += [iv.start_t + k / FPS for k in range(count)]
    return times


def _video_frames(doc, timeline, frames, *, style=None, inputs=None, quality='low'):
    """The frames ``frames`` (indices) the video of ``timeline`` writes, as
    RGBA arrays taken from the renderer before the codec, the number of
    frames and the time of each."""
    from manim import tempconfig

    from animageo.native import rendering
    from animageo.native.document import as_document

    doc = as_document(doc)
    bridge = rendering._bridged_timeline(doc, timeline, inputs)
    width, height, _ = rendering._video_size(doc, {}, rendering._check_video({'fps': FPS, 'quality': quality}))
    got, count, times = {}, [0], []

    class Scene(rendering._import_scene()):
        def construct(self):
            self.loadDocument(doc, style=style, inputs=inputs)
            times.extend(_frame_times(self, bridge))
            add_frame = self.renderer.add_frame

            def capture(frame, num_frames=1):
                for k in range(num_frames):
                    if count[0] + k in frames:
                        got[count[0] + k] = np.array(frame, copy=True)
                count[0] += num_frames
                return add_frame(frame, num_frames)
            self.renderer.add_frame = capture
            self.play_keyframes(bridge)

    with tempfile.TemporaryDirectory() as media:
        with tempconfig({'media_dir': media, 'pixel_width': width, 'pixel_height': height,
                         'frame_rate': float(FPS), 'disable_caching': True, 'verbosity': 'ERROR',
                         'progress_bar': 'none', 'write_to_movie': False}):
            Scene().render()
    return got, count[0], times


def _still(doc, timeline, t, *, style=None, inputs=None, quality='low'):
    from PIL import Image
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        result = native.render(doc, fmt='png', out=f.name, t=t, timeline=timeline, inputs=inputs,
                               style_config=style, video={'fps': FPS, 'quality': quality})
        return np.asarray(Image.open(f.name).convert('RGBA')), result.report


def _psnr(a, b):
    a, b = a[..., :3].astype(float), b[..., :3].astype(float)
    mse = float(((a - b) ** 2).mean())
    return float('inf') if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def _assert_frames(doc, timeline, frames, *, style=None, inputs=None):
    video, count, times = _video_frames(doc, timeline, set(frames), style=style, inputs=inputs)
    assert count == len(times)
    for n in frames:
        still, _ = _still(doc, timeline, times[n], style=style, inputs=inputs)
        assert video[n].shape == still.shape
        psnr = _psnr(video[n], still)
        assert psnr >= 60, f'frame {n} (t = {times[n]:.3f}): {psnr:.1f} dB'


def _triangle():
    d = _Doc('frames').free('A', 0, 0).free('B', 5, 0).free('C', 1.5, 3.5)
    d.segment('a', 'B', 'C').segment('b', 'C', 'A').segment('c', 'A', 'B').circle('k', 'A', 'B')
    d.polygon('T', 'A', 'B', 'C').angle('alpha', 'B', 'A', 'C').text('t', 'ABC', 'C')
    d.label('a').label('alpha', 'value')
    return d.doc


def test_the_steps_of_a_construction_inside_their_effects():
    from animageo.native.timeline import steps_timeline
    doc = _triangle()
    steps = steps_timeline(doc, lag=0.3, duration=0.5, pause=0.2)
    end = steps.keyframes['keyframes'][-1]['t']
    _assert_frames(doc, steps.keyframes, list(range(0, int(end * FPS), 2)))


def test_every_effect_inside_its_window():
    doc = _triangle()
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'a': False, 'k': False, 'T': False, 't': False, 'alpha': False}},
        {'t': 1, 'visible': {'a': True, 'k': True, 'T': True, 't': True, 'alpha': True},
         'enter': {'a': {'effect': 'create', 'duration': 0.8}, 'k': {'effect': 'grow', 'duration': 1.0},
                   'T': {'effect': 'fade', 'duration': 0.6, 'at': 0.2}, 't': {'effect': 'write', 'duration': 1.0},
                   'alpha': {'effect': 'none', 'duration': 0.5}}},
        {'t': 2, 'visible': {'a': False, 'k': False, 'T': False},
         'exit': {'a': {'effect': 'uncreate', 'duration': 0.8}, 'k': {'effect': 'shrink', 'duration': 0.6},
                  'T': 'fade'}},
        {'t': 2.5},
    ]}
    _assert_frames(doc, timeline, list(range(0, 25)))


def test_an_element_appears_in_the_interval_before_its_keyframe():
    doc = _triangle()
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'b': False, 'C': False}},
        {'t': 2, 'visible': {'b': True, 'C': True}},
        {'t': 3},
    ]}
    _assert_frames(doc, timeline, [1, 3, 5, 10, 19, 20, 25])
    # the report keeps the visibility of the keyframes and tells the effect
    _, report = _still(doc, timeline, 1.0)
    assert report['visible']['b'] is False
    assert report['effects']['b'] == {'phase': 'enter', 'effect': 'fade', 'progress': 1.0}
    assert report['elements']['b']['visible'] is True


def test_values_styles_and_a_moving_point():
    doc = _triangle()
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'C': [1.5, 3.5]}},
        {'t': 1, 'values': {'C': [3.0, 4.0]}, 'easing': 'linear'},
        {'t': 2, 'values': {'C': [4.5, 2.0]}, 'styles': {'c': {'stroke': '#ff0000', 'stroke_width_px': 4}}},
    ]}
    _assert_frames(doc, timeline, [0, 3, 5, 10, 13, 17, 19])


def test_labels_placed_at_every_keyframe():
    doc = _triangle()
    style = {'overlay': {'label_placement': {'enabled': True, 'keyframe_snapshots': True,
                                             'dynamic_angles': True}}}
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'C': [1.5, 3.5]}},
        {'t': 1, 'values': {'C': [4.5, 2.0]}},
    ]}
    _assert_frames(doc, timeline, [0, 2, 5, 7, 9], style=style)


def test_events_and_the_camera():
    doc = _triangle()
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'@camera': {'center': [2.5, 1.5], 'width': 9}}},
        {'t': 1.5, 'values': {'@camera': {'center': [2.0, 1.0], 'width': 7}},
         'events': [{'effect': 'indicate', 'targets': ['C'], 'at': 0.2, 'duration': 0.6},
                    {'effect': 'flash', 'targets': ['A'], 'at': 0.5, 'duration': 0.6},
                    {'effect': 'circumscribe', 'targets': ['T'], 'at': 0.3, 'duration': 1.0}]},
    ]}
    _assert_frames(doc, timeline, [0, 3, 5, 7, 9, 11, 12, 14])


def test_explicit_inputs_win_over_the_timeline_in_the_still_and_the_video():
    doc = _triangle()
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'C': [1.5, 3.5], 'B': [5, 0]}},
        {'t': 1, 'values': {'C': [3.0, 4.0], 'B': [6, 1]}},
    ]}
    inputs = {'B': {'kind': 'point', 'value': [4.0, -0.5]}}
    _assert_frames(doc, timeline, [0, 4, 8], inputs=inputs)


def test_the_vector_still_draws_the_state_of_the_video_frame():
    """The SVG still at ``t`` and the video frame are one state: the same
    mobjects in the same places, the same label texts (TeX in the still,
    cached digits in the video)."""
    from animageo.native import rendering
    from animageo.native.document import as_document
    doc = as_document(_triangle())
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'C': [1.5, 3.5]}, 'visible': {'k': False}},
        {'t': 1, 'values': {'C': [3.0, 4.0]}, 'visible': {'k': True}, 'enter': {'k': 'create'}},
    ]}
    for t in (0.2, 0.5):
        still = rendering._still_scene(doc, None, None, {}, timeline, t, video_labels=False)
        frame = rendering._still_scene(doc, None, None, {}, timeline, t, video_labels=True)
        assert sorted(still.native_names.by_id) == sorted(frame.native_names.by_id)
        for el_id, name in still.native_names.by_id.items():
            a, b = still.mobject(name), frame.mobject(name)
            assert (a is None) == (b is None), el_id
            if a is None:
                continue
            geometry = [m for m in a.family_members_with_points() if not _in_label(a, m)]
            other = [m for m in b.family_members_with_points() if not _in_label(b, m)]
            assert len(geometry) == len(other), el_id
            for m, n in zip(geometry, other):
                assert np.allclose(m.points, n.points, atol=1e-9), el_id
                assert m.get_stroke_opacity() == pytest.approx(n.get_stroke_opacity()), el_id
        from animageo.labels import resolve_label_text
        for el_id in ('a', 'alpha'):
            elem = still.geo.element(still.native_names.by_id[el_id])
            assert resolve_label_text(still, elem) == resolve_label_text(frame, frame.geo.element(elem.name))


def _in_label(root, leaf):
    for node in root.get_family():
        if getattr(node, '_animageo_is_label', False) and leaf in node.get_family():
            return True
    return False
