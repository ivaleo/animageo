"""Tests for the GGB → .pyi stub generator."""

import numpy as np
from pathlib import Path

from animageo.geo.construction import Construction
from animageo.parsers import dsl
from animageo.parsers.dsl.stub_gen import _proxy_type_for, write_ggb_stubs


class TestProxyTypeMapping:
    def test_point_maps_to_point_proxy(self):
        from animageo.geo.lib_elements import Point
        assert _proxy_type_for(Point([0, 0])) == 'Point'

    def test_segment_before_line(self):
        from animageo.geo.lib_elements import Segment
        s = Segment(np.array([0, 0]), np.array([1, 1]))
        # Segment inherits from Line — must map to 'Segment', not 'Line'.
        assert _proxy_type_for(s) == 'Segment'

    def test_arc_before_circle(self):
        from animageo.geo.lib_elements import Arc
        a = Arc(np.array([0, 0]), 1, [0, np.pi])
        assert _proxy_type_for(a) == 'Arc'

    def test_circle_base(self):
        from animageo.geo.lib_elements import Circle
        c = Circle(np.array([0, 0]), 2)
        assert _proxy_type_for(c) == 'Circle'

    def test_measure(self):
        from animageo.geo.lib_vars import Measure
        m = Measure(5.0)
        assert _proxy_type_for(m) == 'Measure'

    def test_boolean(self):
        from animageo.geo.lib_vars import Boolean
        b = Boolean(True)
        assert _proxy_type_for(b) == 'Boolean'

    def test_unknown_data_falls_back(self):
        class NotAShape:
            pass
        assert _proxy_type_for(NotAShape()) == 'ElementProxy'


class TestWriteStubs:
    def test_stub_file_created_next_to_ggb(self, tmp_path):
        ggb_path = tmp_path / "myscene.ggb"
        ggb_path.touch()  # fake GGB, we just need the path

        c = Construction()
        dsl.run(c, """
            A = Point(0, 0)
            B = Point(3, 4)
            M = Midpoint(A, B)
        """)

        stub_file = write_ggb_stubs(c, ggb_path)
        assert stub_file is not None
        assert stub_file.name == "myscene_stubs.pyi"
        assert stub_file.parent == tmp_path
        assert stub_file.exists()

    def test_stub_content_lists_elements(self, tmp_path):
        ggb = tmp_path / "s.ggb"
        ggb.touch()

        c = Construction()
        dsl.run(c, """
            A = Point(0, 0)
            B = Point(1, 0)
            L = Line(A, B)
        """)

        stub = write_ggb_stubs(c, ggb)
        text = stub.read_text()

        assert "from animageo.dsl import *" in text
        assert "A: Point" in text
        assert "B: Point" in text
        assert "L: Line" in text

    def test_stub_skips_phantoms(self, tmp_path):
        ggb = tmp_path / "s.ggb"
        ggb.touch()

        c = Construction()
        # Nested call creates a phantom (_1).
        dsl.run(c, "M = Midpoint(Point(0, 0), Point(2, 2))")
        stub = write_ggb_stubs(c, ggb)
        text = stub.read_text()

        assert "M: Point" in text
        # Phantom names starting with _ are filtered out.
        assert "_1" not in text
        assert ": " in text  # sanity — at least one declaration

    def test_stub_skips_non_identifier_names(self, tmp_path):
        ggb = tmp_path / "s.ggb"
        ggb.touch()

        c = Construction()
        dsl.run(c, "A = Point(0, 0)")
        # Manually add a bad-name element.
        from animageo.geo.lib_elements import Element, Point
        c.elements.append(Element("has space", Point([1, 1])))
        c.elements.append(Element("1starts-with-digit", Point([2, 2])))

        stub = write_ggb_stubs(c, ggb)
        text = stub.read_text()

        assert "A: Point" in text
        assert "has space" not in text
        assert "1starts" not in text

    def test_stub_handles_empty_construction(self, tmp_path):
        ggb = tmp_path / "s.ggb"
        ggb.touch()
        c = Construction()
        stub = write_ggb_stubs(c, ggb)
        assert stub.exists()
        # Should still have the boilerplate import.
        assert "from animageo.dsl import *" in stub.read_text()

    def test_stub_groups_by_type(self, tmp_path):
        ggb = tmp_path / "s.ggb"
        ggb.touch()
        c = Construction()
        dsl.run(c, """
            A = Point(0, 0)
            B = Point(1, 0)
            C = Point(0, 1)
            L1 = Line(A, B)
            L2 = Line(B, C)
        """)
        stub = write_ggb_stubs(c, ggb)
        text = stub.read_text()

        # Each proxy-type gets a header comment.
        assert "# ── Line ──" in text
        assert "# ── Point ──" in text


class TestLoadGGBIntegration:
    """Stub file appears next to the .ggb after loadGGB()."""

    def test_loadggb_generates_stub_by_default(self, tmp_path):
        # Use a real GGB file from the examples — simplest one available.
        import shutil
        src = Path(__file__).parent.parent / "examples"
        if not src.exists():
            # Examples not bundled with test env — skip.
            import pytest
            pytest.skip("examples/ directory not available")

        # Grab any .ggb file we can find.
        candidates = list(src.rglob("*.ggb"))
        if not candidates:
            import pytest
            pytest.skip("no .ggb examples available")
        ggb_src = candidates[0]

        ggb_tmp = tmp_path / ggb_src.name
        shutil.copy(ggb_src, ggb_tmp)

        from animageo.animageo import AnimaGeoScene
        scene = AnimaGeoScene()
        scene.loadGGB(str(ggb_tmp))

        stub = ggb_tmp.with_name(ggb_tmp.stem + "_stubs.pyi")
        assert stub.exists()
        text = stub.read_text()
        assert "from animageo.dsl import *" in text
