"""«Команды» of L3 stage 3 (plan L3 §4): conditions, checks, check commands,
queries, steps from comments, the print order by steps and ``seq``, edit mode
with conditions; both properties of §4.3 on every scene and fixture."""
from __future__ import annotations

import copy

import pytest

from animageo import native
from animageo.native.commands import (
    ERROR_CODES,
    Lexicon,
    LexiconError,
    apply_condition_requests,
    default_lexicon,
    lexicon_problems,
    parse_commands,
    print_commands,
    printable_document,
)
from animageo.native.commands.fixtures import CATALOG, build_fixtures, counter_ids, render_template
from animageo.native.commands.fixtures_l3 import CATALOG_L3, R, build_case
from animageo.native.registry import registry
from tests.native.conftest import SCENES_DIR, read_json
from tests.native.test_native_commands import describe as describe_ops

SCENES = sorted(p for p in SCENES_DIR.glob('*.json') if p.stem != 'graph_errors')
# formulas and texts cannot be typed yet; number_free has a step without min/max
LOSSY = {'l2a5_number_expression', 'l2a5_text', 'number_free'}


def parse(text, base=None, **kw):
    return parse_commands(text, base=base, id_factory=counter_ids(), document_id='doc', **kw)


def names(doc):
    return {el['displayName']: el_id for el_id, el in as_doc(doc).elements.items() if el.get('displayName')}


def as_doc(doc):
    return native.as_document(doc) if not hasattr(doc, 'elements') else doc


def structure_problems(original, parsed, skip_inputs=()):
    """Like the L2 helper, matching rows with more named outputs first;
    ``skip_inputs`` — names whose inputs are not compared (receivers: their
    parameter is the projection of ``receiverOrigin``, plan L3 §4.3)."""
    a, a_inputs = describe_ops(original)
    b, b_inputs = describe_ops(parsed)
    a = sorted(a, key=lambda row: -len(row[2]))
    pool = list(b)
    problems = []
    for op, args, outs, hidden in a:
        hit = next((j for j, (op2, args2, outs2, hidden2) in enumerate(pool)
                    if (op2, args2, hidden2) == (op, args, hidden) and all(outs2.get(k) == v for k, v in outs.items())),
                   None)
        if hit is None:
            problems.append(f'missing {op} {args} {outs}')
        else:
            pool.pop(hit)
    problems += [f'extra {row}' for row in pool]
    for name, value in a_inputs.items():
        if name in skip_inputs:
            continue
        other = b_inputs.get(name)
        want = value['value'] if isinstance(value['value'], list) else [value['value']]
        got = None if other is None else (other['value'] if isinstance(other['value'], list) else [other['value']])
        if other is None or other['kind'] != value['kind'] or [float(x) for x in want] != [float(x) for x in got]:
            problems.append(f'input {name}: {value} vs {other}')
    return problems


def condition_shape(doc):
    """Conditions by display names (no IDs, sources or seq)."""
    doc = as_doc(doc)
    label = {el_id: el.get('displayName') or '' for el_id, el in doc.elements.items()}

    def relabel(value):
        if isinstance(value, dict):
            return {k: relabel(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relabel(v) for v in value]
        return label.get(value, value) if isinstance(value, str) else value

    out = []
    for cond in doc.data.get('conditions') or ():
        out.append((cond['mode'], native.canonical_json(relabel(cond['statement'])), label.get(cond.get('receiver')),
                    cond.get('recipe')))
    return sorted(out)


def check_properties(doc, name=''):
    """§4.3: parse(print(doc), base=doc) ≡ doc byte for byte; parse(print(doc))
    plus its requests ≡ doc by structure and conditions."""
    printed = print_commands(doc)
    edited = parse_commands(printed.text, base=doc)
    assert edited.conditionRequests == [], name
    assert native.canonical_json(edited.document.data) == native.canonical_json(as_doc(doc).data), name
    fresh = parse_commands(printed.text, document_id='doc')
    applied = apply_condition_requests(fresh.document, fresh.conditionRequests)
    assert [r for r in applied.results if r['refusal']] == [], name
    doc = as_doc(doc)
    receivers = {doc.elements[c['receiver']].get('displayName') for c in doc.data.get('conditions') or ()
                 if c.get('mode') == 'construct' and c.get('receiver') in doc.elements}
    assert structure_problems(doc.data, applied.document.data, receivers) == [], name
    assert condition_shape(applied.document) == condition_shape(doc), name


# ── the properties ───────────────────────────────────────────────────────


@pytest.mark.parametrize('path', SCENES, ids=lambda p: p.stem)
def test_properties_on_scenes(path):
    doc = read_json(path)['document']
    if path.stem in LOSSY:
        edited = parse_commands(print_commands(doc).text, base=doc)
        assert native.canonical_json(edited.document.data) == native.canonical_json(doc)
        return
    check_properties(doc, path.stem)


def _fixture_documents():
    lex = Lexicon()
    for fixture_id, cases in CATALOG_L3:
        for name, spec in cases:
            case = build_case(name, spec, lex)
            result = parse_commands(case['text'], base=case['base'], id_factory=counter_ids(), document_id='doc')
            doc = apply_condition_requests(result.document, result.conditionRequests).document
            yield f'{fixture_id}/{name}', doc
    for fixture_id, cases in CATALOG:
        for name, text, _base in cases:
            yield f'{fixture_id}/{name}', parse(render_template(text, lex)).document


def test_properties_on_fixture_documents():
    count = 0
    for name, doc in _fixture_documents():
        printed = print_commands(doc)
        if any(i.code.startswith('unprintable') for i in printed.issues):
            continue
        check_properties(doc, name)
        count += 1
    assert count >= 380


# ── grammar ──────────────────────────────────────────────────────────────


class TestStatements:
    @pytest.mark.parametrize('text', [
        '|AB| = |AC|', '|AB| ≠ 3', '∠ABC = 90°', '∠ABC = ∠BCA', 'AB ∥ CD', 'AB ⟂ CD', 'C ∈ AB', 'D ∈ c',
        'CD касается c', '|AB|^2 = |AC|·|BC| + 2/3 - sqrt(4)', 'sin(∠BAC) = |BC|/|AB|', '∠ABC = π/2',
        '-|AB| + 3 = -2', '(|AB| + |BC|)·2 = 10', 'ПроверкаКоллинеарности(A, B, C)',
        'ПроверкаКонцикличности(A, B, C, D)', 'ПроверкаРавенства(AB, CD)', 'A = B',
    ])
    def test_check_round_trip(self, text):
        base = 'A = (0, 0)\nB = (4, 0)\nC = (1, 3)\nD = (5, 4)\nc = Окружность(A, B)\n'
        result = parse(base + f'Проверить({text})')
        assert result.issues == []
        [cond] = result.document.data['conditions']
        assert cond['mode'] == 'check' and cond['id'] == 'c1' and cond['seq'] == 1
        assert f'Проверить({text})' in print_commands(result.document).text.split('\n')

    def test_typed_replacements(self):
        result = parse(R + 'Check(<)ADB = 90 deg)\nПроверить(AB || CD)\nПроверить(AB _|_ CD)\nПроверить(C in AB)')
        assert result.issues == []
        assert print_commands(result.document).text.split('\n')[-4:] == [
            'Проверить(∠ADB = 90°)', 'Проверить(AB ∥ CD)', 'Проверить(AB ⟂ CD)', 'Проверить(C ∈ AB)']

    def test_check_commands_print_canonically(self):
        result = parse(R + 'AreParallel(AB, CD)\nПроверкаПринадлежности(C, AB)\nIsTangent(AB, CD)')
        assert result.issues == []
        assert print_commands(result.document).text.split('\n')[-3:] == [
            'Проверить(AB ∥ CD)', 'Проверить(C ∈ AB)', 'Проверить(AB касается CD)']

    def test_element_name_wins_over_pair(self):
        result = parse('A = (0, 0)\nB = (1, 0)\nAB = (2, 2)\nC = (0, 1)\nПроверить(C ∈ AB)')
        [cond] = result.document.data['conditions']
        assert cond['statement']['object'] == {'ref': names(result.document)['AB']}

    def test_relation_is_a_query(self):
        result = parse(R + 'h = Отрезок(C, D)\nОтношение(h, AB)')
        n = names(result.document)
        assert result.queries == [{'line': 6, 'kind': 'relation', 'a': n['h'], 'b': {'pair': [n['A'], n['B']]}}]
        assert 'conditions' not in result.document.data

    @pytest.mark.parametrize('line, code', [
        ('Условие(|AX| = 2)', 'unknown_name'),
        ('Условие(AB)', 'syntax'),
        ('Условие(AB ∥ CD ∥ AC)', 'syntax'),
        ('Условие(|AC| = 2, тянуть C)', 'syntax'),
        ('Условие(|AC| = 2, двигать C, D)', 'syntax'),
        ('Условие()', 'syntax'),
        ('Условие(ПроверкаКоллинеарности(A, B, C, D))', 'unsupported_condition'),
        ('Условие(|AB| = 3, двигать C)', 'unsupported_condition'),
        ('ПроверкаПараллельности(AB)', 'arity'),
        ('ПроверкаКоллинеарности(A, B)', 'arity'),
        ('Отношение(AB)', 'arity'),
        ('t = Проверить(A ∈ AB)', 'syntax'),
        ('AB ∥ CD', 'forbidden'),
    ])
    def test_errors(self, line, code):
        result = parse(R + line)
        assert [i.code for i in result.issues] == [code]
        assert result.conditionRequests == [] and 'conditions' not in result.document.data

    def test_without_lexicon_words_the_old_refusal_stays(self):
        from animageo.native.commands.lexer import tokenize
        from animageo.native.commands.syntax import parse_line
        from animageo.native.commands.issues import LineError
        with pytest.raises(LineError) as info:
            parse_line(tokenize('Условие(A ∈ b)')[0], 1)
        assert info.value.code == 'forbidden'


class TestLexiconL3:
    def test_keywords_and_checks(self):
        lex = Lexicon()
        assert lex.keyword('УСЛОВИЕ') == 'condition' and lex.keyword('move') == 'move'
        assert lex.word('touches') == 'касается'
        assert lex.check_kind('arecollinear') == 'collinear'
        assert lex.check_name('parallel') == 'ПроверкаПараллельности'
        assert 'AreParallel' in lex.names()

    def test_other_keywords(self):
        data = default_lexicon()
        data['keywords'] = {'condition': ['Условие'], 'check': ['Проверь'], 'move': ['тянуть'],
                            'touches': ['касается']}
        lex = Lexicon(data)
        result = parse_commands(R + 'Проверь(AB ∥ CD)\nУсловие(|AC| = 2, тянуть C)', lexicon=lex)
        assert result.issues == [] and len(result.conditionRequests) == 1
        assert print_commands(result.document, lexicon=lex).text.endswith('Проверь(AB ∥ CD)')

    @pytest.mark.parametrize('mutate, needle', [
        (lambda d: d['commands'].append({'name': 'Х', 'check': 'nothing'}), 'check must be one of'),
        (lambda d: d['commands'].append({'name': 'Х', 'check': 'parallel', 'op': 'point.free'}), 'unknown keys'),
        (lambda d: d['commands'].append({'name': 'Середина', 'check': 'parallel'}), 'also a command name'),
        (lambda d: d['commands'].append({'name': 'ПроверкаПараллельности', 'check': 'collinear'}),
         'two statement kinds'),
        (lambda d: d.update(keywords={'unknown': ['x']}), 'unknown key'),
        (lambda d: d.update(keywords={'move': []}), 'non-empty list'),
        (lambda d: d.update(keywords={'move': ['Середина']}), 'also a command name'),
    ])
    def test_problems(self, mutate, needle):
        data = default_lexicon()
        mutate(data)
        problems = lexicon_problems(data)
        assert any(needle in p for p in problems), problems
        with pytest.raises(LexiconError):
            Lexicon(data)


# ── conditions ───────────────────────────────────────────────────────────


class TestConditions:
    def test_request_and_application(self):
        result = parse(R + 'Условие(∠ADB = 90°)')
        n = names(result.document)
        assert result.issues == [] and 'conditions' not in result.document.data
        [req] = result.conditionRequests
        assert req == {'line': 5, 'kind': 'apply', 'receiver': n['D'],
                       'statement': {'kind': 'eq', 'left': {'angle': [{'ref': n['A']}, {'ref': n['D']}, {'ref': n['B']}]},
                                     'right': {'deg': 90.0}}}
        applied = apply_condition_requests(result.document, result.conditionRequests)
        [cond] = applied.document.data['conditions']
        assert (cond['recipe'], cond['receiver'], cond['source']) == ('right_angle.vertex', n['D'], 'command')
        assert print_commands(applied.document).text == R + 'Условие(∠ADB = 90°)'
        assert print_commands(result.document).text == R.rstrip('\n')     # requests are not in the document

    def test_move_is_printed_only_for_another_receiver(self):
        result = parse(R + 'Условие(|AC| = |BC|, двигать C)\nУсловие(∠BAD = 90°, двигать D)')
        applied = apply_condition_requests(result.document, result.conditionRequests).document
        text = print_commands(applied).text
        assert 'Условие(|AC| = |BC|)' in text and 'Условие(∠BAD = 90°)' in text
        result = parse(R + 'Условие(∠BDA = 90°, двигать B)')
        assert [i.code for i in result.issues] == []
        applied = apply_condition_requests(result.document, result.conditionRequests).document
        assert print_commands(applied).text.endswith('двигать B)')

    def test_receiver_line_prints_the_origin(self):
        result = parse(R + 'Условие(|AC| = 5)\nM = Середина(A, C)')
        applied = apply_condition_requests(result.document, result.conditionRequests).document
        assert print_commands(applied).text == R + 'Условие(|AC| = 5)\nM = Середина(A, C)'
        assert native.evaluate(applied).elements[names(applied)['C']]['value'] != {'x': 0.5, 'y': 2}

    def test_auto_marks_and_places_are_not_printed(self):
        doc = read_json(SCENES_DIR / 'shape_square.json')['document']
        data = printable_document(doc)
        assert 'conditions' not in data or all(c['mode'] == 'check' for c in data['conditions'])
        assert all(not (el.get('origin') or {}).get('kind') == 'auto' for el in data['elements'].values())
        assert print_commands(doc).text.count('Условие(') == 4

    def test_edit_kinds(self):
        base = apply_condition_requests(*_parsed(R + 'Условие(∠ADB = 90°)\nM = Середина(A, B)')).document
        text = print_commands(base).text
        same = parse(text, base=base)
        assert same.conditionRequests == [] and same.lines[-2].get('conditionId') == 'c1'
        replaced = parse(text.replace('90°', '60°').replace('∠ADB', '∠ADB'), base=base)
        assert [r['kind'] for r in replaced.conditionRequests] == ['release', 'apply']
        replaced = parse(text.replace('∠ADB = 90°', '|AD| = 3'), base=base)
        assert [(r['kind'], r.get('conditionId')) for r in replaced.conditionRequests] == [('replace', 'c1')]
        released = parse(text.replace('Условие(∠ADB = 90°)\n', ''), base=base)
        assert released.conditionRequests == [{'line': None, 'kind': 'release', 'conditionId': 'c1'}]
        moved = parse(text.replace('D = (1, -0.5)', 'D = (2, -1)'), base=base)
        n = names(base)
        assert moved.conditionRequests == [{'line': 4, 'kind': 'move', 'conditionId': 'c1', 'receiver': n['D'],
                                            'point': [2.0, -1.0]}]
        assert moved.document.data['conditions'][0]['receiverOrigin']['input'] == {'point': [2.0, -1.0]}
        assert moved.document.operations[n['D'] and base.elements[n['D']]['producer']['operationId']] == \
            base.operations[base.elements[n['D']]['producer']['operationId']]
        after = apply_condition_requests(moved.document, moved.conditionRequests).document
        assert native.evaluate(after).elements[n['D']]['state'] == 'defined'
        broken = parse(text.replace('∠ADB', '∠ADX'), base=base)
        assert [i.code for i in broken.issues] == ['unknown_name'] and broken.conditionRequests == []

    def test_too_many_conditions(self):
        result = parse(R + 'Условие(|AC| = 5)\nУсловие(|BC| = 4)\nУсловие(∠ACB = 90°)')
        assert [(i.code, i.line) for i in result.issues] == [('too_many_conditions', 7)]
        assert len(result.conditionRequests) == 2

    def test_receiver_leaves_its_explicit_step(self):
        result = parse('# Дано\n' + R + '\nУсловие(|CA| = |CB|)')
        applied = apply_condition_requests(result.document, result.conditionRequests)
        assert [r['refusal'] for r in applied.results] == [None]
        doc = applied.document
        [given] = doc.data['steps']
        assert names(doc)['C'] not in [doc.operations[o]['outputs'][0]['elementId'] for o in given['operationIds']]
        assert [s.kind for s in native.steps(doc)] == ['given', 'condition']


def _parsed(text):
    result = parse(text)
    return result.document, result.conditionRequests


# ── steps from comments ──────────────────────────────────────────────────


class TestCommentSteps:
    def test_groups_titles_and_texts(self):
        text = ('# Дано\nA = (0, 0)\nB = (4, 0)\nC = (1, 3)\n\n# Высота\nH = Проекция(C, AB)  # из C\n'
                'h = Отрезок(C, H)\nM = Середина(A, B)  # середина')
        result = parse(text)
        assert result.issues == []
        given, group = result.document.data['steps']
        assert (given['id'], given['kind'], len(given['operationIds'])) == ('s1', 'given', 3)
        assert (group['id'], group['kind'], group['title'], group['text']) == ('s2', 'group', 'Высота', 'из C; середина')
        assert len(group['operationIds']) == 4          # the hidden line AB goes with its line
        # a heading closes the group before it: no blank line is printed
        assert print_commands(result.document).text == text.replace('  # из C', '  # из C; середина').replace(
            '  # середина', '').replace('\n\n# Высота', '\n# Высота')

    def test_single_step_text(self):
        result = parse(P3 + 'M = Середина(A, B)  # середина AB\nN = Середина(B, C)')
        [step] = result.document.data['steps']
        assert (step['kind'], step['text'], len(step['operationIds'])) == ('group', 'середина AB', 1)
        assert print_commands(result.document).text == P3 + 'M = Середина(A, B)  # середина AB\nN = Середина(B, C)'

    def test_group_without_title_and_blank_line(self):
        text = P3 + '#\nM = Середина(A, B)\nN = Середина(B, C)\n\nK = Середина(C, A)'
        result = parse(text)
        [step] = result.document.data['steps']
        assert 'title' not in step and len(step['operationIds']) == 2
        assert print_commands(result.document).text == text

    def test_edit_keeps_steps_and_retitles(self):
        base = parse('# Дано\n' + P3 + '# Середины\nM = Середина(A, B)\nN = Середина(B, C)').document
        text = print_commands(base).text
        same = parse(text, base=base)
        assert native.canonical_json(same.document.data) == native.canonical_json(base.data)
        retitled = parse(text.replace('# Середины', '# Построение'), base=base)
        assert [s.get('title') for s in retitled.document.data['steps']] == [None, 'Построение']
        assert [s['id'] for s in retitled.document.data['steps']] == ['s1', 's2']

    def test_print_follows_steps_and_seq(self):
        doc = parse(P3 + 'M = Середина(A, B)\nN = Середина(B, C)\nK = Середина(C, A)').document
        n = names(doc)
        op = {k: doc.elements[v]['producer']['operationId'] for k, v in n.items()}
        ordered = native.assign_seq(doc, [op['K'], op['N'], op['M']])
        assert print_commands(ordered).text.split('\n')[3:] == ['K = Середина(C, A)', 'N = Середина(B, C)',
                                                                'M = Середина(A, B)']


P3 = 'A = (0, 0)\nB = (4, 0)\nC = (1, 3)\n'


# ── fixtures ─────────────────────────────────────────────────────────────


class TestFixturesL3:
    def test_counts(self):
        fixtures = build_fixtures()
        cases = {name: f['cases'] for name, f in fixtures.items() if name != 'naming.json'}
        total = sum(len(c) for c in cases.values())
        assert total >= 300
        new = sum(len(cases[f'{fid}.json']) for fid, _ in CATALOG_L3)
        assert new >= 200
        assert len(cases['comment_steps.json']) >= 12 and len(cases['print_order.json']) >= 10
        assert len(cases['edit_conditions.json']) >= 12
        recipes = {}
        for case in cases['conditions.json']:
            for r in case['expect'].get('afterRequests', {}).get('results', ()):
                if r['recipe']:
                    recipes[r['recipe']] = recipes.get(r['recipe'], 0) + 1
        assert len(recipes) == 13 and min(recipes.values()) >= 2
        issues = {i['code'] for c in cases['condition_errors.json'] for i in c['expect']['issues']}
        assert {'unsupported_condition', 'receiver_not_free', 'receiver_is_ancestor', 'too_many_conditions',
                'ambiguous_pair'} <= issues
        kinds = {}
        for case in cases['checks.json']:
            for cond in case['expect'].get('conditions', ()):
                kinds[cond['statement']['kind']] = kinds.get(cond['statement']['kind'], 0) + 1
        assert set(kinds) == {'eq', 'ne', 'parallel', 'perpendicular', 'tangent', 'on', 'collinear', 'concyclic',
                              'concurrent', 'congruent', 'coincident'}
        assert min(kinds.values()) >= 2
        everything = {i['code'] for c in sum(cases.values(), []) for i in c['expect']['issues']}
        assert set(ERROR_CODES) <= everything

    def test_l2a4_ops_have_two_clean_cases(self):
        cases = build_fixtures()['parse_l2a4.json']['cases']
        per_op = {}
        for case in cases:
            if not case['expect']['issues']:
                for op in {o['op'] for o in case['expect']['operations'] if not o['hidden']}:
                    per_op[op] = per_op.get(op, 0) + 1
        l2a4 = {op for op, r in registry().ops.items() if r['since'] == '1.4'} - {'number.expression', 'text.free'}
        assert {op for op in l2a4 if per_op.get(op, 0) >= 2} == l2a4

    def test_cases_replay_with_requests(self):
        for fid, _cases in CATALOG_L3:
            for case in build_fixtures()[f'{fid}.json']['cases']:
                result = parse_commands(case['text'], base=copy.deepcopy(case['base']), id_factory=counter_ids(),
                                        document_id='doc')
                assert len(result.conditionRequests) == len(case['expect'].get('conditionRequests', ())), case['name']
                assert print_commands(result.document).text == case['expect']['print'], case['name']
            break


def _text_of_300():
    lines = ['A = (-3, -2)', 'B = (3, -2)', 'C = (0.5, 2)', '# Дано']
    prev = ('A', 'B')
    for i in range(1, 99):
        lines += [f'M{i} = Середина({prev[0]}, {prev[1]})  # шаг {i}', f'l{i} = Прямая(M{i}, C)',
                  f'c{i} = Окружность(M{i}, C)']
        prev = (f'M{i}', 'C' if i % 2 else 'A')
    lines += ['D = (1, -0.5)', 'Условие(|AD| = |BD|)', 'Проверить(AB ⟂ CD)']
    return '\n'.join(lines)


@pytest.mark.slow
def test_parse_and_print_300_lines_within_budget():
    """Plan L3 §6: ``parse_commands``/``print_commands`` on 300 lines 50 ms
    (here with a group, step texts, a condition and a check; measured p95
    ≈ 35 ms new, ≈ 15 ms print), a margin of 2 for a busy machine; edit mode
    (print of the base inside, measured median ≈ 60 ms) — 3."""
    from tests.native.test_native_l3a2_budgets import _p95
    text = _text_of_300()
    parsed = parse_commands(text, document_id='doc')
    assert not [i for i in parsed.issues if i.severity == 'error']
    doc = apply_condition_requests(parsed.document, parsed.conditionRequests).document
    printed = print_commands(doc).text
    assert parse_commands(printed, base=doc).effects['added']['operations'] == []
    assert _p95(lambda: parse_commands(text, document_id='doc')) < 0.100
    assert _p95(lambda: print_commands(doc)) < 0.100
    assert _p95(lambda: parse_commands(printed, base=doc)) < 0.150
