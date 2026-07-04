"""Tests for GeoGebra file parsing (ggb_parser.py).

Covers: XML extraction, expression conversion, batch parsing of .ggb files.
"""
import os
import glob
import tempfile
import zipfile
from xml.etree import ElementTree
import numpy as np
import pytest

from animageo.geo.lib_elements import Point, Line, Segment, Circle, Element
from animageo.geo.lib_vars import Var, Measure, AngleSize
from animageo.geo.lib_commands import Command
from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'examples')


def _all_ggb_files():
    return sorted(glob.glob(os.path.join(EXAMPLES_DIR, '**', '*.ggb'), recursive=True))


# ── Expression conversion ─────────────────────────────────────────────

class TestExpressionConversion:
    def test_replace_with_point(self):
        result = ggb_parser.replace_with_point('(3, 4)')
        assert 'Point' in result

    def test_is_number(self):
        assert ggb_parser.is_number('3.14')
        assert ggb_parser.is_number('-2')
        assert not ggb_parser.is_number('abc')

    def test_is_angle_degrees(self):
        assert ggb_parser.is_angle_degrees('90°')
        assert not ggb_parser.is_angle_degrees('90')

    def test_convert_simple_expression(self):
        c = Construction()
        result = ggb_parser.convert_ggb_expr_to_python(c, 'Midpoint[A, B]')
        assert 'Midpoint' in result
        assert '(' in result  # brackets converted

    def test_convert_inline_line_expression_keeps_dsl_factory_name(self):
        c = Construction()
        result = ggb_parser.convert_ggb_expr_to_python(c, 'Line[A, M]')
        assert result == 'Line(A, M)'

    def test_convert_inline_distance_expression_keeps_dsl_factory_name(self):
        c = Construction()
        result = ggb_parser.convert_ggb_expr_to_python(c, 'Distance[B, C] / 2')
        assert result == 'Distance(B, C) / 2'

    def test_convert_inline_coordinate_and_vector_expressions(self):
        c = Construction()
        assert ggb_parser.convert_ggb_expr_to_python(c, '(0, 0)') == 'Point(0, 0)'
        assert ggb_parser.convert_ggb_expr_to_python(c, 'Vector[(t, 0)]') == 'Vector(Point(t, 0))'

    def test_convert_angle_degree_expression_to_radians(self):
        c = Construction()
        result = ggb_parser.convert_ggb_expr_to_python(c, '4 * (α - 90°)')
        assert result == '4 * (α - AngleSize((90) * pi / 180))'

    def test_is_simple_value(self):
        assert ggb_parser.is_simple_value('3.14')
        assert ggb_parser.is_simple_value('90°')
        assert ggb_parser.is_simple_value('A')
        assert ggb_parser.is_simple_value(None)


# ── XML extraction ─────────────────────────────────────────────────────

class TestXMLExtraction:
    @pytest.fixture
    def simple_ggb(self):
        """Find a simple .ggb file for testing."""
        files = _all_ggb_files()
        if not files:
            pytest.skip('No .ggb files found in examples/')
        return files[0]

    def test_extract_xml(self, simple_ggb):
        constr_xelem, view_xelem, gui_xelem = ggb_parser.get_xelems(simple_ggb)
        assert constr_xelem is not None
        assert view_xelem is not None


# ── Full parsing ───────────────────────────────────────────────────────

class TestFullParsing:
    @pytest.fixture
    def simple_ggb(self):
        files = _all_ggb_files()
        if not files:
            pytest.skip('No .ggb files found in examples/')
        # Find a file that we know works (from the batch test: 125/140 pass)
        for f in files:
            basename = os.path.basename(f)
            if basename.startswith('scene4'):
                return f
        return files[0]

    def test_parse_produces_elements(self, simple_ggb):
        c = Construction()
        view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
        ggb_parser.load(c, view, simple_ggb, debug=False)
        # Should have more than just the default axes
        assert len(c.elements) > 2

    def test_parse_produces_commands(self, simple_ggb):
        c = Construction()
        view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
        ggb_parser.load(c, view, simple_ggb, debug=False)
        assert len(c.commands) > 0

    def test_view_populated(self, simple_ggb):
        c = Construction()
        view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
        ggb_parser.load(c, view, simple_ggb, debug=False)
        assert view['ptUnit'] >= 0

    def test_view_reads_axes_and_grid_settings(self):
        ggb_path = os.path.join(EXAMPLES_DIR, 'test', 'sector.ggb')
        if not os.path.exists(ggb_path):
            pytest.skip('sector.ggb not available')

        c = Construction()
        view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
        ggb_parser.load(c, view, ggb_path, debug=False)

        assert view['showAxes'] is True
        assert view['showGrid'] is True
        assert view['gridType'] == 0
        assert view['axesColor'] == '#252525'
        assert view['gridColor'] == '#c0c0c0'
        assert view['axes']['x']['show'] is True
        assert view['axes']['y']['showNumbers'] is True

    def test_view_reads_grid_and_axis_distances(self):
        xml = ElementTree.fromstring("""
<euclidianView>
  <coordSystem xZero="0" yZero="0" scale="50" yscale="60"/>
  <evSettings axes="true" grid="true" gridIsBold="true" gridType="3"/>
  <axis id="0" show="true" tickDistance="0.5" axisCross="0" positiveAxis="false" showNumbers="true"/>
  <axis id="1" show="true" tickDistance="2" axisCross="0" positiveAxis="true" showNumbers="false"/>
  <grid distX="0.5" distY="2" distTheta="0.7853981633974483"/>
</euclidianView>
""")
        view = {}
        ggb_parser.parse_view(view, xml)

        assert view['ptYUnit_ggb'] == 60
        assert view['gridIsBold'] is True
        assert view['gridDistX'] == 0.5
        assert view['gridDistY'] == 2
        assert view['gridDistTheta'] == pytest.approx(np.pi / 4)
        assert view['axes']['x']['tickDistance'] == 0.5
        assert view['axes']['y']['positiveAxis'] is True

    def test_get_xelems_falls_back_to_euclideanView(self):
        """GeoGebra uses 'euclideanView' (with 'e'); old files have 'euclidianView' (with 'i')."""
        import tempfile, zipfile
        with tempfile.TemporaryDirectory() as tmp:
            ggb_path = os.path.join(tmp, 'test.ggb')
            with zipfile.ZipFile(ggb_path, 'w') as zf:
                zf.writestr('geogebra.xml', '<geogebra><euclideanView><coordSystem scale="42"/></euclideanView></geogebra>')
            constr_xelem, view_xelem, gui_xelem = ggb_parser.get_xelems(ggb_path)
            assert view_xelem is not None
            assert view_xelem.tag == 'euclideanView'
            assert view_xelem.find('coordSystem').attrib['scale'] == '42'

    def test_real_locus_file_builds_sampled_locus(self):
        from animageo.geo.lib_elements import LocusCurve, Point

        ggb_path = os.path.join(
            EXAMPLES_DIR,
            '25 -  Задача Феди про прямоугольник',
            'scene25.ggb',
        )
        if not os.path.exists(ggb_path):
            pytest.skip('scene25.ggb not available')

        c = Construction()
        view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
        ggb_parser.load(c, view, ggb_path, debug=False)

        loc = c.element('loc1')
        point_on_locus = c.element('N')
        assert loc is not None
        assert isinstance(loc.data, LocusCurve)
        assert len(loc.data.points) > 1
        assert point_on_locus is not None
        assert isinstance(point_on_locus.data, Point)
        assert c.command_diagnostics == []


# ── Batch parsing ──────────────────────────────────────────────────────

class TestBatchParsing:
    """Regression test: parse all available .ggb files, track success rate."""

    def test_batch_parse_success_rate(self):
        files = _all_ggb_files()
        if not files:
            pytest.skip('No .ggb files found in examples/')

        ok, fail = 0, 0
        failures = []
        for f in files:
            try:
                c = Construction()
                view = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}
                ggb_parser.load(c, view, f, debug=False)
                ok += 1
            except Exception as e:
                fail += 1
                failures.append((os.path.basename(f), str(e)[:80]))

        total = len(files)
        success_rate = ok / total if total > 0 else 0

        print(f"\nGGB Batch: {ok}/{total} passed ({success_rate:.0%})")
        for name, err in failures[:5]:
            print(f"  FAIL: {name}: {err}")

        # After Phase 1 fixes: 138/140 pass (98%)
        assert success_rate >= 0.95, f"Success rate {success_rate:.0%} below 95% threshold"


# ── Safe ZIP extraction (zip-slip / zip-bomb) ─────────────────────────

class TestSafeExtract:
    def _make_zip(self, members):
        """Create a tmp .zip with given (name, data) members. Returns path."""
        fd, path = tempfile.mkstemp(suffix=".ggb")
        os.close(fd)
        with zipfile.ZipFile(path, 'w') as zf:
            for name, data in members:
                zf.writestr(name, data)
        return path

    def test_rejects_parent_traversal(self, tmp_path):
        bad = self._make_zip([("../escape.txt", b"pwn")])
        try:
            with zipfile.ZipFile(bad) as zf:
                with pytest.raises(ValueError, match="escapes"):
                    ggb_parser._safe_extract_ggb(zf, str(tmp_path))
        finally:
            os.unlink(bad)

    def test_rejects_absolute_path(self, tmp_path):
        bad = self._make_zip([("/etc/passwd", b"x")])
        try:
            with zipfile.ZipFile(bad) as zf:
                with pytest.raises(ValueError, match="absolute"):
                    ggb_parser._safe_extract_ggb(zf, str(tmp_path))
        finally:
            os.unlink(bad)

    def test_rejects_too_many_members(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ggb_parser, "_GGB_MAX_MEMBERS", 3)
        bad = self._make_zip([(f"f{i}.txt", b"x") for i in range(5)])
        try:
            with zipfile.ZipFile(bad) as zf:
                with pytest.raises(ValueError, match="too many members"):
                    ggb_parser._safe_extract_ggb(zf, str(tmp_path))
        finally:
            os.unlink(bad)

    def test_rejects_oversize(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ggb_parser, "_GGB_MAX_UNCOMPRESSED_BYTES", 10)
        bad = self._make_zip([("big.bin", b"x" * 100)])
        try:
            with zipfile.ZipFile(bad) as zf:
                with pytest.raises(ValueError, match="uncompressed size"):
                    ggb_parser._safe_extract_ggb(zf, str(tmp_path))
        finally:
            os.unlink(bad)

    def test_accepts_safe_archive(self, tmp_path):
        ok = self._make_zip([("geogebra.xml", b"<x/>")])
        try:
            with zipfile.ZipFile(ok) as zf:
                ggb_parser._safe_extract_ggb(zf, str(tmp_path))
            assert (tmp_path / "geogebra.xml").exists()
        finally:
            os.unlink(ok)
