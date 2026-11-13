from manim.utils.family import extract_mobject_family_members

from animageo import AnimaGeoScene
from animageo.geo.lib_elements import Point


def _display_rows(scene, parent_names):
    parent_by_child = {}
    for parent in scene.mobjects:
        parent_name = getattr(parent, "name", None)
        parent_by_child[id(parent)] = parent_name
        for child in getattr(parent, "submobjects", []) or []:
            parent_by_child[id(child)] = parent_name

    rows = []
    for index, mobject in enumerate(
        extract_mobject_family_members(
            scene.mobjects,
            use_z_index=True,
            only_those_with_points=True,
        )
    ):
        parent_name = parent_by_child.get(id(mobject))
        if parent_name in parent_names:
            rows.append((index, parent_name, type(mobject).__name__, mobject.z_index))
    return rows


def test_polygon_stroke_layer_order_is_stable_after_update():
    scene = AnimaGeoScene()
    scene.putCode(
        """
A = Point(0, 0)
B = Point(2, 0)
C = Point(2, 2)
D = Point(0, 2)
poly, AB, BC, CD, DA = Polygon(A, B, C, D)
diag = Segment(A, C)
"""
    )

    before = _display_rows(scene, {"poly", "diag"})
    poly_stroke_before = max(index for index, name, _, z in before if name == "poly" and z > 1)
    diag_before = min(index for index, name, _, _ in before if name == "diag")
    assert poly_stroke_before < diag_before

    scene.geo.update("A", Point([0.3, 0.2]))
    updates = scene.geo.rebuild()
    scene.updateGeoElements(updates)

    after = _display_rows(scene, {"poly", "diag"})
    poly_stroke_after = max(index for index, name, _, z in after if name == "poly" and z > 1)
    diag_after = min(index for index, name, _, _ in after if name == "diag")
    assert poly_stroke_after < diag_after


def test_area_display_order_recomputes_all_fills_after_update_and_become():
    from tests.test_fill_order_defaults import classic_scene
    scene = classic_scene({'rendering': {'fill_order': 'area'}})
    def fills():
        return [m._animageo_owner for m in scene._ordered_display_family()
                if getattr(m, '_animageo_part', None) == 'fill']
    assert fills() == ['outer', 'inner']
    scene.geo.update('R', Point([.1, 0]))
    scene.updateGeoElements(scene.geo.rebuild())
    assert fills() == ['inner', 'outer']
    scene.geo.update('R', Point([3, 0]))
    scene.updateGeoElements(scene.geo.rebuild())
    assert fills() == ['outer', 'inner']
    assert [m for m in scene.camera.get_mobjects_to_display(scene.mobjects)
            if getattr(m, '_animageo_part', None) == 'fill'] == [
                m for m in scene._ordered_display_family() if getattr(m, '_animageo_part', None) == 'fill']
    # A stationary neighbor must never be baked below a changing fill.
    moving = scene.get_moving_mobjects()
    assert scene.mobject('inner') in moving


def test_area_classic_conic_splits_fill_from_stroke():
    from animageo.geo.lib_conic import Conic
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    scene.putCode('c=Conic("x^2/4+y^2=1")')
    elem = scene.geo.element('c')
    elem.style.update(z_index=8, fill='#ff0000')
    scene.updateAllGeometry()
    group = scene.mobject('c')
    assert group.submobjects[0].z_index == .01
    assert group.submobjects[1].z_index >= 8
    assert group.submobjects[1].get_fill_opacity() == 0


def test_full_native_arc_and_zero_arc_have_distinct_area_domains():
    import math
    from animageo.native.kernel.bridge import to_classic
    from animageo.geo.construction import Element
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    arc = to_classic('arc', {'c': [0, 0], 'r': 2, 'a0': 0, 'a1': math.tau})
    elem = Element('full', arc)
    elem.style.update(fill='#ff0000', label_visible=False)
    scene.geo.add(elem)
    full = scene.CreateMObject(elem)
    assert full._animageo_fill_part.area_style_px2 > 0
    assert full[1].width > 3.9 and full[1].height > 3.9
    arc.angles = [0, 0]
    assert scene.CreateMObject(elem)._animageo_fill_part is None
    arc.angles = [0, math.tau]
    scene.applyStyle(style={'rendering': {'fill_order': 'construction'}})
    legacy = scene.CreateMObject(elem)
    assert legacy[1].width < 1e-6


def test_explicit_fill_can_draw_above_points_without_shifting_the_outline():
    from tests.test_fill_order_defaults import classic_scene
    scene = classic_scene({'rendering': {'fill_order': 'area'}})
    old_stroke = scene.mobject('inner')[1].z_index
    scene.geo.element('inner').style['z_index_fill'] = 100
    scene.updateGeoElements({'inner'})
    family = scene._ordered_display_family()
    assert getattr(family[-1], '_animageo_owner', None) == 'inner'
    assert getattr(family[-1], '_animageo_part', None) == 'fill'
    assert scene.mobject('inner')[1].z_index == old_stroke


def test_classic_conic_point_is_a_body_without_a_fill():
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    scene.putCode('c=Conic("x^2+y^2=0")')
    glyph = scene.mobject('c')[0]
    assert glyph._animageo_part == 'body'
    assert scene.mobject('c')._animageo_fill_part is None
