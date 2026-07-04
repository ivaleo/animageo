"""End-to-end wiring of the Phase-1 (P0) label-placement options through
``compute_label_layout`` on a real scene. Verifies the new config knobs are
read and applied, and that the default path is unchanged.
"""
import pytest

from animageo.animageo import AnimaGeoScene
import animageo.label_placement as lp

ANCHORS = {'TL', 'TC', 'TR', 'ML', 'MC', 'MR', 'BL', 'BC', 'BR'}


def _three_points_scene():
    scene = AnimaGeoScene()
    scene.style.export.update({
        'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
        'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50,
    })
    scene.putCode("A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n")
    for n in ('A', 'B', 'C'):
        scene.element(n).style['label_visible'] = True
    scene.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    return scene


def test_default_layout_labels_all_points():
    scene = _three_points_scene()
    layout = lp.compute_label_layout(scene)
    assert set(layout) == {'A', 'B', 'C'}
    for pl in layout.values():
        assert pl.label_anchor in ANCHORS


def test_position_priority_changes_offset_direction():
    """An isolated point under a high preference weight should sit in the
    canonical best direction: NE for 'classic', due-North for 'perceptual'."""
    scene = _three_points_scene()
    classic = lp.compute_label_layout(
        scene, cfg={'w_anchor': 0.0, 'position_priority': 'classic', 'w_pref': 100.0})
    perceptual = lp.compute_label_layout(
        scene, cfg={'w_anchor': 0.0, 'position_priority': 'perceptual', 'w_pref': 100.0})

    cx, cy = classic['B'].offset_ggb
    px, py = perceptual['B'].offset_ggb
    assert cx > 0 and cy > 0          # classic → NE
    assert py > 0 and abs(px) < abs(cx)  # perceptual → ~due North


def test_new_knobs_run_and_preserve_label_set():
    scene = _three_points_scene()
    variants = [
        {'repair_iterations': 3},
        {'consistent_placement': True},
        {'soft_falloff_px': 4.0},
        {'position_priority': 'classic', 'w_pref': 50.0,
         'repair_iterations': 2, 'consistent_placement': True,
         'soft_falloff_px': 4.0},
    ]
    for cfg in variants:
        layout = lp.compute_label_layout(scene, cfg=cfg)
        assert set(layout) == {'A', 'B', 'C'}, cfg
        for pl in layout.values():
            assert pl.label_anchor in ANCHORS


def test_consistency_makes_isolated_points_share_anchor():
    scene = _three_points_scene()
    layout = lp.compute_label_layout(
        scene, cfg={'position_priority': 'classic', 'w_pref': 50.0,
                    'consistent_placement': True})
    anchors = {pl.label_anchor for pl in layout.values()}
    assert len(anchors) == 1  # systematic: all three points labelled alike


def test_fill_contrast_collects_fills_and_runs():
    """P1-C placement: a filled polygon is collected as a fill obstacle and the
    contrast-weighted layout runs end-to-end."""
    scene = AnimaGeoScene()
    scene.style.export.update({
        'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
        'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50,
    })
    scene.putCode("A = Point(-2,-1)\nB = Point(2,-1)\nC = Point(0,2)\n"
                  "t = Polygon(A, B, C)\nP = Point(0, 0.2)\n")
    scene.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    scene.element('P').style['label_visible'] = True
    tri = scene.element('t')
    tri.style['fill'] = '#101010'        # near-black, dense
    tri.style['fill_opacity'] = 1.0

    fills = lp._collect_fills(scene)
    poly = [f for f in fills if f[0] == 'poly']
    assert poly, "filled polygon should be collected"
    assert poly[0][2] == pytest.approx(1.0)        # opacity
    assert poly[0][3] < 0.2                          # dark luminance

    layout = lp.compute_label_layout(scene, cfg={'enabled': True, 'w_fill': 10.0})
    assert 'P' in layout


def test_respect_current_preserves_manual_side():
    """P1-D: a manually placed offset on the LEFT keeps its SIDE when
    respect_current_position is on (instead of snapping to the default NE), but
    its (often large) GGB magnitude is NOT reproduced verbatim — it is pulled to
    a compact distance so the label stays close to its point. Pinning the full
    far magnitude was the dominant round-4 "labels drift far from their points"
    regression, so the contract is now: preserve sector, place compactly."""
    import math
    scene = _three_points_scene()
    scene.element('B').style['label_offset_px'] = [-30.0, 0.0]  # manual: left, far

    default = lp.compute_label_layout(scene)  # respect off
    respected = lp.compute_label_layout(
        scene, cfg={'enabled': True, 'respect_current_position': True})

    assert default['B'].offset_ggb[0] > 0          # default would go right (NE)
    assert respected['B'].offset_ggb[0] < 0        # manual left side is preserved
    rmag = math.hypot(*respected['B'].offset_ggb)
    assert rmag < 30.0 - 1e-6   # the far manual magnitude is NOT pinned verbatim
    assert rmag > 6.0           # but it is still a real, substantive distance
