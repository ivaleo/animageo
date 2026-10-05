"""Fixtures of «Команды» ``animageo-commands/v1`` and the default-name table
``animageo-naming/v1`` (commands.md §9).

The cases are templates: ``{point.midpoint}`` is replaced by the first name
the lexicon gives the operation (the registry ID when it gives none),
``{point.midpoint:alias}`` by the first alias of that entry (the name when
it has none). So one catalog yields the fixtures of any lexicon, and the
browser parser is checked against the fixtures of its own lexicon.

A case is ``{name, text, base, expect}``. New documents get ``documentId``
``"doc"``; IDs come from counters ``o1, o2…`` (operations) and ``e1, e2…``
(elements) that skip IDs already in ``base``. ``expect`` is normalized: IDs
are replaced by display names, hidden elements by ``#1, #2…`` in order of
appearance, operations follow the lines (the hidden operations of a line
before it); ``print`` is the printer's text for the parsed document; a case
with ``base`` adds the raw ``effects``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..canonical import canonical_json
from ..edit import name_key
from ..registry import REGISTRY_VERSION
from .build import is_helper, parse_commands
from .lexicon import Lexicon, lexicon_hash
from .naming import next_name, polygon_side_names
from .printer import print_commands

__all__ = [
    'COMMANDS_FORMAT',
    'NAMING_FORMAT',
    'DEFAULT_DIR',
    'counter_ids',
    'render_template',
    'normalize',
    'build_fixtures',
    'write_fixtures',
    'check_fixtures',
]

COMMANDS_FORMAT = 'animageo-commands/v1'
NAMING_FORMAT = 'animageo-naming/v1'
DEFAULT_DIR = Path(__file__).resolve().parent.parent / 'parity' / 'v1' / 'commands'

_PLACEHOLDER = re.compile(r'\{([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)(:alias)?\}')

P3 = 'A = (0, 0)\nB = (4, 0)\nC = (1, 3)\n'
P4 = P3 + 'D = (5, 4)\n'


def counter_ids():
    """The fixture ID factory: ``o1, o2…`` and ``e1, e2…``."""
    counts = {'operation': 0, 'element': 0}

    def factory(kind):
        counts[kind] += 1
        return ('o' if kind == 'operation' else 'e') + str(counts[kind])

    return factory


def render_template(text: str, lexicon: Lexicon) -> str:
    def name(match):
        op = match.group(1)
        entry = next((e for e in lexicon.entries if e.op == op), None)
        if entry is None:
            return op
        if match.group(2) and entry.aliases:
            return entry.aliases[0]
        return entry.name

    return _PLACEHOLDER.sub(name, text)


# ── the catalog ──────────────────────────────────────────────────────────
# (fixture id, [(case name, text, base text or None)])

_OPS = [
    ('parse_points', [
        ('free_point', 'A = (1, 2)', None),
        ('free_point_signs', 'A = (-1.5, 2.25)\nB = (+3, -0)', None),
        ('free_point_unnamed', '(3, 4)\n(5, 6)', None),
        ('on_path_parameter', P3 + 'l = {line.by_points}(A, B)\nP = {point.on_path}(l, 0.25)', None),
        ('on_path_default', P3 + 'c = {circle.center_point}(A, B)\nP = {point.on_path}(c)', None),
        ('on_path_pair', P3 + 'P = {point.on_path}(AB, 2)', None),
        ('midpoint', P3 + 'M = {point.midpoint}(A, B)', None),
        ('midpoint_unnamed', P3 + '{point.midpoint}(B, C)', None),
        ('midpoint_chain', P3 + 'M = {point.midpoint}(A, B)\nN = {point.midpoint}(M, C)', None),
        ('projection_pair', P3 + 'H = {point.projection}(C, AB)', None),
        ('projection_strict', P3 + 's = {segment.by_points}(A, B)\nH = {point.projection}(C, s, 1)', None),
        ('projection_unnamed', P3 + 'l = {line.by_points}(A, B)\n{point.projection}(C, l)', None),
        ('number_value', 'r = 3', None),
        ('number_slider', 'k = {number.free}(1, 0, 5, 0.5)', None),
        ('number_slider_short', 'k = {number.free}(2, -1)\nm = {number.free}()', None),
    ]),
    ('parse_lines', [
        ('segment', P3 + 's = {segment.by_points}(A, B)', None),
        ('segment_unnamed', P3 + '{segment.by_points}(B, C)\n{segment.by_points}(C, A)', None),
        ('segment_alias', P3 + 's = {segment.by_points:alias}(A, C)', None),
        ('line', P3 + 'l = {line.by_points}(A, B)', None),
        ('line_unnamed', P3 + '{line.by_points}(A, B)\n{line.by_points}(B, C)', None),
        ('line_alias', P3 + 'l = {line.by_points:alias}(C, A)', None),
        ('ray', P3 + 'r = {ray.by_points}(A, B)', None),
        ('ray_unnamed', P3 + '{ray.by_points}(B, C)', None),
        ('ray_on_path', P3 + 'r = {ray.by_points}(A, C)\nP = {point.on_path}(r, 1.5)', None),
        ('parallel', P3 + 'l = {line.by_points}(A, B)\np = {line.parallel}(C, l)', None),
        ('parallel_pair', P3 + 'p = {line.parallel}(C, AB)', None),
        ('parallel_segment', P3 + 's = {segment.by_points}(A, B)\np = {line.parallel}(C, s)', None),
        ('perpendicular', P3 + 'l = {line.by_points}(A, B)\nq = {line.perpendicular}(C, l)', None),
        ('perpendicular_pair', P3 + 'q = {line.perpendicular}(C, AB)', None),
        ('perpendicular_ray', P3 + 'r = {ray.by_points}(A, B)\nq = {line.perpendicular}(C, r)', None),
        ('bisector', P3 + 'm = {line.perpendicular_bisector}(A, B)', None),
        ('bisector_unnamed', P3 + '{line.perpendicular_bisector}(B, C)', None),
        ('bisector_chain', P3 + 'm = {line.perpendicular_bisector}(A, B)\nn = {line.perpendicular_bisector}(B, C)\n'
                           'O = {intersect.line_line}(m, n)', None),
        ('angle_bisector', P3 + 'w = {line.angle_bisector}(B, A, C)', None),
        ('angle_bisector_unnamed', P3 + '{line.angle_bisector}(A, B, C)', None),
        ('angle_bisector_chain', P3 + 'w = {line.angle_bisector}(B, A, C)\nW = {intersect.line_line}(w, BC)', None),
        ('vector', P3 + 'v = {vector.by_points}(A, B)', None),
        ('vector_unnamed', P3 + '{vector.by_points}(B, C)', None),
        ('vector_alias', P3 + 'v = {vector.by_points:alias}(C, A)', None),
    ]),
    ('parse_intersections', [
        ('line_line', P4 + 'l = {line.by_points}(A, B)\nm = {line.by_points}(C, D)\nX = {intersect.line_line}(l, m)', None),
        ('line_line_pairs', P4 + 'X = {intersect.line_line}(AB, CD)', None),
        ('line_line_segments', P4 + 's = {segment.by_points}(A, D)\nt = {segment.by_points}(B, C)\n'
                               '{intersect.line_line}(s, t)', None),
        ('line_circle', P3 + 'c = {circle.center_point}(A, C)\nl = {line.by_points}(A, B)\n'
                        'P, Q = {intersect.line_circle}(l, c)', None),
        ('line_circle_swapped', P3 + 'c = {circle.center_point}(A, C)\nl = {line.by_points}(A, B)\n'
                                'P, Q = {intersect.line_circle}(c, l)', None),
        ('line_circle_prefix', P3 + 'c = {circle.center_point}(A, C)\nP = {intersect.line_circle}(AB, c)', None),
        ('circle_circle', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                          'P, Q = {intersect.circle_circle}(c, d)', None),
        ('circle_circle_unnamed', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                                  '{intersect.circle_circle}(d, c)', None),
        ('circle_circle_one', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                              'X = {intersect.circle_circle}(c, d)', None),
        ('other_than_circles', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                               'X = {intersect.other_than}(c, d, не C)', None),
        ('other_than_line', P3 + 'c = {circle.center_point}(B, A)\nX = {intersect.other_than}(AC, c, не A)', None),
        ('other_than_lines', P4 + 'l = {line.by_points}(A, B)\nm = {line.by_points}(C, A)\n'
                             'Y = {intersect.other_than}(l, m, не A)', None),
    ]),
    ('parse_circles', [
        ('center_point', P3 + 'c = {circle.center_point}(A, B)', None),
        ('center_point_unnamed', P3 + '{circle.center_point}(A, B)\n{circle.center_point}(B, C)', None),
        ('center_point_alias', P3 + 'c = {circle.center_point:alias}(C, A)', None),
        ('center_radius_literal', P3 + 'c = {circle.center_radius}(A, 2.5)', None),
        ('center_radius_number', P3 + 'r = 2\nc = {circle.center_radius}(A, r)', None),
        ('center_radius_slider', P3 + 'k = {number.free}(1, 0, 3)\nc = {circle.center_radius}(B, k)', None),
        ('three_points', P3 + 'k, O = {circle.three_points}(A, B, C)', None),
        ('three_points_prefix', P3 + 'k = {circle.three_points}(A, B, C)', None),
        ('three_points_unnamed', P3 + '{circle.three_points}(A, B, C)', None),
        ('incircle', P3 + 'ω, I, T_a, T_b, T_c = {circle.incircle}(A, B, C)', None),
        ('incircle_prefix', P3 + 'ω = {circle.incircle}(A, B, C)', None),
        ('incircle_center', P3 + 'ω, I = {circle.incircle}(A, B, C)\ns = {segment.by_points}(A, I)', None),
        ('polygon_triangle', P3 + 't = {polygon.by_points}(A, B, C)', None),
        ('polygon_named_sides', P3 + 't, z, x, y = {polygon.by_points}(A, B, C)', None),
        ('polygon_quad', P4 + 'q = {polygon.by_points}(A, B, D, C)', None),
    ]),
    ('parse_angles_marks', [
        ('angle', P3 + 'α = {angle.by_points}(B, A, C)', None),
        ('angle_symbol', P3 + 'β = ∠ABC', None),
        ('angle_unnamed', P3 + '∠BCA\n{angle.by_points}(C, A, B)', None),
        ('equal_segments_pairs', P3 + 'M = {point.midpoint}(A, B)\n{mark.equal_segments}(AM, MB)', None),
        ('equal_segments_named', P3 + 's = {segment.by_points}(A, C)\nt = {segment.by_points}(B, C)\n'
                                 '{mark.equal_segments}(s, t, 2)', None),
        ('equal_segments_three', P3 + 't = {polygon.by_points}(A, B, C)\n{mark.equal_segments}(a, b, c, 3)', None),
        ('equal_angles_symbols', P3 + '{mark.equal_angles}(∠BAC, ∠ACB)', None),
        ('equal_angles_named', P3 + 'α = ∠BAC\nβ = ∠CBA\n{mark.equal_angles}(α, β, 2)', None),
        ('equal_angles_named_mark', P3 + 'α = ∠BAC\nm = {mark.equal_angles}(α, ∠ACB, ∠CBA)', None),
        ('right_angle', P3 + 'H = {point.projection}(C, AB)\n{mark.right_angle}(C, H, B)', None),
        ('right_angle_named', P3 + 'r = {mark.right_angle}(B, A, C)', None),
        ('right_angle_count_free', P3 + '{mark.right_angle}(A, B, C)\n{mark.right_angle}(B, C, A)', None),
    ]),
    ('parse_triangle', [                    # registry 1.5 (L3 stage 1)
        ('altitude_pair', P3 + 'h = {triangle.altitude}(C, AB)', None),
        ('altitude_named', P3 + 'h, H = {triangle.altitude}(A, BC)', None),
        ('altitude_segment', P3 + 's = {segment.by_points}(B, C)\nh, H, e = {triangle.altitude:alias}(A, s)', None),
        ('median_pair', P3 + 'm = {triangle.median}(A, BC)', None),
        ('median_named', P3 + 'm, M = {triangle.median}(B, CA)', None),
        ('median_alias', P3 + 's = {segment.by_points}(A, B)\nm = {triangle.median:alias}(C, s)', None),
        ('bisector_pair', P3 + 'l = {triangle.bisector}(A, BC)', None),
        ('bisector_named', P3 + 'l, L = {triangle.bisector}(B, CA)', None),
        ('bisector_segment', P3 + 's = {segment.by_points}(A, B)\nl = {triangle.bisector}(C, s)', None),
        ('centroid', P3 + 'G = {triangle.centroid}(A, B, C)', None),
        ('centroid_alias', P3 + 'G = {triangle.centroid:alias}(B, C, A)', None),
        ('centroid_unnamed', P3 + '{triangle.centroid}(A, B, C)', None),
        ('incenter', P3 + 'I = {triangle.incenter}(A, B, C)', None),
        ('incenter_alias', P3 + 'I = {triangle.incenter:alias}(C, A, B)', None),
        ('incenter_unnamed', P3 + '{triangle.incenter}(A, B, C)', None),
        ('circumcenter', P3 + 'O = {triangle.circumcenter}(A, B, C)', None),
        ('circumcenter_alias', P3 + 'O = {triangle.circumcenter:alias}(B, C, A)', None),
        ('circumcenter_unnamed', P3 + '{triangle.circumcenter}(A, B, C)', None),
        ('orthocenter', P3 + 'H = {triangle.orthocenter}(A, B, C)', None),
        ('orthocenter_alias', P3 + 'H = {triangle.orthocenter:alias}(C, A, B)', None),
        ('orthocenter_unnamed', P3 + '{triangle.orthocenter}(A, B, C)', None),
        ('excenter', P3 + 'J = {triangle.excenters}(A, B, C)', None),
        ('excenter_alias', P3 + 'J = {triangle.excenters:alias}(B, C, A)', None),
        ('excenter_unnamed', P3 + '{triangle.excenters}(C, A, B)', None),
        ('locus_segment', P3 + 'P = {point.on_path}(AB, 0.25)\nM = {point.midpoint}(C, P)\n'
                          'g = {locus.of_point}(M, P)', None),
        ('locus_circle', P3 + 'c = {circle.center_point}(A, B)\nP = {point.on_path}(c, 1)\n'
                         'M = {point.midpoint}(C, P)\ng = {locus.of_point:alias}(M, P)', None),
        ('locus_slider', P3 + 'k = {number.free}(1, 0, 3)\nd = {circle.center_radius}(A, k)\n'
                         'P, Q = {intersect.line_circle}(AB, d)\n{locus.of_point}(Q, k)', None),
    ]),
]

_SYNTAX = [
    ('pairs', [
        ('pair_segment_slot', P4 + '{mark.equal_segments}(AB, CD)', None),
        ('pair_line_slot', P4 + 'X = {intersect.line_line}(AB, CD)', None),
        ('pair_reuses_visible', P4 + 's = {segment.by_points}(A, B)\n{mark.equal_segments}(AB, CD)', None),
        ('pair_reuses_hidden', P4 + 'X = {intersect.line_line}(AB, CD)\nY = {intersect.line_line}(AB, CD)', None),
        ('pair_element_wins', P3 + 'AB = (2, 2)\nM = {point.midpoint}(AB, C)', None),
        ('element_name_reads_as_pair', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                                       'X, BC = {intersect.circle_circle}(c, d)\nM = {point.midpoint}(BC, A)\n'
                                       'A_1 = (5, 5)\nBA_{1} = {segment.by_points}(A, C)', None),
        ('pair_indexed_points', 'A_1 = (0, 0)\nB = (3, 0)\nC = (0, 2)\nH = {point.projection}(C, A_1B)', None),
        ('pair_primes', "A' = (0, 1)\nB' = (3, 1)\nC = (0, 2)\nH = {point.projection}(C, A'B')", None),
        ('pair_order_kept', P4 + '{mark.equal_segments}(BA, DC)', None),
    ]),
    ('overloads', [
        ('english_names', P3 + 'M = Midpoint(A, B)\nc = Circle(A, B)', None),
        ('case_and_spaces', P3 + 'm = серединный перпендикуляр(A, B)\nn = СЕРЕДИНА(A, C)', None),
        ('circle_overloads', P3 + 'r = 2\nc = {circle.center_point}(A, B)\nd = {circle.center_point}(A, r)\n'
                             'e = {circle.center_point}(A, B, C)', None),
        ('point_overloads', P3 + 'l = {line.by_points}(A, B)\nP = {point.free}((1, 1))\nQ = {point.free}(l)', None),
        ('line_alias_parallel', P3 + 'l = {line.by_points}(A, B)\np = {line.by_points}(C, l)', None),
        ('registry_id', P3 + 'M = point.midpoint(A, B)\nl = line.by_points(A, C)', None),
        ('intersection_overloads', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                                   'X = {intersect.line_line}(AB, BC)\nP, Q = {intersect.line_line}(c, AB)\n'
                                   'R, S = {intersect.line_line}(c, d)\nT = {intersect.line_line}(c, d, не C)', None),
    ]),
    ('names', [
        ('default_points', '(0, 0)\n(1, 0)\n(2, 0)', None),
        ('default_points_skip_taken', 'B = (0, 0)\n(1, 0)\n(2, 0)\nA_1 = (3, 0)', None),
        ('default_points_index', '\n'.join(['(0, 0)'] * 28), None),
        ('default_lines', P3 + '{line.by_points}(A, B)\n{segment.by_points}(B, C)\n{ray.by_points}(C, A)\n'
                          '{vector.by_points}(A, C)\n{line.by_points}(B, A)', None),
        ('default_circles', P3 + '{circle.center_point}(A, B)\n{circle.center_point}(B, C)\n'
                            '{circle.center_point}(C, A)', None),
        ('default_polygons', P4 + '{polygon.by_points}(A, B, C)\n{polygon.by_points}(A, B, D)', None),
        ('default_angles', P3 + '∠ABC\n∠BCA\nα = ∠CAB\n∠ACB', None),
        ('reserved_names', P3 + '{line.by_points}(A, B)\na = {line.by_points}(B, C)', None),
        ('school_sides_taken', P3 + 'a = {line.by_points}(A, B)\nt = {polygon.by_points}(A, B, C)', None),
        ('school_sides_long_names', 'A_1 = (0, 0)\nB = (4, 0)\nC = (1, 3)\nt = {polygon.by_points}(A_1, B, C)', None),
        ('left_prefix', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                        'X = {intersect.circle_circle}(c, d)', None),
        ('name_forms', "A_{1} = (0, 0)\nB' = (1, 0)\nC2 = (2, 0)\nD₃ = (3, 0)\nПи = (4, 0)", None),
    ]),
    ('numbers', [
        ('decimals', 'A = (0.1, 0.000001)\nB = (123456789012345.6, -2.5)', None),
        ('exponents', 'A = (1.5e-7, 2E+21)\nB = (1e15, .5)', None),
        ('negative_zero', 'A = (-0, -0.0)\nr = -0', None),
        ('degrees', 'α = 40°\nβ = 90 deg\nγ = -30°', None),
        ('long_fraction', 'A = (0.30000000000000004, 0.1)\nr = 3.14159265358979', None),
    ]),
    ('errors', [
        ('unknown_command', P3 + 'M = Серидина(A, B)', None),
        ('unknown_command_nothing_close', P3 + 'Q = Квадрат(A, B)', None),
        ('unknown_name', P3 + 'M = {point.midpoint}(A, D)', None),
        ('unknown_name_forward', P3 + 'M = {point.midpoint}(A, D)\nD = (5, 5)', None),
        ('unknown_name_not', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                             'X = {intersect.other_than}(c, d, не D)', None),
        ('arity_args', P3 + 'M = {point.midpoint}(A, B, C)', None),
        ('arity_list_min', P3 + '{mark.equal_segments}(AB)', None),
        ('arity_names', P3 + 'M, N = {point.midpoint}(A, B)', None),
        ('type_mismatch_point', P3 + 'l = {line.by_points}(A, B)\nM = {point.midpoint}(A, l)', None),
        ('type_mismatch_literal', P3 + 'M = {point.midpoint}(A, 2)', None),
        ('type_mismatch_not', P3 + 'l = {line.by_points}(A, B)\nm = {line.by_points}(A, C)\n'
                              'X = {intersect.other_than}(l, m, A)', None),
        ('ambiguous_pair', 'A = (0, 0)\nAB = (1, 1)\nB = (2, 0)\nBC = (3, 3)\nC = (4, 4)\n'
                           'H = {point.projection}(C, ABC)', None),
        ('ambiguous_angle', 'A = (0, 0)\nB = (2, 0)\nC = (3, 3)\nD = (4, 0)\nAB = (1, 1)\nCD = (4, 4)\n'
                            'α = ∠ABCD', None),
        ('name_taken', P3 + 'A = (5, 5)', None),
        ('name_taken_left', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                            'P, P = {intersect.circle_circle}(c, d)', None),
        ('name_taken_key', 'A_{1} = (0, 0)\nA_1 = (1, 1)', None),
        ('invalid_name', 'A_ = (0, 0)', None),
        ('invalid_name_long', 'A' * 33 + ' = (0, 0)', None),
        ('forbidden_condition', P3 + 'Условие(|AB| = |AC|)', None),
        ('forbidden_check', P3 + 'Проверить(A ∈ AB)', None),
        ('forbidden_equation', 'y = 2x + 1', None),
        ('forbidden_function', 'f(x) = x^2 - 2x', None),
        ('forbidden_inequality', 'y > x^2', None),
        ('forbidden_expression', 'r = 2 * 3', None),
        ('forbidden_key_value', 'k = {number.free}(1, min = 0)', None),
        ('forbidden_near', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                           'X = {intersect.other_than}(c, d, около C)', None),
        ('forbidden_copy', P3 + 'b = A', None),
        ('syntax_paren', P3 + 'M = {point.midpoint}(A, B', None),
        ('syntax_extra_paren', P3 + 'M = {point.midpoint}(A, B))', None),
        ('syntax_empty_arg', P3 + 'M = {point.midpoint}(A,, B)', None),
        ('syntax_comma', P3 + 'M = {point.midpoint}(A B)', None),
        ('syntax_char', P3 + 'M = {point.midpoint}(A; B) @', None),
        ('syntax_no_right', 'M =', None),
        ('comment_dropped', P3 + 'M = {point.midpoint}(A, B)  # середина AB\n# строка-комментарий', None),
        ('errors_skip_line', P3 + 'M = {point.midpoint}(A, X)\nN = {point.midpoint}(B, C)\nK = {point.midpoint}(M, N)',
         None),
        ('columns_in_code_points', 'Ω = (0, 0)\nΣ = (1, 1)\nζ = {point.midpoint}(Ω, Ψ)', None),
        ('columns_before_replacements', 'A = (0, 0)\nB = (1, 1)  # a || b\nk = 2 * 3', None),
    ]),
]

_BASE = P3 + 't = {polygon.by_points}(A, B, C)\nM = {point.midpoint}(A, B)\ns = {segment.by_points}(C, M)\n' \
             '{mark.equal_segments}(AM, MB)'

_EDIT = [
    ('edit', [
        ('unchanged', _BASE, _BASE),
        ('move_point', _BASE.replace('C = (1, 3)', 'C = (1, 4)'), _BASE),
        ('change_number', 'r = 2\nA = (0, 0)\nc = {circle.center_radius}(A, r)'.replace('r = 2', 'r = 2.5'),
         'r = 2\nA = (0, 0)\nc = {circle.center_radius}(A, r)'),
        ('redefine', _BASE.replace('M = {point.midpoint}(A, B)', 'M = {point.projection}(C, AB)'), _BASE),
        ('redefine_refused', _BASE.replace('M = {point.midpoint}(A, B)', 'M = {circle.center_point}(A, B)'), _BASE),
        ('redefine_free', _BASE.replace('M = {point.midpoint}(A, B)', 'M = (2, -1)'), _BASE),
        ('delete_line', _BASE.replace('s = {segment.by_points}(C, M)\n', ''), _BASE),
        ('delete_line_cascade', _BASE.replace('M = {point.midpoint}(A, B)\n', '').replace('s = {segment.by_points}(C, M)\n',
                                                                                          '')
         .replace('\n{mark.equal_segments}(AM, MB)', ''), _BASE),
        ('new_line', _BASE + '\nN = {point.midpoint}(B, C)', _BASE),
        ('new_name_is_new_operation', _BASE.replace('s = {segment.by_points}(C, M)', 'u = {segment.by_points}(C, M)'),
         _BASE),
        ('mark_count', _BASE.replace('(AM, MB)', '(AM, MB, 2)'), _BASE),
        ('mark_removed', _BASE.replace('\n{mark.equal_segments}(AM, MB)', ''), _BASE),
        ('secondary_names', _BASE.replace('t = {polygon.by_points}', 't, z, x = {polygon.by_points}'), _BASE),
        ('error_keeps_operation', _BASE.replace('M = {point.midpoint}(A, B)', 'M = {point.midpoint}(A, B'), _BASE),
        ('swap_outputs', P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\n'
                         'Q, P = {intersect.circle_circle}(c, d)',
         P3 + 'c = {circle.center_point}(A, C)\nd = {circle.center_point}(B, C)\nP, Q = {intersect.circle_circle}(c, d)'),
        ('redefine_moves_down', P3.replace('C = (1, 3)\n', '') + 'c = {circle.center_point}(A, B)\n'
                                'C, D = {intersect.line_circle}(AB, c)',
         P3 + 'c = {circle.center_point}(A, B)'),
        ('free_name_reused', P3.replace('C = (1, 3)\n', '') + 'c = {circle.center_point}(A, B)\n'
                             'D, C = {intersect.line_circle}(AB, c)',
         P3 + 'c = {circle.center_point}(A, B)'),
    ]),
]

CATALOG = _OPS + _SYNTAX + _EDIT

_NAMING_CASES = [
    ('point_first', 'point', []),
    ('point_next', 'point', ['A', 'B', 'D']),
    ('point_after_z', 'point', list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
    ('point_key_braces', 'point', list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['A_{1}']),
    ('line_first', 'line', []),
    ('line_skips_e', 'line', ['a', 'b', 'c', 'd']),
    ('segment_like_line', 'segment', ['a']),
    ('ray_like_line', 'ray', ['a', 'b']),
    ('vector_like_line', 'vector', []),
    ('number_like_line', 'number', ['a']),
    ('line_index', 'line', list('abcdfghjklmnopqrstuvw')),
    ('circle_first', 'circle', []),
    ('circle_next', 'circle', ['c', 'd']),
    ('circle_wraps', 'circle', list('cdfghjklmnopqrstuvw')),
    ('polygon_first', 'polygon', []),
    ('polygon_next', 'polygon', ['t', 't_1']),
    ('angle_first', 'angle', []),
    ('angle_next', 'angle', ['α', 'β']),
    ('angle_index', 'angle', list('αβγδεζηθκλμνξπρστφχψω')),
    ('mark', 'mark', []),
]

_KEY_NAMES = ['A', 'A_1', 'A_{1}', 'A_{12}', "A_{1}'", 'A1', 'A₁', 'α_{2}', 'T_{ab}', 'Пи_{1}', "B''"]

_SIDE_CASES = [
    ('triangle_school', ['A', 'B', 'C'], []),
    ('triangle_rotated', ['B', 'C', 'A'], []),
    ('triangle_one_taken', ['A', 'B', 'C'], ['a']),
    ('triangle_all_taken', ['A', 'B', 'C'], ['a', 'b', 'c']),
    ('triangle_long_vertex', ['A_1', 'B', 'C'], []),
    ('triangle_vertex_e', ['E', 'F', 'G'], []),
    ('quadrilateral', ['A', 'B', 'C', 'D'], []),
    ('pentagon_taken', ['A', 'B', 'C', 'D', 'F'], ['a', 'c']),
]


# ── expectations ─────────────────────────────────────────────────────────


def normalize(result, *, with_effects: bool = False) -> dict:
    """The ``expect`` of a parse result (without ``print``)."""
    data = result.document.data
    ops = data['operations']
    elements = data['elements']
    order = []
    for entry in result.lines:
        for op_id in entry['operationIds'][1:] + entry['operationIds'][:1]:
            if op_id not in order:
                order.append(op_id)
    order += [op_id for op_id in ops if op_id not in order]
    hidden = {}

    def label(el_id):
        el = elements.get(el_id)
        if el is None:
            return '?'
        if el.get('displayName'):
            return el['displayName']
        producer = (el.get('producer') or {}).get('operationId')
        if producer is not None and is_helper(data, producer):
            if el_id not in hidden:
                hidden[el_id] = f'#{len(hidden) + 1}'
            return hidden[el_id]
        return ''

    def arg(value):
        if value.get('kind') == 'ref':
            return label(value.get('elementId'))
        if value.get('kind') == 'list':
            return [arg(item) for item in value.get('items') or ()]
        return value.get('value')

    operations = []
    for op_id in order:
        op = ops[op_id]
        helper = is_helper(data, op_id)
        outputs = {o['slot']: label(o['elementId']) for o in op.get('outputs') or ()}
        operations.append({'op': op['op'], 'args': {k: arg(v) for k, v in (op.get('args') or {}).items()},
                           'outputs': outputs, 'hidden': helper})
    expect = {
        'operations': operations,
        'inputs': {label(k): v for k, v in (data.get('inputs') or {}).items()},
        'lines': [{'line': e['line'], 'elements': [label(x) for x in e['elementIds']]} for e in result.lines],
        'issues': [{'code': i.code, 'line': i.line, 'column': i.column, 'severity': i.severity}
                   for i in result.issues],
    }
    if with_effects:
        expect['effects'] = result.effects
    return expect


def _library_version() -> str:
    from ... import __version__
    return __version__


def _case(name: str, text: str, base_text, lexicon: Lexicon) -> dict:
    text = render_template(text, lexicon)
    base = None
    if base_text is not None:
        base = parse_commands(render_template(base_text, lexicon), lexicon=lexicon,
                              id_factory=counter_ids(), document_id='doc').document.data
    result = parse_commands(text, lexicon=lexicon, base=base, id_factory=counter_ids(), document_id='doc')
    expect = normalize(result, with_effects=base is not None)
    printed = print_commands(result.document, lexicon=lexicon)
    expect['print'] = printed.text
    if printed.issues:
        expect['printIssues'] = [{'code': i.code, 'line': i.line, 'column': i.column, 'severity': i.severity}
                                 for i in printed.issues]
    return {'name': name, 'text': text, 'base': base, 'expect': expect}


def _naming_fixture() -> dict:
    return {
        'format': NAMING_FORMAT,
        'id': 'naming',
        'registry': REGISTRY_VERSION,
        'generatedBy': f'animageo {_library_version()}',
        'cases': [{'name': n, 'type': t, 'taken': taken, 'expect': next_name(t, taken)}
                  for n, t, taken in _NAMING_CASES],
        'sides': [{'name': n, 'vertices': v, 'taken': taken, 'expect': polygon_side_names(v, taken)}
                  for n, v, taken in _SIDE_CASES],
        'keys': [{'name': n, 'key': name_key(n)} for n in _KEY_NAMES],
    }


def build_fixtures(lexicon=None) -> dict:
    """``{file name: fixture}`` for ``lexicon`` (a dict, a :class:`Lexicon` or ``None``)."""
    lex = lexicon if isinstance(lexicon, Lexicon) else Lexicon(lexicon)
    out = {}
    for fixture_id, cases in CATALOG:
        out[f'{fixture_id}.json'] = {
            'format': COMMANDS_FORMAT,
            'id': fixture_id,
            'lexiconHash': lexicon_hash(lex.data),
            'registry': REGISTRY_VERSION,
            'generatedBy': f'animageo {_library_version()}',
            'cases': [_case(name, text, base, lex) for name, text, base in cases],
        }
    out['naming.json'] = _naming_fixture()
    return out


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def write_fixtures(out_dir, lexicon=None) -> list:
    """Write the fixtures of ``lexicon`` into ``out_dir``; returns the paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fixture in build_fixtures(lexicon).items():
        path = out_dir / name
        path.write_text(_dump(fixture), encoding='utf-8')
        written.append(path)
    return written


def _comparable(data):
    if isinstance(data, dict):
        return canonical_json({k: v for k, v in data.items() if k != 'generatedBy'})
    return canonical_json(data)


def check_fixtures(out_dir, lexicon=None) -> list:
    """Differences between ``out_dir`` and fresh fixtures of ``lexicon``
    (``generatedBy`` is not compared), as readable lines."""
    out_dir = Path(out_dir)
    problems = []
    fresh = build_fixtures(lexicon)
    for name, fixture in fresh.items():
        path = out_dir / name
        if not path.exists():
            problems.append(f'missing: {path}')
            continue
        try:
            on_disk = json.loads(path.read_text(encoding='utf-8'))
        except ValueError as exc:
            problems.append(f'{path}: not JSON ({exc})')
            continue
        if _comparable(on_disk) == _comparable(fixture):
            continue
        cases = {c.get('name'): c for c in on_disk.get('cases', ()) if isinstance(c, dict)}
        changed = [c['name'] for c in fixture.get('cases', ()) if _comparable(cases.get(c['name'])) != _comparable(c)]
        detail = f" (cases: {', '.join(changed[:8])}{'…' if len(changed) > 8 else ''})" if changed else ''
        problems.append(f'out of date: {path}{detail}')
    for path in sorted(out_dir.glob('*.json')):
        if path.name not in fresh:
            problems.append(f'unexpected: {path}')
    return problems
