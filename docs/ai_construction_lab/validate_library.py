"""Lightweight semantic validation for AI construction lab records."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any


LAB = Path(__file__).resolve().parent
LIBRARY_PATH = LAB / "assets" / "library.json"


def _diag(code: str, message: str, *, severity: str = "warning") -> dict[str, str]:
    return {"type": "validation", "severity": severity, "code": code, "message": message}


def _has_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) for pattern in patterns)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def validate_record(record: dict[str, Any]) -> list[dict[str, str]]:
    prompt = str(record.get("prompt") or "")
    expected = "\n".join(str(item) for item in record.get("expected") or [])
    dsl = str(record.get("dsl") or "")
    style_obj = record.get("style")
    text = f"{prompt}\n{expected}"
    diagnostics: list[dict[str, str]] = []

    tree: ast.Module | None = None
    try:
        tree = ast.parse(dsl)
        compile(dsl, "<ai-construction-dsl>", "exec")
    except SyntaxError as exc:
        diagnostics.append(_diag(
            "dsl_syntax_error",
            f"Generated DSL is not valid Python syntax: {exc.msg}.",
            severity="error",
        ))

    if tree is not None:
        single_proxy_assignments: dict[str, str] = {}
        measure_assignments: set[str] = set()
        segment_assignments: set[str] = set()
        command_by_name: dict[str, str] = {}
        assigned_names: set[str] = set()
        for nested in ast.walk(tree):
            if not isinstance(nested, ast.Assign):
                continue
            for target in nested.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for item in target.elts:
                        if isinstance(item, ast.Name):
                            assigned_names.add(item.id)
            nested_call = _call_name(nested.value)
            if nested_call:
                for target in nested.targets:
                    if isinstance(target, ast.Name):
                        command_by_name[target.id] = nested_call
                    elif isinstance(target, (ast.Tuple, ast.List)):
                        for item in target.elts:
                            if isinstance(item, ast.Name):
                                command_by_name[item.id] = nested_call
            if nested_call in {"Area", "Perimeter", "Length", "Distance", "Radius"}:
                for target in nested.targets:
                    if isinstance(target, ast.Name):
                        measure_assignments.add(target.id)
            if nested_call == "Segment":
                for target in nested.targets:
                    if isinstance(target, ast.Name):
                        segment_assignments.add(target.id)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for item in target.elts:
                        if isinstance(item, ast.Name):
                            assigned_names.add(item.id)
            call = _call_name(node.value)
            if call == "Axes":
                if any(isinstance(target, (ast.Tuple, ast.List)) for target in node.targets):
                    diagnostics.append(_diag(
                        "unpack_single_proxy_command",
                        "Do not tuple-unpack Axes(...); commands with no documented multi-return contract produce one proxy. Use named semantic helpers such as MajorAxis(...) and MinorAxis(...) when separate axes are needed.",
                        severity="error",
                    ))
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        single_proxy_assignments[target.id] = call
            elif isinstance(node.value, ast.Name) and node.value.id in single_proxy_assignments:
                if any(isinstance(target, (ast.Tuple, ast.List)) for target in node.targets):
                    diagnostics.append(_diag(
                        "unpack_single_proxy_assignment",
                        f"Do not tuple-unpack {node.value.id}; it stores the single proxy returned by {single_proxy_assignments[node.value.id]}(...). Use explicit semantic helper commands for separate objects.",
                        severity="error",
                    ))
            elif call in {"Area", "Perimeter", "Length", "Distance", "Radius"}:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        measure_assignments.add(target.id)
        label_text_by_element: dict[str, set[str]] = {}
        trig_projection_segment_labels: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "Angle":
                angle_names = [arg.id for arg in node.args if isinstance(arg, ast.Name)]
                if len(angle_names) == 3 and len(set(angle_names)) < 3:
                    diagnostics.append(_diag(
                        "degenerate_angle_repeats_point",
                        "Angle(...) needs three distinct point arguments; do not repeat the vertex or an arm point.",
                        severity="error",
                    ))
                non_point_args = [
                    name for name in angle_names
                    if command_by_name.get(name) in {
                        "Angle",
                        "AngularBisector",
                        "Circle",
                        "CircleArc",
                        "CircularArc",
                        "CircleSector",
                        "Ellipse",
                        "Line",
                        "LineBisector",
                        "PerpendicularBisector",
                        "PerpendicularLine",
                        "Segment",
                        "Semicircle",
                    }
                ]
                if non_point_args:
                    diagnostics.append(_diag(
                        "angle_args_must_be_points",
                        "Angle(...) arguments must be points; use a point lying on the relevant line/segment instead of passing geometry objects: " + ", ".join(sorted(set(non_point_args))) + ".",
                        severity="error",
                    ))
            if node.func.id not in {"style", "hide", "show"}:
                continue
            missing = [
                arg.id for arg in node.args
                if isinstance(arg, ast.Name) and arg.id not in assigned_names
            ]
            if missing:
                diagnostics.append(_diag(
                    "undefined_name_in_helper_call",
                    f"{node.func.id}(...) references names that are not assigned in the DSL: " + ", ".join(sorted(set(missing))) + ".",
                    severity="error",
                ))
                reversed_side_names = sorted({
                    name for name in missing
                    if re.fullmatch(r"[A-Z]{2}", name) and name[::-1] in assigned_names
                })
                if reversed_side_names:
                    diagnostics.append(_diag(
                        "side_name_order_mismatch",
                        "Use the side name that was actually assigned by Polygon(...) or Segment(...); do not invent the reversed alias: " + ", ".join(reversed_side_names) + ".",
                        severity="error",
                    ))
            if node.func.id == "style":
                if any(kw.arg is None for kw in node.keywords):
                    diagnostics.append(_diag(
                        "style_kwargs_unpack_not_supported",
                        "Do not use **dict unpacking inside style(...). Pass style properties directly as keyword arguments.",
                        severity="error",
                    ))
                styled_measures = [
                    arg.id for arg in node.args
                    if isinstance(arg, ast.Name) and arg.id in measure_assignments
                ]
                if styled_measures:
                    diagnostics.append(_diag(
                        "measure_proxy_styled_as_label",
                        "Measure proxies such as Area(...) and Perimeter(...) are numeric values, not drawable labels. Attach the visible value to a polygon, segment, or other semantic host instead: " + ", ".join(sorted(set(styled_measures))) + ".",
                        severity="error",
                    ))
                label_value: str | None = None
                for kw in node.keywords:
                    if kw.arg == "label_text" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        label_value = kw.value.value
                        break
                if label_value is not None:
                    for arg in node.args:
                        if isinstance(arg, ast.Name) and arg.id not in measure_assignments:
                            label_text_by_element.setdefault(arg.id, set()).add(label_value)
                        if isinstance(arg, ast.Name) and arg.id in segment_assignments:
                            if re.search(r"\\?cos", label_value):
                                trig_projection_segment_labels.add("cos")
                            if re.search(r"\\?sin", label_value):
                                trig_projection_segment_labels.add("sin")
                has_label_mode = any(kw.arg == "label_mode" for kw in node.keywords)
                has_dynamic_measure_label = any(
                    kw.arg == "label_text"
                    and (
                        isinstance(kw.value, ast.JoinedStr)
                        or (
                            isinstance(kw.value, ast.Call)
                            and isinstance(kw.value.func, ast.Attribute)
                            and kw.value.func.attr == "format"
                        )
                    )
                    for kw in node.keywords
                )
                if has_label_mode and has_dynamic_measure_label:
                    diagnostics.append(_diag(
                        "dynamic_measure_label_should_not_use_label_mode",
                        "If label_text already formats a measurement via .data.value or .format(...), do not also set label_mode=value/label_value; attach it as a plain static label to the host element.",
                        severity="error",
                    ))
        duplicate_label_hosts = sorted(
            name for name, labels in label_text_by_element.items() if len(labels) > 1
        )
        if duplicate_label_hosts:
            diagnostics.append(_diag(
                "competing_label_text_on_same_element",
                "Do not use several different label_text values on the same element to show separate labels; later style calls override earlier labels. Use separate semantic host elements instead: " + ", ".join(duplicate_label_hosts) + ".",
                severity="error",
            ))
        if _has_any([r"отношен", r"ratio", r"2\s*:\s*1"], text):
            segment_endpoints: dict[tuple[str, str], list[str]] = {}
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign) or _call_name(node.value) != "Segment":
                    continue
                if len(node.value.args) != 2 or not all(isinstance(arg, ast.Name) for arg in node.value.args):
                    continue
                endpoints = tuple(sorted(arg.id for arg in node.value.args))  # type: ignore[union-attr]
                names = [
                    target.id for target in node.targets
                    if isinstance(target, ast.Name)
                ]
                if names:
                    segment_endpoints.setdefault(endpoints, []).extend(names)
            duplicates = sorted(
                ", ".join(names) for names in segment_endpoints.values() if len(names) > 1
            )
            if duplicates:
                diagnostics.append(_diag(
                    "duplicate_ratio_subsegment_labels",
                    "For ratio annotations, attach labels to the existing subsegment objects instead of creating coincident duplicate segments: " + "; ".join(duplicates) + ".",
                    severity="error",
                ))
        if _has_any([r"\bsin\b", r"\bcos\b", r"синус", r"косинус"], text) and _has_any([r"проекц", r"projection"], text):
            if not {"sin", "cos"}.issubset(trig_projection_segment_labels):
                diagnostics.append(_diag(
                    "trig_projection_labels_must_be_on_segments",
                    "For unit-circle projection diagrams, label the visible sine and cosine projection segments, not only the projection foot points.",
                    severity="error",
                ))

    if "style=style(" in dsl:
        diagnostics.append(_diag(
            "style_inside_factory",
            "Apply style with a standalone style(element, ...) call, not as style=style(...) inside geometry factories.",
            severity="error",
        ))
    if re.search(r"\bcolor\s*=\s*color\.", dsl) or re.search(r"\bline_width\s*=\s*line_width\.", dsl):
        diagnostics.append(_diag(
            "style_token_as_python_object",
            "Style tokens in DSL must be string values such as stroke=\"color.accent\", not Python objects like color.accent.",
            severity="error",
        ))
    if re.search(r"\blabel_text\s*=\s*\[", dsl) or re.search(r"\blabel_text\s*=\s*\(", dsl):
        diagnostics.append(_diag(
            "label_text_must_be_single_string",
            "label_text must be one string for all elements in that style(...) call. Use separate style calls for different labels.",
            severity="error",
        ))
    if re.search(r"\bIntersect\s*\([^)]*\bindex\s*=", dsl):
        diagnostics.append(_diag(
            "intersect_index_keyword",
            "The current public DSL does not accept Intersect(..., index=...); use the simplest form until the library task is implemented.",
            severity="error",
        ))
    if re.search(r"(?im)^\s*#.*\b(wait|actually|but|instead|however)\b.*\?", dsl) or re.search(
        r"(?im)^\s*#.*\b(wait|actually)\b", dsl,
    ):
        diagnostics.append(_diag(
            "self_debating_dsl_comments",
            "Keep generated DSL comments declarative; do not include self-corrections or reasoning traces in comments.",
            severity="error",
        ))
    if re.search(
        r"\b[A-Z][A-Za-z0-9_]*\s*\([^)]*\b("
        r"stroke|fill|stroke_width_px|size_px|font_size_px|arc_size_px|"
        r"right_angle|right_angle_marker|tick_count|label_visible|label_text"
        r")\s*=",
        dsl,
    ):
        diagnostics.append(_diag(
            "style_kwargs_inside_factory",
            "Do not pass style fields as CamelCase factory kwargs; create the object, assign it to a name, then call style(...).",
            severity="error",
        ))
    if _has_any([r"\bsin\b", r"\bcos\b", r"синус", r"косинус"], text) and _has_any([r"проекц", r"projection"], text):
        has_axes = (
            re.search(r"\bAxes\s*\(", dsl)
            or (
                re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Line\s*\(\s*O\s*,\s*A\s*\)", dsl)
                and re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Line\s*\(\s*O\s*,\s*B\s*\)", dsl)
            )
        )
        if not has_axes:
            diagnostics.append(_diag(
                "unit_circle_projection_needs_axes",
                "Unit-circle sine/cosine projection diagrams should include visible coordinate axes or named axis lines.",
                severity="error",
            ))
    if _has_any([r"uses style JSON", r"global .*style", r"общ\w+\s+.*стил"], text):
        if style_obj is None:
            diagnostics.append(_diag(
                "missing_global_style_json",
                "When the request asks for broad/global visual style, return a style JSON object instead of encoding the theme only in DSL.",
                severity="error",
            ))
        elif isinstance(style_obj, dict):
            unsupported = sorted(set(style_obj) - {"name", "version", "presets", "defaults", "reference", "overlay", "rendering", "import"})
            if unsupported:
                diagnostics.append(_diag(
                    "unsupported_style_json_top_level_keys",
                    "Style JSON must use the current schema top-level sections only; unsupported keys: " + ", ".join(unsupported) + ".",
                    severity="error",
                ))
            defaults = style_obj.get("defaults")
            if isinstance(defaults, dict) and any(
                key in defaults
                for key in ("stroke", "fill", "stroke_width_px", "size_px", "font_size_px", "label_visible")
            ):
                diagnostics.append(_diag(
                    "style_defaults_must_be_per_type",
                    "Top-level style defaults must be a per-type map, not a single style block; use defaults.<type> or overlay.per_type.",
                    severity="error",
                ))
        if "does not repeat global style calls in DSL" in expected:
            broad_style_calls = [
                match.group(0)
                for match in re.finditer(r"\bstyle\s*\([^)]*\)", dsl, flags=re.MULTILINE)
                if re.search(
                    r"\b(stroke|fill|stroke_width_px|size_px|font_size_px|opacity)\s*=",
                    match.group(0),
                )
            ]
            if broad_style_calls:
                diagnostics.append(_diag(
                    "global_style_repeated_in_dsl",
                    "Do not restate broad theme styling in construction DSL; keep DSL style calls for labels or local semantic emphasis and put global per-type/default styling in style JSON.",
                    severity="error",
                ))
    if _has_any([r"\bABC\b", r"треугольник\s+ABC", r"triangle\s+ABC"], text):
        if all(re.search(rf"\b{name}\s*=\s*Point\s*\(", dsl) for name in ("A", "B", "C")):
            if not re.search(r"style\s*\([^)]*\bA\b[^)]*\bB\b[^)]*\bC\b[^)]*label_visible\s*=\s*True", dsl):
                diagnostics.append(_diag(
                    "missing_named_triangle_vertex_labels",
                    "For a named triangle ABC, keep A, B, and C labels visible with style(A, B, C, label_visible=True).",
                    severity="error",
                ))
    if re.search(r"\bIntersect\s*\([^)]*\b[A-Z][A-Za-z0-9_]*\s*\(", dsl):
        diagnostics.append(_diag(
            "inline_geometry_inside_intersect",
            "Do not create geometry inline inside Intersect; assign or reuse the named object first so the construction is explicit and helper objects can be hidden or styled.",
            severity="error",
        ))
    if re.search(r"\b(?:style|hide|show)\s*\([^)]*\b[A-Z][A-Za-z0-9_]*\s*\(", dsl):
        diagnostics.append(_diag(
            "inline_geometry_inside_helper_call",
            "Do not create geometry inline inside style(...), hide(...), or show(...); assign the object to a named variable first.",
            severity="error",
        ))
    if re.search(r"\b[A-Z][A-Za-z0-9_]*\s*\([^)]*\b[A-Z][A-Za-z0-9_]*\s*\(", dsl):
        diagnostics.append(_diag(
            "inline_geometry_inside_geometry_call",
            "Do not create geometry inline inside another geometry command; assign the helper object first so the construction stays inspectable and can be styled or hidden deliberately.",
            severity="error",
        ))

    polygon_names: set[str] = set()
    polygon_side_names: set[str] = set()
    for match in re.finditer(r"\b([A-Za-z][A-Za-z0-9_]*)\s*,\s*([A-Za-z][A-Za-z0-9_]*)\s*,\s*([A-Za-z][A-Za-z0-9_]*)\s*,\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*Polygon\s*\(", dsl):
        polygon_names.add(match.group(1))
        polygon_side_names.update(match.groups()[1:])
    asks_for_highlight = _has_any([r"highlight", r"выдел", r"покаж"], text)
    if asks_for_highlight and polygon_side_names:
        highlighted_sides = [
            name for name in polygon_side_names
            if re.search(rf"style\s*\([^)]*\b{name}\b[^)]*stroke\s*=\s*[\"']color\.(accent|strong)[\"']", dsl)
        ]
        polygon_suppressed = any(
            re.search(rf"style\s*\([^)]*\b{name}\b[^)]*stroke_width_px\s*=\s*0", dsl)
            or re.search(rf"style\s*\([^)]*\b{name}\b[^)]*stroke_opacity\s*=\s*0", dsl)
            or re.search(rf"hide\s*\([^)]*\b{name}\b", dsl)
            for name in polygon_names
        )
        if highlighted_sides and not polygon_suppressed:
            diagnostics.append(_diag(
                "highlighted_polygon_side_overlap_risk",
                "A highlighted polygon side can be visually covered by the polygon boundary; prefer explicit side segments or suppress the polygon boundary/fill for this diagram.",
                severity="error",
            ))

    if _has_any([r"равносторон", r"equilateral"], text) and not re.search(r"\bPolygon\s*\([^)]*,\s*3\s*\)", dsl):
        diagnostics.append(_diag(
            "regular_triangle_should_use_polygon_overload",
            "Use the regular polygon overload Polygon(A, B, 3) for equilateral triangles instead of manual rotation or circle intersections.",
            severity="error",
        ))
    if re.search(r"\bPolygon\s*\(\s*([A-Za-z][A-Za-z0-9_]*)\s*,\s*\1\s*,\s*[3-9]\s*\)", dsl):
        diagnostics.append(_diag(
            "regular_polygon_degenerate_first_side",
            "The regular Polygon(A, B, n) overload needs two distinct points for the first side; do not pass the same point twice.",
            severity="error",
        ))
    if _has_any([r"marks equal sides", r"equal sides", r"равн\w+\s+сторон"], text):
        if "tick_count" not in dsl:
            diagnostics.append(_diag(
                "missing_equal_side_ticks",
                "When equal sides are requested or checked, mark the relevant side segments with matching tick_count.",
                severity="error",
            ))
    if "constructs isosceles triangle" in expected:
        if (
            all(re.search(rf"\b{name}\s*=\s*Point\s*\(", dsl) for name in ("A", "B", "C"))
            and not re.search(r"\b(C|B)\s*=\s*(Rotate|Reflect)\s*\(", dsl)
            and not re.search(r"\bCircle\s*\(\s*A\s*,\s*B\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "isosceles_triangle_not_constructed_by_dependency",
                "For an isosceles triangle with AB = AC, construct the equal sides by dependency, not by approximate free coordinates.",
                severity="error",
            ))
        if not re.search(r"style\s*\([^)]*\bAB\b[^)]*\bAC\b[^)]*tick_count\s*=", dsl):
            diagnostics.append(_diag(
                "missing_isosceles_equal_side_ticks",
                "For an isosceles triangle with AB = AC, mark sides AB and AC themselves with matching tick_count.",
                severity="error",
            ))
    if "marks congruent segments" in expected and "tick_count" not in dsl:
        diagnostics.append(_diag(
            "missing_congruent_segment_ticks",
            "When a copy-length construction asks to mark congruent segments, style the original segment and copied segment with matching tick_count.",
            severity="error",
        ))
    if "constructs target ray by rotating Q around P by the source angle" in expected:
        if not re.search(r"\bRotate\s*\(\s*Q\s*,[^)]*,\s*P\s*\)", dsl):
            diagnostics.append(_diag(
                "copy_angle_should_use_rotation",
                "This prompt/check asks to copy the angle by rotating Q around P by the source Angle(...) object; do not replace that with a compass-circle construction.",
                severity="error",
            ))
        if not ("Angle(" in dsl and "tick_count" in dsl):
            diagnostics.append(_diag(
                "missing_copied_angle_ticks",
                "When copying an angle, visibly mark the source and copied angles with matching tick_count.",
                severity="error",
            ))
    if _has_any([r"equal\s+.*radii", r"marks\s+.*radii", r"radii\s+.*equal", r"равн\w+\s+радиус"], text):
        radius_segments = re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*O\s*,", dsl)
        midpoint_radius_segments = re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*(?:M|O)\s*,", dsl)
        if len(radius_segments) < 2 or "tick_count" not in dsl:
            if len(midpoint_radius_segments) < 2 or "tick_count" not in dsl:
                diagnostics.append(_diag(
                    "missing_equal_radii_segments",
                    "When equal radii are requested or checked, draw the radius segments from the center and mark them with matching tick_count.",
                    severity="error",
                ))
    if "constructs three external squares on the sides" in expected:
        if len(re.findall(r"\bPolygon\s*\([^)]*,\s*4\s*\)", dsl)) < 3:
            diagnostics.append(_diag(
                "side_squares_should_use_regular_polygon_overload",
                "For squares on triangle sides, use the regular polygon overload Polygon(side_start, side_end, 4) for each side instead of fragile manual rotation arithmetic.",
                severity="error",
            ))
        if "fill=" not in dsl or re.search(r"\bhide\s*\([^)]*\bsq_", dsl):
            diagnostics.append(_diag(
                "pythagorean_squares_should_keep_filled_faces",
                "Pythagorean-square diagrams should keep square polygon faces visible with semantic fills; do not hide the square polygons and redraw only outlines.",
                severity="error",
            ))
        square_fill_tokens = set()
        for match in re.finditer(r"style\s*\([^)]*\bsq_[A-Za-z0-9_]*[^)]*fill\s*=\s*[\"']([^\"']+)[\"']", dsl):
            square_fill_tokens.add(match.group(1))
        if len(square_fill_tokens) < 2:
            diagnostics.append(_diag(
                "pythagorean_square_fills_not_distinct",
                "When fills are expected to distinguish the three side squares, use at least two different semantic fill tokens or otherwise visibly distinct semantic fill settings.",
                severity="error",
            ))
    if "marks multiple roots" in expected:
        if not re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*,\s*[A-Za-z][A-Za-z0-9_]*\s*=\s*Intersect\s*\(", dsl):
            diagnostics.append(_diag(
                "multiple_intersections_should_be_tuple_unpacked",
                "When multiple intersection points are requested, tuple-unpack Intersect(...) into named point variables and style those points.",
                severity="error",
            ))
    if _has_any([r"marks equal angles", r"equal angles", r"равн\w+\s+угл"], text):
        if not ("Angle(" in dsl and "tick_count" in dsl):
            diagnostics.append(_diag(
                "missing_equal_angle_marks",
                "When equal angles are requested or checked, create Angle(...) objects and mark them with matching tick_count.",
                severity="error",
            ))
    if "uses distinct labels and tick groups" in expected:
        tick_values = set(re.findall(r"tick_count\s*=\s*([0-9]+)", dsl))
        label_count = len(re.findall(r"label_text\s*=", dsl))
        if len(tick_values) < 3 or label_count < 3:
            diagnostics.append(_diag(
                "missing_distinct_angle_labels_or_ticks",
                "When three angles need distinct labels and tick groups, create three Angle(...) objects and give them visible label_text plus different tick_count values.",
                severity="error",
            ))
    if "marks equal angle pairs for two vertices" in expected:
        tick_values = set(re.findall(r"tick_count\s*=\s*([0-9]+)", dsl))
        if len(tick_values) < 2:
            diagnostics.append(_diag(
                "bisector_pairs_need_distinct_tick_groups",
                "For multiple bisectors in a generic triangle, use one tick_count per equal-angle pair and different tick groups for different vertices.",
                severity="error",
            ))
    if "extends side AC beyond C" in expected:
        has_extension_point = bool(re.search(
            r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*C\s*\+\s*(?:[0-9.]+\s*\*\s*)?\(\s*C\s*-\s*A\s*\)",
            dsl,
        ))
        has_visible_extension = bool(
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*(?:Segment|Ray)\s*\(\s*C\s*,", dsl)
        )
        if not (has_extension_point and has_visible_extension):
            diagnostics.append(_diag(
                "missing_visible_side_extension_for_exterior_angle",
                "For an exterior angle at C made by extending AC beyond C, construct a dependent point beyond C, draw the visible extension from C, and use that extension as an angle arm.",
                severity="error",
            ))
    if "marks remote interior angles" in expected:
        if not (
            re.search(r"\bAngle\s*\(\s*B\s*,\s*A\s*,\s*C\s*\)", dsl)
            and re.search(r"\bAngle\s*\(\s*A\s*,\s*B\s*,\s*C\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "missing_remote_interior_angle_objects",
                "For an exterior-angle theorem diagram, mark the remote interior angles explicitly as Angle(B, A, C) and Angle(A, B, C).",
                severity="error",
            ))
    if "chooses D and E with the same ratio from A" in expected:
        if re.search(r"\bD\s*=\s*Point\s*\(", dsl) or re.search(r"\bE\s*=\s*Point\s*\(", dsl):
            diagnostics.append(_diag(
                "similarity_cut_points_should_be_dependent",
                "For a similarity cut, construct D and E with the same ratio from A, for example D = A + t*(B-A) and E = A + t*(C-A), not as free coordinate points.",
                severity="error",
            ))
        if not (
            re.search(r"\bD\s*=\s*A\s*\+\s*[A-Za-z0-9_.]+\s*\*\s*\(\s*B\s*-\s*A\s*\)", dsl)
            and re.search(r"\bE\s*=\s*A\s*\+\s*[A-Za-z0-9_.]+\s*\*\s*\(\s*C\s*-\s*A\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "missing_same_ratio_side_points",
                "Use the same ratio expression to place D on AB and E on AC so DE is parallel to BC by construction.",
                severity="error",
            ))
    if "uses extension of BC for F" in expected:
        if not re.search(r"\bF\s*=\s*C\s*\+\s*[A-Za-z0-9_.]+\s*\*\s*\(\s*C\s*-\s*B\s*\)", dsl):
            diagnostics.append(_diag(
                "menelaus_f_should_be_on_bc_extension",
                "For a Menelaus-style transversal, construct F on the extension of BC beyond C with F = C + k*(C-B) or an equivalent dependent construction.",
                severity="error",
            ))
        if not (
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Line\s*\(\s*D\s*,\s*F\s*\)", dsl)
            and re.search(r"\bE\s*=\s*Intersect\s*\([^)]*,\s*CA\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "menelaus_points_should_share_one_transversal",
                "For a Menelaus-style transversal, construct one line through two transversal points, e.g. Line(D, F), then derive the third point E by intersecting that line with side AC.",
                severity="error",
            ))
        if not re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*C\s*,\s*F\s*\)", dsl):
            diagnostics.append(_diag(
                "missing_visible_bc_extension_to_f",
                "When F lies on the extension of BC beyond C, draw the visible extension segment CF as auxiliary geometry.",
                severity="error",
            ))
    if _has_any([r"inscribed angle", r"вписанн\w+\s+уг"], text):
        if re.search(r"\bC\s*=\s*Point\s*\(", dsl):
            diagnostics.append(_diag(
                "inscribed_angle_vertex_not_on_circle_by_construction",
                "For an inscribed angle ACB, put C on the circle by construction, for example with Rotate(point_on_circle, angle, center), not by an approximate free Point(...).",
                severity="error",
            ))
    if _has_any([r"chord\s+AB", r"хорд\w+\s+AB"], text):
        b_is_on_circle_by_midpoint_center = re.search(r"\bO\s*=\s*Midpoint\s*\(\s*A\s*,\s*B\s*\)", dsl)
        if (
            re.search(r"\bcircle\s*=\s*Circle\s*\(\s*O\s*,\s*A\s*\)", dsl)
            and re.search(r"\bB\s*=\s*Point\s*\(", dsl)
            and not b_is_on_circle_by_midpoint_center
        ):
            diagnostics.append(_diag(
                "chord_endpoint_not_on_circle_by_construction",
                "For chord AB on Circle(O, A), construct B on the same circle by dependency, not as an approximate free Point(...).",
                severity="error",
            ))
    if "uses perpendicular bisectors of two chords" in expected:
        free_chord_points = [
            name for name in ("B", "C", "D")
            if re.search(rf"\b{name}\s*=\s*Point\s*\(", dsl)
        ]
        if free_chord_points:
            diagnostics.append(_diag(
                "chord_endpoints_should_lie_on_circle_by_construction",
                "When recovering a circle center from chords, construct chord endpoints on the helper circle by dependency rather than as free approximate points: " + ", ".join(free_chord_points) + ".",
                severity="error",
            ))
        hidden_names = set()
        for match in re.finditer(r"\bhide\s*\(([^)]*)\)", dsl):
            hidden_names.update(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", match.group(1)))
        circle_names = set(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*Circle\s*\(", dsl))
        hidden_circles = sorted(circle_names & hidden_names)
        if hidden_circles:
            diagnostics.append(_diag(
                "hidden_given_circle_for_center_recovery",
                "When recovering a circle center from two chords, keep the given circle visible; hide only the helper center point, not the circle: " + ", ".join(hidden_circles) + ".",
                severity="error",
            ))
    if "constructs two chords with endpoints on the circle" in expected:
        free_chord_points = [
            name for name in ("B", "C", "D")
            if re.search(rf"\b{name}\s*=\s*Point\s*\(", dsl)
        ]
        if free_chord_points:
            diagnostics.append(_diag(
                "intersecting_chord_endpoints_should_be_dependent",
                "For intersecting-chord theorem diagrams, construct all chord endpoints on the circle by dependency, for example with Rotate(...), not free approximate points: " + ", ".join(free_chord_points) + ".",
                severity="error",
            ))
    if "draws perpendicular from center" in expected:
        if not re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*O\s*,\s*H\s*\)", dsl):
            diagnostics.append(_diag(
                "missing_visible_center_to_chord_perpendicular",
                "When drawing the perpendicular from center O to chord AB with foot H, create a visible finite segment OH = Segment(O, H).",
                severity="error",
            ))
    if "marks equal tangent-chord and inscribed angles" in expected:
        if re.search(r"\bT\s*=\s*Rotate\s*\(\s*A\s*,[^)]*\bO\s*\)", dsl):
            diagnostics.append(_diag(
                "wrong_tangent_direction_helper",
                "A helper point for the tangent direction at A should lie on the tangent. Rotate the center O around A by 90 degrees, not A around O.",
                severity="error",
            ))
    if "adds concise theorem label" in expected:
        if "label_text" not in dsl:
            diagnostics.append(_diag(
                "missing_concise_theorem_label",
                "When a theorem diagram asks for a concise theorem label, attach a short visible formula label to a semantic host element.",
                severity="error",
            ))
    if "labels central angle as 2 alpha and inscribed angle as alpha" in expected or "labels central angle as 2alpha and inscribed as alpha" in expected:
        if not (re.search(r"\bAngle\s*\(\s*A\s*,\s*O\s*,\s*B\s*\)", dsl) and re.search(r"\bAngle\s*\(\s*A\s*,\s*C\s*,\s*B\s*\)", dsl)):
            diagnostics.append(_diag(
                "missing_central_or_inscribed_angle_objects",
                "Create explicit central Angle(A, O, B) and inscribed Angle(A, C, B) objects when the theorem asks to label both.",
                severity="error",
            ))
        if not (re.search(r"label_text\s*=\s*[\"'][^\"']*2[^\"']*alpha", dsl) and re.search(r"label_text\s*=\s*[\"'][^\"']*alpha", dsl)):
            diagnostics.append(_diag(
                "missing_central_inscribed_angle_labels",
                "Label the central angle as 2 alpha and the inscribed angle as alpha when requested.",
                severity="error",
            ))
        hidden_names = set()
        for match in re.finditer(r"\bhide\s*\(([^)]*)\)", dsl):
            hidden_names.update(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", match.group(1)))
        requested_angle_arms = {"OA", "OB", "CA", "CB"}
        hidden_arms = sorted(requested_angle_arms & hidden_names)
        if hidden_arms:
            diagnostics.append(_diag(
                "hidden_requested_angle_arms",
                "When the request asks to build central and inscribed angles, keep their visible arms; hidden arms: " + ", ".join(hidden_arms) + ".",
                severity="error",
            ))
    if "keeps arms visible" in expected:
        hidden_names = set()
        for match in re.finditer(r"\bhide\s*\(([^)]*)\)", dsl):
            hidden_names.update(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", match.group(1)))
        requested_angle_arms = {"OA", "OB", "CA", "CB"}
        hidden_arms = sorted(requested_angle_arms & hidden_names)
        if hidden_arms:
            diagnostics.append(_diag(
                "hidden_requested_angle_arms",
                "When the expected result asks to keep angle arms visible, do not hide: " + ", ".join(hidden_arms) + ".",
                severity="error",
            ))
    if "shows radii, chord and arc" in expected:
        if not (
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*O\s*,\s*A\s*\)", dsl)
            and re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*O\s*,\s*B\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "missing_sector_radii",
                "A sector diagram should show the two radius segments OA and OB when expected checks ask for radii.",
                severity="error",
            ))
    if "labels central angle" in expected:
        labeled_angle_style = any(
            "label_visible=True" in match.group(0).replace(" ", "")
            and "label_text" in match.group(0)
            for match in re.finditer(r"\bstyle\s*\([^)]*\)", dsl)
        )
        if not (re.search(r"\bAngle\s*\(\s*A\s*,\s*O\s*,\s*B\s*\)", dsl) and labeled_angle_style):
            diagnostics.append(_diag(
                "missing_labeled_central_angle",
                "Create Angle(A, O, B) and give it a visible label when the central angle should be labeled.",
                severity="error",
            ))
    if "marks one reflected angle pair" in expected:
        if not ("Angle(" in dsl and "tick_count" in dsl):
            diagnostics.append(_diag(
                "missing_reflected_angle_pair_marks",
                "When an isogonal construction asks to mark a reflected angle pair, create the two relevant Angle(...) objects and mark them with matching tick_count.",
                severity="error",
            ))
    if _has_any([r"parallel through", r"параллельн\w+.*через", r"through\s+P.*parallel"], text):
        if not re.search(r"\bLine\s*\(\s*P\s*,\s*[A-Za-z][A-Za-z0-9_]*\s*\)", dsl):
            diagnostics.append(_diag(
                "parallel_should_use_line_point_line",
                "For the current DSL, construct a line through a point parallel to an existing line with Line(P, base_line), not a double-perpendicular workaround.",
                severity="error",
            ))
    if "constructs equal circles from A and B" in expected:
        hidden_circles = re.findall(r"\bhide\s*\([^)]*\b([A-Za-z][A-Za-z0-9_]*)\b[^)]*\)", dsl)
        circle_names = set(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*Circle\s*\(", dsl))
        if circle_names and any(name in circle_names for name in hidden_circles):
            diagnostics.append(_diag(
                "hidden_requested_compass_circles",
                "When the construction method asks for equal compass circles, keep those circles/arcs visible as auxiliary geometry instead of hiding them.",
                severity="error",
            ))
    if "marks midpoint equality" in expected and "tick_count" not in dsl:
        diagnostics.append(_diag(
            "missing_midpoint_equality_ticks",
            "When midpoint equality is requested, create the two half-segments and mark them with matching tick_count.",
            severity="error",
        ))
    if "marks equal halves" in expected and "tick_count" not in dsl:
        diagnostics.append(_diag(
            "missing_equal_halves_ticks",
            "When equal halves are requested or checked, create the half-segments and mark each pair with matching tick_count.",
            severity="error",
        ))
    if _has_any([r"centroid", r"центроид", r"медиан\w+.*пересеч"], text):
        midpoint_pairs = {
            "M_AB": ("A", "B"),
            "M_BA": ("A", "B"),
            "M_BC": ("B", "C"),
            "M_CB": ("B", "C"),
            "M_CA": ("C", "A"),
            "M_AC": ("C", "A"),
        }
        for midpoint, endpoints in midpoint_pairs.items():
            if not re.search(rf"\b{midpoint}\s*=\s*Midpoint\s*\(\s*{endpoints[0]}\s*,\s*{endpoints[1]}\s*\)", dsl):
                continue
            for vertex in endpoints:
                if re.search(rf"\b(Line|Segment)\s*\(\s*{vertex}\s*,\s*{midpoint}\s*\)", dsl):
                    diagnostics.append(_diag(
                        "median_uses_adjacent_side_midpoint",
                        "A median for centroid construction must connect a vertex to the midpoint of the opposite side, not to a midpoint on a side incident to that vertex. Prefer Centroid(...) when available.",
                        severity="error",
                    ))
                    break
    if "uses IsogonalConjugation" in expected:
        if not re.search(r"\bIsogonalConjugation\s*\(\s*A\s*,\s*B\s*,\s*C\s*,", dsl):
            diagnostics.append(_diag(
                "isogonal_conjugation_requires_triangle_vertices",
                "Use IsogonalConjugation(A, B, C, P) with explicit triangle vertices and the source point; do not pass a triangle object as the second argument.",
                severity="error",
            ))
    if "draws concurrence lines" in expected:
        line_names = set(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*(?:Line|Segment)\s*\(", dsl))
        hidden_names = set()
        for match in re.finditer(r"\bhide\s*\(([^)]*)\)", dsl):
            hidden_names.update(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", match.group(1)))
        hidden_lines = sorted(line_names & hidden_names)
        if hidden_lines:
            diagnostics.append(_diag(
                "hidden_requested_concurrence_lines",
                "When the expected result asks to draw concurrence lines, keep those Line objects visible; hidden lines: " + ", ".join(hidden_lines) + ".",
                severity="error",
            ))
    if _has_any([r"external equilateral", r"внешн\w+\s+равносторон"], text):
        if (
            re.search(r"\bPolygon\s*\(\s*A\s*,\s*B\s*,\s*3\s*\)", dsl)
            and re.search(r"\bPolygon\s*\(\s*B\s*,\s*C\s*,\s*3\s*\)", dsl)
            and re.search(r"\bPolygon\s*\(\s*C\s*,\s*A\s*,\s*3\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "external_equilateral_orientation_risk",
                "For a normally oriented triangle ABC, Polygon(A, B, 3), Polygon(B, C, 3), Polygon(C, A, 3) can build equilateral triangles toward the same side as the triangle interior. Choose side order deliberately, e.g. reverse side order for external triangles.",
                severity="error",
            ))
    if "shows relation to center line" in expected:
        if not re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*O1\s*,\s*O2\s*\)", dsl):
            diagnostics.append(_diag(
                "missing_center_line_relation",
                "When a circle radical-axis diagram asks to show relation to the center line, draw the segment or line through O1 and O2.",
                severity="error",
            ))
    if "uses common chords as radical axes" in expected:
        pair_intersections = [
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*,\s*[A-Za-z][A-Za-z0-9_]*\s*=\s*Intersect\s*\(\s*c1\s*,\s*c2\s*\)", dsl),
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*,\s*[A-Za-z][A-Za-z0-9_]*\s*=\s*Intersect\s*\(\s*c1\s*,\s*c3\s*\)", dsl),
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*,\s*[A-Za-z][A-Za-z0-9_]*\s*=\s*Intersect\s*\(\s*c2\s*,\s*c3\s*\)", dsl),
        ]
        if not all(pair_intersections):
            diagnostics.append(_diag(
                "radical_axes_should_use_common_chords",
                "For radical-center diagrams that ask for common chords, derive radical axes from pairwise circle intersections, not manually solved line equations.",
                severity="error",
            ))
    if "uses indexed labels" in expected:
        indexed_labels = re.findall(r"label_text\s*=\s*[\"']\$[A-Z]_\d\$[\"']", dsl)
        if len(indexed_labels) < 4:
            diagnostics.append(_diag(
                "missing_indexed_point_labels",
                "When indexed labels are requested, use explicit math labels such as $A_1$, $B_1$, $C_1$, and $D_1$ for the relevant points.",
                severity="error",
            ))
    if "labels the directrix d without exposing helper endpoints" in expected:
        hidden_names = set()
        for match in re.finditer(r"\bhide\s*\(([^)]*)\)", dsl):
            hidden_names.update(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", match.group(1)))
        if "d" in hidden_names:
            diagnostics.append(_diag(
                "hidden_requested_directrix",
                "When the directrix d is requested and should be labeled, keep d visible; hide only helper endpoints.",
                severity="error",
            ))
        if not re.search(r"style\s*\([^)]*\bd\b[^)]*label_visible\s*=\s*True", dsl):
            diagnostics.append(_diag(
                "missing_directrix_label",
                "Label the directrix d with style(d, label_visible=True, label_text=\"$d$\") or equivalent.",
                severity="error",
            ))
    if "draws latus rectum through focus" in expected:
        if "right_angle_marker" not in dsl:
            diagnostics.append(_diag(
                "missing_latus_rectum_right_angle_marker",
                "For a latus rectum/focal chord perpendicular to the parabola axis, mark the right angle between the axis and chord.",
                severity="error",
            ))
    if "chooses a point on the ellipse" in expected:
        if re.search(r"\bP\s*=\s*Rotate\s*\([^)]*Center\s*\(\s*ellipse\s*\)", dsl):
            diagnostics.append(_diag(
                "ellipse_point_not_on_conic_by_rotation",
                "Rotating a focus around the center does not generally produce a point on the ellipse. Derive P by intersecting the ellipse with an axis or helper line.",
                severity="error",
            ))
        if not re.search(r"\bP\b[^=]*,\s*[A-Za-z][A-Za-z0-9_]*\s*=\s*Intersect\s*\(\s*ellipse\s*,", dsl):
            diagnostics.append(_diag(
                "missing_ellipse_point_intersection",
                "Choose the focal-radii point P on the ellipse by an Intersect(ellipse, helper) construction.",
                severity="error",
            ))
    if "marks that diagonals bisect each other" in expected and "tick_count" not in dsl:
        diagnostics.append(_diag(
            "missing_diagonal_bisect_ticks",
            "When a parallelogram diagram asks to mark that diagonals bisect each other, split both diagonals at their intersection and mark equal halves with tick_count.",
            severity="error",
        ))
    if "does not assume A and B lie on the opposite circles" in expected:
        if re.search(r"\bCircle\s*\(\s*A\s*,\s*B\s*\)", dsl) or re.search(r"\bCircle\s*\(\s*B\s*,\s*A\s*\)", dsl):
            diagnostics.append(_diag(
                "equal_center_circles_should_use_shared_radius",
                "For equal circles centered at A and B, use an explicit shared radius value/helper, not Circle(A, B) and Circle(B, A), unless the prompt states A and B lie on the opposite circles.",
                severity="error",
            ))
        if re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Distance\s*\(\s*A\s*,\s*B\s*\)", dsl):
            diagnostics.append(_diag(
                "equal_center_circles_radius_should_not_be_ab",
                "Do not set the shared circle radius to Distance(A, B) for this rhombus prompt; choose an independent radius so A and B are not treated as points on the opposite circles.",
                severity="error",
            ))
    if "marks the four rhombus sides equal without showing radius segments" in expected:
        if "tick_count" not in dsl:
            diagnostics.append(_diag(
                "missing_rhombus_equal_side_ticks",
                "Mark the four rhombus sides equal with matching tick_count and do not replace that with radius segments.",
                severity="error",
            ))
        required_sides = [
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*A\s*,\s*C\s*\)", dsl),
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*(?:C\s*,\s*B|B\s*,\s*C)\s*\)", dsl),
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*B\s*,\s*D\s*\)", dsl),
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*D\s*,\s*A\s*\)", dsl),
        ]
        if not all(required_sides):
            diagnostics.append(_diag(
                "wrong_rhombus_side_set",
                "For a rhombus from equal circles centered at A and B with intersections C and D, the side cycle is A-C-B-D. Draw and mark AC, CB, BD, and DA; AB is the diagonal, not a side.",
                severity="error",
            ))
        if re.search(r"style\s*\([^)]*\bAB\b[^)]*tick_count\s*=", dsl):
            diagnostics.append(_diag(
                "rhombus_diagonal_marked_as_side",
                "AB is the requested diagonal of the rhombus, not one of the four equal sides; do not give AB the equal-side tick_count.",
                severity="error",
            ))
    if "uses Polar(P, circle)" in expected and not re.search(r"\bPolar\s*\(\s*P\s*,\s*circle\s*\)", dsl):
        diagnostics.append(_diag(
            "missing_polar_command",
            "When the expected result asks for Polar(P, circle), use the semantic Polar(P, circle) command rather than only reconstructing the contact chord manually.",
            severity="error",
        ))
    if "draws Apollonius circle for ratio 2:1" in expected:
        if not re.search(r"label_text\s*=\s*[\"'][^\"']*(?:2\s*:\s*1|2x|PA\s*:\s*PB)", dsl):
            diagnostics.append(_diag(
                "missing_visible_apollonius_ratio_label",
                "For an Apollonius-circle ratio diagram, show the ratio with a concise visible label such as $PA:PB = 2:1$ or segment labels 2x and x; do not encode unequal ratios only with tick_count.",
                severity="error",
            ))
    if "shows correspondence segments" in expected:
        required = [
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*A\s*,\s*A1\s*\)", dsl),
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*B\s*,\s*B1\s*\)", dsl),
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*C\s*,\s*C1\s*\)", dsl),
        ]
        if not all(required):
            diagnostics.append(_diag(
                "missing_reflection_correspondence_segments",
                "When reflection checks ask for correspondence segments, draw AA1, BB1, and CC1 or equivalent segments between each point and its image.",
                severity="error",
            ))
    if "shows perpendicular diagonals" in expected:
        has_ac = (
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*A\s*,\s*C\s*\)", dsl)
            or re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Line\s*\(\s*A\s*,\s*C\s*\)", dsl)
        )
        has_bd = (
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*B\s*,\s*D\s*\)", dsl)
            or re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Line\s*\(\s*B\s*,\s*D\s*\)", dsl)
        )
        if not (has_ac and has_bd and "right_angle_marker" in dsl):
            diagnostics.append(_diag(
                "missing_perpendicular_diagonals",
                "When perpendicular diagonals are requested or checked, draw both diagonals and mark their right angle at the intersection.",
                severity="error",
            ))
    if "constructs kite" in expected:
        if re.search(r"\bC\s*=\s*Reflect\s*\(\s*B\s*,\s*(?:sym_axis|axis)\s*\)", dsl) and re.search(
            r"\bPolygon\s*\(\s*A\s*,\s*B\s*,\s*C\s*,\s*D\s*\)",
            dsl,
        ):
            diagnostics.append(_diag(
                "kite_reflection_uses_wrong_vertex",
                "For a symmetry-based kite ABCD, put A and C on the symmetry diagonal and derive the opposite side vertex as D = Reflect(B, axis); do not make C the reflection of B.",
                severity="error",
            ))
        if len(re.findall(r"\btick_count\s*=", dsl)) < 2:
            diagnostics.append(_diag(
                "kite_missing_adjacent_equal_side_ticks",
                "For a kite/deltoid, mark both adjacent equal side pairs with matching tick_count.",
                severity="error",
            ))
    if "constructs image vertices by vector arithmetic" in expected:
        if re.search(r"\b[A-Z]\d?\s*=\s*Point\s*\([^)]*\.[xy]\b", dsl):
            diagnostics.append(_diag(
                "homothety_should_use_proxy_arithmetic",
                "For homothety image points, use proxy arithmetic such as A1 = O + k * (A - O), not Point(O.x + ...).",
                severity="error",
            ))
    if _has_any([r"draws symmedians through K", r"symmedians through K", r"симмедиан"], text):
        if not (
            re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*A\s*,\s*K\s*\)", dsl)
            and re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*B\s*,\s*K\s*\)", dsl)
            and re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Segment\s*\(\s*C\s*,\s*K\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "missing_visible_symmedian_segments",
                "When symmedians through K are requested, draw segments from A, B, and C to K.",
                severity="error",
            ))
        hidden_symmedian = re.search(r"\bhide\s*\([^)]*\b(AK|BK|CK|sym_A|sym_B|sym_C)\b", dsl)
        if hidden_symmedian:
            diagnostics.append(_diag(
                "hidden_requested_symmedians",
                "Do not hide the requested symmedian segments through K; style them as the visible result.",
                severity="error",
            ))
    if _has_any([r"правильн\w+\s+пятиуголь", r"regular\s+pentagon"], text) and not re.search(r"\bPolygon\s*\([^)]*,\s*5\s*\)", dsl):
        diagnostics.append(_diag(
            "regular_pentagon_should_use_polygon_overload",
            "Use the regular polygon overload Polygon(A, B, 5) for regular pentagons.",
            severity="error",
        ))
    if _has_any([r"правильн\w+\s+шестиуголь", r"regular\s+hexagon"], text) and not re.search(r"\bPolygon\s*\([^)]*,\s*6\s*\)", dsl):
        diagnostics.append(_diag(
            "regular_hexagon_should_use_polygon_overload",
            "Use the regular polygon overload Polygon(A, B, 6) for regular hexagons.",
            severity="error",
        ))
    if _has_any([r"медиан", r"medians"], text) and _has_any([r"equal halves", r"равн\w+\s+полов"], text):
        if "tick_count" not in dsl:
            diagnostics.append(_diag(
                "missing_median_half_ticks",
                "When expected checks ask for equal halves, create half-segments and mark them with tick_count.",
                severity="error",
            ))
    if _has_any([r"концентр", r"annulus", r"concentric"], text) and _has_any([r"радиус", r"radii"], text):
        radius_label_calls = [
            match.group(0)
            for match in re.finditer(r"\bstyle\s*\([^)]*\)", dsl, flags=re.MULTILINE)
            if re.search(r"\b(r1|r2|r_in|r_out|inner_radius|outer_radius|inner|outer|radius)\b", match.group(0), flags=re.IGNORECASE)
            and "label_text" in match.group(0)
        ]
        if len(radius_label_calls) < 2:
            diagnostics.append(_diag(
                "annulus_radii_need_segment_labels",
                "For concentric-circle/annulus diagrams, label the inner and outer radius segments directly, not only their endpoints.",
                severity="error",
            ))
    if _has_any([r"касательн", r"tangent"], text):
        if "uses Tangent" in expected and not re.search(r"\bTangent\s*\(", dsl):
            diagnostics.append(_diag(
                "missing_tangent_command",
                "Expected result asks to use Tangent(...); do not replace it with a manual auxiliary-circle construction.",
                severity="error",
            ))
        if _has_any([r"точк\w+\s+касани", r"tangent points"], text) and not re.search(
            r"\bIntersect\s*\([^)]*\b(circle|circ|inc|[A-Za-z]*circle|ellipse|ell|hyperbola|conic)\b",
            dsl,
            flags=re.IGNORECASE,
        ):
            diagnostics.append(_diag(
                "missing_tangent_contact_intersections",
                "Derive tangent contact points by intersecting tangent lines with the circle/conic.",
                severity="error",
            ))
        if "draws radius OT" in expected:
            if not re.search(r"\bOT\s*=\s*Segment\s*\(\s*O\s*,\s*T\s*\)", dsl):
                diagnostics.append(_diag(
                    "missing_single_tangent_radius_segment",
                    "For a tangent at T, draw the visible radius OT.",
                    severity="error",
                ))
            if not (
                re.search(r"Angle\s*\(\s*O\s*,\s*T\s*,", dsl)
                or re.search(r"Angle\s*\([^,]+,\s*T\s*,\s*O\s*\)", dsl)
            ):
                diagnostics.append(_diag(
                    "wrong_single_tangent_right_angle_vertex",
                    "For a tangent at T, the right angle marker must have T as the middle Angle argument.",
                    severity="error",
                ))
        elif _has_any([r"radius-tangent perpendicular", r"прям\w+\s+уг", r"perpendicular"], text):
            if not (
                re.search(r"\bOT1\s*=\s*Segment\s*\(\s*O\s*,\s*T1\s*\)", dsl)
                and re.search(r"\bOT2\s*=\s*Segment\s*\(\s*O\s*,\s*T2\s*\)", dsl)
            ):
                diagnostics.append(_diag(
                    "missing_tangent_radius_segments",
                    "Show radius segments OT1 and OT2 so the radius-tangent perpendicularity marker has visible arms.",
                    severity="error",
                ))
            has_t1_angle = (
                re.search(r"Angle\s*\(\s*P\s*,\s*T1\s*,\s*O\s*\)", dsl)
                or re.search(r"Angle\s*\(\s*O\s*,\s*T1\s*,\s*P\s*\)", dsl)
            )
            has_t2_angle = (
                re.search(r"Angle\s*\(\s*P\s*,\s*T2\s*,\s*O\s*\)", dsl)
                or re.search(r"Angle\s*\(\s*O\s*,\s*T2\s*,\s*P\s*\)", dsl)
            )
            if not (has_t1_angle and has_t2_angle):
                diagnostics.append(_diag(
                    "wrong_tangent_right_angle_vertex",
                    "Radius-tangent right angles must have the tangent point as the middle Angle argument: Angle(P, T1, O) and Angle(P, T2, O).",
                    severity="error",
                ))
        if "subscripts" in expected.lower():
            has_t1_label = re.search(r"style\s*\([^)]*\bT1\b[^)]*label_text\s*=\s*[\"']\$T_1\$[\"']", dsl)
            has_t2_label = re.search(r"style\s*\([^)]*\bT2\b[^)]*label_text\s*=\s*[\"']\$T_2\$[\"']", dsl)
            if not (has_t1_label and has_t2_label):
                diagnostics.append(_diag(
                    "missing_tangent_point_subscript_labels",
                    "When tangent points require subscripts, set explicit math label_text values $T_1$ and $T_2$.",
                    severity="error",
                ))
    if _has_any([r"вневписан", r"excircle", r"excentral"], text):
        if _has_any([r"напротив\s+вершины\s+A", r"opposite\s+A", r"A-excircle"], text):
            has_internal_a = re.search(
                r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*AngularBisector\s*\(\s*B\s*,\s*A\s*,\s*C\s*\)",
                dsl,
            )
            has_external_b_or_c = re.search(
                r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*PerpendicularLine\s*\(\s*(?:B|C)\s*,\s*[A-Za-z][A-Za-z0-9_]*\s*\)",
                dsl,
            )
            if not (has_internal_a and has_external_b_or_c and re.search(r"\bI_A\s*=\s*Intersect\s*\(", dsl)):
                diagnostics.append(_diag(
                    "a_excircle_needs_external_bisector",
                    "For the A-excircle, use the internal bisector at A and an external bisector at B or C; do not intersect the two ordinary internal bisectors at B and C.",
                    severity="error",
                ))
            if "right_angle_marker" not in dsl:
                diagnostics.append(_diag(
                    "excircle_contact_needs_right_angle_marker",
                    "When showing an excircle contact point, mark the perpendicular radius/contact right angle.",
                    severity="error",
                ))
    if "uses CircleArc" in expected and not re.search(r"\bCircleArc\s*\(", dsl):
        diagnostics.append(_diag(
            "missing_circle_arc_command",
            "Expected result asks to use CircleArc(...); do not use a different arc alias in this case.",
            severity="error",
        ))
    if "uses CircleSector and CircleArc" in expected and not re.search(r"\bCircleSector\s*\(", dsl):
        diagnostics.append(_diag(
            "missing_circle_sector_command",
            "Expected result asks to use CircleSector(...); do not use a different sector alias in this case.",
            severity="error",
        ))
    if "uses CircumcircleArc(A, B, C)" in expected and not re.search(r"\bCircumcircleArc\s*\(\s*A\s*,\s*B\s*,\s*C\s*\)", dsl):
        diagnostics.append(_diag(
            "missing_circumcircle_arc_command",
            "Expected result asks to use CircumcircleArc(A, B, C); do not replace it with CircleArc(...) from a manually accessed center.",
            severity="error",
        ))
    if "keeps full circle as helper" in expected:
        if not re.search(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*Circle\s*\(\s*A\s*,\s*B\s*,\s*C\s*\)", dsl):
            diagnostics.append(_diag(
                "missing_requested_helper_circle",
                "When the expected result asks to keep the full circle as helper, construct the circumcircle with Circle(A, B, C) or equivalent.",
                severity="error",
            ))
        if re.search(r"\bhide\s*\([^)]*\b(circle|circ)\b", dsl):
            diagnostics.append(_diag(
                "hidden_requested_helper_circle",
                "When the expected result asks to keep the full circle as helper, keep it visible as auxiliary geometry instead of hiding it.",
                severity="error",
            ))
    if _has_any([r"верхн\w+\s+част", r"upper"], text):
        if not re.search(r"\bCircleArc\s*\(\s*O\s*,\s*Q\s*,\s*P\s*\)", dsl):
            diagnostics.append(_diag(
                "upper_arc_wrong_orientation",
            "For the upper arc PQ with P left-above and Q right-above, use CircleArc(O, Q, P) so the CCW arc goes through the top.",
            severity="error",
        ))
    if "uses three semicircles on aligned points" in expected:
        required_semicircles = [
            re.search(r"\bSemicircle\s*\(\s*A\s*,\s*B\s*\)", dsl),
            re.search(r"\bSemicircle\s*\(\s*A\s*,\s*C\s*\)", dsl),
            re.search(r"\bSemicircle\s*\(\s*C\s*,\s*B\s*\)", dsl),
        ]
        if not all(required_semicircles):
            diagnostics.append(_diag(
                "arbelos_should_use_diameter_endpoint_semicircles",
                "For an arbelos, use Semicircle(A, B), Semicircle(A, C), and Semicircle(C, B) on the shared diameter endpoints; do not pass midpoint centers.",
                severity="error",
            ))
        if re.search(r"\bhide\s*\([^)]*\b(AB|AC|CB)\b", dsl):
            diagnostics.append(_diag(
                "hidden_arbelos_baseline",
                "The shared diameter baseline or its subsegments should remain visible in an arbelos diagram.",
                severity="error",
            ))
    if "places the first two Pappus chain circles by the standard radius formula" in expected:
        if re.search(r"\bP2\s*=\s*C\s*\+", dsl) or _has_any([r"Actually", r"Let's check", r"for simplicity", r"Not exactly", r"Better:"], dsl):
            diagnostics.append(_diag(
                "pappus_chain_uses_speculative_or_arbitrary_placement",
                "For Pappus-chain circles, use a compact standard radius/center formula rather than speculative comments or arbitrary vertical stacking.",
                severity="error",
            ))
        if not (re.search(r"for\s+n\s+in\s+range\s*\(\s*1\s*,\s*3\s*\)", dsl) and re.search(r"n\s*\*\s*n|n\s*\*\*\s*2", dsl) and re.search(r"2\s*\*\s*n\s*\*\s*r", dsl)):
            diagnostics.append(_diag(
                "missing_pappus_standard_loop_formula",
                "The first two Pappus-chain circles should be generated from a standard formula over n=1,2 with radius depending on n*n and height 2*n*r.",
                severity="error",
            ))
    if "uses Ellipse(F1, F2, 3)" in expected and not re.search(r"\bEllipse\s*\(\s*F1\s*,\s*F2\s*,\s*3\s*\)", dsl):
        diagnostics.append(_diag(
            "missing_direct_ellipse_foci_semimajor",
            "Expected result asks to use Ellipse(F1, F2, 3); do not replace the semi-major-axis form with an extra point construction.",
            severity="error",
        ))
    if _has_any([r"эллипс.*оси", r"axes?.*ellipse", r"ellipse.*axes?"], text):
        if re.search(r"\bAxes\s*\([^)]*ellipse", dsl, flags=re.IGNORECASE) and not (
            re.search(r"\bMajorAxis\s*\(", dsl) and re.search(r"\bMinorAxis\s*\(", dsl)
        ):
            diagnostics.append(_diag(
                "ellipse_axes_should_use_semantic_helpers",
                "For separate ellipse axes, use MajorAxis(ellipse) and MinorAxis(ellipse); Axes(...) is not a two-object unpacking command in the current DSL.",
                severity="error",
            ))
    if _has_any([r"\bF1\b.*\bF2\b", r"\bF_?1\b.*\bF_?2\b"], text):
        has_f1_label = re.search(r"style\s*\([^)]*\bF1\b[^)]*label_text\s*=\s*[\"']\$F_1\$[\"']", dsl)
        has_f2_label = re.search(r"style\s*\([^)]*\bF2\b[^)]*label_text\s*=\s*[\"']\$F_2\$[\"']", dsl)
        if not (has_f1_label and has_f2_label):
            diagnostics.append(_diag(
                "missing_focus_subscript_labels",
                "For foci named F1 and F2, set explicit math label_text values $F_1$ and $F_2$.",
                severity="error",
            ))
    if "marks foci" in expected:
        if re.search(r"\bhide\s*\([^)]*\bF1\b", dsl) or re.search(r"\bhide\s*\([^)]*\bF2\b", dsl):
            diagnostics.append(_diag(
                "hidden_requested_foci",
                "When foci are requested or checked, keep F1 and F2 visible; do not hide them after labeling.",
                severity="error",
            ))

    asks_for_ad_bisector = _has_any([
        r"биссектрис\w+\s+AD\b",
        r"\bAD\b.*биссектрис",
        r"angle bisector\s+AD\b",
        r"bisector\s+AD\b",
    ], text)
    if asks_for_ad_bisector:
        correct = _has_any([
            r"AngularBisector\s*\(\s*B\s*,\s*A\s*,\s*C\s*\)",
            r"AngularBisector\s*\(\s*C\s*,\s*A\s*,\s*B\s*\)",
        ], dsl)
        if not correct:
            diagnostics.append(_diag(
                "wrong_angle_bisector_vertex",
                "Prompt asks for bisector AD, so AngularBisector must use A as the middle vertex argument: AngularBisector(B, A, C) or AngularBisector(C, A, B).",
                severity="error",
            ))
        if not re.search(r"\bAD\s*=\s*Segment\s*\(\s*A\s*,\s*D\s*\)", dsl):
            diagnostics.append(_diag(
                "missing_visible_ad_segment",
                "Prompt names bisector AD; create the visible segment as AD = Segment(A, D).",
                severity="error",
            ))
        if "equal split angles" in expected and not (
            re.search(r"Angle\s*\(\s*B\s*,\s*A\s*,\s*D\s*\)", dsl)
            and re.search(r"Angle\s*\(\s*D\s*,\s*A\s*,\s*C\s*\)", dsl)
        ):
            diagnostics.append(_diag(
                "missing_bisector_angle_marks",
                "Expected result asks to show equal split angles; add Angle(B, A, D) and Angle(D, A, C) with matching tick_count.",
                severity="error",
            ))
        elif "equal split angles" in expected and "tick_count" not in dsl:
            diagnostics.append(_diag(
                "missing_bisector_angle_ticks",
                "Equal split angles should be visibly marked with matching tick_count on the two angle objects.",
                severity="error",
            ))
        helper_names = re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*AngularBisector\s*\(", dsl)
        unhidden = [
            name for name in helper_names
            if not re.search(rf"\bhide\s*\([^)]*\b{name}\b", dsl)
        ]
        if unhidden:
            diagnostics.append(_diag(
                "visible_infinite_bisector_helper",
                "For triangle bisector AD, hide the infinite AngularBisector helper after drawing the finite segment AD.",
                severity="error",
            ))

    asks_for_midsegment = _has_any([
        r"средн\w+\s+лини",
        r"midsegment",
    ], text)
    if asks_for_midsegment and "midpoint labels visible" in expected.lower():
        midpoint_names = re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*Midpoint\s*\(", dsl)
        if midpoint_names:
            missing = [
                name for name in midpoint_names[:2]
                if not re.search(rf"style\s*\([^)]*\b{name}\b[^)]*label_visible\s*=\s*True", dsl)
            ]
            if missing:
                diagnostics.append(_diag(
                    "missing_midpoint_labels",
                    "Midpoints define the requested midsegment; keep the midpoint labels visible with style(..., label_visible=True).",
                    severity="error",
                ))

    asks_for_right_angle = _has_any([
        r"right angle",
        r"прям\w+\s+уг",
        r"перпендикуляр",
        r"высот",
        r"проекц",
    ], text)
    if asks_for_right_angle:
        if "right_angle_marker" not in dsl:
            diagnostics.append(_diag(
                "missing_right_angle_marker",
                "Perpendicular/altitude diagrams should mark the right angle with style(angle, right_angle_marker=True).",
                severity="error",
            ))
        helper_names = re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*(?:PerpendicularLine|OrthogonalLine)\s*\(", dsl)
        if _has_any([r"основан\w+\s+AB", r"base\s+AB"], text):
            helper_names.extend(
                re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*Line\s*\(\s*A\s*,\s*B\s*\)", dsl)
            )
        unhidden = [
            name for name in helper_names
            if not re.search(rf"\bhide\s*\([^)]*\b{name}\b", dsl)
        ]
        if unhidden:
            diagnostics.append(_diag(
                "visible_altitude_helper_line",
                "Hide infinite helper lines after drawing the finite base/altitude/projection segments.",
                severity="error",
            ))

    return diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, default=LIBRARY_PATH)
    args = parser.parse_args()
    library = json.loads(args.library.read_text(encoding="utf-8"))
    failed = 0
    for record in library.get("records", []):
        diagnostics = validate_record(record)
        if not diagnostics:
            continue
        failed += sum(1 for item in diagnostics if item.get("severity") == "error")
        variant = record.get("variant") or "flash"
        print(f"{variant}::{record.get('id')}")
        for item in diagnostics:
            print(f"  {item['severity']}: {item['code']}: {item['message']}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
