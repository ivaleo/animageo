"""Fixtures of «Команды» added by L3 stage 3 (plan L3 §4.5): the ops of
registry 1.4 in the default lexicon, conditions by recipe, their refusals,
checks and check commands, queries, steps from comments, the print order by
steps and ``seq``, and edit mode with conditions.

A case spec is one of:

- ``text`` — a new document;
- ``('base', base_text, text)`` — ``text`` edits the document of
  ``base_text``;
- ``('edit', base_text, [(old, new), …])`` — the printed text of the base,
  with the replacements, edits it;
- ``('seq', text, [name, …])`` — the document of ``text`` gets ``seq`` in the
  order of the operations that make these names; its printed text edits it
  (nothing changes; ``print`` shows the order).

A base is parsed and then its condition requests are carried out
(:func:`apply_condition_requests`), so it holds conditions with their places
and automatic marks. A case with requests adds ``afterRequests``: the printed
text after carrying them out, the refusals and the recipes of the new
conditions.

The cases are written with the names of the default lexicon (they read as
the user writes them); :func:`localize` renames the commands, check commands
and keywords for another lexicon, then ``{op.id}`` placeholders are filled as
in :mod:`.fixtures`.
"""
from __future__ import annotations

import re

from ..document import NativeDocument
from ..steps import assign_seq
from .build import parse_commands
from .fixtures import P3, P4, counter_ids, normalize, render_template
from .lexicon import Lexicon
from .printer import print_commands
from .requests import apply_condition_requests

__all__ = ['CATALOG_L3', 'build_case']

R = 'A = (-3, -2)\nB = (3, -2)\nC = (0.5, 2)\nD = (1, -0.5)\n'
W = R + 'O = (4, 2.5)\nw = Окружность(O, 0.8)\n'


def _ops_cases():
    two = {
        'angle.between_lines': ('α = {op}(AB, AC)', 'l = {line.by_points}(A, B)\nm = {line.by_points}(A, C)\n{op}(l, m)'),
        'angle.between_vectors': ('u = {vector.by_points}(A, B)\nv = {vector.by_points}(A, C)\nα = {op}(u, v)',
                                  'u = {vector.by_points}(B, C)\nv = {vector.by_points}(B, A)\n{op}(u, v)'),
        'angle.by_size': ('α, P = {op}(A, B, 40°)', '{op}(B, C, 1)'),
        'arc.center_two_points': ('d = {op}(A, B, C)', '{op}(B, C, A)'),
        'arc.on_circle': ('c = {circle.center_point}(A, B)\nd = {op}(c, B, C)',
                          'c = {circle.center_point}(C, A)\n{op}(c, A, B)'),
        'arc.semicircle': ('s = {op}(A, B)', '{op}(B, C)'),
        'arc.three_points': ('d, O = {op}(A, B, C)', '{op}(C, A, B)'),
        'circle.center_segment': ('s = {segment.by_points}(B, C)\nc = {op}(A, s)', 'c = {op}(A, BC)'),
        'circle.diameter': ('c, O = {op}(A, B)', '{op}(B, C)'),
        'circle.excircle': ('c, J, T = {op}(A, B, C)', '{op}(B, C, A)'),
        'intersect.line_sector': ('S = {sector.center_two_points}(A, B, C)\nl = {line.by_points}(B, C)\n'
                                  'P, Q = {op}(l, S)', 'S = {sector.center_two_points}(A, B, C)\n{op}(BC, S)'),
        'intersect.nearest': ('c = {circle.center_point}(A, B)\nl = {line.by_points}(A, C)\nP = {op}(c, l, C)',
                              'c = {circle.center_point}(A, B)\nd = {circle.center_point}(B, A)\n{op}(c, d, C)'),
        'line.angle_bisectors_of_lines': ('l = {line.by_points}(A, B)\nm = {line.by_points}(A, C)\np, q = {op}(l, m)',
                                          '{op}(AB, AC)'),
        'line.external_bisector': ('e = {op}(B, A, C)', '{op}(A, B, C)'),
        'line.tangent_at': ('c = {circle.center_point}(A, B)\nt = {op}(B, c)',
                            'c = {circle.center_point}(C, A)\n{op}(A, c)'),
        'line.tangents_from_point': ('c = {circle.center_point}(A, C)\nt, u, P, Q = {op}(B, c)',
                                     'c = {circle.center_point}(B, C)\n{op}(A, c)'),
        'measure.angle': ('α = ∠ABC\nv = {op}(α)', 'β = ∠BCA\n{op}(β)'),
        'measure.area': ('t = {polygon.by_points}(A, B, C)\nS = {op}(t)', 'c = {circle.center_point}(A, B)\n{op}(c)'),
        'measure.circumference': ('c = {circle.center_point}(A, B)\nL = {op}(c)',
                                  'c = {circle.center_radius}(C, 2)\n{op}(c)'),
        'measure.distance': ('d = {op}(C, AB)', 'l = {line.by_points}(A, B)\n{op}(C, l)'),
        'measure.length': ('s = {segment.by_points}(A, B)\nL = {op}(s)', 's = {segment.by_points}(B, C)\n{op}(s)'),
        'measure.perimeter': ('t = {polygon.by_points}(A, B, C)\nP = {op}(t)',
                              'c = {circle.center_point}(A, B)\n{op}(c)'),
        'measure.polygon_angles': ('t = {polygon.by_points}(A, B, C)\nα = {op}(t)',
                                   'q = {polygon.by_points}(A, B, C, D)\n{op}(q)'),
        'measure.radius': ('c = {circle.center_point}(A, B)\nr = {op}(c)', 'c = {circle.center_radius}(C, 2)\n{op}(c)'),
        'number.angle': ('α = {op}(0.5)', 'β = {op}(1, 0, 3, 0.1)\n{op}()'),
        'point.at_distance': ('P, s = {op}(A, B, 2)', '{op}(C, A, 1.5)'),
        'point.center': ('c = {circle.center_point}(A, B)\nO = {op}(c)', 'c = {circle.three_points}(A, B, C)\n{op}(c)'),
        'point.closest': ('c = {circle.center_point}(A, B)\nP = {op}(C, c)', 'l = {line.by_points}(A, B)\n{op}(C, l)'),
        'point.divide': ('P = {op}(A, B, 1, 2)', '{op}(B, C, 3, 1)'),
        'polygon.centroid': ('t = {polygon.by_points}(A, B, C)\nG = {op}(t)',
                             'q = {polygon.by_points}(A, B, C, D)\n{op}(q)'),
        'polygon.parallelogram': ('p = {op}(A, B, C)', '{op}(B, C, A)'),
        'polygon.regular': ('p = {op}(A, B, 5)', '{op}(A, B, 6)'),
        'polygon.regular_center': ('p = {op}(A, B, 4)', '{op}(C, A, 3)'),
        'polygon.vertex': ('t = {polygon.by_points}(A, B, C)\nV = {op}(t, 2)',
                           'q = {polygon.by_points}(A, B, C, D)\n{op}(q, 4)'),
        'polyline.by_points': ('p = {op}(A, B, C)', '{op}(A, B, C, D)'),
        'ray.at_angle': ('r, P = {op}(A, B, 30°)', '{op}(B, C, 1)'),
        'ray.by_vector': ('u = {vector.by_points}(B, C)\nr = {op}(A, u)',
                          'u = {vector.by_points}(A, B)\n{op}(C, u)'),
        'sector.center_two_points': ('S = {op}(A, B, C)', '{op}(B, C, A)'),
        'sector.from_angle': ('S = {op}(A, B, 60°)', '{op}(C, A, 1)'),
        'sector.on_circle': ('c = {circle.center_point}(A, B)\nS = {op}(c, B, C)',
                             'c = {circle.center_point}(C, A)\n{op}(c, A, B)'),
        'sector.three_points': ('S, O = {op}(A, B, C)', '{op}(C, A, B)'),
        'segment.from_point_length': ('s, P = {op}(A, 3)', '{op}(B, 2, 45°)'),
        'segment.midline': ('s = {segment.by_points}(A, B)\nt = {segment.by_points}(C, D)\nm = {op}(s, t)',
                            '{op}(AB, CD)'),
        'transform.dilate': ("A' = {op}(B, 2, A)", "t = {polygon.by_points}(A, B, C)\nt' = {op}(t, 0.5, D)"),
        'transform.reflect_line': ("C' = {op}(C, AB)", "l = {line.by_points}(A, B)\n{op}(D, l)"),
        'transform.reflect_point': ("C' = {op}(C, A)", "s = {segment.by_points}(A, B)\n{op}(s, D)"),
        'transform.rotate': ("B' = {op}(B, 90°, A)", "t = {polygon.by_points}(A, B, C)\n{op}(t, 1, D)"),
        'transform.translate': ("u = {vector.by_points}(A, B)\nC' = {op}(C, u)",
                                "u = {vector.by_points}(C, D)\nt = {polygon.by_points}(A, B, C)\n{op}(t, u)"),
    }
    cases = []
    for op, variants in two.items():
        for k, text in enumerate(variants, 1):
            cases.append((f'{op.replace(".", "_")}_{k}', P4 + text.replace('{op}', '{' + op + '}')))
    return cases


_RECIPES = [
    ('right_angle_vertex', [R + 'Условие(∠ADB = 90°)', R + 'Условие(∠BDA = 90°, двигать D)',
                            R + 'Condition(<)ADB = 90 deg)']),
    ('right_angle_side', [R + 'Условие(∠ABC = 90°)', R + 'Условие(∠BAD = 90°, двигать D)',
                          R + 'Условие(∠CBA = 90°)']),
    ('angle_value', [R + 'Условие(∠BAD = 40°)', R + 'Условие(∠BAC = 30°, двигать C)', R + 'Условие(∠DAB = 60°)']),
    ('angle_equal', [R + 'Условие(∠BAD = ∠ABC)', R + 'Условие(∠ABD = ∠BAC, двигать D)',
                     R + 'Условие(∠CAB = ∠DBA)']),
    ('equal_length_free', [R + 'Условие(|AD| = |BC|)', R + 'Условие(|CD| = |AB|)', R + 'Условие(|BD| = |AC|)']),
    ('equal_length_vertex', [R + 'Условие(|AB| = |AC|)', R + 'Условие(|AD| = |AB|)', R + 'Условие(|BA| = |BD|)']),
    ('equal_length_apex', [R + 'Условие(|DA| = |DB|)', R + 'Условие(|CA| = |CB|, двигать C)',
                           R + 'Условие(|CA| = |CB|)']),
    ('length_value', [R + 'Условие(|AC| = 5)', R + 'Условие(|BD| = 2)', R + 'Условие(|DC| = 3, двигать D)']),
    ('on_line', [R + 'Условие(D ∈ AB)', R + 'l = Прямая(A, C)\nУсловие(D ∈ l)', R + 'Условие(C in BD)']),
    ('on_object', [R + 'k = Окружность(A, B)\nУсловие(D ∈ k)', R + 's = Отрезок(A, B)\nУсловие(D ∈ s)',
                   R + 'k = Окружность(C, 2)\nУсловие(D ∈ k)']),
    ('parallel', [R + 'Условие(AB ∥ DC)', R + 'Условие(AC || BD)', R + 'Условие(BD ∥ AC, двигать D)']),
    ('perpendicular', [R + 'Условие(AB ⟂ CD)', R + 'Условие(AC _|_ BD)', R + 'Условие(BD ⟂ AC, двигать D)']),
    ('tangent', [W + 'Условие(CD касается w)', W + 'Условие(AD касается w)', W + 'Condition(BD touches w)']),
]

_REFUSALS = [
    ('unsupported', R + 'Условие(ПроверкаКоллинеарности(A, B, C, D))'),
    ('unsupported_receiver', R + 'Условие(|AB| = 3, двигать C)'),
    ('not_free', P3 + 'M = Середина(A, B)\nN = Середина(B, C)\nУсловие(|MN| = 2)'),
    ('not_free_explicit', P3 + 'M = Середина(A, B)\nУсловие(|MC| = 2, двигать M)'),
    ('ancestor', P3 + 'M = Середина(A, B)\nУсловие(∠AMC = 90°, двигать A)'),
    ('ancestor_all', P3 + 'M = Середина(A, B)\nУсловие(|AM| = 3)'),
    ('too_many', R + 'Условие(|AC| = 5)\nУсловие(|BC| = 4)\nУсловие(∠ACB = 90°)'),
    ('too_many_on_path', R + 'l = Прямая(A, B)\nP = Точка(l)\nУсловие(|CP| = 3)\nУсловие(|DP| = 2)'),
    ('ambiguous_pair', 'A = (0, 0)\nB = (1, 0)\nC = (2, 1)\nAB = (3, 3)\nBC = (4, 1)\nУсловие(|ABC| = 2)'),
    ('ambiguous_pair_object', 'A = (0, 0)\nB = (1, 0)\nC = (2, 1)\nAB = (3, 3)\nBC = (4, 1)\nD = (1, 2)\nУсловие(D ∈ ABC)'),
    ('unknown_name', R + 'Условие(|AX| = 2)'),
    ('statement_missing', R + 'Условие(AB)'),
    ('two_relations', R + 'Условие(AB ∥ CD ∥ AC)'),
    ('move_word', R + 'Условие(|AC| = 2, тянуть C)'),
    ('move_not_point', R + 'k = Окружность(A, B)\nУсловие(|AC| = 2, двигать k)'),
    ('length_of_number', R + 'r = 2\nУсловие(|r| = 2)'),
    ('segment_as_number', R + 's = Отрезок(A, B)\nУсловие(s = 2)'),
    ('point_on_point', R + 'Проверить(A ∈ B)'),
    ('check_point_not_object', R + 'Проверить(AB ∈ C)'),
    ('empty', R + 'Условие()'),
    ('names_on_left', R + 't = Проверить(A ∈ AB)'),
]

_CHECKS = [
    ('eq_lengths', P3 + 'M = Середина(A, B)\nПроверить(|AM| = |MB|)'),
    ('eq_value', P3 + 'Проверить(|AB| = 4)'),
    ('ne_lengths', P3 + 'Проверить(|AC| ≠ |BC|)'),
    ('ne_angle', P3 + 'Проверить(∠ABC ≠ 90°)'),
    ('eq_expression', P3 + 'r = 2\nПроверить(|AB|^2 = |AC|·|BC| + r/2 - √(4))'),
    ('eq_trig', P3 + 'Проверить(sin(∠BAC) = |BC|/|AB| · cos(π/3))'),
    ('eq_angle_ref', P3 + 'α = ∠BAC\nПроверить(α + ∠ABC + ∠BCA = 180°)'),
    ('parallel', P4 + 'Проверить(AB ∥ CD)'),
    ('parallel_named', P4 + 'l = Прямая(A, B)\nm = Параллельная(C, l)\nПроверить(l ∥ m)'),
    ('perpendicular', P3 + 'H = Проекция(C, AB)\nПроверить(CH ⟂ AB)'),
    ('perpendicular_typed', P3 + 'H = Проекция(C, AB)\nh = Отрезок(C, H)\nПроверить(h _|_ AB)'),
    ('tangent', P3 + 'c = Окружность(A, B)\nt = Касательная(B, c)\nПроверить(t касается c)'),
    ('tangent_english', P3 + 'c = Окружность(A, B)\nCheck(BC touches c)'),
    ('on', P3 + 'M = Середина(A, B)\nПроверить(M ∈ AB)'),
    ('on_circle', P3 + 'c = Окружность(A, B)\nПроверить(C in c)'),
    ('coincident', P3 + 'M = Середина(A, B)\nN = Середина(B, A)\nПроверить(M = N)'),
    ('coincident_command', P3 + 'M = Середина(A, B)\nN = Середина(B, A)\nПроверкаСовпадения(M, N)'),
    ('collinear', P3 + 'M = Середина(A, B)\nПроверить(ПроверкаКоллинеарности(A, M, B))'),
    ('collinear_command', P3 + 'M = Середина(A, B)\nAreCollinear(A, M, B)'),
    ('concyclic', P4 + 'Проверить(ПроверкаКонцикличности(A, B, C, D))'),
    ('concyclic_command', P4 + 'AreConcyclic(A, B, C, D)'),
    ('concurrent', P3 + 'p = Медиана(A, BC)\nq = Медиана(B, CA)\nr = Медиана(C, AB)\n'
                   'Проверить(ПроверкаКонкурентности(p, q, r))'),
    ('concurrent_command', P3 + 'p = Медиана(A, BC)\nq = Медиана(B, CA)\nr = Медиана(C, AB)\nAreConcurrent(p, q, r)'),
    ('congruent', P4 + 'Проверить(ПроверкаРавенства(AB, CD))'),
    ('congruent_command', P4 + 'AreCongruent(AB, CD)'),
    ('parallel_command', P4 + 'ПроверкаПараллельности(AB, CD)'),
    ('parallel_alias', P4 + 'AreParallel(AB, CD)'),
    ('perpendicular_command', P3 + 'H = Проекция(C, AB)\nПроверкаПерпендикулярности(CH, AB)'),
    ('perpendicular_alias', P3 + 'H = Проекция(C, AB)\nArePerpendicular(CH, AB)'),
    ('tangent_command', P3 + 'c = Окружность(A, B)\nt = Касательная(B, c)\nПроверкаКасания(t, c)'),
    ('tangent_alias', P3 + 'c = Окружность(A, B)\nt = Касательная(B, c)\nIsTangent(t, c)'),
    ('on_command', P3 + 'M = Середина(A, B)\nПроверкаПринадлежности(M, AB)'),
    ('on_alias', P3 + 'c = Окружность(A, B)\nIsOnPath(B, c)'),
    ('order_by_seq', P3 + 'Проверить(|AB| = 4)\nПроверить(|AC| ≠ 2)\nM = Середина(A, B)\nПроверить(M ∈ AB)\n'
                     'Проверить(|AM| = 2)'),
    ('check_command_arity', P3 + 'ПроверкаПараллельности(AB)'),
    ('collinear_arity', P3 + 'ПроверкаКоллинеарности(A, B)'),
    ('relation', P4 + 'Отношение(AB, CD)'),
    ('relation_named', P3 + 'M = Середина(A, B)\nh = Отрезок(C, M)\nRelation(h, AB)'),
    ('relation_arity', P3 + 'Отношение(AB)'),
]

_STEPS = [
    ('given', '# Дано\n' + P3 + '\nM = Середина(A, B)'),
    ('given_english', '# Given\n' + P3),
    ('group_title', P3 + '# Середины сторон\nM = Середина(A, B)\nN = Середина(B, C)\nK = Середина(C, A)'),
    ('group_bare', P3 + '#\nM = Середина(A, B)\nN = Середина(B, C)\n\nK = Середина(C, A)'),
    ('group_ends_on_comment', P3 + '# Первая\nM = Середина(A, B)\n# Вторая\nN = Середина(B, C)\nK = Середина(C, A)'),
    ('group_ends_on_blank', P3 + '# Середины\nM = Середина(A, B)\nN = Середина(B, C)\n\nK = Середина(C, A)'),
    ('step_text', P3 + 'H = Проекция(C, AB)  # основание высоты'),
    ('step_text_two', P3 + 'M = Середина(A, B)  # середина AB\nN = Середина(B, C)  # середина BC'),
    ('group_text', P3 + '# Высота\nH = Проекция(C, AB)  # из вершины C\nh = Отрезок(C, H)'),
    ('group_two_texts', P3 + '# Середины\nM = Середина(A, B)  # первая\nN = Середина(B, C)  # вторая'),
    ('group_with_pairs', P3 + '# Высоты\nH = Проекция(C, AB)\nK = Проекция(A, BC)'),
    ('group_with_check', P3 + '# Середина\nM = Середина(A, B)\nПроверить(|AM| = |MB|)\nN = Середина(M, C)'),
    ('empty_group', P3 + '# Пусто\n\nM = Середина(A, B)'),
    ('title_with_hash', P3 + '# Шаг # 2\nM = Середина(A, B)\nN = Середина(B, C)'),
    ('given_then_group', '# Дано\n' + P3 + '# Построение\nM = Середина(A, B)\nc = Окружность(M, A)'),
    ('failed_line_in_group', P3 + '# Середины\nM = Середина(A, X)\nN = Середина(B, C)\nK = Середина(N, A)'),
]

_ORDER = [
    ('seq_reverse', ('seq', P3 + 'M = Середина(A, B)\nN = Середина(B, C)\nK = Середина(C, A)', ['K', 'N', 'M'])),
    ('seq_partial', ('seq', P3 + 'M = Середина(A, B)\nN = Середина(B, C)\nK = Середина(C, A)', ['M'])),
    ('seq_points', ('seq', P3 + 'D = (5, 4)', ['D', 'C', 'B', 'A'])),
    ('seq_dependencies_win', ('seq', P3 + 'M = Середина(A, B)\nN = Середина(M, C)', ['N', 'M', 'C'])),
    ('seq_numbers', ('seq', 'r = 2\nk = 3\nA = (0, 0)\nc = Окружность(A, r)\nd = Окружность(A, k)', ['k', 'd', 'r', 'c'])),
    ('steps_group_order', ('seq', P3 + '# Вторая\nN = Середина(B, C)\nK = Середина(C, A)\n\n# Первая\n'
                           'M = Середина(A, B)', ['M', 'N', 'K'])),
    ('condition_after_step', ('edit', R + 'M = Середина(A, B)\nУсловие(∠ADB = 90°)\nh = Отрезок(D, M)', [])),
    ('condition_after_last_participant', ('edit', R + 'E = (2, 2)\nУсловие(|AD| = |BC|)', [])),
    ('conditions_by_seq', ('edit', R + 'Условие(|AC| = 5)\nУсловие(∠ADB = 90°)\nПроверить(|AB| = 6)', [])),
    ('checks_by_seq', ('edit', P3 + 'Проверить(|BC| = 1)\nПроверить(|AB| = 4)\nM = Середина(A, B)\n'
                       'Проверить(M ∈ AB)', [])),
    ('receiver_by_origin', ('edit', R + 'Условие(|AC| = 5)\nM = Середина(A, C)', [])),
    ('move_printed', ('edit', R + 'Условие(|AC| = |BC|, двигать C)\nУсловие(∠ADB = 90°, двигать D)', [])),
    ('auto_marks_hidden', ('edit', R + 'Условие(∠ADB = 90°)\nУсловие(|AC| = |BC|)', [])),
    ('group_with_condition', ('edit', '# Дано\n' + R + '# Построение\nM = Середина(A, B)\nУсловие(|DM| = 2)', [])),
]

_BASE_C = R + 'Условие(∠ADB = 90°)\nM = Середина(A, B)\nПроверить(|DM| = |MA|)'
_BASE_TWO = R + 'Условие(|AC| = 5)\nУсловие(|BC| = 4)'

_EDIT = [
    ('unchanged', ('edit', _BASE_C, [])),
    ('replace_statement', ('edit', _BASE_C, [('∠ADB = 90°', '∠ADB = 60°')])),
    ('replace_kind', ('edit', _BASE_C, [('∠ADB = 90°', '|AD| = 3')])),
    ('release', ('edit', _BASE_C, [('Условие(∠ADB = 90°)\n', '')])),
    ('apply_new', ('edit', _BASE_C, [('M = Середина(A, B)', 'M = Середина(A, B)\nУсловие(|AC| = 5)')])),
    ('move_receiver', ('edit', _BASE_C, [('D = (1, -0.5)', 'D = (1.5, -1)')])),
    ('move_receiver_twice', ('edit', _BASE_TWO, [('C = (0.5, 2)', 'C = (0, 3)')])),
    ('rename_participant', ('edit', _BASE_C, [('A = (-3, -2)', 'P = (-3, -2)'), ('∠ADB', '∠PDB'),
                                              ('Середина(A, B)', 'Середина(P, B)'), ('|MA|', '|MP|')])),
    ('delete_participant', ('edit', _BASE_C, [('B = (3, -2)\n', '')])),
    ('change_receiver', ('edit', _BASE_C, [('∠ADB = 90°', '∠ADB = 90°, двигать A')])),
    ('same_receiver_explicit', ('edit', _BASE_C, [('∠ADB = 90°', '∠ADB = 90°, двигать D')])),
    ('check_removed', ('edit', _BASE_C, [('\nПроверить(|DM| = |MA|)', '')])),
    ('check_changed', ('edit', _BASE_C, [('|DM| = |MA|', '|DM| = |MB|')])),
    ('check_added', ('edit', _BASE_C, [('Проверить(|DM| = |MA|)', 'Проверить(|DM| = |MA|)\nПроверить(D ∈ AB)')])),
    ('release_one_of_two', ('edit', _BASE_TWO, [('Условие(|BC| = 4)', '')])),
    ('replace_one_of_two', ('edit', _BASE_TWO, [('|BC| = 4', '|BC| = 3')])),
    ('third_condition', ('edit', _BASE_TWO, [('Условие(|BC| = 4)', 'Условие(|BC| = 4)\nУсловие(∠ACB = 90°)')])),
    ('swap_order', ('edit', _BASE_TWO, [('Условие(|AC| = 5)\nУсловие(|BC| = 4)',
                                         'Условие(|BC| = 4)\nУсловие(|AC| = 5)')])),
    ('error_in_condition', ('edit', _BASE_C, [('∠ADB = 90°', '∠ADX = 90°')])),
    ('steps_kept', ('edit', '# Дано\n' + R + '# Построение\nM = Середина(A, B)\nУсловие(|DM| = 2)', [])),
    ('steps_retitled', ('edit', '# Дано\n' + R + '# Построение\nM = Середина(A, B)\nN = Середина(A, C)',
                        [('# Построение', '# Середины')])),
]

CATALOG_L3 = [
    ('parse_l2a4', _ops_cases()),
    ('conditions', [(f'{name}_{k}', text) for name, texts in _RECIPES for k, text in enumerate(texts, 1)]),
    ('condition_errors', _REFUSALS),
    ('checks', _CHECKS),
    ('comment_steps', _STEPS),
    ('print_order', _ORDER),
    ('edit_conditions', _EDIT),
]


_WORD = re.compile(r'[^\W\d]\w*')
_DEFAULT = []


def localize(text: str, lexicon: Lexicon) -> str:
    """``text`` written with the names of the default lexicon, renamed for
    ``lexicon``: a command name by its operation, a check command by its
    kind, a keyword by its key; other words stay."""
    if not _DEFAULT:
        _DEFAULT.append(Lexicon())
    default = _DEFAULT[0]
    if lexicon.hash == default.hash:
        return text

    def word(match):
        w = match.group(0)
        for entry in default.entries:
            if entry.name == w:
                target = next((e for e in lexicon.entries if e.op == entry.op), None)
                if target is not None:
                    return target.name
        kind = default.check_kind(w)
        if kind is not None and default.check_name(kind) == w:
            return lexicon.check_name(kind) or w
        key = default.keyword(w)
        if key is not None and default.word(key) == w:
            return lexicon.word(key)
        return w

    return _WORD.sub(word, text)


def _t(text: str, lexicon: Lexicon) -> str:
    return render_template(localize(text, lexicon), lexicon)


def _parse(text, base, lexicon):
    return parse_commands(text, lexicon=lexicon, base=base, id_factory=counter_ids(), document_id='doc')


def _base(text, lexicon):
    result = _parse(_t(text, lexicon), None, lexicon)
    return apply_condition_requests(result.document, result.conditionRequests).document


def build_case(name: str, spec, lexicon) -> dict:
    base = None
    if isinstance(spec, str):
        text = _t(spec, lexicon)
    elif spec[0] == 'base':
        base = _base(spec[1], lexicon)
        text = _t(spec[2], lexicon)
    elif spec[0] == 'edit':
        base = _base(spec[1], lexicon)
        text = print_commands(base, lexicon=lexicon).text
        for old, new in spec[2]:
            text = text.replace(_t(old, lexicon), _t(new, lexicon))
    else:   # seq
        doc = _base(spec[1], lexicon)
        by_name = {el.get('displayName'): el['producer']['operationId'] for el in doc.elements.values()
                   if el.get('displayName')}
        base = assign_seq(doc, [by_name[n] for n in spec[2]])
        text = print_commands(base, lexicon=lexicon).text
    data = base.data if isinstance(base, NativeDocument) else base
    result = _parse(text, data, lexicon)
    expect = normalize(result, with_effects=base is not None)
    printed = print_commands(result.document, lexicon=lexicon)
    expect['print'] = printed.text
    if printed.issues:
        expect['printIssues'] = [{'code': i.code, 'line': i.line, 'column': i.column, 'severity': i.severity}
                                 for i in printed.issues]
    if result.conditionRequests:
        applied = apply_condition_requests(result.document, result.conditionRequests)
        after = {c['id']: c for c in applied.document.data.get('conditions') or ()}
        expect['afterRequests'] = {
            'print': print_commands(applied.document, lexicon=lexicon).text,
            'results': [{'line': r['line'], 'kind': r['kind'],
                         'refusal': None if r['refusal'] is None else r['refusal']['code'],
                         'recipe': (after.get(r['conditionId']) or {}).get('recipe')
                         if r['refusal'] is None and r['kind'] in ('apply', 'replace') else None}
                        for r in applied.results],
        }
    return {'name': name, 'text': text, 'base': data, 'expect': expect}
