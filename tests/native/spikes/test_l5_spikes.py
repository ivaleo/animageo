"""Witnesses of the L5 spikes C0–C4 (plan L5 §2; conclusions in docs/native/l5-notes.md).

Each test pins the fact a decision of stage 1 or 2 rests on; when one fails,
the decision is to be revisited, not the test.
"""
import ast
import collections
import logging
import random
import sys
import uuid
import zipfile

import pytest

from animageo import native
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import COMMAND_REGISTRY, Command
from animageo.native.convert import _classic_parse, dsl_map, from_ggb
from animageo.native.convert.ggb import parse_xml, scan
from animageo.parsers.dsl import run
from tests.native.conftest import REPO_ROOT
from tests.native.ggb_synth import command, element, expression, ggb_xml, point

NS = uuid.UUID('2d1b5f39-9a3e-4c35-8a8e-0f7b5cfa1d64')


def _constr(code):
    c = Construction()
    run(c, code)
    return c


# ── C0: the inventory of signatures and the classic parser on what it does not know ──

def test_c0_inventory():
    rows = dsl_map().commands
    assert set(rows) == set(COMMAND_REGISTRY)
    by = collections.Counter('op' if 'op' in r else 'free' if 'free' in r else r['unmapped'] for r in rows.values())
    assert by['op'] >= 140 and by['free'] == 2
    assert by['no_registry_op'] + by['formula_unsupported'] + by['unsupported_signature'] == len(rows) - by['op'] - 2


@pytest.mark.parametrize('body, built, diag', [
    # an unknown command: the classic keeps a Command with no implementation (the object has its saved value)
    (point('A', 0.0, 0.0) + command('FooBar', ['A'], ['B']) + point('B', 1.0, 1.0), {'A', 'B'}, 'unsupported_signature'),
    (element('point3d', 'P', extra='<coords x="1" y="2" z="3" w="1"/>'), set(), None),        # 3D: skipped
    ('<cascell><inputCell><expression value="x+1"/></inputCell></cascell>', set(), None),   # CAS: skipped
    (expression('L', '{1,2,3}') + element('list', 'L'), set(), None),                       # list: skipped
    (element('button', 'b1', extra='<javascript val="alert(1)"/>'), set(), None),          # button: skipped
    (point('A', 0.0, 0.0, extra='<ggbscript val="SetValue[A,(1,1)]"/>'), {'A'}, None),     # script: ignored
    (expression('L', 'Sequence((k, 0), k, 1, 3)') + element('list', 'L'), set(), 'expression_parse_error'),
    (expression('a', '().__class__') + element('numeric', 'a', extra='<value val="0"/>'), {'a'},
     'expression_parse_error'),                                         # the guard of _check_ggb_code
])
def test_c0_classic_parser_on_unknown_content(body, built, diag):
    logging.disable(logging.CRITICAL)
    try:
        root = parse_xml(ggb_xml(body))
        constr, cut = _classic_parse(root, None, scan(root))
    finally:
        logging.disable(logging.NOTSET)
    names = {str(e.name) for e in list(constr.elements) + list(constr.vars)} - {'xAxis', 'yAxis'}
    assert names == built and cut == []
    assert [d['reason'] for d in constr.command_diagnostics] == ([diag] if diag else [])


# ── C1: the line of a DSL call, from the stack ─────────────────────────

def test_c1_line_from_the_stack(monkeypatch):
    seen = []
    orig = Construction.add

    def add(self, obj, *a, **kw):
        if isinstance(obj, Command):
            frames, f = [], sys._getframe()
            while f is not None:
                if f.f_code.co_filename == '<dsl>':
                    frames.append(f.f_lineno)
                f = f.f_back
            seen.append((obj.name, frames[0], frames[-1]))
        return orig(self, obj, *a, **kw)

    monkeypatch.setattr(Construction, 'add', add)
    _constr('A = Point(0, 0)\n'
            'for i in range(2):\n'
            '    P = Point(i, 1)\n'
            'def mid(X, Y):\n'
            '    return Midpoint(X,\n'
            '                    Y)\n'
            'M = mid(A, Point(4, 0))\n'
            'tri, a, b, c = Polygon(A, Point(4, 0), Point(1, 3))\n')
    # (command, innermost <dsl> frame — where the factory is written, outermost — the top-level statement)
    assert seen == [('Point', 1, 1), ('Point', 3, 3), ('Point', 3, 3), ('Point', 7, 7), ('Midpoint', 5, 7),
                    ('Point', 8, 8), ('Point', 8, 8), ('Polygon', 8, 8)]


# ── C2: values of the XML and tol.import ────────────────────────────────

def test_c2_values_of_real_files_match_far_below_the_tolerance(monkeypatch):
    import animageo.native.convert.construction as construction
    worst = collections.defaultdict(float)
    orig = construction.compare

    def compare(expected, actual, scale, **kw):
        status, delta = orig(expected, actual, scale, **kw)
        if delta is not None:
            worst[expected['kind']] = max(worst[expected['kind']], delta / scale)
        return status, delta

    monkeypatch.setattr(construction, 'compare', compare)
    for rel in ('docs/guide/assets/ggb/sample_triangle.ggb', 'examples/ai_style_generation_scene10/scene10.ggb',
                'tests/fixtures/label_anchor_types.ggb', 'tests/fixtures/label_offset_points.ggb'):
        _, rep = from_ggb(REPO_ROOT / rel, id_namespace=NS)
        assert rep['summary']['differs'] == 0
    assert set(worst) >= {'point', 'line', 'circle', 'angle'}
    assert max(worst.values()) < 1e-12          # GGB writes full doubles: tol.import = 1e-6·S has room
    with zipfile.ZipFile(REPO_ROOT / 'docs/guide/assets/ggb/sample_triangle.ggb') as zf:
        xml = zf.read('geogebra.xml').decode('utf-8')
    assert 'x="' in xml and any(len(v.split('.')[-1]) > 10 for v in xml.split('"') if v.replace('.', '').replace(
        '-', '').isdigit())


# ── C3: the classic output order against the native slots ────────────────

C3_CASES = {
    'intersect_cc': lambda P, r: f'k = Circle({P()}, {r(1.5, 3)})\nm = Circle({P()}, {r(1.5, 3)})\nX1, X2 = Intersect(k, m)',
    'intersect_cl': lambda P, r: f'g = Line({P()}, {P()})\nk = Circle(Point(0, 0), 3.5)\nX1, X2 = Intersect(k, g)',
    'tangent_pc': lambda P, r: f'k = Circle(Point(0, 0), 1)\nX1, X2 = Tangent(Point({r(1.5, 4)}, {r(-4, 4)}), k)',
    'angular_bisector_ll': lambda P, r: f'a = Line({P()}, {P()})\nb = Line({P()}, {P()})\nX1, X2 = AngularBisector(a, b)',
}


def test_c3_no_static_slot_order():
    rnd = random.Random(7)

    def P():
        return f'Point({rnd.uniform(-3, 3):.3f}, {rnd.uniform(-3, 3):.3f})'

    def r(a, b):
        return f'{rnd.uniform(a, b):.3f}'

    slots = {}
    for key, make in C3_CASES.items():
        count = collections.Counter()
        for _ in range(40):
            doc, rep = native.from_construction(_constr(make(P, r)), id_namespace=NS, mode='partial')
            e = {x['name']: x for x in rep['elements']}
            assert e['X1']['category'] == e['X2']['category'] == 'editable'
            count[doc['elements'][e['X1']['native_ids'][0]]['producer']['slot']] += 1
        slots[key] = count
    assert set(slots['tangent_pc']) == {'tangent.2'}                    # the reverse order, always
    assert len(slots['angular_bisector_ll']) == 2                       # no static order
    assert slots['intersect_cc']['first'] >= 35                         # mostly, not by contract


# ── C4: dynamic topology — reads of values during the run ─────────────────

def test_c4_runtime_reads_miss_an_indirect_condition(monkeypatch):
    from animageo.parsers.dsl import proxy
    reads = []
    orig = proxy.ElementProxy.__getattr__

    def hooked(self, attr):
        f = sys._getframe(1)
        while f is not None and f.f_code.co_filename != '<dsl>':
            f = f.f_back
        reads.append(f.f_lineno if f else None)
        return orig(self, attr)

    monkeypatch.setattr(proxy.ElementProxy, '__getattr__', hooked)
    code = 'A = Point(1, 2)\nv = A.x > 0\nif v:\n    C = Midpoint(A, Point(4, 0))\n'
    _constr(code)
    conditions = {n.test.lineno for n in ast.walk(ast.parse(code)) if isinstance(n, ast.If)}
    assert reads == [2] and conditions == {3}       # the read is not on the condition line: AST taint is needed
    with pytest.raises(TypeError):                  # a measure proxy has no comparison: such a DSL fails anyway
        _constr('A = Point(1, 2)\nd = Distance(A, Point(4, 0))\nif d > 1:\n    C = Midpoint(A, A)\n')
