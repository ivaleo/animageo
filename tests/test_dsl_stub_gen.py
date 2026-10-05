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


class TestStubsFollowTheFactories:
    """``namespace.pyi`` and ``dsl.pyi`` declare exactly the factories the
    DSL discovers in ``COMMAND_REGISTRY`` — generated by ``_regen_stubs``,
    checked in CI with ``--check`` (1.11.0rc1)."""

    def _namespace(self):
        from animageo.parsers.dsl import _regen_stubs
        return _regen_stubs.Declarations(_regen_stubs.NAMESPACE_PYI.read_text(encoding='utf-8'))

    def _dsl(self):
        from animageo.parsers.dsl import _regen_stubs
        return _regen_stubs.DSL_PYI.read_text(encoding='utf-8')

    def test_every_factory_has_a_stub(self):
        from animageo.parsers.dsl.namespace import _DISCOVERED_COMMANDS
        assert sorted(set(_DISCOVERED_COMMANDS) - self._namespace().factories) == []

    def test_no_stub_of_a_gone_factory(self):
        from animageo.parsers.dsl.namespace import _DISCOVERED_COMMANDS
        assert sorted(self._namespace().factory_functions - set(_DISCOVERED_COMMANDS)) == []
        assert 'CpxTo' not in self._dsl()

    def test_dsl_pyi_reexports_exactly_the_factories(self):
        import ast
        from animageo.parsers.dsl.namespace import _DISCOVERED_COMMANDS
        names = set()
        for node in ast.parse(self._dsl()).body:
            if isinstance(node, ast.ImportFrom):
                names.update(alias.asname or alias.name for alias in node.names)
        camel = {n for n in names if n[:1].isupper() and not n.isupper()}  # not TYPE_CHECKING
        types_only = {'Boolean', 'ElementProxy', 'LocusCurve', 'Measure', 'StyleProxy'}
        assert camel - types_only == set(_DISCOVERED_COMMANDS)

    def test_the_stubs_are_up_to_date(self):
        from animageo.parsers.dsl import _regen_stubs
        assert _regen_stubs.problems() == []

    def test_check_mode_exit_code(self, capsys):
        from animageo.parsers.dsl import _regen_stubs
        assert _regen_stubs.main(['--check']) == 0
        assert 'stubs up to date' in capsys.readouterr().out

    def test_every_factory_exists_in_animageo_dsl(self):
        import animageo.dsl as module
        from animageo.parsers.dsl.namespace import _DISCOVERED_COMMANDS
        assert sorted(n for n in _DISCOVERED_COMMANDS if not hasattr(module, n)) == []


class TestRegenStubsLogic:
    """The generator on small texts: a stale typed stub goes, a factory with
    no typed stub gets a plain one in the generated block."""

    HEAD = ('from typing import Any, Optional\n'
            'from .proxy import (\n    Point,\n    Measure,\n)\n\n'
            'def Midpoint(a: Point, b: Point, *, name: Optional[str] = ...) -> Point: ...\n'
            '@overload\n'
            'def Gone(x: int) -> Point: ...\n'
            'def style(*a: Any) -> None: ...\n\n')

    def text(self, block=''):
        from animageo.parsers.dsl._regen_stubs import BEGIN, END
        return self.HEAD + BEGIN + '\n' + block + END + '\n\nSAFE_BUILTINS: dict\n'

    def test_stale_goes_missing_comes(self):
        from animageo.parsers.dsl._regen_stubs import namespace_pyi
        new, stale = namespace_pyi(self.text('def Old(*args: Any) -> Any: ...\n'),
                                   frozenset({'Point', 'Midpoint', 'Distance'}))
        assert stale == ['Gone']
        assert 'Gone' not in new and '@overload' not in new and 'Old' not in new
        assert 'def Distance(*args: Any, name: Optional[str] = ...) -> ElementProxy: ...' in new
        assert 'def Midpoint(a: Point' in new

    def test_idempotent(self):
        from animageo.parsers.dsl._regen_stubs import namespace_pyi
        factories = frozenset({'Point', 'Midpoint', 'Distance'})
        once, _ = namespace_pyi(self.text(), factories)
        twice, stale = namespace_pyi(once, factories)
        assert (twice, stale) == (once, [])

    def test_markers_are_required(self):
        import pytest
        from animageo.parsers.dsl._regen_stubs import namespace_pyi
        with pytest.raises(SystemExit, match='markers'):
            namespace_pyi(self.HEAD, frozenset({'Point'}))

    def test_dsl_pyi_blocks(self):
        from animageo.parsers.dsl._regen_stubs import dsl_pyi, namespace_pyi
        new, _ = namespace_pyi(self.text(), frozenset({'Point', 'Midpoint', 'Distance'}))
        out = dsl_pyi(new)
        assert 'from .parsers.dsl.proxy import (\n    Measure as Measure,\n    Point as Point,\n)' in out
        assert '    Distance as Distance,\n    Midpoint as Midpoint,\n' in out
        assert '    style as style,\n    SAFE_BUILTINS' not in out
        assert 'from .style.proxy import StyleProxy as StyleProxy' in out
