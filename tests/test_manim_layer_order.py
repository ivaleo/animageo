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
