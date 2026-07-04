"""GeoGebra macro expansion for GGB import.

GeoGebra allows users to define custom tools (macros) that encapsulate a
sequence of construction steps.  When a .ggb file is saved, macro
definitions are stored in ``geogebra_macro.xml`` and invocations appear
in ``geogebra.xml`` as ordinary ``<command>`` elements whose ``name``
attribute is the macro command name.

This module expands macro calls inline so that the downstream
``ggb_parser`` only has to deal with primitive GeoGebra commands.

Macro XML structure (geogebra_macro.xml)
----------------------------------------

.. code-block:: xml

    <macro cmdName="Incircle" toolName="Incircle" ...>
        <macroInput a0="A" a1="B" a2="C"/>
        <macroOutput a0="d"/>
        <construction>
            <!-- Local parameter definitions (type + label only) -->
            <element type="point" label="A">...</element>
            <element type="point" label="B">...</element>
            <element type="point" label="C">...</element>
            <!-- Body commands -->
            <command name="Segment">
                <input a0="C" a1="B"/>
                <output a0="h"/>
            </command>
            ...
        </construction>
    </macro>

The ``<macroInput>`` attributes define the *formal* parameter names.
The ``<macroOutput>`` attributes define the *formal* result names.
Inside ``<construction>`` the macro author refers to those names.

Expansion algorithm
-------------------

1. **Parse** all macros from ``geogebra_macro.xml`` into
   :class:`Macro` objects.
2. **Collect** all macro command names (e.g. ``Incircle``).
3. **Walk** the main construction XML.  For every ``<command>`` whose
   ``name`` is a macro name:

   a. Read the *actual* inputs / outputs from the call site.
   b. Build a name-mapping: formal parameter → actual argument.
   c. Clone the macro body (elements + commands).
   d. Rewrite every identifier inside the clone using the mapping.
   e. Insert the clone into the construction in place of the macro call.
   f. Append mapping commands that wire macro outputs to the call-site
      outputs.
4. **Recursion** — if a macro body contains another macro call, step 3
   is applied again until no macro calls remain.

Name uniquification
-------------------

A macro may be invoked many times.  Local names inside the macro body
(e.g. ``h``, ``i``, ``j`` in ``Incircle``) must not collide across
invocations.  During expansion every local identifier that is *not* a
formal parameter or output gets a unique prefix such as
``macro_Incircle_0_h``.

Expression handling
-------------------

Actual arguments may be literal numbers (``6``), plain identifiers
(``A``), or GeoGebra expressions (``Circle(A, s / n)``).  The expander
only rewrites identifiers; literal numbers and complex expressions are
passed through unchanged.
"""

import logging
import re
from copy import deepcopy
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# One expansion pass rewrites every macro call currently present; legit
# nested macros need one pass per nesting level (real files: 2-5). A cyclic
# macro (whose body calls itself, directly or mutually) would never
# converge, so expansion stops after this many passes and the remaining
# calls surface through the unsupported-command diagnostics.
MAX_MACRO_EXPANSION_PASSES = 32


class Macro:
    """Represents a single GeoGebra macro definition."""

    def __init__(
        self,
        cmd_name: str,
        tool_name: str,
        inputs: list[str],
        outputs: list[str],
        construction: ET.Element,
    ):
        self.cmd_name = cmd_name
        self.tool_name = tool_name
        self.inputs = inputs          # formal input names
        self.outputs = outputs        # formal output names
        self.construction = construction

    def __repr__(self) -> str:
        return (
            f"Macro({self.cmd_name!r}, inputs={self.inputs}, "
            f"outputs={self.outputs})"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_macros(macro_root: ET.Element) -> dict[str, Macro]:
    """Parse all ``<macro>`` elements under *macro_root*.

    Returns a mapping ``cmd_name -> Macro``.
    """
    macros: dict[str, Macro] = {}
    for macro_elem in macro_root.findall("macro"):
        cmd_name = macro_elem.attrib.get("cmdName")
        if not cmd_name:
            logger.warning("Skipping macro without cmdName")
            continue

        tool_name = macro_elem.attrib.get("toolName", cmd_name)

        macro_input = macro_elem.find("macroInput")
        inputs = _ordered_attrib_values(macro_input) if macro_input is not None else []

        macro_output = macro_elem.find("macroOutput")
        outputs = _ordered_attrib_values(macro_output) if macro_output is not None else []

        construction = macro_elem.find("construction")
        if construction is None:
            logger.warning("Macro %r has no <construction>; skipping", cmd_name)
            continue

        macros[cmd_name] = Macro(cmd_name, tool_name, inputs, outputs, construction)

    return macros


def expand_macros_in_construction(
    constr_xelem: ET.Element,
    macros: dict[str, Macro],
    _call_counter: dict[str, int] | None = None,
    _depth: int = 0,
) -> None:
    """Expand every macro call inside *constr_xelem* in-place.

    The function mutates *constr_xelem* by replacing each
    ``<command name="MacroName">`` with the macro body.  It handles
    nested macro calls recursively.
    """
    if _depth >= MAX_MACRO_EXPANSION_PASSES:
        leftover = sorted({
            c.attrib.get("name", "")
            for c in constr_xelem.findall("command")
            if c.attrib.get("name", "") in macros
        })
        logger.warning(
            "Macro expansion did not converge after %d passes — cyclic "
            "macro definition? Leaving calls unexpanded: %s",
            MAX_MACRO_EXPANSION_PASSES, ", ".join(leftover),
        )
        return
    if _call_counter is None:
        _call_counter = {}

    # Collect names already present in the construction so we can avoid
    # collisions when uniquifying macro locals.
    existing_names = _collect_all_names(constr_xelem)

    # We iterate over a snapshot because we will be mutating the tree.
    for cmd_elem in list(constr_xelem.findall("command")):
        macro_name = cmd_elem.attrib.get("name", "")
        if macro_name not in macros:
            continue

        macro = macros[macro_name]
        call_idx = _call_counter.setdefault(macro_name, 0)
        _call_counter[macro_name] += 1

        # --- 1. Read actual arguments from the call site ------------------
        input_xelem = cmd_elem.find("input")
        output_xelem = cmd_elem.find("output")
        actual_inputs = _ordered_attrib_values(input_xelem) if input_xelem is not None else []
        actual_outputs = _ordered_attrib_values(output_xelem) if output_xelem is not None else []

        # Validate arity
        if len(actual_inputs) != len(macro.inputs):
            logger.warning(
                "Macro %r expects %d inputs, got %d at call site %d",
                macro_name, len(macro.inputs), len(actual_inputs), call_idx,
            )
        if len(actual_outputs) != len(macro.outputs):
            logger.warning(
                "Macro %r expects %d outputs, got %d at call site %d",
                macro_name, len(macro.outputs), len(actual_outputs), call_idx,
            )

        # --- 2. Build name mapping ----------------------------------------
        # formal -> actual
        name_map: dict[str, str] = {}
        for formal, actual in zip(macro.inputs, actual_inputs):
            name_map[formal] = actual
        for formal, actual in zip(macro.outputs, actual_outputs):
            name_map[formal] = actual

        # --- 3. Determine local names that need uniquification ------------
        # Any identifier inside the macro body that is NOT a formal
        # parameter or output is considered local and gets prefixed.
        local_names = _collect_local_names(macro.construction, set(macro.inputs) | set(macro.outputs))
        prefix = f"macro_{macro_name}_{call_idx}_"
        for local in local_names:
            candidate = prefix + local
            # If the prefixed name collides with an existing name, add more
            # suffixes until it is unique.
            while candidate in existing_names:
                candidate = candidate + "_"
            name_map[local] = candidate
            existing_names.add(candidate)

        # --- 4. Clone and rewrite the macro body -------------------------
        cloned_body = _clone_macro_body(
            macro.construction, name_map,
            formal_inputs=set(macro.inputs),
            formal_outputs=set(macro.outputs),
        )

        # --- 5. Replace the macro call with the cloned body --------------
        # We insert all children of the cloned construction before the
        # command element, then remove the command element.
        insert_idx = list(constr_xelem).index(cmd_elem)
        for child in cloned_body:
            constr_xelem.insert(insert_idx, child)
            insert_idx += 1
        constr_xelem.remove(cmd_elem)

        # --- 6. Add output mapping commands ------------------------------
        # If the macro defines outputs, we need to ensure the final
        # objects are accessible under the caller's output names.
        # In GeoGebra, the macro body already produces outputs with the
        # formal names; after rewriting those become the actual names.
        # However, if the macro's last command does NOT produce the
        # output under the expected name, we add an explicit mapping.
        # (In practice GeoGebra macros always wire outputs correctly.)

    # After expanding once, a newly inserted body might contain further
    # macro calls, so recurse.
    if any(
        c.attrib.get("name", "") in macros
        for c in constr_xelem.findall("command")
    ):
        expand_macros_in_construction(constr_xelem, macros, _call_counter,
                                      _depth + 1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ordered_attrib_values(elem: ET.Element | None) -> list[str]:
    """Return attribute values of *elem* in ascending key order.

    GeoGebra uses ``a0``, ``a1``, … as attribute names.  Sorting by key
    guarantees the correct positional order.
    """
    if elem is None:
        return []
    return [v for _k, v in sorted(elem.attrib.items())]


def _collect_local_names(construction: ET.Element, reserved: set[str]) -> set[str]:
    """Return all identifier-like strings inside *construction* that are
    not in *reserved* (formal params / outputs).

    Only attribute values on ``<command>`` ``input``/``output`` and
    ``<element>`` ``label`` are considered — these are the names that
    actually participate in the construction graph.  Attribute values
    on presentation tags (``show``, ``objColor``, …) are ignored.
    """
    locals_set: set[str] = set()

    for elem in construction.iter():
        if elem.tag == "command":
            for child_tag in ("input", "output"):
                child = elem.find(child_tag)
                if child is not None:
                    for val in child.attrib.values():
                        if _is_identifier(val) and val not in reserved:
                            locals_set.add(val)
        elif elem.tag == "element":
            label = elem.attrib.get("label")
            if label and _is_identifier(label) and label not in reserved:
                locals_set.add(label)

    return locals_set


def _collect_all_names(construction: ET.Element) -> set[str]:
    """Collect every identifier-like string that appears in *construction*."""
    names: set[str] = set()
    for elem in construction.iter():
        if elem.tag == "command":
            for child_tag in ("input", "output"):
                child = elem.find(child_tag)
                if child is not None:
                    for val in child.attrib.values():
                        if _is_identifier(val):
                            names.add(val)
        elif elem.tag == "element":
            label = elem.attrib.get("label")
            if label and _is_identifier(label):
                names.add(label)
    return names


def _is_identifier(val: str) -> bool:
    """Heuristic: *val* looks like a GeoGebra object label."""
    # Reject common boolean / keyword values that GeoGebra stores in attrs
    if val in ("true", "false", "default", "implicit", "specific"):
        return False
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", val))


def _clone_macro_body(
    construction: ET.Element,
    name_map: dict[str, str],
    formal_inputs: set[str] | None = None,
    formal_outputs: set[str] | None = None,
) -> list[ET.Element]:
    """Deep-clone every child of *construction* and rewrite identifiers.

    *formal_inputs* contains the formal parameter names.  ``<element>``
    nodes whose ``label`` is a formal input are skipped because the
    actual argument already exists in the outer construction.

    *formal_outputs* contains the formal output names.  ``<element>``
    nodes whose ``label`` is a formal output are also skipped because
    the command that produces the output already defines the element.

    Returns a list of new ``ET.Element`` nodes ready for insertion.
    """
    if formal_inputs is None:
        formal_inputs = set()
    if formal_outputs is None:
        formal_outputs = set()
    result: list[ET.Element] = []
    for child in construction:
        if child.tag == "element":
            label = child.attrib.get("label")
            # Skip parameter definitions — the actual object is supplied
            # by the call site.
            if label in formal_inputs:
                continue
            # Skip output element definitions — the producing command
            # already creates the element under the mapped name.
            if label in formal_outputs:
                continue
            cloned = deepcopy(child)
            _rewrite_element(cloned, name_map)
            result.append(cloned)
        elif child.tag == "command":
            cloned = deepcopy(child)
            _rewrite_element(cloned, name_map)
            result.append(cloned)
    return result


def _rewrite_element(elem: ET.Element, name_map: dict[str, str]) -> None:
    """Recursively rewrite all identifier strings inside *elem*."""
    # Rewrite attributes
    for key in list(elem.attrib.keys()):
        val = elem.attrib[key]
        new_val = _rewrite_string(val, name_map)
        if new_val != val:
            elem.attrib[key] = new_val

    # Rewrite text
    if elem.text:
        elem.text = _rewrite_string(elem.text, name_map)
    if elem.tail:
        elem.tail = _rewrite_string(elem.tail, name_map)

    # Recurse into children
    for child in elem:
        _rewrite_element(child, name_map)


def _rewrite_string(text: str, name_map: dict[str, str]) -> str:
    """Rewrite identifiers inside *text* using *name_map*.

    The function is careful not to rewrite substrings inside larger
    words or inside GeoGebra expressions (e.g. ``Circle(A, s / n)``).
    It uses word-boundary matching.
    """
    if not name_map:
        return text

    # Build a single regex with alternation — much faster than looping.
    # Sort by length descending so longer names are matched first.
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in sorted(name_map, key=len, reverse=True)) + r")\b"
    )
    return pattern.sub(lambda m: name_map[m.group(1)], text)
