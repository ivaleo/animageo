"""The tip of a vector goes with its stem under the effects (1.11.0rc7):
``fade`` gives the tip the opacity it gives the stem; ``write`` reveals the
leaves of the element in order — the stem, then the tip, which appears once
the stem is there (the last leaf: ``round(a·2) = 2``, from ``a = 3/4``), as
the manim ``Create`` of an arrow (``lag_ratio = 1``) draws the tip after its
line. Before, the fade of the stem (``set_fill`` of its family) took the
fill of the tip to 0 and both effects hid the tip for good."""
import numpy as np
import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo.native.paint_fixtures import _Doc  # noqa: E402

from .test_native_frame_equals_video import _assert_frames  # noqa: E402

TIMES = [round(x, 3) for x in np.linspace(0.0, 1.0, 11)]


def _doc():
    d = _Doc('tip').free('A', 0, 0).free('B', 5, 2).free('C', 1, 3)
    d.vector('v', 'A', 'B').segment('s', 'A', 'C')
    return d.doc


def _timeline(effect):
    return {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'v': False}},
        {'t': 1, 'visible': {'v': True}, 'enter': {'v': {'effect': effect, 'duration': 1.0}}},
        {'t': 2, 'visible': {'v': False}, 'exit': {'v': {'effect': 'fade', 'duration': 1.0}}},
    ]}


def _parts(scene):
    """``(stem, tip)`` of the vector as drawn."""
    from animageo.ui import CustomArrowTip
    group = scene.mobject(scene.native_names.by_id['v'])
    if group is None:
        return None, None
    leaves = group.family_members_with_points()
    tips = [m for m in leaves if isinstance(m, CustomArrowTip)]
    stems = [m for m in leaves if not isinstance(m, CustomArrowTip)]
    assert len(tips) == 1 and len(stems) == 1
    return stems[0], tips[0]


def _opacities(doc, timeline, t):
    from animageo.native import rendering
    from animageo.native.document import as_document
    scene = rendering._still_scene(as_document(doc), None, None, {}, timeline, t)
    stem, tip = _parts(scene)
    if stem is None:
        return None
    return (stem.get_stroke_opacity(), tip.get_fill_opacity(), tip.get_stroke_opacity())


def _static(doc):
    """The opacities of the vector without a timeline (the tip is a fill)."""
    from animageo.native import rendering
    from animageo.native.document import as_document
    stem, tip = _parts(rendering._load(rendering._import_scene(), as_document(doc), None, None, {}))
    base = (stem.get_stroke_opacity(), tip.get_fill_opacity(), tip.get_stroke_opacity())
    assert base[0] > 0 and base[1] > 0
    return np.array(base)


def test_the_tip_is_drawn_in_full_when_the_effect_is_done():
    doc = _doc()
    base = _static(doc)
    for effect in ('fade', 'write', 'create', 'grow'):
        assert np.allclose(_opacities(doc, _timeline(effect), 1.0), base), effect


def test_fade_gives_the_tip_the_opacity_of_the_stem_frame_by_frame():
    doc = _doc()
    base = _static(doc)
    for phase in ('enter', 'exit'):
        for t in TIMES:
            at = t if phase == 'enter' else 1.0 + t
            alpha = t if phase == 'enter' else 1.0 - t
            got = _opacities(doc, _timeline('fade'), at)
            if alpha <= 0:
                assert got is None or max(got) == pytest.approx(0.0), (phase, t)
                continue
            assert np.allclose(got, alpha * base), (phase, t, got)


def test_write_reveals_the_stem_then_the_tip_frame_by_frame():
    doc = _doc()
    base = _static(doc)
    for t in TIMES:
        shown = int(round(t * 2))                 # leaves open: the stem, then the tip
        got = _opacities(doc, _timeline('write'), t)
        if shown == 0:
            assert got is None or max(got) == pytest.approx(0.0), t
            continue
        tip = 1.0 if shown == 2 else 0.0
        assert np.allclose(got, [base[0], tip * base[1], tip * base[2]]), (t, got)


@pytest.mark.parametrize('effect', ['fade', 'write'])
def test_the_video_draws_the_tip_as_the_frame(effect):
    _assert_frames(_doc(), _timeline(effect), [0, 3, 5, 8, 9, 10, 13, 16])
