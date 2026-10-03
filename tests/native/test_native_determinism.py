"""The kernel has no state: order, repetition and key order do not change results."""
import random
import re

from animageo import native
from tests.native.conftest import NATIVE_DIR, DocBuilder, number_input, path_input, point_input

SEED = 20261003


def all_ops_doc():
    b = DocBuilder('determinism', registry_version='1.1')
    b.free('A', -4, -1).free('B', 4, 2).free('C', -1, 5).free('D', 3, -4).free('O', 0, 0)
    b.segment('s', 'A', 'B').line('l', 'C', 'D').ray('r', 'A', 'C').circle('c', 'O', 'B')
    b.midpoint('M', 'A', 'B').intersect('X', 's', 'l').intersect('Y', 'r', 'l')
    b.line_circle('P1', 'P2', 'l', 'c').circle('k', 'M', 'C').circle_circle('Q1', 'Q2', 'c', 'k')
    b.other_than('Z', 'c', 'k', 'Q1')
    b.polygon('T', 'A', 'B', 'C', 'D', sides=[(1, 'tAB'), (3, 'tCD')])
    b.on_path('U', 'T', 1.5).on_path('V', 'r', 0.75).midpoint('W', 'U', 'V')
    return b.doc


def l2a1_doc():
    b = DocBuilder('determinism_l2', registry_version='1.2')
    b.free('A', -4, -1).free('B', 4, 2).free('C', -1, 5).free('D', 3, -4).number('n', 2, min=0.5, max=6)
    b.segment('s', 'A', 'B').ray('r', 'A', 'C').line('l', 'C', 'D')
    b.projection('H', 'C', 's', strict=1).projection('G', 'D', 'r').parallel('p', 'D', 's')
    b.perpendicular('q', 'A', 'r').perp_bisector('m', 'A', 'D').angle_bisector('w', 'B', 'A', 'C')
    b.vector('v', 'H', 'D').circle_radius('cr', 'H', 'n').circle_radius('c1', 'G', 1.5)
    b.circle3('k', 'A', 'B', 'D', center='O').on_path('U', 'm', 0.5).on_path('V', 'w', 1.25)
    b.intersect('X', 'p', 'q').line_circle('P1', 'P2', 'w', 'k')
    return b.doc


def l2a1_positions(n=50):
    rng = random.Random(SEED + 2)
    out = []
    for _ in range(n):
        case = {e: point_input(rng.uniform(-9, 9), rng.uniform(-9, 9)) for e in ('A', 'B', 'C', 'D')}
        case['n'] = number_input(rng.uniform(-1, 8))
        case['U'] = path_input(rng.uniform(-3, 3))
        case['V'] = path_input(rng.uniform(-3, 3))
        out.append(case)
    return out


def test_l2a1_order_and_repetition_do_not_matter():
    doc = l2a1_doc()
    cases = l2a1_positions()
    in_order = [canonical(doc, c) for c in cases]
    shuffled = list(range(len(cases)))
    random.Random(SEED + 3).shuffle(shuffled)
    by_shuffle = {i: canonical(doc, cases[i]) for i in shuffled}
    assert [by_shuffle[i] for i in range(len(cases))] == in_order
    for i in (0, 23, 49):
        assert canonical(l2a1_doc(), cases[i]) == in_order[i]
    states = {(e, r['state']) for c in cases for e, r in native.evaluate(doc, inputs=c).elements.items()}
    for el_id in ('H', 'G', 'p', 'q', 'm', 'w', 'v', 'cr', 'c1', 'k', 'O', 'U', 'V', 'X', 'P1', 'n'):
        assert (el_id, 'defined') in states, el_id
    assert ('H', 'undefined') in states                 # strict foot outside the segment
    for case in cases[:10]:
        assert native.check(doc, inputs=case).results == native.check(doc, inputs=case).results


def positions(n=50):
    rng = random.Random(SEED)
    out = []
    for _ in range(n):
        case = {e: point_input(rng.uniform(-9, 9), rng.uniform(-9, 9)) for e in ('A', 'B', 'C', 'D', 'O')}
        case['U'] = path_input(rng.uniform(-2, 6))
        case['V'] = path_input(rng.uniform(-1, 3))
        out.append(case)
    return out


def canonical(doc, inputs):
    return native.canonical_json(native.evaluate(doc, inputs=inputs).to_dict())


def test_order_and_repetition_do_not_matter():
    doc = all_ops_doc()
    cases = positions()
    in_order = [canonical(doc, c) for c in cases]
    shuffled = list(range(len(cases)))
    random.Random(SEED + 1).shuffle(shuffled)
    by_shuffle = {i: canonical(doc, cases[i]) for i in shuffled}
    assert [by_shuffle[i] for i in range(len(cases))] == in_order
    for i in (0, 17, 49):
        assert canonical(all_ops_doc(), cases[i]) == in_order[i]
    # the positions reach both defined and undefined states of the L1 ops
    states = {(e, r['state']) for c in cases for e, r in native.evaluate(doc, inputs=c).elements.items()}
    for el_id in ('P1', 'Q1', 'Z', 'U', 'W'):
        assert (el_id, 'defined') in states, el_id
    assert any(state == 'undefined' for _e, state in states)


def test_key_order_of_the_document_does_not_matter():
    doc = all_ops_doc()
    rng = random.Random(SEED)
    for case in positions(10):
        shuffled = dict(doc)
        for section in ('operations', 'elements', 'inputs'):
            items = list(doc[section].items())
            rng.shuffle(items)
            shuffled[section] = dict(items)
        assert canonical(shuffled, case) == canonical(doc, case)


def test_checks_are_stable():
    doc = all_ops_doc()
    for case in positions(10):
        assert native.check(doc, inputs=case).results == native.check(doc, inputs=case).results


RANDOMNESS = re.compile(r'^\s*(import\s+random\b|from\s+random\s+import)|\bnp\.random\b|\bnumpy\.random\b',
                        re.MULTILINE)


def test_no_randomness_in_the_native_package():
    offenders = []
    for path in sorted(NATIVE_DIR.rglob('*.py')):
        text = path.read_text(encoding='utf-8')
        for match in RANDOMNESS.finditer(text):
            line = text[text.rfind('\n', 0, match.start()) + 1:text.find('\n', match.end())]
            if re.search(r'default_rng\(\s*[\[\w]', line) and 'default_rng()' not in line:
                continue                      # an explicitly seeded generator is allowed
            offenders.append(f'{path.relative_to(NATIVE_DIR)}: {line.strip()}')
    assert offenders == []
