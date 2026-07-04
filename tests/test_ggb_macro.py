"""Tests for GeoGebra macro expansion (ggb_macro.py).

Covers: parse_macros, expand_macros_in_construction, name uniquification,
recursive expansion, and integration with ggb_parser.
"""
import logging
import os
import zipfile
from xml.etree import ElementTree as ET

import pytest

from animageo.parsers.ggb_macro import (
    Macro,
    parse_macros,
    expand_macros_in_construction,
    _collect_local_names,
    _collect_all_names,
    _is_identifier,
    _rewrite_string,
    _clone_macro_body,
)
from animageo.parsers.ggb_parser import get_xelems, parse_constr
from animageo.geo.construction import Construction

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'examples')


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def simple_macro_xml():
    """A minimal macro that doubles a segment."""
    return ET.fromstring("""
    <geogebra>
        <macro cmdName="DoubleSegment" toolName="DoubleSegment">
            <macroInput a0="A" a1="B"/>
            <macroOutput a0="C"/>
            <construction>
                <command name="Midpoint">
                    <input a0="A" a1="B"/>
                    <output a0="M"/>
                </command>
                <command name="Line">
                    <input a0="A" a1="M"/>
                    <output a0="l"/>
                </command>
                <command name="Circle">
                    <input a0="M" a1="A"/>
                    <output a0="c"/>
                </command>
                <command name="Intersect">
                    <input a0="l" a1="c" a2="2"/>
                    <output a0="C"/>
                </command>
            </construction>
        </macro>
    </geogebra>
    """)


@pytest.fixture
def macro_with_elements_xml():
    """Macro whose body contains <element> nodes for inputs and outputs."""
    return ET.fromstring("""
    <geogebra>
        <macro cmdName="Incircle" toolName="Incircle">
            <macroInput a0="A" a1="B" a2="C"/>
            <macroOutput a0="d"/>
            <construction>
                <element type="point" label="A"/>
                <element type="point" label="B"/>
                <element type="point" label="C"/>
                <command name="Segment">
                    <input a0="C" a1="B"/>
                    <output a0="h"/>
                </command>
                <element type="segment" label="h"/>
                <command name="AngularBisector">
                    <input a0="A" a1="B" a2="C"/>
                    <output a0="i"/>
                </command>
                <element type="line" label="i"/>
                <command name="Circle">
                    <input a0="D" a1="E"/>
                    <output a0="d"/>
                </command>
                <element type="conic" label="d"/>
            </construction>
        </macro>
    </geogebra>
    """)


@pytest.fixture
def nested_macro_xml():
    """Two macros where the second calls the first."""
    return ET.fromstring("""
    <geogebra>
        <macro cmdName="Inner" toolName="Inner">
            <macroInput a0="P" a1="Q"/>
            <macroOutput a0="R"/>
            <construction>
                <command name="Midpoint">
                    <input a0="P" a1="Q"/>
                    <output a0="R"/>
                </command>
            </construction>
        </macro>
        <macro cmdName="Outer" toolName="Outer">
            <macroInput a0="X" a1="Y"/>
            <macroOutput a0="Z"/>
            <construction>
                <command name="Inner">
                    <input a0="X" a1="Y"/>
                    <output a0="M"/>
                </command>
                <command name="Inner">
                    <input a0="M" a1="Y"/>
                    <output a0="Z"/>
                </command>
            </construction>
        </macro>
    </geogebra>
    """)


# ── parse_macros ──────────────────────────────────────────────────────

class TestParseMacros:
    def test_parse_single_macro(self, simple_macro_xml):
        macros = parse_macros(simple_macro_xml)
        assert len(macros) == 1
        assert "DoubleSegment" in macros
        macro = macros["DoubleSegment"]
        assert macro.inputs == ["A", "B"]
        assert macro.outputs == ["C"]
        assert macro.tool_name == "DoubleSegment"

    def test_parse_multiple_macros(self, nested_macro_xml):
        macros = parse_macros(nested_macro_xml)
        assert len(macros) == 2
        assert "Inner" in macros
        assert "Outer" in macros
        assert macros["Inner"].inputs == ["P", "Q"]
        assert macros["Outer"].inputs == ["X", "Y"]

    def test_skip_macro_without_cmdname(self):
        root = ET.fromstring("""
        <geogebra>
            <macro toolName="NoName">
                <construction/>
            </macro>
        </geogebra>
        """)
        macros = parse_macros(root)
        assert len(macros) == 0

    def test_skip_macro_without_construction(self):
        root = ET.fromstring("""
        <geogebra>
            <macro cmdName="Empty" toolName="Empty">
                <macroInput a0="A"/>
            </macro>
        </geogebra>
        """)
        macros = parse_macros(root)
        assert len(macros) == 0


# ── _collect_local_names ──────────────────────────────────────────────

class TestCollectLocalNames:
    def test_locals_excluding_reserved(self, simple_macro_xml):
        macro = parse_macros(simple_macro_xml)["DoubleSegment"]
        reserved = {"A", "B", "C"}
        locals_set = _collect_local_names(macro.construction, reserved)
        # M, l, c are local; A, B, C are reserved
        assert locals_set == {"M", "l", "c"}

    def test_empty_locals_when_all_reserved(self):
        construction = ET.fromstring("""
        <construction>
            <command name="Line">
                <input a0="A" a1="B"/>
                <output a0="C"/>
            </command>
        </construction>
        """)
        reserved = {"A", "B", "C"}
        assert _collect_local_names(construction, reserved) == set()


# ── _is_identifier ────────────────────────────────────────────────────

class TestIsIdentifier:
    def test_valid_identifiers(self):
        assert _is_identifier("A")
        assert _is_identifier("A1")
        assert _is_identifier("macro_1_x")
        assert _is_identifier("line_AB")

    def test_invalid_identifiers(self):
        assert not _is_identifier("true")
        assert not _is_identifier("false")
        assert not _is_identifier("default")
        assert not _is_identifier("123")
        assert not _is_identifier("")
        assert not _is_identifier("A B")


# ── _rewrite_string ───────────────────────────────────────────────────

class TestRewriteString:
    def test_simple_rewrite(self):
        name_map = {"A": "X", "B": "Y"}
        assert _rewrite_string("A", name_map) == "X"
        assert _rewrite_string("B", name_map) == "Y"

    def test_no_rewrite_for_unmapped(self):
        name_map = {"A": "X"}
        assert _rewrite_string("C", name_map) == "C"

    def test_word_boundary_no_partial_match(self):
        name_map = {"A": "X", "AB": "Z"}
        # "AB" should be rewritten as "Z", not "XB"
        assert _rewrite_string("AB", name_map) == "Z"

    def test_expression_rewrite(self):
        name_map = {"A": "p1", "B": "p2", "M": "mid"}
        result = _rewrite_string("Midpoint(A, B) + M", name_map)
        assert result == "Midpoint(p1, p2) + mid"


# ── _clone_macro_body ─────────────────────────────────────────────────

class TestCloneMacroBody:
    def test_skips_input_elements(self, macro_with_elements_xml):
        macro = parse_macros(macro_with_elements_xml)["Incircle"]
        name_map = {"A": "P", "B": "Q", "C": "R", "d": "out"}
        cloned = _clone_macro_body(
            macro.construction, name_map,
            formal_inputs={"A", "B", "C"},
            formal_outputs={"d"},
        )
        labels = [c.attrib.get("label") for c in cloned if c.tag == "element"]
        # A, B, C (inputs) and d (output) should be skipped
        assert "A" not in labels
        assert "B" not in labels
        assert "C" not in labels
        assert "d" not in labels
        # h and i are local elements and should be present
        assert "h" in labels
        assert "i" in labels

    def test_rewrites_local_names(self, simple_macro_xml):
        macro = parse_macros(simple_macro_xml)["DoubleSegment"]
        name_map = {"A": "X", "B": "Y", "C": "Z", "M": "mid", "l": "line", "c": "circ"}
        cloned = _clone_macro_body(macro.construction, name_map)
        # Check that commands have been rewritten
        cmds = [c for c in cloned if c.tag == "command"]
        first_cmd = cmds[0]
        inp = first_cmd.find("input")
        assert inp.attrib["a0"] == "X"
        assert inp.attrib["a1"] == "Y"
        out = first_cmd.find("output")
        assert out.attrib["a0"] == "mid"


# ── expand_macros_in_construction ─────────────────────────────────────

class TestExpandMacros:
    def test_expand_single_macro_call(self, simple_macro_xml):
        macros = parse_macros(simple_macro_xml)
        construction = ET.fromstring("""
        <construction>
            <element type="point" label="P"/>
            <element type="point" label="Q"/>
            <command name="DoubleSegment">
                <input a0="P" a1="Q"/>
                <output a0="R"/>
            </command>
        </construction>
        """)
        expand_macros_in_construction(construction, macros)
        # The macro call should be replaced by its body
        cmd_names = [c.attrib["name"] for c in construction.findall("command")]
        assert "DoubleSegment" not in cmd_names
        assert "Midpoint" in cmd_names
        assert "Line" in cmd_names
        assert "Circle" in cmd_names
        assert "Intersect" in cmd_names

    def test_local_names_get_uniquified(self, simple_macro_xml):
        macros = parse_macros(simple_macro_xml)
        construction = ET.fromstring("""
        <construction>
            <element type="point" label="P"/>
            <element type="point" label="Q"/>
            <command name="DoubleSegment">
                <input a0="P" a1="Q"/>
                <output a0="R"/>
            </command>
            <command name="DoubleSegment">
                <input a0="Q" a1="P"/>
                <output a0="S"/>
            </command>
        </construction>
        """)
        expand_macros_in_construction(construction, macros)
        # Local names M, l, c should have prefixes
        all_outputs = []
        for cmd in construction.findall("command"):
            out = cmd.find("output")
            if out is not None:
                all_outputs.extend(out.attrib.values())
        # Should have macro_0 and macro_1 prefixed locals
        assert any("macro_DoubleSegment_0_" in o for o in all_outputs)
        assert any("macro_DoubleSegment_1_" in o for o in all_outputs)

    def test_recursive_expansion(self, nested_macro_xml):
        macros = parse_macros(nested_macro_xml)
        construction = ET.fromstring("""
        <construction>
            <element type="point" label="A"/>
            <element type="point" label="B"/>
            <command name="Outer">
                <input a0="A" a1="B"/>
                <output a0="C"/>
            </command>
        </construction>
        """)
        expand_macros_in_construction(construction, macros)
        cmd_names = [c.attrib["name"] for c in construction.findall("command")]
        # Outer and Inner should both be expanded
        assert "Outer" not in cmd_names
        assert "Inner" not in cmd_names
        assert "Midpoint" in cmd_names
        # Should have 2 Midpoint calls (1 from first Inner, 1 from second Inner)
        assert cmd_names.count("Midpoint") == 2

    def test_input_output_mapping(self, simple_macro_xml):
        macros = parse_macros(simple_macro_xml)
        construction = ET.fromstring("""
        <construction>
            <element type="point" label="P"/>
            <element type="point" label="Q"/>
            <command name="DoubleSegment">
                <input a0="P" a1="Q"/>
                <output a0="R"/>
            </command>
        </construction>
        """)
        expand_macros_in_construction(construction, macros)
        # The final Intersect command should output R (mapped from C)
        cmds = construction.findall("command")
        last_cmd = cmds[-1]
        assert last_cmd.attrib["name"] == "Intersect"
        out = last_cmd.find("output")
        assert out.attrib["a0"] == "R"


# ── Integration with pict.ggb ─────────────────────────────────────────

class TestPictGGBIntegration:
    def test_pict_ggb_loads_without_errors(self):
        path = os.path.join(EXAMPLES_DIR, "pict.ggb")
        if not os.path.exists(path):
            pytest.skip("pict.ggb not found")
        constr_xelem, view, gui = get_xelems(path)
        assert constr_xelem is not None

    def test_pict_ggb_no_duplicate_labels(self):
        path = os.path.join(EXAMPLES_DIR, "pict.ggb")
        if not os.path.exists(path):
            pytest.skip("pict.ggb not found")
        constr_xelem, view, gui = get_xelems(path)
        labels = {}
        for elem in constr_xelem.findall("element"):
            label = elem.attrib.get("label")
            labels[label] = labels.get(label, 0) + 1
        duplicates = {k: v for k, v in labels.items() if v > 1}
        assert not duplicates, f"Duplicate element labels: {duplicates}"

    def test_pict_ggb_no_duplicate_command_outputs(self):
        path = os.path.join(EXAMPLES_DIR, "pict.ggb")
        if not os.path.exists(path):
            pytest.skip("pict.ggb not found")
        constr_xelem, view, gui = get_xelems(path)
        outputs = {}
        for cmd in constr_xelem.findall("command"):
            out = cmd.find("output")
            if out is not None:
                for val in out.attrib.values():
                    outputs[val] = outputs.get(val, 0) + 1
        duplicates = {k: v for k, v in outputs.items() if v > 1}
        assert not duplicates, f"Duplicate command outputs: {duplicates}"

    def test_pict_ggb_parse_constr(self):
        path = os.path.join(EXAMPLES_DIR, "pict.ggb")
        if not os.path.exists(path):
            pytest.skip("pict.ggb not found")
        constr_xelem, view, gui = get_xelems(path)
        constr = Construction()
        parse_constr(constr, constr_xelem, debug=False)
        # Should have all expected elements
        names = [e.name for e in constr.elements]
        assert "A" in names
        assert "B" in names
        assert "C" in names
        assert "e" in names  # Incircle output
        assert "D" in names  # Center
        assert "E" in names  # Point on incircle
        assert "F" in names  # Rotated point
        assert "G" in names  # Isogonal conjugate

    def test_pict_ggb_macro_calls_expanded(self):
        path = os.path.join(EXAMPLES_DIR, "pict.ggb")
        if not os.path.exists(path):
            pytest.skip("pict.ggb not found")
        constr_xelem, view, gui = get_xelems(path)
        cmd_names = [c.attrib["name"] for c in constr_xelem.findall("command")]
        # Macro calls should be replaced by primitive commands
        assert "Incircle" not in cmd_names
        assert "IsogonalConjugation" not in cmd_names
        # Primitive commands should be present
        assert "Segment" in cmd_names
        assert "AngularBisector" in cmd_names
        assert "Line" in cmd_names
        assert "OrthogonalLine" in cmd_names
        assert "Intersect" in cmd_names
        assert "Circle" in cmd_names

    def test_pict_ggb_all_macros_defined(self):
        path = os.path.join(EXAMPLES_DIR, "pict.ggb")
        if not os.path.exists(path):
            pytest.skip("pict.ggb not found")
        with zipfile.ZipFile(path, 'r') as z:
            macro_xml = z.read('geogebra_macro.xml').decode('utf-8')
        macro_root = ET.fromstring(macro_xml)
        macros = parse_macros(macro_root)
        # pict.ggb should have both macros
        assert "Incircle" in macros
        assert "IsogonalConjugation" in macros
        # Verify macro structures
        incircle = macros["Incircle"]
        assert incircle.inputs == ["A", "B", "C"]
        assert incircle.outputs == ["d"]
        isogonal = macros["IsogonalConjugation"]
        assert isogonal.inputs == ["A", "B", "C", "D"]
        assert isogonal.outputs == ["K"]


# ── Cyclic macro guard ────────────────────────────────────────────────

@pytest.fixture
def cyclic_macro_xml():
    """A macro whose body calls itself — malformed, but must not blow the
    stack (RecursionError) or hang; leftover calls go to the
    unsupported-command diagnostics instead."""
    return ET.fromstring("""
    <geogebra>
        <macro cmdName="Loop" toolName="Loop">
            <macroInput a0="P" a1="Q"/>
            <macroOutput a0="R"/>
            <construction>
                <command name="Loop">
                    <input a0="P" a1="Q"/>
                    <output a0="R"/>
                </command>
            </construction>
        </macro>
    </geogebra>
    """)


class TestCyclicMacroGuard:
    def test_cyclic_macro_terminates_without_recursion_error(
            self, cyclic_macro_xml, caplog):
        macros = parse_macros(cyclic_macro_xml)
        constr = ET.fromstring("""
        <construction>
            <command name="Loop">
                <input a0="A" a1="B"/>
                <output a0="C"/>
            </command>
        </construction>
        """)
        with caplog.at_level(logging.WARNING,
                             logger="animageo.parsers.ggb_macro"):
            expand_macros_in_construction(constr, macros)

        # Terminated: exactly one unexpandable call left in place.
        leftover = [c for c in constr.findall("command")
                    if c.attrib.get("name") == "Loop"]
        assert len(leftover) == 1
        assert any("did not converge" in r.getMessage()
                   for r in caplog.records)
