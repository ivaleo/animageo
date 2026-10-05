"""«Команды»: lexicon, lexer, parser, default names, printer, edit mode,
fixtures and the command line (docs/native/commands.md)."""
import copy
import json
import math

import pytest

from animageo import native
from animageo.native.cli import main
from animageo.native.commands import (
    ERROR_CODES,
    CommandIssue,
    Lexicon,
    LexiconError,
    default_lexicon,
    format_number,
    is_helper,
    lexicon_hash,
    lexicon_problems,
    next_name,
    parse_commands,
    polygon_side_names,
    print_commands,
)
from animageo.native.commands.build import HELPER_OPS, time_ordered_id
from animageo.native.commands.fixtures import (
    CATALOG,
    DEFAULT_DIR,
    build_fixtures,
    check_fixtures,
    counter_ids,
    render_template,
)
from animageo.native.commands.lexer import tokenize
from animageo.native.edit import valid_name
from animageo.native.registry import registry
from tests.native.conftest import SCENES_DIR, read_json

P3 = 'A = (0, 0)\nB = (4, 0)\nC = (1, 3)\n'


def parse(text, **kwargs):
    kwargs.setdefault('id_factory', counter_ids())
    kwargs.setdefault('document_id', 'doc')
    return parse_commands(text, **kwargs)


def by_name(result, name):
    data = result.document.data
    return next(e for e in data['elements'].values() if e['displayName'] == name)


def producer(result, name):
    data = result.document.data
    return data['operations'][by_name(result, name)['producer']['operationId']]


def errors(result):
    return [(i.code, i.line, i.column) for i in result.issues if i.severity == 'error']


def changed(effects):
    return {g: {k: v for k, v in effects[g].items() if v} for g in ('added', 'removed', 'modified')
            if any(effects[g].values())}


# ── structure for the round trip ─────────────────────────────────────────


def describe(data):
    """Operations by names: ``(op, args, named outputs, hidden)``; hidden
    elements are described by their definition."""
    ops, els = data['operations'], data['elements']
    helpers = {o for o in ops if is_helper(data, o)}

    def label(el):
        e = els.get(el)
        if e is None:
            return '?' + el
        if e.get('displayName'):
            return e['displayName']
        prod = (e.get('producer') or {}).get('operationId')
        if prod in helpers:
            op = ops[prod]
            return '#' + op['op'] + '(' + ','.join(label(op['args'][s]['elementId'])
                                                    for s in HELPER_OPS[op['op']]) + ')'
        return '~'

    def arg(a):
        if a['kind'] == 'ref':
            return label(a['elementId'])
        if a['kind'] == 'list':
            return [arg(i) for i in a['items']]
        if a['kind'] == 'expr':
            return a['ast']
        if a['kind'] == 'template':
            return a['value']
        return float(a['value'])

    rows = []
    for op_id, op in ops.items():
        outs = {o['slot']: label(o['elementId']) for o in op['outputs']
                if o['elementId'] in els and els[o['elementId']].get('displayName')}
        rows.append((op['op'], native.canonical_json({k: arg(v) for k, v in op['args'].items()}), outs,
                     op_id in helpers))
    inputs = {label(k): v for k, v in (data.get('inputs') or {}).items()}
    return rows, inputs


def structure_problems(original, parsed):
    """Differences of structure: every operation of ``original`` is in
    ``parsed`` (named outputs equal; outputs that ``original`` leaves
    unbound or unnamed are not compared) and nothing else is."""
    a, a_inputs = describe(original)
    b, b_inputs = describe(parsed)
    pool = list(b)
    problems = []
    for op, args, outs, hidden in a:
        hit = next((j for j, (op2, args2, outs2, hidden2) in enumerate(pool)
                    if (op2, args2, hidden2) == (op, args, hidden)
                    and all(outs2.get(k) == v for k, v in outs.items())), None)
        if hit is None:
            problems.append(f'missing {op} {args} {outs}')
        else:
            pool.pop(hit)
    problems += [f'extra {row}' for row in pool]
    for name, value in a_inputs.items():
        other = b_inputs.get(name)
        want = value['value'] if isinstance(value['value'], list) else [value['value']]
        got = None if other is None else (other['value'] if isinstance(other['value'], list) else [other['value']])
        if other is None or other['kind'] != value['kind'] or [float(x) for x in want] != [float(x) for x in got]:
            problems.append(f'input {name}: {value} vs {other}')
    return problems


SCENES = sorted(p for p in SCENES_DIR.glob('*.json') if p.stem != 'graph_errors')
# Ops of registry 1.4 get lexicon entries in L3; the default lexicon covers 1.0–1.3.
LEXICON_OPS = {op for op, r in registry().ops.items() if r['since'] != '1.4'}


# ── lexicon ──────────────────────────────────────────────────────────────


class TestLexicon:
    def test_default_lexicon_is_usable(self):
        assert lexicon_problems(default_lexicon()) == []
        lex = Lexicon()
        assert lex.hash == lexicon_hash(default_lexicon())
        assert lex.hash.startswith('sha256:')

    def test_names_ignore_case_and_spaces(self):
        lex = Lexicon()
        assert [e.op for e in lex.lookup('серединный  ПЕРПЕНДИКУЛЯР')] == ['line.perpendicular_bisector']
        assert {e.op for e in lex.lookup('Пересечение')} == {
            'intersect.line_line', 'intersect.line_circle', 'intersect.circle_circle', 'intersect.other_than'}

    def test_registry_id_is_a_command(self):
        lex = Lexicon()
        [entry] = lex.lookup('point.on_path')
        assert [p.slot or p.kind for p in entry.positions] == ['path', '$input']
        assert entry.min_args == 1
        assert lex.lookup('Point.On_Path') == []

    def test_every_op_has_a_name(self):
        lex = Lexicon()
        named = {e.op for e in lex.entries}
        assert named == LEXICON_OPS

    @pytest.mark.parametrize('mutate, needle', [
        (lambda d: d.update(format='x'), 'format'),
        (lambda d: d['commands'].append({'name': 'Х', 'op': 'point.nothing'}), 'not an operation'),
        (lambda d: d['commands'].append({'name': 'Х', 'op': 'point.midpoint', 'form': ['a']}),
         'leaves out the input slots'),
        (lambda d: d['commands'].append({'name': 'Х', 'op': 'point.midpoint', 'form': ['a', 'b', 'c']}),
         'is not an input slot'),
        (lambda d: d['commands'].append({'name': 'Х', 'op': 'point.free'}), 'needs $input'),
        (lambda d: d['commands'].append({'name': 'Х', 'op': 'point.midpoint', 'minArgs': 1}),
         'cannot be left out'),
        (lambda d: d['commands'].append({'name': 'Середина', 'op': 'line.perpendicular_bisector'}),
         'unreachable'),
        (lambda d: d['commands'].append({'name': 'Х', 'op': 'point.midpoint', 'extra': 1}), 'unknown keys'),
    ])
    def test_problems(self, mutate, needle):
        data = default_lexicon()
        mutate(data)
        problems = lexicon_problems(data)
        assert any(needle in p for p in problems), problems
        with pytest.raises(LexiconError):
            Lexicon(data)

    def test_ambiguous_overload(self):
        data = {'format': 'animageo-lexicon/v1', 'commands': [
            {'name': 'Х', 'op': 'line.parallel'},
            {'name': 'Х', 'op': 'line.perpendicular'},
        ]}
        assert any('unreachable' in p or 'ambiguous' in p for p in lexicon_problems(data))

    def test_narrower_overload_first_is_fine(self):
        data = {'format': 'animageo-lexicon/v1', 'commands': [
            {'name': 'Х', 'op': 'intersect.line_line'},
            {'name': 'Х', 'op': 'intersect.other_than'},
        ]}
        assert lexicon_problems(data) == []


# ── lexer and grammar ────────────────────────────────────────────────────


class TestLexer:
    def test_replacements_keep_columns(self):
        tokens, comment = tokenize('a || b _|_ c <)ABC x >= 1 <= 2 * 3 P in a 40deg  # x')
        syms = [(t.text, t.column) for t in tokens if t.kind == 'sym']
        assert syms == [('∥', 3), ('⟂', 8), ('∠', 14), ('≥', 22), ('≤', 27), ('·', 32), ('∈', 38),
                        ('°', 45)]
        assert comment == 50

    def test_names_and_numbers(self):
        tokens, _ = tokenize("A_{1} B'' C₂ point.midpoint 1.5e-3 .5 −2")
        assert [(t.kind, t.text) for t in tokens] == [
            ('name', 'A_{1}'), ('name', "B''"), ('name', 'C₂'), ('name', 'point.midpoint'),
            ('number', '1.5e-3'), ('number', '.5'), ('sym', '-'), ('number', '2')]

    def test_unknown_character(self):
        result = parse('A = (0, 0) @')
        assert errors(result) == [('syntax', 1, 12)]

    def test_columns_count_code_points(self):
        result = parse('Ω = (0, 0)\nζ = Середина(Ω, Ψ)')
        assert errors(result) == [('unknown_name', 2, 17)]


class TestGrammar:
    @pytest.mark.parametrize('text, code', [
        ('Условие(|AB| = |AC|)', 'forbidden'),
        ('Проверить(AB ∥ CD)', 'forbidden'),
        ('y = 2x + 1', 'forbidden'),
        ('x = 3', 'forbidden'),
        ('f(x) = x^2', 'forbidden'),
        ('x^2 + y^2 = 4', 'forbidden'),
        ('y > x', 'forbidden'),
        ('r = 2 + 3', 'forbidden'),
        ('r = Середина(A, B) + 1', 'forbidden'),
        ('k = Параметр(1, min = 0)', 'forbidden'),
        ('M = Середина(A, (1 + 2))', 'forbidden'),
        ('b = A', 'forbidden'),
        ('A = B = C', 'forbidden'),
        ('M = Середина(A, B', 'syntax'),
        ('M = Середина(A, B))', 'syntax'),
        ('M = Середина(A,, B)', 'syntax'),
        ('M = Середина(A B)', 'syntax'),
        ('A, = (1, 2)', 'syntax'),
        ('= (1, 2)', 'syntax'),
        ('M =', 'syntax'),
        ('M = Середина(не)', 'syntax'),
    ])
    def test_refused(self, text, code):
        result = parse(text)
        assert [i.code for i in result.issues] == [code]
        assert result.document.operations == {}

    def test_near_suggests_not(self):
        result = parse(P3 + 'c = Окружность(A, C)\nd = Окружность(B, C)\nX = Пересечение(c, d, около C)')
        [issue] = result.issues
        assert (issue.code, issue.line, issue.column, issue.hint) == ('forbidden', 6, 23, 'не C')
        assert 'будет позже' in issue.message

    def test_comments_are_dropped_with_a_warning(self):
        result = parse('A = (0, 0)  # начало\n# только комментарий\n\n')
        assert [(i.code, i.line, i.column, i.severity) for i in result.issues] == [
            ('comment_dropped', 1, 13, 'warning'), ('comment_dropped', 2, 1, 'warning')]
        assert len(result.document.operations) == 1

    def test_crlf(self):
        result = parse('A = (0, 0)\r\nB = (1, 1)\r\n')
        assert result.issues == [] and len(result.document.operations) == 2

    def test_issue_to_dict(self):
        issue = CommandIssue('name_taken', 2, 1, 'm', hint='A_1')
        assert issue.to_dict() == {'code': 'name_taken', 'line': 2, 'column': 1, 'message': 'm',
                                   'severity': 'error', 'hint': 'A_1'}


# ── parsing ──────────────────────────────────────────────────────────────


class TestParse:
    def test_default_ids_follow_creation_order(self):
        ids = [time_ordered_id() for _ in range(5000)]
        assert ids == sorted(ids) and len(set(ids)) == len(ids)
        assert all(i[14] == '7' and i[19] in '89ab' for i in ids)
        text = '\n'.join(f'P_{{{k}}} = ({k}, 0)' for k in range(1, 40))
        doc = parse_commands(text).document
        assert print_commands(doc).text == text

    def test_new_document(self):
        result = parse(P3 + 'M = Середина(A, B)')
        data = result.document.data
        assert data['format'] == native.DOCUMENT_FORMAT
        assert data['documentId'] == 'doc'
        assert data['operationRegistryVersion'] == native.__registry_version__
        assert native.validate(result.document) == []
        assert sorted(data['operations']) == ['o1', 'o2', 'o3', 'o4']
        assert producer(result, 'M')['args'] == {'a': {'kind': 'ref', 'elementId': 'e1'},
                                                 'b': {'kind': 'ref', 'elementId': 'e2'}}
        assert data['inputs']['e3'] == {'kind': 'point', 'value': [1.0, 3.0]}
        assert result.lines[-1] == {'line': 4, 'operationIds': ['o4'], 'elementIds': ['e4']}
        assert changed(result.effects) == {'added': {'operations': ['o1', 'o2', 'o3', 'o4'],
                                                     'elements': ['e1', 'e2', 'e3', 'e4'],
                                                     'inputs': ['e1', 'e2', 'e3']}}

    def test_default_ids_are_uuids(self):
        result = parse_commands('A = (0, 0)')
        [op_id] = result.document.operations
        assert len(op_id) == 36 and result.document.document_id != op_id

    def test_id_factory_without_kind(self):
        counter = iter(range(100))
        result = parse_commands('A = (0, 0)', id_factory=lambda: f'id{next(counter)}', document_id='d')
        assert list(result.document.operations) == ['id0'] and list(result.document.elements) == ['id1']

    def test_bad_id_factory(self):
        with pytest.raises(ValueError):
            parse_commands('A = (0, 0)', id_factory=lambda kind: 'not an id!')

    def test_values(self):
        result = parse('A = (-1.5, 2)\nr = 3\nα = 40°\nk = Параметр(1, 0, 5)\nm = Параметр()')
        inputs = result.document.inputs
        assert inputs[by_name(result, 'A')['id']]['value'] == [-1.5, 2.0]
        assert inputs[by_name(result, 'α')['id']]['value'] == 40 * math.pi / 180
        assert producer(result, 'k')['args'] == {'min': {'kind': 'number', 'value': 0.0},
                                                 'max': {'kind': 'number', 'value': 5.0}}
        assert inputs[by_name(result, 'm')['id']] == {'kind': 'number', 'value': 0.0}

    def test_slider_value_defaults_to_min(self):
        data = {'format': 'animageo-lexicon/v1', 'commands': [
            {'name': 'Ползунок', 'op': 'number.free', 'form': ['min', 'max', '$input'], 'minArgs': 2}]}
        result = parse('k = Ползунок(2, 5)', lexicon=data)
        assert result.document.inputs[by_name(result, 'k')['id']] == {'kind': 'number', 'value': 2.0}

    def test_on_path_default_parameter(self):
        result = parse(P3 + 'c = Окружность(A, B)\nP = Точка(c)\nQ = Точка(BC)')
        inputs = result.document.inputs
        paths = registry().paths
        assert inputs[by_name(result, 'P')['id']]['value'] == paths['circle']['default']
        assert inputs[by_name(result, 'Q')['id']]['value'] == paths['line']['default']

    def test_left_side_is_a_prefix(self):
        result = parse(P3 + 'ω = ВписаннаяОкружность(A, B, C)')
        outputs = producer(result, 'ω')['outputs']
        names = [result.document.elements[o['elementId']]['displayName'] for o in outputs]
        assert [o['slot'] for o in outputs] == ['circle', 'center', 'touch_a', 'touch_b', 'touch_c']
        assert names == ['ω', 'D', 'E', 'F', 'G']

    def test_explicit_names_are_reserved(self):
        result = parse(P3 + 'Прямая(A, B)\na = Прямая(B, C)')
        assert result.issues == []
        assert by_name(result, 'b')['type'] == 'line' and by_name(result, 'a')['type'] == 'line'

    def test_triangle_sides_get_school_names(self):
        result = parse(P3 + 't = Многоугольник(A, B, C)')
        outputs = producer(result, 't')['outputs']
        assert [(o['slot'], result.document.elements[o['elementId']]['displayName']) for o in outputs] == [
            ('polygon', 't'), ('side.1', 'c'), ('side.2', 'a'), ('side.3', 'b')]

    def test_line_after_an_error_is_built(self):
        result = parse(P3 + 'M = Середина(A, X)\nN = Середина(B, C)\nK = Середина(M, N)')
        assert errors(result) == [('unknown_name', 4, 17), ('unknown_name', 6, 14)]
        assert {e['displayName'] for e in result.document.elements.values()} == {'A', 'B', 'C', 'N'}

    def test_forward_reference(self):
        result = parse(P3 + 'M = Середина(A, D)\nD = (5, 5)')
        [issue] = result.issues
        assert (issue.code, issue.line) == ('unknown_name', 4)
        assert issue.message == 'D задаётся ниже, в строке 5'
        assert issue.hint == 'ссылаться можно только на строки выше'

    @pytest.mark.parametrize('text, code, column', [
        ('M = Сeредина(A, B)', 'unknown_command', 5),
        ('M = Середина(A, B, C)', 'arity', 5),
        ('M, N = Середина(A, B)', 'arity', 4),
        ('l = Прямая(A, B)\nM = Середина(A, l)', 'type_mismatch', 17),
        ('M = Середина(A, 2)', 'type_mismatch', 17),
        ('A = (5, 5)', 'name_taken', 1),
        ('A_ = (5, 5)', 'invalid_name', 1),
        ('ОтметкаРавныхОтрезков(AB)', 'arity', 1),
    ])
    def test_errors(self, text, code, column):
        result = parse(P3 + text)
        issue = result.issues[-1]
        assert (issue.code, issue.column) == (code, column)

    def test_unknown_command_hint(self):
        [issue] = parse('M = Сeредина(A, B)').issues
        assert issue.hint == 'Середина'
        [issue] = parse('M = Квадрат(A, B)').issues
        assert issue.hint is None

    def test_name_taken_hint_and_key(self):
        [issue] = parse('A_{1} = (0, 0)\nA_1 = (1, 1)').issues
        assert (issue.code, issue.hint) == ('name_taken', 'A_2')


class TestPairs:
    def test_slot_type_picks_the_operation(self):
        result = parse(P3 + 'D = (5, 4)\nОтметкаРавныхОтрезков(AB, CD)\nX = Пересечение(AB, CD)')
        data = result.document.data
        hidden = sorted((op['op'], tuple(a['elementId'] for a in op['args'].values()))
                        for op_id, op in data['operations'].items() if is_helper(data, op_id))
        assert [h[0] for h in hidden] == ['line.by_points', 'line.by_points',
                                          'segment.by_points', 'segment.by_points']
        for op_id, op in data['operations'].items():
            if is_helper(data, op_id):
                el = op['outputs'][0]['elementId']
                assert data['elements'][el]['displayName'] == ''
                assert data['appearance'][el] == {'visible': False}

    def test_hidden_pair_is_reused(self):
        result = parse(P3 + 'H = Проекция(C, AB)\nK = Проекция(C, AB)')
        data = result.document.data
        assert sum(is_helper(data, o) for o in data['operations']) == 1

    def test_visible_element_is_reused(self):
        result = parse(P3 + 's = Отрезок(A, B)\nM = Середина(A, B)\nОтметкаРавныхОтрезков(AM, MB)\n'
                            'ОтметкаРавныхОтрезков(AB, AB)')
        data = result.document.data
        mark = [op for op in data['operations'].values() if op['op'] == 'mark.equal_segments'][-1]
        s_id = by_name(result, 's')['id']
        assert [i['elementId'] for i in mark['args']['segments']['items']] == [s_id, s_id]

    def test_element_name_wins(self):
        result = parse(P3 + 'AB = (2, 2)\nM = Середина(AB, C)')
        [issue] = result.issues
        assert (issue.code, issue.line, issue.column, issue.severity) == ('ambiguous_name', 4, 1, 'warning')
        assert producer(result, 'M')['args']['a']['elementId'] == by_name(result, 'AB')['id']

    def test_ambiguous_name_in_parser_and_printer(self):
        text = (P3 + 'c = Окружность(A, C)\nd = Окружность(B, C)\nX, BC = Пересечение(c, d)\n'
                'A_1 = (5, 5)\nBA_{1} = Отрезок(A, C)\nK = (1, 1)')
        result = parse(text)
        got = [(i.code, i.line, i.column, i.severity) for i in result.issues]
        assert got == [('ambiguous_name', 6, 4, 'warning'), ('ambiguous_name', 8, 1, 'warning')]
        assert 'пара точек B, A_{1}' in result.issues[1].message
        printed = print_commands(result.document)
        assert [(i.code, i.line, i.column) for i in printed.issues] == [(c, l, k) for c, l, k, _ in got]
        # the points may come later: the whole document counts
        late = parse('BC = (1, 1)\nB = (0, 0)\nC = (2, 0)')
        assert [(i.code, i.line) for i in late.issues] == [('ambiguous_name', 1)]
        # a line with an error is not flagged; nor a name of no two points
        assert [i.code for i in parse(P3 + 'AB = Середина(A, X)').issues] == ['unknown_name']
        assert parse(P3 + 'AD = (1, 1)').issues == []

    def test_split_with_indices(self):
        result = parse('A_1 = (0, 0)\nB = (3, 0)\nC = (0, 2)\nH = Проекция(C, A_1B)')
        assert result.issues == []

    def test_ambiguous(self):
        result = parse('A = (0, 0)\nAB = (1, 1)\nB = (2, 0)\nBC = (3, 3)\nC = (4, 4)\nH = Проекция(C, ABC)')
        assert [(i.code, i.line) for i in result.issues if i.severity == 'warning'] == [
            ('ambiguous_name', 2), ('ambiguous_name', 4)]
        [issue] = [i for i in result.issues if i.severity == 'error']
        assert (issue.code, issue.column) == ('ambiguous_pair', 17)
        assert issue.hint == 'A, BC или AB, C'

    def test_angle_symbol(self):
        result = parse(P3 + 'β = ∠ABC\nОтметкаРавныхУглов(∠BAC, ∠ACB)')
        assert producer(result, 'β')['op'] == 'angle.by_points'
        data = result.document.data
        assert sum(is_helper(data, o) and data['operations'][o]['op'] == 'angle.by_points'
                   for o in data['operations']) == 2

    def test_unused_hidden_pairs_do_not_stay(self):
        result = parse(P3 + 'M = Середина(A, B)\nОтметкаРавныхОтрезков(AM, MB, X)')
        assert errors(result) == [('unknown_name', 5, 31)]
        data = result.document.data
        assert not any(is_helper(data, o) for o in data['operations'])
        assert 'appearance' not in data


class TestOverloads:
    def test_line_circle_either_order(self):
        result = parse(P3 + 'c = Окружность(A, C)\nl = Прямая(A, B)\nP, Q = Пересечение(c, l)')
        op = producer(result, 'P')
        assert op['op'] == 'intersect.line_circle'
        assert op['args']['line']['elementId'] == by_name(result, 'l')['id']

    def test_known_point(self):
        result = parse(P3 + 'c = Окружность(A, C)\nd = Окружность(B, C)\nX = Пересечение(c, d, не C)')
        op = producer(result, 'X')
        assert op['op'] == 'intersect.other_than'
        assert op['args']['known']['elementId'] == by_name(result, 'C')['id']

    def test_known_point_must_be_a_point(self):
        result = parse(P3 + 'c = Окружность(A, C)\nd = Окружность(B, C)\nX = Пересечение(c, d, не d)')
        assert errors(result) == [('type_mismatch', 6, 26)]

    def test_aliases_and_ids(self):
        result = parse(P3 + 'M = Midpoint(A, B)\nl = line.by_points(A, C)\np = Прямая(B, l)')
        assert result.issues == []
        assert [producer(result, n)['op'] for n in 'Mlp'] == ['point.midpoint', 'line.by_points', 'line.parallel']


# ── default names ────────────────────────────────────────────────────────


class TestNaming:
    @pytest.mark.parametrize('element_type, taken, expected', [
        ('point', [], 'A'),
        ('point', list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'A_1'),
        ('point', list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['A_{1}'], 'B_1'),
        ('line', ['a', 'b', 'c', 'd'], 'f'),
        ('vector', [], 'a'),
        ('number', ['a'], 'b'),
        ('circle', [], 'c'),
        ('circle', list('cdfghjklmnopqrstuvw'), 'a'),
        ('polygon', ['t'], 't_1'),
        ('angle', ['α'], 'β'),
        ('angle', list('αβγδεζηθκλμνξπρστφχψω'), 'α_1'),
        ('mark', [], ''),
    ])
    def test_next_name(self, element_type, taken, expected):
        assert next_name(element_type, taken) == expected

    @pytest.mark.parametrize('vertices, taken, expected', [
        (['A', 'B', 'C'], [], ['c', 'a', 'b']),
        (['A', 'B', 'C'], ['a'], ['c', 'd', 'b']),
        (['E', 'F', 'G'], [], ['g', 'a', 'f']),
        (['A_1', 'B', 'C'], [], ['a', 'b', 'c']),
        (['A', 'B', 'C', 'D'], ['b'], ['a', 'c', 'd', 'f']),
    ])
    def test_polygon_sides(self, vertices, taken, expected):
        assert polygon_side_names(vertices, taken) == expected


class TestNumbers:
    @pytest.mark.parametrize('value, text', [
        (0.0, '0'), (-0.0, '0'), (3.0, '3'), (300, '300'), (0.1, '0.1'), (1e-6, '0.000001'),
        (9.99e-7, '9.99e-7'), (1.5e-7, '1.5e-7'), (1e15, '1e+15'), (123456789012345.6, '123456789012345.6'),
        (2e21, '2e+21'), (-2.5, '-2.5'), (0.30000000000000004, '0.30000000000000004'),
    ])
    def test_format(self, value, text):
        assert format_number(value) == text
        assert float(text) == value

    def test_not_finite(self):
        with pytest.raises(ValueError):
            format_number(math.inf)


# ── printing and the round trip ──────────────────────────────────────────


class TestPrint:
    def test_text_and_lines(self):
        result = parse(P3 + 't = Многоугольник(A, B, C)\nH = Проекция(C, AB)\nОтметкаРавныхОтрезков(a, b, 2)')
        printed = print_commands(result.document)
        assert printed.text == ('A = (0, 0)\nB = (4, 0)\nC = (1, 3)\nt, c, a, b = Многоугольник(A, B, C)\n'
                                'H = Проекция(C, AB)\nОтметкаРавныхОтрезков(a, b, 2)')
        assert printed.issues == []
        assert printed.lines[4]['elementIds'] == [by_name(result, 'H')['id']]
        assert len(printed.lines[4]['operationIds']) == 2          # the projection and its hidden line

    @pytest.mark.parametrize('path', SCENES, ids=lambda p: p.stem)
    def test_round_trip_on_parity_scenes(self, path):
        doc = read_json(path)['document']
        if doc.get('conditions'):
            pytest.skip('conditions are printed in «Команды» from 1.9.0a3 (plan L3 §4)')
        printed = print_commands(doc)
        result = parse_commands(printed.text, document_id='doc')
        # the only issues are ambiguous_name, at the same places as the printer's
        ambiguous = [(i.code, i.line, i.column) for i in printed.issues if i.code == 'ambiguous_name']
        problems = structure_problems(doc, result.document.data)
        if path.stem == 'l2a5_number_expression':
            # the grammar has no expressions yet: a formula line reads back as forbidden
            formulas = [i for i in printed.issues if i.code == 'unprintable_operation']
            assert len(formulas) == 8 and [i.code for i in printed.issues] == ['unprintable_operation'] * 8
            assert [(i.code, i.line) for i in result.issues] == [('forbidden', i.line) for i in formulas]
            assert len(problems) == 8 and all(p.startswith('missing number.expression') for p in problems)
            return
        if path.stem == 'l2a5_text':
            # the grammar has no strings yet: a text line reads back as a syntax error at «"»
            texts = [i for i in printed.issues if i.code == 'unprintable_operation']
            assert len(texts) == 5 and [i.code for i in printed.issues] == ['unprintable_operation'] * 5
            assert [(i.code, i.line) for i in result.issues] == [('syntax', i.line) for i in texts]
            assert len(problems) == 5 and all(p.startswith('missing text.free') for p in problems)
            return
        assert [(i.code, i.line, i.column) for i in result.issues] == ambiguous
        others = [i.code for i in printed.issues if i.code != 'ambiguous_name']
        if path.stem in ('intersect_lines', 'intersect_segments'):
            # lines AB and CD of points A, B, C, D
            assert [(c, l) for c, l, _ in ambiguous] == [('ambiguous_name', 3), ('ambiguous_name', 6)]
        else:
            assert ambiguous == []
        if path.stem == 'number_free':
            # n4 has step but no min/max: positional arguments cannot say it
            assert others == ['unprintable_params']
            assert sorted(problems) == sorted(["missing number.free {\"step\":0} {'number': 'n4'}",
                                               "extra ('number.free', '{}', {'number': 'n4'}, False)"])
        else:
            assert others == []
            assert problems == []

    @pytest.mark.parametrize('path', SCENES, ids=lambda p: p.stem)
    def test_printed_text_edits_nothing(self, path):
        doc = read_json(path)['document']
        if path.stem == 'recipe_angle_equal':
            pytest.skip('the number.expression of angle.equal is printed from 1.9.0a3 (plan L3 §4)')
        result = parse_commands(print_commands(doc).text, base=doc)
        if path.stem == 'l2a5_number_expression':     # formula lines fail and keep their operations
            assert {i.code for i in result.issues} == {'forbidden'}
        elif path.stem == 'l2a5_text':
            assert {i.code for i in result.issues} == {'syntax'}
        else:
            assert {i.code for i in result.issues} <= {'ambiguous_name'}
        assert changed(result.effects) == {}
        assert native.canonical_json(result.document.data) == native.canonical_json(doc)

    def test_round_trip_on_fixture_documents(self):
        for _fixture_id, cases in CATALOG:
            for name, text, _base in cases:
                first = parse(render_template(text, Lexicon()))
                second = parse_commands(print_commands(first.document).text, document_id='doc')
                assert [i.code for i in second.issues if i.severity == 'error'] == [], name
                assert structure_problems(first.document.data, second.document.data) == [], name

    def test_unprintable_pair(self):
        result = parse(P3 + 'D = (5, 4)\nОтметкаРавныхОтрезков(AB, CD)')
        data = copy.deepcopy(result.document.data)
        data['operations']['o0'] = {'id': 'o0', 'op': 'point.free', 'args': {},
                                    'outputs': [{'slot': 'point', 'elementId': 'e0'}]}
        data['elements']['e0'] = {'id': 'e0', 'type': 'point', 'displayName': 'AB',
                                  'producer': {'operationId': 'o0', 'slot': 'point'}}
        data['inputs']['e0'] = {'kind': 'point', 'value': [5, 5]}
        printed = print_commands(data)
        assert printed.text.splitlines()[0] == 'AB = (5, 5)'
        assert [i.code for i in printed.issues] == ['ambiguous_name', 'unprintable_pair']
        issue = printed.issues[1]
        assert (issue.code, issue.severity) == ('unprintable_pair', 'warning')
        assert printed.text.splitlines()[issue.line - 1][issue.column - 1:].startswith('AB')

    def test_registry_fallback_name(self):
        data = {'format': 'animageo-lexicon/v1', 'commands': [{'name': 'Середина', 'op': 'point.midpoint'}]}
        result = parse(P3 + 'M = Середина(A, B)\nl = line.by_points(A, B)\nP = point.on_path(l, 0.3)',
                       lexicon=data)
        assert result.issues == []
        assert print_commands(result.document, lexicon=data).text.splitlines()[3:] == [
            'M = Середина(A, B)', 'l = line.by_points(A, B)', 'P = point.on_path(l, 0.3)']

    def test_broken_operations_are_printed_with_a_warning(self):
        doc = read_json(SCENES_DIR / 'graph_errors.json')['document']
        printed = print_commands(doc)
        assert {i.code for i in printed.issues} == {'unprintable_operation'}
        assert 'mBad = point.midpoint(A)' in printed.text.splitlines()


# ── edit mode ────────────────────────────────────────────────────────────

BASE = P3 + 't = Многоугольник(A, B, C)\nM = Середина(A, B)\ns = Отрезок(C, M)\nОтметкаРавныхОтрезков(AM, MB)'


@pytest.fixture
def base():
    return parse(BASE).document


class TestEdit:
    def edit(self, base, text):
        return parse_commands(text, base=base, id_factory=counter_ids())

    def test_unchanged(self, base):
        result = self.edit(base, BASE)
        assert changed(result.effects) == {} and result.issues == []

    def test_move_point(self, base):
        result = self.edit(base, BASE.replace('C = (1, 3)', 'C = (1, 4)'))
        assert changed(result.effects) == {'modified': {'inputs': ['e3']}}
        assert result.document.inputs['e3']['value'] == [1.0, 4.0]

    def test_redefine_keeps_ids(self, base):
        result = self.edit(base, BASE.replace('M = Середина(A, B)', 'M = Проекция(C, AB)'))
        m = by_name(result, 'M')
        assert m['id'] == 'e8' and m['producer'] == {'operationId': 'o5', 'slot': 'foot'}
        assert result.document.operations['o5']['op'] == 'point.projection'
        assert changed(result.effects)['modified'] == {'operations': ['o5'], 'elements': ['e8']}

    def test_redefine_refused(self, base):
        result = self.edit(base, BASE.replace('M = Середина(A, B)', 'M = Окружность(A, B)'))
        assert errors(result) == [('type_mismatch', 5, 5)]
        assert changed(result.effects) == {}

    def test_delete_line(self, base):
        result = self.edit(base, BASE.replace('s = Отрезок(C, M)\n', ''))
        assert changed(result.effects) == {'removed': {'operations': ['o6'], 'elements': ['e9']}}

    def test_delete_line_with_dependents(self, base):
        text = BASE.replace('M = Середина(A, B)\n', '')
        result = self.edit(base, text)
        assert [i.code for i in result.issues] == ['unknown_name', 'unknown_name']
        assert changed(result.effects)['removed']['operations'] == ['o5', 'o6', 'o7', 'o8', 'o9']

    def test_new_line(self, base):
        result = self.edit(base, BASE + '\nN = Середина(B, C)')
        assert changed(result.effects) == {'added': {'operations': ['o10'], 'elements': ['e13']}}

    def test_new_name_is_a_new_operation(self, base):
        result = self.edit(base, BASE.replace('s = Отрезок', 'u = Отрезок'))
        assert changed(result.effects) == {'added': {'operations': ['o10'], 'elements': ['e13']},
                                           'removed': {'operations': ['o6'], 'elements': ['e9']}}

    def test_mark_count_keeps_its_id(self, base):
        result = self.edit(base, BASE.replace('(AM, MB)', '(AM, MB, 2)'))
        assert changed(result.effects) == {'modified': {'operations': ['o9']}}

    def test_secondary_names_rename(self, base):
        result = self.edit(base, BASE.replace('t = Многоугольник', 't, z = Многоугольник'))
        assert changed(result.effects) == {'modified': {'elements': ['e5']}}
        assert by_name(result, 'z')['id'] == 'e5'

    def test_error_keeps_the_operation(self, base):
        result = self.edit(base, BASE.replace('M = Середина(A, B)', 'M = Середина(A, B'))
        assert errors(result) == [('syntax', 5, 13)]
        assert changed(result.effects) == {}
        assert [entry['line'] for entry in result.lines] == [1, 2, 3, 4, 5, 6, 7]

    def test_free_name_goes_to_a_new_element(self, base):
        text = P3.replace('C = (1, 3)\n', '') + 'c = Окружность(A, B)\nD, C = Пересечение(AB, c)'
        old = parse(P3 + 'c = Окружность(A, B)').document
        result = self.edit(old, text)
        assert result.issues == []
        assert by_name(result, 'C')['id'] != 'e3'
        assert 'e3' in changed(result.effects)['removed']['elements']

    def test_lossy_line_typed_back_keeps_the_operation(self):
        doc = read_json(SCENES_DIR / 'number_free.json')['document']
        text = print_commands(doc).text.replace('O = (0, 0)', 'O = (1, 0)')
        result = parse_commands(text, base=doc)
        assert changed(result.effects) == {'modified': {'inputs': ['O']}}
        assert result.document.operations['op_n4']['args'] == {'step': {'kind': 'number', 'value': 0}}


# ── fixtures and the command line ────────────────────────────────────────


class TestScaling:
    """Parsing, printing and editing grow about linearly with the text: the
    work per line does not scan the whole document (counted in name keys, so
    the test does not depend on the machine)."""

    @staticmethod
    def text(n):
        lines = []
        for k in range(1, n + 1):
            lines += [f'P_{{{k}}} = ({k}, {k % 7})', f'Q_{{{k}}} = ({k + 0.5}, {k * 3 % 5})',
                      f'M_{{{k}}} = Середина(P_{{{k}}}, Q_{{{k}}})', f'c_{{{k}}} = Окружность(M_{{{k}}}, P_{{{k}}})',
                      f'l_{{{k}}} = Перпендикуляр(M_{{{k}}}, P_{{{k}}}Q_{{{k}}})',
                      f'X_{{{k}}}, Y_{{{k}}} = Пересечение(l_{{{k}}}, c_{{{k}}})',
                      f'ОтметкаРавныхОтрезков(P_{{{k}}}M_{{{k}}}, M_{{{k}}}Q_{{{k}}})']
        return '\n'.join(lines)

    def test_linear(self, monkeypatch):
        from animageo.native import edit
        from animageo.native.commands import build, naming, printer

        count = [0]
        original = edit.name_key

        def counting(name):
            count[0] += 1
            return original(name)

        for module in (build, naming, printer):
            monkeypatch.setattr(module, 'name_key', counting)

        def work(n):
            out = []
            count[0] = 0
            doc = parse_commands(self.text(n)).document
            out.append(count[0])
            count[0] = 0
            text = print_commands(doc).text
            out.append(count[0])
            count[0] = 0
            result = parse_commands(text.replace('P_{2} = (2, 2)', 'P_{2} = (3, 2)'), base=doc)
            out.append(count[0])
            assert not result.issues and result.effects['modified']['inputs']
            return out

        small, large = work(8), work(80)
        assert all(b < 15 * a for a, b in zip(small, large)), (small, large)


class TestFixtures:
    def test_shipped_fixtures_are_up_to_date(self):
        assert check_fixtures(DEFAULT_DIR) == []

    def test_coverage(self):
        fixtures = build_fixtures()
        cases = [c for name, f in fixtures.items() if name != 'naming.json' for c in f['cases']]
        assert len(cases) >= 100
        per_op = {}
        for case in cases:
            if case['base'] is None and not case['expect']['issues']:
                for op in {o['op'] for o in case['expect']['operations'] if not o['hidden']}:
                    per_op[op] = per_op.get(op, 0) + 1
        assert {op for op, n in per_op.items() if n >= 3} == LEXICON_OPS
        issues = [i for c in cases for i in c['expect']['issues']]
        assert len([i for i in issues if i['severity'] == 'error']) >= 20
        assert set(ERROR_CODES) <= {i['code'] for i in issues}
        warnings = {i['code'] for i in issues if i['severity'] == 'warning'}
        printed = {i['code'] for c in cases for i in c['expect'].get('printIssues', ())}
        assert {'comment_dropped', 'ambiguous_name'} <= warnings and 'ambiguous_name' in printed
        assert len([c for c in cases if c['base'] is not None]) >= 10

    def test_cases_replay(self):
        for name, fixture in build_fixtures().items():
            if name == 'naming.json':
                continue
            assert fixture['format'] == 'animageo-commands/v1'
            assert fixture['lexiconHash'] == Lexicon().hash
            for case in fixture['cases']:
                result = parse_commands(case['text'], base=case['base'], id_factory=counter_ids(),
                                        document_id='doc')
                got = [{'code': i.code, 'line': i.line, 'column': i.column, 'severity': i.severity}
                       for i in result.issues]
                assert got == case['expect']['issues'], case['name']
                assert print_commands(result.document).text == case['expect']['print'], case['name']

    def test_naming_table(self):
        table = build_fixtures()['naming.json']
        assert table['format'] == 'animageo-naming/v1'
        for case in table['cases']:
            assert next_name(case['type'], case['taken']) == case['expect']
        for case in table['sides']:
            assert polygon_side_names(case['vertices'], case['taken']) == case['expect']
        keys = {case['name']: case['key'] for case in table['keys']}
        assert keys['A_{1}'] == keys['A_1'] == 'A_1' and keys['A₁'] == 'A₁' and keys['A1'] == 'A1'
        assert all(valid_name(name) for name in keys)

    def test_other_lexicon(self, tmp_path):
        data = default_lexicon()
        for entry in data['commands']:
            entry['name'], entry['aliases'] = entry['aliases'][0] if entry['aliases'] else entry['name'], []
        names = {}
        for entry in data['commands']:
            names.setdefault(entry['name'], []).append(entry)
        data['commands'] = [e for e in data['commands'] if e['op'] != 'line.parallel']
        assert lexicon_problems(data) == []
        fixtures = build_fixtures(data)
        midpoint = next(c for c in fixtures['parse_points.json']['cases'] if c['name'] == 'midpoint')
        assert 'Midpoint(A, B)' in midpoint['text'] and midpoint['expect']['print'].endswith('Midpoint(A, B)')
        parallel = next(c for c in fixtures['parse_lines.json']['cases'] if c['name'] == 'parallel')
        assert 'line.parallel(C, l)' in parallel['text']
        assert parallel['expect']['issues'] == []

    def test_deterministic(self):
        text = render_template(CATALOG[0][1][3][1], Lexicon())
        first = parse(text).document.data
        second = parse(text).document.data
        assert native.canonical_json(first) == native.canonical_json(second)


class TestCli:
    def run(self, capsys, *argv):
        code = main(list(argv))
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    def test_fixtures_check(self, capsys):
        code, out, _ = self.run(capsys, 'commands', 'fixtures', '--check')
        assert code == 0 and 'up to date' in out

    def test_fixtures_write_and_check(self, capsys, tmp_path):
        lexicon = tmp_path / 'lexicon.json'
        lexicon.write_text(json.dumps(default_lexicon(), ensure_ascii=False), encoding='utf-8')
        out_dir = tmp_path / 'fixtures'
        code, out, _ = self.run(capsys, 'commands', 'fixtures', '--lexicon', str(lexicon), '-o', str(out_dir))
        assert code == 0 and 'naming.json' in out
        code, _, _ = self.run(capsys, 'commands', 'fixtures', '--lexicon', str(lexicon), '-o', str(out_dir),
                              '--check')
        assert code == 0
        (out_dir / 'edit.json').write_text('{}', encoding='utf-8')
        code, out, _ = self.run(capsys, 'commands', 'fixtures', '--lexicon', str(lexicon), '-o', str(out_dir),
                                '--check')
        assert code == 1 and 'out of date' in out

    def test_bad_lexicon(self, capsys, tmp_path):
        lexicon = tmp_path / 'lexicon.json'
        lexicon.write_text('{"format": "animageo-lexicon/v1", "commands": [{"name": "X", "op": "no.op"}]}',
                           encoding='utf-8')
        code, _, err = self.run(capsys, 'commands', 'fixtures', '--lexicon', str(lexicon), '-o', str(tmp_path))
        assert code == 2 and 'no.op' in err

    def test_parse_and_print(self, capsys, tmp_path):
        text = tmp_path / 'a.txt'
        text.write_text(P3 + 'M = Середина(A, B)\n', encoding='utf-8')
        code, out, _ = self.run(capsys, 'commands', 'parse', str(text), '--document-id', 'x')
        assert code == 0
        payload = json.loads(out)
        assert set(payload) == {'document', 'effects', 'lines', 'issues'}
        doc = tmp_path / 'doc.json'
        doc.write_text(json.dumps(payload['document']), encoding='utf-8')
        code, out, _ = self.run(capsys, 'commands', 'print', str(doc))
        assert code == 0 and out == P3 + 'M = Середина(A, B)\n'
        edited = tmp_path / 'b.txt'
        edited.write_text(P3 + 'M = Середина(A, Q)\n', encoding='utf-8')
        code, out, err = self.run(capsys, 'commands', 'parse', str(edited), '--base', str(doc))
        assert code == 1 and 'unknown_name 4:17' in err
