"""Scene-level PDF / EPS export tests (require manim + pycairo).

The top-level ``from animageo.animageo import AnimaGeoScene`` makes ``conftest``
skip this whole module when manim is unavailable. Drives
``AnimaGeoScene.exportPDF`` / ``exportEPS`` end-to-end and checks the cairo
vector surfaces produce valid, correctly-sized files — mirroring the existing
SVG path (``exportSVG``).
"""
import logging
import re
import textwrap

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.parsers.svg_parser import _make_cairo_surface


def _framed_scene(code, *, width=480, height=400, ptUnit=80):
    """Build a scene from DSL ``code`` with a deterministic export frame and
    materialised mobjects (the cairo path walks ``scene.mobjects``)."""
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(export={"size": {"width": width, "height": height}})
    exp = s.style.export
    exp.update(ptUnit=ptUnit, ptUnit_style=ptUnit, ptUnit_ggb=ptUnit,
               ptWidth=width, ptHeight=height, ptXZero=width / 4, ptYZero=height * 0.85)
    s._set_camera_from_export(exp)
    s.addAllGeometry(show=True)
    return s


TRIANGLE = """
    A = Point(0, 0)
    B = Point(4, 0)
    C = Point(1, 3)
    p = Polygon(A, B, C)
    k = Circle(A, 2)
"""


class TestPDF:
    def test_header_and_nonempty(self, tmp_path):
        s = _framed_scene(TRIANGLE)
        out = tmp_path / "fig.pdf"
        ret = s.exportPDF(str(out))
        assert ret == str(out)
        data = out.read_bytes()
        assert data[:5] == b"%PDF-"
        assert len(data) > 500

    def test_returns_path_and_writes(self, tmp_path):
        s = _framed_scene("A = Point(1, 1)\nA.style.label_visible = True")
        out = tmp_path / "p.pdf"
        s.exportPDF(str(out))
        assert out.exists() and out.stat().st_size > 0


class TestEPS:
    def test_header(self, tmp_path):
        s = _framed_scene(TRIANGLE)
        out = tmp_path / "fig.eps"
        s.exportEPS(str(out))
        head = out.read_bytes()[:23]
        assert head.startswith(b"%!PS-Adobe-3.0 EPSF")

    @pytest.mark.parametrize("dpi,expected", [
        (96, "0 0 360 300"),   # 480*0.75 x 400*0.75
        (72, "0 0 480 400"),   # 1:1 px==pt
    ])
    def test_boundingbox_scales_with_dpi(self, tmp_path, dpi, expected):
        s = _framed_scene("A = Point(0,0)\nB = Point(4,0)\nm = Segment(A,B)")
        out = tmp_path / f"bb_{dpi}.eps"
        s.exportEPS(str(out), dpi=dpi)
        txt = out.read_text(errors="ignore")[:2000]
        bb = re.search(r"%%BoundingBox:\s*(.+)", txt)
        assert bb is not None
        assert bb.group(1).strip() == expected

    def test_transparency_warning(self, tmp_path, caplog):
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(4, 0)
            C = Point(1, 3)
            p = Polygon(A, B, C)
            p.style.fill_opacity = 0.4
        """)
        out = tmp_path / "t.eps"
        with caplog.at_level(logging.WARNING, logger="animageo.animageo"):
            s.exportEPS(str(out))
        assert any("transparency" in r.message.lower() for r in caplog.records)

    def test_no_transparency_no_warning(self, tmp_path, caplog):
        s = _framed_scene("A = Point(0,0)\nB = Point(4,0)\nm = Segment(A,B)")
        out = tmp_path / "ok.eps"
        with caplog.at_level(logging.WARNING, logger="animageo.animageo"):
            s.exportEPS(str(out))
        assert not any("transparency" in r.message.lower() for r in caplog.records)


class TestSVGRegression:
    """The refactor of exportSVG through _export_cairo must not change output."""

    def test_svg_still_xml(self, tmp_path):
        s = _framed_scene(TRIANGLE)
        out = tmp_path / "fig.svg"
        ret = s.exportSVG(str(out))
        assert ret == str(out)
        assert out.read_bytes()[:5] == b"<?xml"


class TestSurfaceFactory:
    def test_unknown_kind_raises(self, tmp_path):
        with pytest.raises(ValueError):
            _make_cairo_surface("tiff", str(tmp_path / "x.tiff"), 10, 10)
