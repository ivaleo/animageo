"""Phase 3 — StyleProxy: dict-compat + attribute access."""

import json
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_elements import Point
from animageo.parsers import dsl
from animageo.style.proxy import StyleProxy


# ── Attribute-style access (the new surface) ─────────────────────

class TestAttributeAPI:
    def test_set_and_get(self):
        sp = StyleProxy()
        sp.stroke = "#ff0000"
        assert sp.stroke == "#ff0000"

    def test_missing_returns_none(self):
        sp = StyleProxy()
        # Attr access on unset key returns None, not AttributeError.
        assert sp.nonexistent_key is None

    def test_delete_attribute(self):
        sp = StyleProxy()
        sp.stroke = "#ff0000"
        del sp.stroke
        assert "stroke" not in sp

    def test_delete_missing_raises(self):
        sp = StyleProxy()
        with pytest.raises(AttributeError):
            del sp.nonexistent

    def test_underscore_names_are_real_attrs(self):
        sp = StyleProxy()
        # Internal bookkeeping: should bypass the dict.
        sp._private = 42
        assert sp._private == 42
        assert "_private" not in sp


# ── Mapping operations ───────────────────────────────────────────

class TestDictCompat:
    def test_subscript_read_write(self):
        sp = StyleProxy()
        sp["stroke"] = "#00ff00"
        assert sp["stroke"] == "#00ff00"

    def test_get_with_default(self):
        sp = StyleProxy({"stroke": "#0000ff"})
        assert sp.get("stroke") == "#0000ff"
        assert sp.get("fill", "none") == "none"

    def test_contains(self):
        sp = StyleProxy({"stroke": "#fff"})
        assert "stroke" in sp
        assert "fill" not in sp

    def test_items_iteration(self):
        sp = StyleProxy({"a": 1, "b": 2})
        keys = set()
        for k, v in sp.items():
            keys.add(k)
        assert keys == {"a", "b"}

    def test_keys_values(self):
        sp = StyleProxy({"a": 1, "b": 2})
        assert set(sp.keys()) == {"a", "b"}
        assert set(sp.values()) == {1, 2}

    def test_dict_conversion(self):
        sp = StyleProxy({"a": 1})
        d = dict(sp)
        assert d == {"a": 1}
        assert type(d) is dict

    def test_unpacking(self):
        sp = StyleProxy({"a": 1, "b": 2})
        combined = {**sp, "c": 3}
        assert combined == {"a": 1, "b": 2, "c": 3}

    def test_json_serialization(self):
        sp = StyleProxy({"stroke": "#f00", "size": 10})
        s = json.dumps(sp)
        assert json.loads(s) == {"stroke": "#f00", "size": 10}

    def test_length(self):
        sp = StyleProxy({"a": 1, "b": 2})
        assert len(sp) == 2

    def test_update(self):
        sp = StyleProxy({"a": 1})
        sp.update({"b": 2, "c": 3})
        assert sp["b"] == 2
        assert sp["c"] == 3


# ── Attribute + subscript interop ────────────────────────────────

class TestInterop:
    def test_set_attr_reads_via_subscript(self):
        sp = StyleProxy()
        sp.stroke = "#f00"
        assert sp["stroke"] == "#f00"

    def test_set_subscript_reads_via_attr(self):
        sp = StyleProxy()
        sp["fill"] = "#0ff"
        assert sp.fill == "#0ff"


# ── Integration with real elements ───────────────────────────────

class TestElementIntegration:
    def test_point_style_is_style_proxy(self):
        p = Point([0, 0])
        assert isinstance(p.style, StyleProxy)

    def test_attr_access_via_element(self):
        from animageo.geo.lib_elements import Element
        elem = Element("A", Point([0, 0]))
        # elem.style is the same proxy as data.style
        elem.style.stroke = "#ff0000"
        assert elem.style["stroke"] == "#ff0000"
        assert elem.data.style["stroke"] == "#ff0000"  # shared


class TestDSLStyleSyntax:
    def test_attribute_style_in_dsl(self):
        c = Construction()
        # Attribute-style writes via DSL should work — the AST doesn't
        # wrap these since the LHS is an Attribute (not Name).
        dsl.run(
            c,
            "A = Point(0, 0)\n"
            "A.style.stroke = '#ff0000'\n"
            "A.style.size = 10",
        )
        assert c.element("A").style["stroke"] == "#ff0000"
        assert c.element("A").style["size"] == 10

    def test_style_batch_helper(self):
        c = Construction()
        dsl.run(
            c,
            "A = Point(0, 0)\n"
            "B = Point(1, 1)\n"
            "style(A, B, stroke='#ff0000', fill_opacity=0.5)",
        )
        assert c.element("A").style.stroke == "#ff0000"
        assert c.element("B").style.fill_opacity == 0.5
