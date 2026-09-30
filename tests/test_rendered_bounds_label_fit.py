"""Regression: ``rendered_bounds`` must reserve room for auto-placed labels.

A tight ``content.source="rendered_bounds"`` crop is measured by
``applyStyle``; label auto-placement then shifts labels outward from the
geometry. If the crop is frozen *before* placement (the original bug), labels
of edge/corner elements end up outside the canvas and clip on export.
"""
import pytest

from animageo.animageo import AnimaGeoScene


def _wide_triangle_scene():
    """A wide, thin triangle whose vertices sit at the extreme corners, so
    auto-placement pushes their labels outward past a tight crop."""
    scene = AnimaGeoScene()
    scene.style.export.update({
        'ptUnit': 50,
        'ptWidth': 600,
        'ptHeight': 200,
        'ptXZero': 300,
        'ptYZero': 100,
        'ptUnit_ggb': 50,
    })
    scene.putCode(
        "A = Point(-5, -1.5)\n"
        "B = Point(5, 1.5)\n"
        "C = Point(5, -1.5)\n"
        "t = Polygon(A, B, C)\n"
    )
    for name in ("A", "B", "C"):
        scene.element(name).style['label_visible'] = True
    return scene


def test_rendered_bounds_reserves_room_for_auto_placed_corner_labels():
    scene = _wide_triangle_scene()

    # Mirror the loadGGB order: applyStyle (computes the rendered_bounds crop),
    # then autoPlaceLabels (shifts labels). The fix makes applyStyle re-fit the
    # crop around the placed labels; the explicit call below stands in for
    # loadGGB's own post-layout autoPlaceLabels().
    scene.applyStyle(
        style={'overlay': {'label_placement': {'enabled': True}}},
        content={'source': 'rendered_bounds', 'padding': 0},
        export={'size': [480, 'auto']},
    )
    scene.autoPlaceLabels()

    frame = scene.camera.frame
    fl, fr = frame.get_left()[0], frame.get_right()[0]
    fb, ft = frame.get_bottom()[1], frame.get_top()[1]
    tol = 0.02 * (fr - fl)  # ~2% slack for stroke width / float noise

    for name in ("A", "B", "C"):
        elem = scene.element(name)
        mobj = scene.CreateMObject(elem, z_auto=True)
        assert mobj is not None
        assert mobj.get_left()[0] >= fl - tol, f"{name}'s label clips off the left edge"
        assert mobj.get_right()[0] <= fr + tol, f"{name}'s label clips off the right edge"
        assert mobj.get_bottom()[1] >= fb - tol, f"{name}'s label clips off the bottom edge"
        assert mobj.get_top()[1] <= ft + tol, f"{name}'s label clips off the top edge"


def test_rendered_bounds_without_placement_is_unchanged():
    """With placement disabled the crop must stay tight to the geometry
    (no spurious re-fit / margin)."""
    scene = _wide_triangle_scene()
    scene.applyStyle(
        style={'overlay': {'label_placement': {'enabled': False}}},
        content={'source': 'rendered_bounds', 'padding': 0},
        export={'size': [480, 'auto']},
    )
    # Geometry x-extent is [-5, 5]; the crop's source rect must hug it (the
    # point dots add a sub-pixel radius, nothing label-sized).
    export = scene.style.export
    assert export.get('sourceLeftPx') is not None
    width_units = (export['sourceRightPx'] - export['sourceLeftPx']) / export['ptUnit_ggb']
    assert width_units == pytest.approx(10, abs=0.5)
