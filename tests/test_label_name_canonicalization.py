"""Label-text canonicalization: GeoGebra names with primes / braced subscripts
(mangled into Python identifiers at parse time) must render with the original
glyphs (``U'''``, ``F_{ab}``), recovered from ``scene.geo.name_mapping``.
"""
from types import SimpleNamespace

import numpy as np

from animageo.geo.lib_elements import Element, Point, Segment
from animageo.labels import resolve_label_text, _display_name


def _scene(mapping=None):
    geo = SimpleNamespace(name_mapping=mapping) if mapping is not None else None
    return SimpleNamespace(style_config=None, geo=geo)


def _pt(name):
    return Element(name, Point(np.array([0.0, 0.0, 0.0])))


class TestPrimeRecovery:
    def test_single_prime(self):
        sc = _scene({"F'": "F_Prime"})
        assert resolve_label_text(sc, _pt("F_Prime")) == "$F'$"

    def test_triple_prime(self):
        sc = _scene({"U'''": "U_Prime_Prime_Prime"})
        assert resolve_label_text(sc, _pt("U_Prime_Prime_Prime")) == "$U'''$"

    def test_braced_subscript(self):
        sc = _scene({"F_{ab}": "F_ab"})
        assert resolve_label_text(sc, _pt("F_ab")) == "$F_{ab}$"


class TestUnaffectedCases:
    def test_no_geo_falls_back_to_name(self):
        sc = _scene(None)  # fake scene without name_mapping (e.g. unit tests)
        assert resolve_label_text(sc, _pt("A")) == "$A$"

    def test_unmangled_name_unchanged(self):
        # identity mapping (DSL / plain name) must not be rewritten
        sc = _scene({"A_1": "A_1"})
        assert resolve_label_text(sc, _pt("A_1")) == "$A_1$"

    def test_name_absent_from_mapping(self):
        sc = _scene({"X'": "X_Prime"})
        assert resolve_label_text(sc, _pt("B")) == "$B$"


class TestPrecedence:
    def test_explicit_label_text_wins(self):
        sc = _scene({"U'": "U_Prime"})
        elem = _pt("U_Prime")
        elem.style["label_text"] = r"$\hat{u}$"
        assert resolve_label_text(sc, elem) == r"$\hat{u}$"

    def test_display_name_style_wins_over_mapping(self):
        sc = _scene({"U'": "U_Prime"})
        elem = _pt("U_Prime")
        elem.style["display_name"] = "u_star"
        assert resolve_label_text(sc, elem) == "$u_star$"

    def test_display_name_helper_direct(self):
        sc = _scene({"U''": "U_Prime_Prime"})
        assert _display_name(sc, _pt("U_Prime_Prime")) == "U''"


class TestValueModePrefix:
    def test_label_value_prefix_uses_display_name(self):
        sc = _scene({"s'": "s_Prime"})
        elem = Element("s_Prime", Segment(np.array([0.0, 0.0]),
                                          np.array([3.0, 4.0])))
        elem.style["label_mode"] = "label_value"
        # prefix recovered to s'; value is the segment length (5)
        assert resolve_label_text(sc, elem) == "$s' = 5$"
