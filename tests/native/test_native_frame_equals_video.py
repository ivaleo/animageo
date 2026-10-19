"""``native.render(t=…)`` is the frame of the video at ``t`` (1.11.0): one
function draws the frame of the playback and the still (``seek_keyframes``),
so the video-camera PNG at ``t`` equals the frame the video writes, before the
codec, inside the windows of the effects and the events too; the vector still
draws the same state (its value labels in TeX, the video's with cached
digits)."""
import copy
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


# ── the effects of the frame: the report, the playback, the contract ─────

GRID = {'version': 2, 'defaults': {'exit': {'effect': 'uncreate', 'duration': 0.3}}, 'keyframes': [
    {'t': 0, 'visible': {'b': False, 'C': False, 'k': False}},
    {'t': 2, 'visible': {'b': True, 'C': True}, 'enter': {'C': {'effect': 'grow', 'duration': 1, 'at': 0.5}}},
    # a window longer than its interval is cut at its end
    {'t': 3, 'visible': {'a': False, 'k': True}, 'enter': {'k': {'effect': 'create', 'duration': 3, 'at': 0.5}}},
    # a zero duration: done from its start
    {'t': 3.5, 'visible': {'b': False}, 'exit': {'b': {'effect': 'fade', 'duration': 0}}},
    {'t': 4.5, 'visible': {'b': True}, 'enter': {'b': {'effect': 'write', 'duration': 0.6, 'at': 0.2}}},
]}


def _effects_doc():
    d = _Doc('effects').free('A', 0, 0).free('B', 5, 0).free('C', 1.5, 3.5)
    d.segment('a', 'B', 'C').segment('b', 'C', 'A').circle('k', 'A', 'B')
    d.label('b')
    return d.doc


def test_the_playback_plays_the_effects_of_the_contract():
    """``seek_keyframes`` (the frame function of the video) and
    ``timeline_effects`` (the contract ``resolve_paint`` and the report
    read, without manim) give the same effects on a grid of times: the same
    elements, phases, kinds and progress."""
    from animageo.native import rendering
    from animageo.native.document import as_document
    from animageo.native.timeline import timeline_effects
    doc = as_document(_effects_doc())
    bridge = rendering._bridged_timeline(doc, GRID)
    times = sorted(set(np.round(np.linspace(0, 4.5, 46), 9)) | {2.5, 3.0, 3.5, 3.55, 4.5})
    seen = set()
    for t in times:
        scene = rendering._load(rendering._import_scene(), doc, None, None, {})
        names = scene.native_names.by_id
        got = scene.seek_keyframes(bridge, t)
        expect = {names[el_id]: e for el_id, e in timeline_effects(doc, GRID, t).items()}
        assert set(got) == set(expect), t
        for name, (phase, kind, progress) in got.items():
            e = expect[name]
            assert (phase, kind) == (e['phase'], e['effect']), (t, name)
            assert progress == pytest.approx(e['progress'], abs=1e-9), (t, name)
            seen.add((name, kind, 0 < progress < 1))
    # the grid passes inside every window
    assert {(kind, inside) for _name, kind, inside in seen} >= {
        ('fade', True), ('grow', True), ('create', True), ('uncreate', True), ('write', True), ('fade', False)}


def test_the_report_rounds_the_progress_of_an_effect_as_resolve_paint():
    from animageo.native.paint import resolve_paint
    doc = _effects_doc()
    t = 0.5 + 1 / 3                              # C: grow at 1/3 of its window
    report = native.render(doc, fmt='svg', t=t, timeline=GRID).report
    paint = resolve_paint(doc, None, t, timeline=GRID)['elements']
    assert report['effects']['C'] == paint['C']['effect']
    assert report['effects']['C']['progress'] == round(1 / 3, 9)


needs_ffmpeg = pytest.mark.skipif(__import__('shutil').which('ffmpeg') is None, reason='ffmpeg is not installed')


@pytest.mark.slow
@needs_ffmpeg
def test_the_video_file_takes_the_explicit_inputs(tmp_path):
    """``render(fmt="mp4", inputs=…)`` — the video the library writes, not
    a harness: an element whose value is given stays put although the
    timeline moves it, its frames are the stills ``render(t, png, video,
    inputs)`` (up to the codec) and not those of the timeline alone."""
    import subprocess

    from PIL import Image
    doc = _triangle()
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'C': [1.5, 3.5], 'B': [5, 0]}},
        {'t': 1, 'values': {'C': [3.0, 4.0], 'B': [6, 1]}},
    ]}
    inputs = {'B': {'kind': 'point', 'value': [4.0, -0.5]}}
    video = {'fps': FPS, 'quality': 'low'}
    result = native.render(doc, fmt='mp4', out=tmp_path / 'v.mp4', timeline=timeline, inputs=inputs, video=video)
    assert result.fmt == 'mp4' and result.report['video']['fps'] == FPS
    for n in (0, 5, 9):
        frame = tmp_path / f'f{n}.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(tmp_path / 'v.mp4'), '-vf',
                        f'select=eq(n\\,{n})', '-vframes', '1', str(frame)], check=True)
        got = np.asarray(Image.open(frame).convert('RGBA'))
        fixed, _ = _still(doc, timeline, n / FPS, inputs=inputs)
        moved, _ = _still(doc, timeline, n / FPS)
        assert got.shape == fixed.shape
        psnr = _psnr(got, fixed)
        assert psnr >= 30, (n, psnr)
        if n:
            assert psnr > _psnr(got, moved) + 3, n


# ── the frame is played without drawing ────────────────────────────────

SNAPSHOTS = {'overlay': {'label_placement': {'enabled': True, 'keyframe_snapshots': True}}}

STEPS = {'version': 2, 'keyframes': [
    {'t': 0, 'values': {'C': [1.5, 3.5]}, 'visible': {'k': False, 'b': False}},
    {'t': 1, 'values': {'C': [3.0, 4.0]}},
    {'t': 2, 'values': {'C': [4.5, 2.0]}, 'visible': {'b': True}},
    {'t': 3, 'values': {'C': [2.0, 3.0]}, 'visible': {'k': True}},
    {'t': 4, 'values': {'C': [1.0, 2.5]}},
    {'t': 5, 'values': {'C': [3.5, 3.5]}},
]}


def _scene_state(scene):
    """The label placement and the points of what a scene draws, by element
    name (a hidden element draws nothing, its label included)."""
    out = {}
    for elem in scene.geo.elements:
        mobj = scene.mobject(elem.name)
        if mobj is None or mobj not in scene.mobjects:
            continue
        out[elem.name] = (
            {k: elem.style.get(k) for k in ('label_offset_px', 'label_anchor', '_auto_placed')},
            [np.round(m.points, 9).tolist() for m in mobj.family_members_with_points()])
    return out


@pytest.mark.parametrize('t, needed', [(0.5, {0, 1}), (2.5, {0, 2, 3}), (3.2, {0, 2, 3, 4}),
                                       (4.7, {0, 2, 4, 5}), (5.0, {0, 2, 4, 5})])
def test_the_frame_reads_the_snapshots_it_needs_only(t, needed, monkeypatch):
    """The label snapshots of the keyframes the frame needs — the start, the
    two ends of its interval, the first layout of each label it shows (the
    anchor of a label is that of its first layout; ``b`` is shown at
    keyframe 2) — give the frame of the full pass; the others are not
    computed."""
    from animageo.animageo import AnimaGeoScene
    from animageo.native import rendering
    from animageo.native.document import as_document
    d = _triangle()
    d['appearance'].setdefault('b', {})['label'] = {'mode': 'name'}
    doc = as_document(d)
    bridge = rendering._bridged_timeline(doc, STEPS)
    bridge['keyframes'][0]['hide'] = ['e_b']
    bridge['keyframes'][2]['show'] = ['e_b']
    computed = []
    layouts = AnimaGeoScene._compute_keyframe_label_layouts

    def spy(self, seq, cfg, indices=None, frame=None):
        out = layouts(self, seq, cfg, indices=indices, frame=frame)
        computed.append({k for k, layout in enumerate(out) if layout})
        return out

    def seek():
        scene = AnimaGeoScene()
        scene.loadDocument(doc, style=SNAPSHOTS)
        scene.seek_keyframes(copy.deepcopy(bridge), t)
        return scene

    monkeypatch.setattr(AnimaGeoScene, '_compute_keyframe_label_layouts', spy)
    lazy = seek()
    prepare = AnimaGeoScene._prepare_keyframes
    monkeypatch.setattr(AnimaGeoScene, '_prepare_keyframes',
                        lambda self, data, frame=None: prepare(self, data))
    full = seek()
    assert _scene_state(lazy) == _scene_state(full)
    assert computed == [needed, set(range(len(bridge['keyframes'])))]


def test_seek_builds_each_mobject_once(monkeypatch):
    """The still at ``t`` builds the mobject of each element it draws once,
    and none of what it does not draw: a scene played to ``t`` touches an
    element many times, the frame draws it once."""
    from animageo.animageo import AnimaGeoScene
    from animageo.native import rendering
    from animageo.native.document import as_document
    doc = as_document(_triangle())
    built = []
    create = AnimaGeoScene.CreateMObject

    def spy(self, elem, *args, **kwargs):
        mobj = create(self, elem, *args, **kwargs)
        if mobj is not None:
            built.append(elem.name)
        return mobj

    monkeypatch.setattr(AnimaGeoScene, 'CreateMObject', spy)
    for t in (0.5, 2.5, 4.7):
        built.clear()
        scene = rendering._still_scene(doc, None, None, {}, STEPS, t)
        drawn = sorted(m.name for m in scene.mobjects if m.name in {e.name for e in scene.geo.elements})
        assert sorted(built) == drawn, t
