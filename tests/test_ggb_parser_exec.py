"""End-to-end: ggb_parser runs expressions through the exec DSL engine."""

from pathlib import Path

import pytest


class TestScene10GGBViaExec:
    """End-to-end: a real GGB file loads correctly through the exec engine."""

    def test_scene10_loads_elements(self):
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser

        ggb_path = (
            Path(__file__).parent.parent
            / "examples"
            / "10 - Задача из учебника - 53, окружности 8 кл"
            / "scene10.ggb"
        )
        if not ggb_path.exists():
            pytest.skip("scene10.ggb not available")

        c = Construction()
        view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480,
                'ptXZero': 0, 'ptYZero': 0}
        ggb_parser.load(c, view, str(ggb_path), debug=False)

        # Exec engine should handle unicode element names (α, β, γ).
        assert c.element('α') is not None or c.var('α') is not None
        # Latin names too.
        assert c.element('R') is not None
        assert c.element('Q') is not None

    def test_scene10_elements_have_correct_types(self):
        from animageo.geo.construction import Construction
        from animageo.geo.lib_elements import Point, Circle, Polygon, Angle
        from animageo.parsers import ggb_parser

        ggb_path = (
            Path(__file__).parent.parent
            / "examples"
            / "10 - Задача из учебника - 53, окружности 8 кл"
            / "scene10.ggb"
        )
        if not ggb_path.exists():
            pytest.skip("scene10.ggb not available")

        c = Construction()
        view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480,
                'ptXZero': 0, 'ptYZero': 0}
        ggb_parser.load(c, view, str(ggb_path), debug=False)

        # Spot-check known types from the .ggb.
        assert isinstance(c.element('R').data, Point)
        assert isinstance(c.element('d').data, Circle)
        assert isinstance(c.element('t1').data, Polygon)
