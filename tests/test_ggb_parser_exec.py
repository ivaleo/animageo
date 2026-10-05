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


class TestGgbCodeGuard:
    """A .ggb is untrusted: the code built from its expressions is one
    assignment of an expression, without dunders (1.10.0a1)."""

    def test_plain_expressions_pass(self):
        from animageo.parsers.ggb_parser import _check_ggb_code
        _check_ggb_code('a = Point(1, 2)')
        _check_ggb_code('_3 = Distance(A, B) + 1')
        _check_ggb_code('B = A.x')

    @pytest.mark.parametrize('code', [
        'a = ().__class__', 'a = __import__("os")', 'a = (lambda: 1)()', 'a = [x for x in b]',
        'a = (x for x in b)', 'a = 1\nb = 2', 'a = b._secret', 'import os',
    ])
    def test_code_is_refused(self, code):
        from animageo.parsers.ggb_parser import _check_ggb_code
        with pytest.raises(ValueError):
            _check_ggb_code(code)

    def test_a_malicious_expression_is_not_run(self, tmp_path):
        from xml.etree import ElementTree
        from animageo.geo.construction import Construction
        from animageo.parsers import ggb_parser
        marker = tmp_path / 'pwned'
        exp = ("[c for c in ().__class__.__base__.__subclasses__() if c.__name__ == 'Popen'][0]"
               f"(['touch', '{marker}'])")
        xml = ('<construction>'
               f'<expression label="a" exp="{exp.replace(chr(34), "&quot;")}"/>'
               '<element type="numeric" label="a"><value val="0"/></element>'
               '<expression label="b" exp="().__class__"/>'
               '<element type="numeric" label="b"><value val="0"/></element>'
               '</construction>')
        c = Construction()
        ggb_parser.parse_constr(c, ElementTree.fromstring(xml))
        assert not marker.exists()
        reasons = {d['outputs'][0]: d['reason'] for d in c.command_diagnostics}
        assert reasons.get('b') == 'expression_parse_error'

