"""Pure-Python tests for the TikZ document/number/colour layer (no manim)."""
from animageo.exporters.tikz.document import TikZDocument, fmt_num, hex_of
from animageo.exporters.tikz.options import TikZOptions


class TestFmtNum:
    def test_strips_trailing_zeros(self):
        assert fmt_num(1.0, 4) == "1"
        assert fmt_num(1.2500, 4) == "1.25"
        assert fmt_num(-0.0, 4) == "0"

    def test_rounds_subthreshold_to_zero(self):
        assert fmt_num(1e-9, 4) == "0"
        assert fmt_num(0.00004, 4) == "0"

    def test_handles_nan_inf(self):
        assert fmt_num(float("nan"), 4) == "0"
        assert fmt_num(float("inf"), 4) == "0"
        assert fmt_num(None, 4) == "0"


class TestHexOf:
    def test_normalizes_hex(self):
        assert hex_of("#1565c0") == "1565C0"
        assert len(hex_of("#fff")) == 6
        assert len(hex_of(None)) == 6


class TestDocument:
    def test_color_interning_is_stable(self):
        doc = TikZDocument(TikZOptions())
        a = doc.color("#1565c0")
        b = doc.color("#1565C0")  # same colour, different case
        c = doc.color("#ff0000")
        assert a == b
        assert a != c

    def test_coord_and_pt_formatting(self):
        doc = TikZDocument(TikZOptions())
        assert doc.coord(1.0, -2.5) == "(1,-2.5)"
        assert doc.pt(0.75) == "0.75pt"

    def test_snippet_render(self):
        doc = TikZDocument(TikZOptions(standalone=False))
        doc.line("\\draw (0,0)--(1,1);")
        out = doc.render()
        assert "\\begin{tikzpicture}" in out
        assert "\\end{tikzpicture}" in out
        assert "documentclass" not in out

    def test_standalone_render(self):
        doc = TikZDocument(TikZOptions(standalone=True))
        doc.line("\\draw (0,0)--(1,1);")
        out = doc.render()
        assert "\\documentclass" in out
        assert "babel" in out and "russian" in out
        assert "\\begin{document}" in out and "\\end{document}" in out

    def test_definecolor_emitted(self):
        doc = TikZDocument(TikZOptions())
        name = doc.color("#1565c0")
        doc.line(f"\\draw[{name}] (0,0) circle (1);")
        out = doc.picture()
        assert f"\\definecolor{{{name}}}{{HTML}}{{1565C0}}" in out

    def test_picture_options_in_output(self):
        doc = TikZDocument(TikZOptions(), picture_options="x=0.5cm, y=0.5cm")
        out = doc.picture()
        assert "\\begin{tikzpicture}[x=0.5cm, y=0.5cm]" in out


class TestOptions:
    def test_conversion_factors(self):
        opt = TikZOptions(dpi=96)
        assert abs(opt.cm_per_px - 2.54 / 96) < 1e-12
        assert abs(opt.pt_per_px - 0.75) < 1e-12
