"""The ticks and the arcs an equality mark puts on its targets follow the mark
in time (1.11.0rc5): the frame at ``t`` (``render(t)``, ``seek_keyframes``)
and the frames of the video (``play_keyframes``) draw them while the mark is
in the frame — not before its keyframe, not after it leaves — and inside the
window of its effect they are drawn as the effect draws the mark (``fade`` —
their opacity, ``create`` — their stroke drawn up to the progress). The
target itself (the segment, the angle's own arc) is drawn as before.

1.11.0rc4 loaded the document once with the static visibility of the mark:
its ticks stayed on the targets while the timeline hid it (the still of rc3
was built from the visibility at ``t``; its video drew the static ticks too).
"""
import copy
import tempfile

import numpy as np
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import native  # noqa: E402
from animageo.native.paint_fixtures import _Doc  # noqa: E402

from .test_native_frame_equals_video import FPS, _assert_frames, _psnr, _video_frames  # noqa: E402

SEGMENTS = ('b', 'c')
ANGLES = ('alpha', 'beta')


def _doc(*, hidden=()):
    """A triangle; ``m`` marks the sides ``b``, ``c`` with two ticks, ``n``
    the angles ``alpha``, ``beta`` with two arcs; ``hidden`` — marks hidden
    in the document."""
    d = _Doc('mark_time').free('A', 0, 0).free('B', 5, 0).free('C', 2.5, 3.5)
    d.segment('a', 'B', 'C').segment('b', 'C', 'A').segment('c', 'A', 'B')
    d.angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    d.equal_segments('m', 'b', 'c', count=2).equal_angles('n', 'alpha', 'beta', count=2)
    for el_id in hidden:
        d.look(el_id, visible=False)
    return d.doc


# m: hidden, enters in [1, 2] (fade, window [1.25, 1.75]), exits in [2, 3]
# (fade, window [2.2, 2.6]); n: hidden, enters in [1, 2] (create, same window).
TIMELINE = {'version': 2, 'keyframes': [
    {'t': 0, 'visible': {'m': False, 'n': False}},
    {'t': 1},
    {'t': 2, 'visible': {'m': True, 'n': True},
     'enter': {'m': {'effect': 'fade', 'duration': 0.5, 'at': 0.25},
               'n': {'effect': 'create', 'duration': 0.5, 'at': 0.25}}},
    {'t': 3, 'visible': {'m': False}, 'exit': {'m': {'effect': 'fade', 'duration': 0.4, 'at': 0.2}}},
    {'t': 4},
]}


def _frame(doc, timeline, t):
    from animageo.native import rendering
    from animageo.native.document import as_document
    return rendering._still_scene(as_document(doc), None, None, {}, timeline, t)


def _parts(scene, el_id):
    """The drawn submobjects of ``el_id`` (no label) or ``None`` when the
    element is not in the frame."""
    mobj = scene.mobject(scene.native_names.by_id[el_id])
    if mobj is None or mobj not in scene.mobjects:
        return None
    return [m for m in mobj.submobjects if not getattr(m, '_animageo_is_label', False)]


def _ticks(scene, el_id):
    """The stroke opacity of each tick of a segment (the strokes after its line)."""
    parts = _parts(scene, el_id)
    assert parts is not None and parts[0].get_stroke_opacity() == pytest.approx(1.0), el_id
    return [round(float(m.get_stroke_opacity()), 6) for m in parts[1:]]


def _arcs(scene, el_id):
    """``(radius, opacity, length)`` of each arc of an angle, outer first
    (the strokes after its sector)."""
    parts = _parts(scene, el_id)
    assert parts is not None, el_id
    vertex = scene.geo.element(scene.native_names.by_id[el_id]).data.vertex
    out = []
    for arc in parts[1:]:
        radius = float(np.linalg.norm(arc.points[-1][:2] - np.asarray(vertex, dtype=float)))
        out.append((round(radius, 6), round(float(arc.get_stroke_opacity()), 6), float(arc.get_arc_length())))
    return sorted(out, reverse=True)


def test_the_static_drawing_keeps_the_ticks_of_a_visible_mark():
    from animageo.native import rendering
    scene = rendering._load(rendering._import_scene(), _doc(), None, None, {})
    for el_id in SEGMENTS:
        assert _ticks(scene, el_id) == [1.0, 1.0]
    for el_id in ANGLES:
        assert [a[1] for a in _arcs(scene, el_id)] == [1.0, 1.0]
    assert _ticks(scene, 'a') == []


@pytest.mark.parametrize('t', [0.0, 0.5, 1.0, 1.2, 1.25])
def test_no_tick_and_no_arc_of_a_mark_before_it_appears(t):
    scene = _frame(_doc(), TIMELINE, t)
    for el_id in SEGMENTS:
        assert _ticks(scene, el_id) == [], (t, el_id)
    for el_id in ANGLES:
        arcs = _arcs(scene, el_id)
        assert [a[1] for a in arcs] == [1.0], (t, el_id)     # the angle's own arc only


def test_inside_the_window_the_ticks_follow_the_effect_of_the_mark():
    full = _frame(_doc(), TIMELINE, 1.9)
    half = _frame(_doc(), TIMELINE, 1.5)                      # progress 0.5 of both entrances
    for el_id in SEGMENTS:
        assert _ticks(full, el_id) == [1.0, 1.0]
        assert _ticks(half, el_id) == [0.5, 0.5]              # fade: the opacity of the mark
    for el_id in ANGLES:
        (r_out, op_out, len_out), (r_in, op_in, len_in) = _arcs(full, el_id)
        (h_out, hop_out, hlen_out), (h_in, hop_in, hlen_in) = _arcs(half, el_id)
        assert (h_out, h_in) == pytest.approx((r_out, r_in))
        assert (op_out, op_in, hop_out, hop_in) == (1.0, 1.0, 1.0, 1.0)
        # create: the arc of the mark is drawn up to the progress, the angle's own in full
        assert hlen_out == pytest.approx(0.5 * len_out, rel=0.02)
        assert hlen_in == pytest.approx(len_in, rel=1e-6)
    exiting = _frame(_doc(), TIMELINE, 2.4)                   # m: exit at progress 0.5
    for el_id in SEGMENTS:
        assert _ticks(exiting, el_id) == [0.5, 0.5]


@pytest.mark.parametrize('t', [2.6, 2.7, 3.0, 3.5, 4.0])
def test_the_ticks_leave_with_their_mark_the_arcs_stay_with_theirs(t):
    scene = _frame(_doc(), TIMELINE, t)
    for el_id in SEGMENTS:
        assert _ticks(scene, el_id) == [], (t, el_id)
    for el_id in ANGLES:
        assert [a[1] for a in _arcs(scene, el_id)] == [1.0, 1.0], (t, el_id)


def test_a_mark_hidden_in_the_document_puts_its_ticks_when_the_timeline_shows_it():
    doc = _doc(hidden=('m', 'n'))
    timeline = {'version': 2, 'keyframes': [{'t': 0}, {'t': 1, 'visible': {'m': True, 'n': True}}, {'t': 2}]}
    before, after = _frame(doc, timeline, 0.0), _frame(doc, timeline, 1.5)
    for el_id in SEGMENTS:
        assert _ticks(before, el_id) == [] and _ticks(after, el_id) == [1.0, 1.0]
    for el_id in ANGLES:
        assert len(_arcs(before, el_id)) == 1 and len(_arcs(after, el_id)) == 2


def test_the_steps_of_a_construction_show_the_ticks_from_the_step_of_the_mark():
    """``steps_timeline``: the targets appear first, the mark in its step —
    until its window opens the targets carry no tick (rc4: from their own
    step on)."""
    from animageo.native.timeline import steps_timeline
    doc = _doc()
    steps = steps_timeline(doc).keyframes
    frames = sorted(steps['keyframes'], key=lambda kf: kf['t'])
    shown = next(kf['t'] for kf in frames if (kf.get('visible') or {}).get('m') is True)
    before = max(kf['t'] for kf in frames if kf['t'] < shown)
    side = next(kf['t'] for kf in frames if (kf.get('visible') or {}).get('b') is True)
    assert side < shown
    for t in (side, before):
        scene = _frame(doc, steps, t)
        assert _ticks(scene, 'b') == [], t
    end = _frame(doc, steps, frames[-1]['t'])
    assert _ticks(end, 'b') == [1.0, 1.0] and len(_arcs(end, 'alpha')) == 2


def _png(doc):
    from PIL import Image
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        native.render(doc, fmt='png', out=f.name, video={'fps': FPS, 'quality': 'low'})
        return np.asarray(Image.open(f.name).convert('RGBA'))


def test_the_video_draws_the_ticks_only_while_their_mark_is_in_the_frame():
    """The frames the video writes (before the codec) are the static drawing
    without the marks before their window and with them after it."""
    doc = _doc()
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'m': False, 'n': False}},
        {'t': 1, 'visible': {'m': True, 'n': True}, 'enter': {'m': {'effect': 'fade', 'duration': 0.4, 'at': 0.3},
                                                              'n': {'effect': 'fade', 'duration': 0.4, 'at': 0.3}}},
        {'t': 2, 'visible': {'m': False, 'n': False}, 'exit': {'m': 'fade', 'n': 'fade'}},
        {'t': 2.6},
    ]}
    without, marked = _png(_doc(hidden=('m', 'n'))), _png(doc)
    assert _psnr(without, marked) < 50                       # the ticks and the arcs are seen
    expect = {0.0: without, 0.2: without, 0.8: marked, 1.0: marked, 1.4: without, 2.3: without}
    got, count, times = _video_frames(doc, timeline, set(range(40)))
    assert count == len(times)
    for t, image in expect.items():
        n = min(range(count), key=lambda i: abs(times[i] - t))
        assert abs(times[n] - t) < 1e-9, (t, times[n])
        assert _psnr(got[n], image) >= 60, (t, _psnr(got[n], image), _psnr(got[n], marked))


def test_the_frame_is_the_video_frame_inside_the_windows_of_the_marks():
    _assert_frames(_doc(), TIMELINE, list(range(0, 40)))
