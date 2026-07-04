"""Round-2 feedback fixes: ignore trivial/default GGB offsets, and directional
placement (keep the preferred direction, nudge out, uniform).
"""
import numpy as np
import pytest

from animageo.label_placement import (
    LabelCostModel,
    LabelInfo,
    _DIRECTIONS,
    _solve_greedy,
)

EMPTY = np.empty((0, 2))


def _model():
    return LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0, ptUnit=1.0)


class TestDirectionalPlacement:
    def test_places_along_preferred_direction(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.preferred_dir = 2  # N (up)
        res = _solve_greedy([lbl], [], [], EMPTY, 0.5, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=_model(),
                            directional=True, directional_cap=5.0)
        c = res[0][1]
        assert abs(c[0]) < 1e-6 and c[1] > 0  # straight up

    def test_uses_bisector_direction_when_set(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.1, half_h=0.1)
        lbl.preferred_dir = 0
        lbl.bisector_dir = np.array([1.0, 1.0]) / np.sqrt(2)  # NE exact
        res = _solve_greedy([lbl], [], [], EMPTY, 0.5, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=_model(),
                            directional=True, directional_cap=5.0)
        c = res[0][1]
        assert c[0] > 0 and c[1] > 0
        assert c[1] / c[0] == pytest.approx(1.0)  # on the NE diagonal

    def test_pushes_out_past_obstacle_keeping_direction(self):
        lbl = LabelInfo(name='A', anchor=np.array([0.0, 0.0]),
                        half_w=0.2, half_h=0.1)
        lbl.preferred_dir = 0  # E (right)
        seg = [(np.array([0.5, -5.0]), np.array([0.5, 5.0]))]  # line at x=0.5
        res = _solve_greedy([lbl], seg, [], EMPTY, 0.3, 0.0, (1.0, 10.0, 8.0),
                            1.0, cost_model=_model(),
                            directional=True, directional_cap=10.0)
        c = res[0][1]
        assert abs(c[1]) < 1e-6      # stayed on the East axis (direction kept)
        assert c[0] > 0.7            # pushed past the line at x=0.5 (+half_w)


def test_trivial_offset_not_respected():
    """A near-zero GGB offset is the default, not a manual placement — the label
    should be laid out fresh rather than pinned to the point."""
    from animageo.animageo import AnimaGeoScene
    import animageo.label_placement as lp
    scene = AnimaGeoScene()
    scene.style.export.update({'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
                               'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50})
    scene.putCode("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
    for n in ('A', 'B', 'C'):
        scene.element(n).style['label_visible'] = True
    scene.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    scene.element('B').style['label_offset_px'] = [0.5, 0.0]   # trivial default

    layout = lp.compute_label_layout(
        scene, cfg={'enabled': True, 'respect_current_position': True,
                    'respect_min_offset_px': 6.0})
    ox, oy = layout['B'].offset_ggb
    assert (ox ** 2 + oy ** 2) ** 0.5 > 6.0  # placed fresh, not kept at [0.5,0]


def test_substantive_offset_is_respected():
    from animageo.animageo import AnimaGeoScene
    import animageo.label_placement as lp
    scene = AnimaGeoScene()
    scene.style.export.update({'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
                               'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50})
    scene.putCode("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
    for n in ('A', 'B', 'C'):
        scene.element(n).style['label_visible'] = True
    scene.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    scene.element('B').style['label_offset_px'] = [-40.0, 0.0]  # deliberate: left

    layout = lp.compute_label_layout(
        scene, cfg={'enabled': True, 'respect_current_position': True,
                    'respect_min_offset_px': 6.0})
    assert layout['B'].offset_ggb[0] < 0  # kept on the manual (left) side
