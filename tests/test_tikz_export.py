"""Scene-level TikZ export tests (require manim).

The top-level ``from animageo.animageo import AnimaGeoScene`` makes
``conftest`` skip this whole module when manim is unavailable. Drives
``AnimaGeoScene.exportTikZ`` end-to-end and, when a LaTeX toolchain is present,
compiles the standalone output to PDF.
"""
import shutil
import subprocess
import textwrap

import pytest

from animageo.animageo import AnimaGeoScene


def _framed_scene(code, *, width=480, height=400, ptUnit=80, centered=False):
    """Build a scene from DSL ``code`` with a deterministic export frame.

    ``centered=True`` puts the origin at the canvas centre so symmetric curves
    (conics/functions) are framed; otherwise the origin sits near the
    lower-left, matching a typical triangle layout.
    """
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    s.applyStyle(export={"size": {"width": width, "height": height}})
    exp = s.style.export
    xzero = width / 2 if centered else width / 4
    yzero = height / 2 if centered else height * 0.85
    exp.update(ptUnit=ptUnit, ptUnit_style=ptUnit, ptUnit_ggb=ptUnit,
               ptWidth=width, ptHeight=height, ptXZero=xzero, ptYZero=yzero)
    s._set_camera_from_export(exp)
    return s


class TestSceneEmitters:
    def test_point_and_label(self):
        s = _framed_scene("""
            A = Point(1, 2)
            A.style.label_visible = True
        """)
        tex = s.exportTikZ()
        assert "circle" in tex            # point marker
        assert "\\node" in tex            # label node
        assert "{$A$}" in tex

    def test_segment_coords(self):
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(4, 0)
            m = Segment(A, B)
        """)
        assert "(0,0) -- (4,0)" in s.exportTikZ()

    def test_circle_native_primitive(self):
        s = _framed_scene("""
            C = Point(1, 1)
            k = Circle(C, 2)
        """)
        assert "(1,1) circle (2)" in s.exportTikZ()

    def test_polygon_cycle(self):
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(2, 0)
            C = Point(0, 2)
            p = Polygon(A, B, C)
        """)
        assert "-- cycle" in s.exportTikZ()

    def test_vector_arrow(self):
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(2, 1)
            v = Vector(A, B)
        """)
        assert "->" in s.exportTikZ()

    def test_angle_arc(self):
        # A non-right angle renders as a swept arc.
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(3, 0)
            C = Point(2, 2)
            a = Angle(B, A, C)
        """)
        assert "arc (" in s.exportTikZ()

    def test_right_angle_marker(self):
        # A 90° angle renders as a square marker (two connected segments), not an arc.
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(3, 0)
            C = Point(0, 3)
            a = Angle(B, A, C)
        """)
        tex = s.exportTikZ()
        assert "arc (" not in tex
        assert "--" in tex

    def test_ellipse_conic(self):
        s = _framed_scene('e = Conic("x^2/9 + y^2/4 = 1")')
        assert "ellipse" in s.exportTikZ()

    def test_function_polyline(self):
        s = _framed_scene('f = Function("y = 0.2*x^2")')
        assert "plot coordinates" in s.exportTikZ()

    def test_line_clipped_to_viewport(self):
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(1, 1)
            l = Line(A, B)
        """)
        assert "--" in s.exportTikZ()

    def test_picture_unit_and_clip(self):
        s = _framed_scene("A = Point(0, 0)")
        tex = s.exportTikZ()
        assert "x=" in tex and "cm" in tex
        assert "\\clip" in tex

    def test_clip_disabled(self):
        s = _framed_scene("A = Point(0, 0)")
        assert "\\clip" not in s.exportTikZ(clip=False)

    def test_standalone_wrapper(self):
        s = _framed_scene("A = Point(0, 0)")
        tex = s.exportTikZ(standalone=True)
        assert "\\documentclass" in tex
        assert "\\begin{document}" in tex

    def test_invisible_element_skipped(self):
        s = _framed_scene("""
            A = Point(0, 0)
            B = Point(5, 5)
            B.style.visible = False
        """)
        tex = s.exportTikZ()
        assert "(0,0) circle" in tex
        assert "(5,5) circle" not in tex

    def test_writes_file(self, tmp_path):
        s = _framed_scene("A = Point(0, 0)")
        out = tmp_path / "fig.tex"
        text = s.exportTikZ(str(out))
        assert out.exists()
        assert out.read_text(encoding="utf-8") == text

    def test_options_and_kwargs_are_exclusive(self):
        from animageo.exporters.tikz import TikZOptions
        s = _framed_scene("A = Point(0, 0)")
        with pytest.raises(TypeError):
            s.exportTikZ(options=TikZOptions(), standalone=True)


class TestMoreEmitters:
    """Broader element-type / decoration / option coverage (string assertions)."""

    def test_point_square_marker(self):
        s = _framed_scene("""
            A = Point(0, 0)
            A.style.point_shape = 'square'
        """)
        assert "rectangle" in s.exportTikZ()

    def test_point_diamond_marker(self):
        s = _framed_scene("""
            A = Point(0, 0)
            A.style.point_shape = 'diamond'
        """)
        tex = s.exportTikZ()
        marker = next(line for line in tex.splitlines() if "-- cycle" in line)
        assert "rectangle" not in marker
        assert marker.count("shift=") == 4

    def test_point_cross_marker(self):
        s = _framed_scene("""
            A = Point(0, 0)
            A.style.point_shape = 'cross'
        """)
        tex = s.exportTikZ()
        # two diagonal strokes positioned by pt shifts
        assert tex.count("shift=") >= 2

    def test_dashed_circle(self):
        s = _framed_scene("""
            C = Point(0, 0)
            k = Circle(C, 2)
            k.style.stroke_dash_ratio = 0.4
        """, centered=True)
        assert "dash pattern=on" in s.exportTikZ()

    def test_segment_tick_marks_add_strokes(self):
        plain = _framed_scene("""
            A = Point(-3, 0); B = Point(3, 0)
            m = Segment(A, B)
        """, centered=True).exportTikZ()
        ticked = _framed_scene("""
            A = Point(-3, 0); B = Point(3, 0)
            m = Segment(A, B); m.style.tick_count = 3
        """, centered=True).exportTikZ()
        assert ticked.count("\\draw") > plain.count("\\draw")

    def test_arc(self):
        s = _framed_scene("""
            c = Circle(Point(0, 0), 3)
            ar = Arc(c, Point(3, 0), Point(0, 3))
        """, centered=True)
        assert "arc (" in s.exportTikZ()

    def test_circle_sector_fill_and_arc(self):
        s = _framed_scene("""
            ce = Point(0, 0)
            sec = CircleSector(ce, Point(3, 0), Point(0, 3))
            sec.style.fill = '#d0ffd0'; sec.style.fill_opacity = 0.6
        """, centered=True)
        tex = s.exportTikZ()
        assert "arc (" in tex
        assert "-- cycle" in tex

    def test_parabola_plot(self):
        s = _framed_scene('p = Conic("y = 0.25*x^2 - 2")', centered=True)
        assert "plot coordinates" in s.exportTikZ()

    def test_hyperbola_two_branches(self):
        s = _framed_scene('h = Conic("x^2/4 - y^2/4 = 1")', centered=True)
        # two branches → at least two plot paths
        assert s.exportTikZ().count("plot coordinates") >= 2

    def test_degenerate_conic_lines(self):
        s = _framed_scene('il = Conic("x^2 - y^2 = 0")', centered=True)
        tex = s.exportTikZ()
        assert tex.count(" -- ") >= 2   # two crossing lines

    def test_implicit_curve_segments(self):
        s = _framed_scene('c = ImplicitCurve("x^2 + y^2 = 4")', centered=True)
        assert s.exportTikZ().count("\\draw") > 10

    def test_piecewise_function(self):
        # GeoGebra If[...] (square brackets) → Piecewise → sampled polyline.
        s = _framed_scene('f = Function("y = If[x < 0, -x - 1, x - 1]")', centered=True)
        assert "plot coordinates" in s.exportTikZ()

    def test_cyrillic_label_passthrough(self):
        s = _framed_scene("""
            A = Point(0, 0)
            A.style.label_visible = True
            A.style.label_text = r'Точка'
        """)
        assert "{Точка}" in s.exportTikZ()

    def test_background_custom_color(self):
        s = _framed_scene("A = Point(0, 0)")
        assert "FFE0E0" in s.exportTikZ(background="#ffe0e0")

    def test_background_off(self):
        s = _framed_scene("A = Point(0, 0)")
        tex = s.exportTikZ(background=False)
        # only the clip rectangle remains, no background fill rectangle
        assert tex.count("rectangle") <= 1

    def test_emit_font_size_toggle(self):
        code = """
            A = Point(0, 0)
            A.style.label_visible = True
        """
        assert "\\fontsize" in _framed_scene(code).exportTikZ(emit_font_size=True)
        assert "\\fontsize" not in _framed_scene(code).exportTikZ(emit_font_size=False)

    def test_dpi_changes_coordinate_unit(self):
        import re
        code = "A = Point(0, 0)"

        def xunit(dpi):
            tex = _framed_scene(code).exportTikZ(dpi=dpi)
            return float(re.search(r"x=([0-9.]+)cm", tex).group(1))

        # Higher dpi → physically smaller unit (cm per MU).
        assert xunit(72) > xunit(150)


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex not installed")
class TestCompile:
    def test_standalone_compiles(self, tmp_path):
        s = _framed_scene(r"""
            A = Point(0, 0)
            B = Point(4, 0)
            C = Point(1, 3)
            A.style.label_visible = True
            poly = Polygon(A, B, C)
            circ = Circle(C, 1.5)
            ang = Angle(B, A, C)
            v = Vector(B, C)
            sq = Point(3, 2)
            sq.style.point_shape = 'square'
        """)
        tex_path = tmp_path / "fig.tex"
        s.exportTikZ(str(tex_path), standalone=True)
        proc = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout[-2000:]
        assert (tmp_path / "fig.pdf").exists()

    def test_curves_and_decorations_compile(self, tmp_path):
        s = _framed_scene("""
            k = Conic("x^2/16 + y^2/9 = 1")
            p = Conic("y = 0.25*x^2 - 4")
            h = Conic("x^2/4 - y^2/9 = 1")
            f = Function("y = sin(x)")
            ic = ImplicitCurve("x^2 + y^2 = 9")
            c = Circle(Point(0, 0), 2); c.style.stroke_dash_ratio = 0.4
            A = Point(-3, 0); B = Point(3, 0)
            m = Segment(A, B); m.style.tick_count = 2
        """, centered=True, ptUnit=40, width=640, height=520)
        tex_path = tmp_path / "curves.tex"
        s.exportTikZ(str(tex_path), standalone=True)
        proc = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout[-2000:]
        assert (tmp_path / "curves.pdf").exists()

    def test_cyrillic_label_standalone_compiles(self, tmp_path):
        s = _framed_scene("""
            A = Point(0, 0)
            A.style.label_visible = True
            A.style.label_text = r'Точка $K$'
        """)
        tex_path = tmp_path / "cyr.tex"
        s.exportTikZ(str(tex_path), standalone=True)
        proc = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout[-2000:]
