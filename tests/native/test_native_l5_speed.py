"""Speed of the import (plan L5 §8, stage 3; 1.10.0a2).

The budgets: ``from_ggb`` of a file of 3000 objects (the limit of
``import_too_many_objects``) ≤ 30 s; ``from_construction`` of a scene of
300 operations ≤ 1 s. Both are ``slow`` and print the measured numbers.
The scene is groups of one triangle: its sides, the midpoints, two medians
and the centroid, a circle about the centroid, a perpendicular and the
medial triangle — 20 objects a group in the file (11 commands), 12
operations a group in the scene; every object editable.
"""
import math
import time
import uuid

import pytest

from animageo import native
from animageo.geo.construction import Construction
from animageo.parsers.dsl import run
from tests.native.ggb_synth import command, element, ggb_bytes, line_style, point

NS = uuid.UUID('5f0c2b1e-7d4a-4c39-8e61-2a9b3c4d5e6f')
GGB_BUDGET_S = 30.0
CONSTRUCTION_BUDGET_S = 1.0
OBJECTS_PER_GROUP = 20


def _vertices(g):
    """The triangle of group ``g``: a non-degenerate triangle that moves with ``g``."""
    ox, oy = 7.0 * (g % 12), 7.0 * (g // 12)
    s = 1.0 + 0.1 * (g % 7)
    return (ox, oy), (ox + 4.0 * s, oy + 0.3 * (g % 3)), (ox + 1.0 + 0.2 * (g % 5), oy + 3.0 * s)


def _mid(p, q):
    return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)


def _line(p, q):
    """GGB ``<coords>`` of the line through ``p`` and ``q``: ``x·X + y·Y + z = 0``."""
    a, b = p[1] - q[1], q[0] - p[0]
    return a, b, -(a * p[0] + b * p[1])


def _meet(l1, l2):
    (a1, b1, c1), (a2, b2, c2) = l1, l2
    d = a1 * b2 - a2 * b1
    return ((b1 * c2 - b2 * c1) / d, (a2 * c1 - a1 * c2) / d)


def _coords(label, type_, abc, **kw):
    a, b, c = abc
    return element(type_, label, extra=line_style() + f'<coords x="{a!r}" y="{b!r}" z="{c!r}"/>', **kw)


def group_xml(g):
    """The 20 objects of group ``g`` with the values GeoGebra saves."""
    A, B, C = _vertices(g)
    n = lambda s: f'{s}_{{{g}}}'                     # noqa: E731 — GGB labels with an index
    Ma, Mb, Mc = _mid(B, C), _mid(C, A), _mid(A, B)
    la, lb = _line(A, Ma), _line(B, Mb)
    G = _meet(la, lb)
    r2 = (A[0] - G[0]) ** 2 + (A[1] - G[1]) ** 2
    side_a = _line(B, C)
    perp = (side_a[1], -side_a[0], -(side_a[1] * G[0] - side_a[0] * G[1]))
    K = _mid(G, Ma)
    out = [point(n('A'), *A), point(n('B'), *B), point(n('C'), *C),
           command('Polygon', [n('A'), n('B'), n('C')], [n('t'), n('c'), n('a'), n('b')]),
           element('polygon', n('t'), alpha=0.1),
           _coords(n('c'), 'segment', _line(A, B)), _coords(n('a'), 'segment', side_a),
           _coords(n('b'), 'segment', _line(C, A))]
    for label, (p, q), m in (('Ma', ('B', 'C'), Ma), ('Mb', ('C', 'A'), Mb), ('Mc', ('A', 'B'), Mc)):
        out += [command('Midpoint', [n(p), n(q)], [n(label)]), point(n(label), *m)]
    out += [command('Line', [n('A'), n('Ma')], [n('la')]), _coords(n('la'), 'line', la),
            command('Line', [n('B'), n('Mb')], [n('lb')]), _coords(n('lb'), 'line', lb),
            command('Intersect', [n('la'), n('lb')], [n('G')]), point(n('G'), *G),
            command('Circle', [n('G'), n('A')], [n('k')]),
            element('conic', n('k'), extra=line_style() + f'<matrix A0="1" A1="1" A2="{G[0] ** 2 + G[1] ** 2 - r2!r}"'
                                                          f' A3="0" A4="{-G[0]!r}" A5="{-G[1]!r}"/>'),
            command('PerpendicularLine', [n('G'), n('a')], [n('p')]), _coords(n('p'), 'line', perp),
            command('Midpoint', [n('G'), n('Ma')], [n('K')]), point(n('K'), *K),
            command('Polygon', [n('Ma'), n('Mb'), n('Mc')], [n('u'), n('mc'), n('ma'), n('mb')]),
            element('polygon', n('u'), alpha=0.1),
            _coords(n('mc'), 'segment', _line(Ma, Mb)), _coords(n('ma'), 'segment', _line(Mb, Mc)),
            _coords(n('mb'), 'segment', _line(Mc, Ma))]
    return ''.join(out)


def big_ggb(objects=3000):
    assert objects % OBJECTS_PER_GROUP == 0
    return ggb_bytes(''.join(group_xml(g) for g in range(objects // OBJECTS_PER_GROUP)))


def group_dsl(g):
    """Group ``g`` as a DSL scene: 12 operations (and 3 free points)."""
    A, B, C = _vertices(g)
    return '\n'.join([
        f'A{g} = Point({A[0]!r}, {A[1]!r})', f'B{g} = Point({B[0]!r}, {B[1]!r})',
        f'C{g} = Point({C[0]!r}, {C[1]!r})',
        f't{g} = Polygon(A{g}, B{g}, C{g})', f'a{g} = Segment(B{g}, C{g})',
        f'Ma{g} = Midpoint(B{g}, C{g})', f'Mb{g} = Midpoint(C{g}, A{g})', f'Mc{g} = Midpoint(A{g}, B{g})',
        f'la{g} = Line(A{g}, Ma{g})', f'lb{g} = Line(B{g}, Mb{g})', f'G{g} = Intersect(la{g}, lb{g})',
        f'k{g} = Circle(G{g}, A{g})', f'p{g} = PerpendicularLine(G{g}, a{g})',
        f'K{g} = Midpoint(G{g}, Ma{g})', f'u{g} = Polygon(Ma{g}, Mb{g}, Mc{g})', ''])


def big_construction(operations=300):
    c = Construction()
    run(c, ''.join(group_dsl(g) for g in range(math.ceil(operations / 12))))
    return c


@pytest.mark.slow
def test_from_ggb_of_3000_objects(capsys):
    data = big_ggb(3000)
    start = time.perf_counter()
    doc, rep = native.from_ggb(data, id_namespace=NS, name='speed.ggb')
    elapsed = time.perf_counter() - start
    assert len(rep['elements']) == 3000
    assert rep['summary']['editable'] == 3000, rep['summary']
    with capsys.disabled():
        print(f'\nfrom_ggb: 3000 objects, {len(doc["operations"])} ops, {len(data) // 1024} KB, '
              f'{elapsed:.2f} s (budget {GGB_BUDGET_S:.0f} s)')
    assert elapsed <= GGB_BUDGET_S, f'{elapsed:.2f} s > {GGB_BUDGET_S:.0f} s'


@pytest.mark.slow
def test_from_construction_of_300_operations(capsys):
    constr = big_construction(300)
    native.from_construction(big_construction(12), id_namespace=NS)      # warm-up (imports, registry)
    start = time.perf_counter()
    doc, rep = native.from_construction(constr, id_namespace=NS)
    elapsed = time.perf_counter() - start
    n_ops = sum(o['op'] not in ('point.free',) for o in doc['operations'].values())
    assert n_ops >= 300
    assert all(e['category'] == 'editable' for e in rep['elements'])
    with capsys.disabled():
        print(f'\nfrom_construction: {n_ops} ops ({len(doc["operations"])} with free points), '
              f'{elapsed:.3f} s (budget {CONSTRUCTION_BUDGET_S:.0f} s)')
    assert elapsed <= CONSTRUCTION_BUDGET_S, f'{elapsed:.3f} s > {CONSTRUCTION_BUDGET_S:.0f} s'
