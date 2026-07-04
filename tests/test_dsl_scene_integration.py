"""AnimaGeoScene.putCode / loadCode integration with the exec DSL engine.

After Phase 5 (short_parser removal) there's only one engine — the
tests here now verify the default behavior end-to-end through the
scene class, not engine selection.
"""

import numpy as np

from animageo.animageo import AnimaGeoScene


class TestScenePutCode:
    def test_putCode_handles_loops(self):
        s = AnimaGeoScene()
        s.putCode("for i in range(3):\n    p = Point(i, 0)")
        assert s.geo.element("p") is not None
        assert s.geo.element("p_2") is not None
        assert s.geo.element("p_3") is not None

    def test_putCode_handles_kwargs(self):
        s = AnimaGeoScene()
        s.putCode("A = Point(3, 4, name='MyA')")
        # Construction element is "MyA", not "A".
        assert s.geo.element("MyA") is not None
        assert s.geo.element("A") is None

    def test_putCode_field_access(self):
        s = AnimaGeoScene()
        s.putCode("A = Point(3, 4)\nx = A.x")
        assert s.geo.var("x").data == 3.0

    def test_putCode_basic_point(self):
        s = AnimaGeoScene()
        s.putCode("A = Point(3, 4)")
        assert np.allclose(s.geo.element("A").data.coords, [3, 4])

    def test_putCode_nested_midpoint(self):
        s = AnimaGeoScene()
        s.putCode("A = Point(0, 0)\nB = Point(4, 2)\nM = Midpoint(A, B)")
        assert np.allclose(s.geo.element("M").data.coords, [2, 1])

    def test_putCode_rebuilds_dependents_after_redefinition(self):
        s = AnimaGeoScene()
        s.putCode("A = Point(0, 0)\nE = Point(0, 1)\nm = Segment(A, E)")
        s.putCode("E = Point(2, 0)")

        assert np.allclose(s.geo.element("E").data.coords, [2, 0])
        assert np.allclose(s.geo.element("m").data.endpoints[1], [2, 0])


class TestExecFeatures:
    def test_def_with_name_kwarg(self):
        s = AnimaGeoScene()
        s.putCode(
            "def pair(prefix):\n"
            "    A = Point(0, 0, name=f'{prefix}_A')\n"
            "    B = Point(1, 0, name=f'{prefix}_B')\n"
            "    return A, B\n"
            "pair('t1')\n"
            "pair('t2')"
        )
        for label in ["t1_A", "t1_B", "t2_A", "t2_B"]:
            assert s.geo.element(label) is not None, f"missing {label}"

    def test_style_attribute_in_dsl(self):
        s = AnimaGeoScene()
        s.putCode(
            "A = Point(0, 0)\n"
            "A.style.stroke = '#ff0000'"
        )
        assert s.geo.element("A").style["stroke"] == "#ff0000"

    def test_show_false(self):
        s = AnimaGeoScene()
        s.putCode("A = Point(0, 0)", show=False)
        assert s.geo.element("A").visible is False
