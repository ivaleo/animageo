"""The area between two graphs, a graph and a line or a graph and the x-axis
(registry 1.9; docs/native/ops/function.area_between.md).

``function.area_between`` makes one ``region``: a ring per lobe between
consecutive roots of ``h = f − g`` (explicit limits ``a``, ``b``, or the
lobe ``lobe`` of the roots in the window ``B4``), each walked
counterclockwise: the lower curve left to right, the right edge, the upper
curve right to left, the left edge. A root ends a lobe with no edge, both
curves at ``y = f(x)`` there, so the ring closes exactly.
"""
from __future__ import annotations

from ...registry import repeat_count
from ..function import BISECT_MAX, GRID_CELLS, evaluator, find_roots, search_interval
from ..region import GRAPH_STEPS, graph_area, graph_xs, line_area
from ..values import Undefined
from . import op
from .function import function_window

__all__ = ['LOBE_MAX', 'area_bound', 'continuity', 'root_vertices']

LOBE_MAX = 64            # rings of one region at most (error limit_exceeded above)


def _limit_x(arg) -> float:
    """The ``x`` of a limit: a number (a literal too) or the ``x`` of a point."""
    return float(arg.value['value']) if arg.type == 'number' else float(arg.value['x'])


def area_bound(args, ctx):
    """``(g, source, graph, domain)`` of the second boundary: the graph of
    ``second``, the non-vertical line ``second`` as ``g(x) = p_y + (x −
    p_x)·dy/dx`` or the x-axis ``g ≡ 0`` (``source`` ``axis``); ``graph`` —
    whether it is drawn as a graph piece; ``domain`` its ``[lo, hi]`` or
    ``None``. A vertical line (decision ``vertical``) is
    ``Undefined('out_of_domain', {'slot': 'second'})``."""
    second = args.get('second')
    if second is None:
        return (lambda x: 0.0), 'axis', False, None
    if second.type == 'function':
        return evaluator(second.value), 'second', True, second.value['domain']
    (px, py), (dx, dy) = second.value['p'], second.value['dir']
    ctx.decide('vertical', dx, ctx.tol.decide_scalar)
    if abs(dx) <= ctx.tol.decide_scalar:
        return Undefined('out_of_domain', {'slot': 'second'})
    slope = dy / dx
    return (lambda x: py + (x - px) * slope), 'second', False, None


def _jump(u, a, b, ua, ub):
    """``|u(b) − u(a)|`` of the cell left by the jump bisection: halves at
    ``m = a + (b − a)/2`` while ``a < m < b`` (at most ``BISECT_MAX``
    times), keeping the half with the larger ``|Δu|`` (the left one on a
    tie); ``None`` when ``u`` has no value at a midpoint."""
    for _ in range(BISECT_MAX):
        m = a + (b - a) / 2
        if not (a < m < b):
            break
        um = u(m)
        if um is None:
            return None
        if abs(um - ua) >= abs(ub - um):
            b, ub = m, um
        else:
            a, ua = m, um
    return abs(ub - ua)


def continuity(u, lo, hi, ctx, slot):
    """``None`` when ``u`` is continuous on ``[lo, hi]`` as far as the grid
    tells, else ``Undefined``: ``out_of_domain`` (``detail.slot``) when it
    has no value at a node of the grid of ``GRID_CELLS`` cells (the last
    node is ``hi`` itself) or at a midpoint of the jump bisection;
    ``discontinuous`` (decision ``jump``) when a cell whose ``|Δu|`` is a
    strict local maximum among its neighbours keeps ``|Δu| > tol.decide``
    after :func:`_jump`."""
    n = GRID_CELLS
    xs = [lo + (k * (hi - lo)) / n for k in range(n + 1)]
    xs[-1] = hi
    us = [u(x) for x in xs]
    if any(v is None for v in us):
        return Undefined('out_of_domain', {'slot': slot})
    d = [abs(us[k + 1] - us[k]) for k in range(n)]
    tol = ctx.tol.decide_length
    for k in range(n):
        if (k > 0 and d[k] <= d[k - 1]) or (k < n - 1 and d[k] <= d[k + 1]):
            continue
        rest = _jump(u, xs[k], xs[k + 1], us[k], us[k + 1])
        if rest is None:
            return Undefined('out_of_domain', {'slot': slot})
        ctx.decide('jump', rest, tol)
        if rest > tol:
            return Undefined('discontinuous', {'slot': slot})
    return None


def _graph_piece(curve, x_start, x_end, y_start, y_end):
    """``(points, mids)`` of a graph piece from ``x_start`` to ``x_end``:
    the ends take ``y_start``/``y_end``, the inner points and the cell
    midpoints ``x_k + (x_{k+1} − x_k)/2`` the curve; ``None`` when the curve
    has no value at one of them."""
    xs = graph_xs(x_start, x_end, GRAPH_STEPS)
    pts = []
    for k, x in enumerate(xs):
        y = y_start if k == 0 else y_end if k == GRAPH_STEPS else curve(x)
        if y is None:
            return None
        pts.append([x, y])
    mids = []
    for xa, xb in zip(xs, xs[1:]):
        y = curve(xa + (xb - xa) / 2)
        if y is None:
            return None
        mids.append(y)
    return pts, mids


def _ring(f, g, g_source, g_graph, xa, xb, edge_a, edge_b):
    """``(pieces, shape, area)`` of the lobe ``[xa, xb]`` walked
    counterclockwise, or ``None`` when a curve has no value on it.
    ``edge_a``/``edge_b`` — whether the end has a vertical edge (a limit
    where ``|h| > tol``); without one both curves meet at ``y = f(x)``."""
    mid = xa + (xb - xa) / 2
    fm, gm = f(mid), g(mid)
    if fm is None or gm is None:
        return None
    f_up = fm - gm >= 0.0
    fa, fb, ga, gb = f(xa), f(xb), g(xa), g(xb)
    if None in (fa, fb, ga, gb):
        return None
    if not edge_a:
        ga = fa
    if not edge_b:
        gb = fb
    lower = (g, g_source, g_graph, ga, gb) if f_up else (f, 'first', True, fa, fb)
    upper = (f, 'first', True, fa, fb) if f_up else (g, g_source, g_graph, ga, gb)
    pieces, shape = [], []
    area = 0.0
    curve, source, graph, ya, yb = lower
    if graph:
        got = _graph_piece(curve, xa, xb, ya, yb)
        if got is None:
            return None
        pieces.append(got[0])
        shape.append(['graph', source])
        area = area + graph_area(*got)
    else:
        pieces.append([[xa, ya], [xb, yb]])
        shape.append(['line', source])
        area = area + line_area([xa, ya], [xb, yb])
    low_b, low_a = yb, ya
    curve, source, graph, ya, yb = upper
    if edge_b:
        pieces.append([[xb, low_b], [xb, yb]])
        shape.append(['line', 'limit'])
        area = area + line_area([xb, low_b], [xb, yb])
    if graph:
        got = _graph_piece(curve, xb, xa, yb, ya)
        if got is None:
            return None
        pieces.append(got[0])
        shape.append(['graph', source])
        area = area + graph_area(*got)
    else:
        pieces.append([[xb, yb], [xa, ya]])
        shape.append(['line', source])
        area = area + line_area([xb, yb], [xa, ya])
    if edge_a:
        pieces.append([[xa, ya], [xa, low_a]])
        shape.append(['line', 'limit'])
        area = area + line_area([xa, ya], [xa, low_a])
    return pieces, shape, area


def root_vertices(value) -> list:
    """The ``x`` of the vertices of a value of ``function.area_between``
    where the two boundaries meet without an edge (a root, or a limit
    where ``|h| ≤ tol``): the ends of the first piece of a ring that no
    ``limit`` piece follows (the right end) or ends the ring (the left)."""
    out = []
    for ring, kinds in zip(value['rings'], value['shape']):
        first = ring[0]
        if kinds[1][1] != 'limit':
            out.append(first[-1][0])
        if kinds[-1][1] != 'limit':
            out.append(first[0][0])
    return out


def _lobe_param(args):
    """The ``lobe`` param: ``None`` when absent, else ``repeat_count`` (``0``
    — not a whole number in ``1..100``)."""
    value = args.get('lobe')
    return None if value is None else repeat_count(value)


@op('function.area_between')
def area_between(args, ctx):
    tol = ctx.tol.decide_length
    first = args['first'].value
    f = evaluator(first)
    bound = area_bound(args, ctx)
    if isinstance(bound, Undefined):
        return {'region': bound}
    g, g_source, g_graph, g_domain = bound
    lobe = _lobe_param(args)
    limits = 'a' in args
    if lobe == 0 or (limits and lobe is not None):
        return {'region': Undefined('invalid_parameter')}

    def h(x):
        fx = f(x)
        if fx is None:
            return None
        gx = g(x)
        return None if gx is None else fx - gx

    domains = [('first', first['domain'])] + ([('second', g_domain)] if g_domain is not None else [])
    if limits:
        xa, xb = _limit_x(args['a']), _limit_x(args['b'])
        lo, hi = min(xa, xb), max(xa, xb)
        ctx.decide('empty_range', hi - lo, tol)
        if hi - lo <= tol:
            return {'region': Undefined('empty_range')}
        for slot, (d_lo, d_hi) in domains:
            if d_lo is not None:
                ctx.decide('domain_end', lo - d_lo, tol)
                if lo < d_lo - tol:
                    return {'region': Undefined('out_of_domain', {'slot': slot})}
                lo = max(lo, d_lo)
            if d_hi is not None:
                ctx.decide('domain_end', d_hi - hi, tol)
                if hi > d_hi + tol:
                    return {'region': Undefined('out_of_domain', {'slot': slot})}
                hi = min(hi, d_hi)
        spans = [(lo, hi)]
    else:
        x0, x1 = function_window(ctx)
        cut = search_interval(x0, x1, *(d for _s, d in domains))
        if cut is None:
            return {'region': Undefined('no_root_in_window')}
        found = find_roots(h, cut[0], cut[1], ctx)
        if found is None:
            return {'region': Undefined('coincident')}
        if not found:
            return {'region': Undefined('no_root_in_window')}
        k = lobe or 1
        if len(found) < k + 1:
            return {'region': Undefined('branch_absent')}
        spans = [(found[k - 1][0], found[k][0])]
    lo, hi = spans[0][0], spans[-1][1]
    for u, slot in ((f, 'first'), (g, 'second')) if g_graph else ((f, 'first'),):
        broken = continuity(u, lo, hi, ctx, slot)
        if broken is not None:
            return {'region': broken}
    if limits:
        found = find_roots(h, lo, hi, ctx)
        if found is None:
            return {'region': Undefined('coincident')}
        cuts = [lo] + [x for x, _m in found if lo < x < hi] + [hi]
        spans = list(zip(cuts, cuts[1:]))
    lobes = []
    for xa, xb in spans:
        ctx.decide('lobe_width', xb - xa, tol)
        if xb - xa > tol:
            lobes.append((xa, xb))

    def edge(x):
        if not limits or (x != lo and x != hi):
            return False                      # a root: the curves meet
        gap = h(x)
        if gap is None:
            return False
        ctx.decide('limit_gap', abs(gap), tol)
        return abs(gap) > tol

    area_tol = tol * ctx.tol.scale
    rings, shape, total = [], [], 0.0
    for xa, xb in lobes:
        got = _ring(f, g, g_source, g_graph, xa, xb, edge(xa), edge(xb))
        if got is None:
            return {'region': Undefined('out_of_domain')}
        pieces, kinds, area = got
        ctx.decide('empty_region', area, area_tol)
        if area <= area_tol:
            continue                          # h ≡ 0 on the lobe: no ring
        if len(rings) == LOBE_MAX:
            return {'region': Undefined('limit_exceeded')}
        rings.append(pieces)
        shape.append(kinds)
        total = total + area
    if not rings:
        return {'region': Undefined('empty_region')}
    return {'region': {'rings': rings, 'shape': shape, 'area': total}}
