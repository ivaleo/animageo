"""Viewport-aware adaptive sampler for parametric curves.

Solves the "infinite curve" problem for rendering: a parabola, hyperbola
branch, or function like y = 1/x extends forever, but we only want to
draw what fits on the canvas without spending unbounded work.

Strategy:
- `sample_parametric` samples a curve t → (x, y) adaptively: starts
  uniform, inserts midpoints where adjacent samples are too far apart in
  scene MU. Points outside the viewport are discarded, and the curve is
  split into multiple polylines at viewport crossings.
- `viewport_t_ranges_parabola` / `viewport_t_range_hyperbola_branch`
  return the narrow parameter interval that could possibly intersect
  the viewport, so the sampler doesn't waste its budget far off-screen.

Hard caps: `max_samples` (default 500) per call guarantees bounded work
— no matter how degenerate the curve, rendering never hangs. The caller
loses density before it loses responsiveness.
"""
from typing import Callable, List, Optional, Sequence, Tuple
import numpy as np


ViewportBounds = Tuple[float, float, float, float]  # (left, bottom, right, top)
TRange = Tuple[float, float]


# ── Adaptive parametric sampler ────────────────────────────────────────

def sample_parametric(
    func: Callable[[float], Sequence[float]],
    t_range: TRange,
    viewport: Optional[ViewportBounds] = None,
    *,
    initial_samples: int = 32,
    max_samples: int = 500,
    segment_mu: float = 0.05,
    viewport_pad: float = 0.1,
) -> List[np.ndarray]:
    """Adaptively sample a parametric curve, clipped to the viewport.

    Args:
        func: parameter → (x, y) in scene MU.
        t_range: (t_min, t_max) parameter domain.
        viewport: (left, bottom, right, top) in scene MU, or None for no
            clipping.
        initial_samples: starting uniform grid size.
        max_samples: hard cap on func evaluations. Prevents hangs.
        segment_mu: target maximum distance between adjacent samples, in
            scene MU. Caller typically passes ``pixel_count / ptUnit``
            (e.g. ``3 / ptUnit`` to aim for ~3 pixels per segment).
        viewport_pad: padding added to viewport on each side (scene MU)
            so clipped samples don't land exactly on the frame edge.

    Returns:
        A list of polylines. Each polyline is an ``(n, 2)`` float array
        of points inside the padded viewport, in parameter order. The
        list has multiple entries when the curve exits and re-enters the
        viewport. Empty list when the curve doesn't intersect at all.
    """
    t_min, t_max = float(t_range[0]), float(t_range[1])
    if t_max <= t_min:
        return []

    n0 = max(2, min(initial_samples, max_samples))
    ts = np.linspace(t_min, t_max, n0)
    pts = np.array([func(t) for t in ts], dtype=float)

    # Adaptive refinement: while any segment exceeds threshold, insert
    # midpoints of the longest segments, respecting the total budget.
    while len(ts) < max_samples:
        diffs = np.diff(pts, axis=0)
        lengths = np.linalg.norm(diffs, axis=1)
        long_mask = lengths > segment_mu
        if not long_mask.any():
            break

        long_indices = np.where(long_mask)[0]
        remaining = max_samples - len(ts)
        if len(long_indices) > remaining:
            # Prioritize the longest segments.
            order = np.argsort(-lengths[long_indices])
            long_indices = np.sort(long_indices[order[:remaining]])

        new_ts = (ts[long_indices] + ts[long_indices + 1]) / 2
        new_pts = np.array([func(t) for t in new_ts], dtype=float)

        ts = np.insert(ts, long_indices + 1, new_ts)
        pts = np.insert(pts, long_indices + 1, new_pts, axis=0)

    if viewport is None:
        return [pts] if len(pts) >= 2 else []

    return _split_by_viewport(pts, viewport, pad=viewport_pad)


def _split_by_viewport(
    pts: np.ndarray,
    viewport: ViewportBounds,
    pad: float = 0.0,
) -> List[np.ndarray]:
    """Clip a polyline against an axis-aligned viewport.

    Walks adjacent sample pairs, clips each segment to the padded
    viewport, and stitches clipped segments into polylines wherever
    consecutive pieces share an endpoint. A missing/non-matching
    segment breaks the current polyline and starts a new one.
    """
    left, bottom, right, top = viewport
    l, b, r, t = left - pad, bottom - pad, right + pad, top + pad
    if len(pts) < 2:
        return []

    polylines: List[List[np.ndarray]] = []
    current: List[np.ndarray] = []

    for i in range(len(pts) - 1):
        clipped = _clip_segment_to_box(pts[i], pts[i + 1], l, b, r, t)
        if clipped is None:
            if current:
                polylines.append(np.array(current, dtype=float))
                current = []
            continue

        cp1, cp2 = clipped
        if not current:
            current.append(cp1)
            current.append(cp2)
        else:
            last = current[-1]
            if np.allclose(cp1, last, atol=1e-9):
                current.append(cp2)
            else:
                polylines.append(np.array(current, dtype=float))
                current = [cp1, cp2]

    if current:
        polylines.append(np.array(current, dtype=float))

    return polylines


def _clip_segment_to_box(
    p1: np.ndarray,
    p2: np.ndarray,
    l: float,
    b: float,
    r: float,
    t: float,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Liang–Barsky: clip segment [p1, p2] to axis-aligned box [l,r]×[b,t].

    Returns (cp1, cp2) where both endpoints lie on or inside the box,
    or None if the segment doesn't intersect the box at all.
    """
    dx, dy = float(p2[0] - p1[0]), float(p2[1] - p1[1])
    t_enter = 0.0
    t_exit = 1.0

    # For each edge, encode as p_coef * t ≤ q_val.
    for p_coef, q_val in (
        (-dx, float(p1[0]) - l),  # x ≥ l
        (dx,  r - float(p1[0])),  # x ≤ r
        (-dy, float(p1[1]) - b),  # y ≥ b
        (dy,  t - float(p1[1])),  # y ≤ t
    ):
        if abs(p_coef) < 1e-15:
            if q_val < 0:
                return None  # parallel to edge, on the outside side
            continue
        t_val = q_val / p_coef
        if p_coef < 0:
            if t_val > t_enter:
                t_enter = t_val
        else:
            if t_val < t_exit:
                t_exit = t_val

    if t_enter > t_exit:
        return None

    cp1 = np.array([p1[0] + t_enter * dx, p1[1] + t_enter * dy])
    cp2 = np.array([p1[0] + t_exit * dx, p1[1] + t_exit * dy])
    return cp1, cp2


# ── Coordinate-frame helpers ───────────────────────────────────────────

def viewport_aabb_in_frame(
    viewport: ViewportBounds,
    origin: Sequence[float],
    axis_u: Sequence[float],
    axis_v: Sequence[float],
) -> Tuple[float, float, float, float]:
    """Project the viewport corners into a rotated (u, v) frame and
    return the bounding box ``(u_min, v_min, u_max, v_max)``.

    Used to turn viewport (world-aligned) into a canonical-frame rectangle
    large enough to enclose it, so analytic t-range computations can be
    done in the conic's canonical basis.
    """
    left, bottom, right, top = viewport
    origin = np.asarray(origin, dtype=float)
    axis_u = np.asarray(axis_u, dtype=float)
    axis_v = np.asarray(axis_v, dtype=float)

    corners = np.array([
        [left, bottom], [right, bottom], [right, top], [left, top],
    ], dtype=float)
    rel = corners - origin
    u = rel @ axis_u
    v = rel @ axis_v
    return float(u.min()), float(v.min()), float(u.max()), float(v.max())


# ── Analytic t-ranges for conic parametrizations ───────────────────────

def viewport_t_ranges_parabola(
    vertex: Sequence[float],
    axis: Sequence[float],
    perp: Sequence[float],
    focal_parameter: float,
    viewport: ViewportBounds,
) -> List[TRange]:
    """Parameter ranges for a parabola (u = t, v = t²/(4p)) that overlap
    the viewport.

    Canonical frame: ``perp`` is the u-axis (direction of quadratic
    variation), ``axis`` is the v-axis (direction of opening from
    ``vertex``). ``focal_parameter`` is p (always > 0).

    Returns a list of ``(t_min, t_max)`` tuples — usually one, but two
    when the viewport lies entirely above the vertex in v (curve enters
    and exits the viewport on both sides of the axis, with a gap in the
    middle where it's below the viewport bottom).
    """
    u_min, v_min, u_max, v_max = viewport_aabb_in_frame(
        viewport, vertex, perp, axis,
    )
    if v_max < 0 or focal_parameter <= 0:
        return []  # curve lies entirely beyond the viewport in v

    p = float(focal_parameter)
    # Upper u-bound: curve at u_bound_max reaches v = v_max.
    u_bound_max = 2.0 * np.sqrt(p * max(v_max, 0.0))
    t_min = max(u_min, -u_bound_max)
    t_max = min(u_max, u_bound_max)
    if t_min > t_max:
        return []

    if v_min <= 0:
        return [(t_min, t_max)]

    # v_min > 0: exclude central u interval where curve is below viewport.
    u_bound_min = 2.0 * np.sqrt(p * v_min)
    ranges: List[TRange] = []
    left = (t_min, min(-u_bound_min, t_max))
    right = (max(u_bound_min, t_min), t_max)
    if left[0] < left[1]:
        ranges.append(left)
    if right[0] < right[1]:
        ranges.append(right)
    return ranges


def viewport_t_range_hyperbola_branch(
    center: Sequence[float],
    axis_u: Sequence[float],
    axis_v: Sequence[float],
    a: float,
    b: float,
    branch_sign: int,
    viewport: ViewportBounds,
) -> Optional[TRange]:
    """Parameter range for one branch of a hyperbola parametrized as
    ``u = branch_sign · a · cosh(t)``, ``v = b · sinh(t)``,
    in the canonical ``(u = axis_u, v = axis_v)`` frame.

    Args:
        center: world coords of hyperbola center.
        axis_u, axis_v: unit vectors spanning the canonical frame.
        a: transverse semi-axis (curve crosses at u = ±a, v = 0).
        b: conjugate semi-axis.
        branch_sign: +1 for the right branch (u ≥ a), -1 for the left
            (u ≤ -a).
        viewport: scene bounds.

    Returns:
        ``(t_min, t_max)`` or None when the branch misses the viewport.
    """
    u_min, v_min, u_max, v_max = viewport_aabb_in_frame(
        viewport, center, axis_u, axis_v,
    )

    if branch_sign > 0:
        if u_max < a:
            return None
        cosh_limit = u_max / a
    else:
        if u_min > -a:
            return None
        cosh_limit = -u_min / a

    if cosh_limit < 1.0:
        return None

    t_bound_u = float(np.arccosh(cosh_limit))
    v_abs_max = max(abs(v_min), abs(v_max))
    t_bound_v = float(np.arcsinh(v_abs_max / b))

    t_bound = min(t_bound_u, t_bound_v)
    if t_bound <= 0:
        # Viewport touches only the branch's vertex (t=0).
        return (0.0, 0.0)
    return (-t_bound, t_bound)


# ── Parametrization factories (convenience for Conic rendering) ────────

def make_ellipse_param(
    center: Sequence[float],
    a: float,
    b: float,
    rotation: float,
) -> Callable[[float], np.ndarray]:
    """Return t → (x, y) for the ellipse
    ``(a·cos t, b·sin t)`` rotated and translated.
    """
    center = np.asarray(center, dtype=float)
    cs, sn = np.cos(rotation), np.sin(rotation)
    R = np.array([[cs, -sn], [sn, cs]], dtype=float)

    def param(t: float) -> np.ndarray:
        local = np.array([a * np.cos(t), b * np.sin(t)])
        return center + R @ local

    return param


def make_parabola_param(
    vertex: Sequence[float],
    axis: Sequence[float],
    perp: Sequence[float],
    focal_parameter: float,
) -> Callable[[float], np.ndarray]:
    """Return t → (x, y) for the parabola
    ``u = t``, ``v = t²/(4p)`` expressed in the (perp, axis) frame.
    """
    vertex = np.asarray(vertex, dtype=float)
    axis = np.asarray(axis, dtype=float)
    perp = np.asarray(perp, dtype=float)
    p4 = 4.0 * float(focal_parameter)

    def param(t: float) -> np.ndarray:
        u = t
        v = (t * t) / p4
        return vertex + u * perp + v * axis

    return param


def make_hyperbola_branch_param(
    center: Sequence[float],
    axis_u: Sequence[float],
    axis_v: Sequence[float],
    a: float,
    b: float,
    branch_sign: int,
) -> Callable[[float], np.ndarray]:
    """Return t → (x, y) for one branch of the hyperbola
    ``u = branch_sign · a · cosh(t)``, ``v = b · sinh(t)``.
    """
    center = np.asarray(center, dtype=float)
    axis_u = np.asarray(axis_u, dtype=float)
    axis_v = np.asarray(axis_v, dtype=float)
    sign = int(branch_sign)

    def param(t: float) -> np.ndarray:
        u = sign * a * np.cosh(t)
        v = b * np.sinh(t)
        return center + u * axis_u + v * axis_v

    return param


# ── Marching squares for implicit F(x, y) = 0 ─────────────────────────

# Lookup table for marching squares. For a sign code 0..15 — where bit i
# is 1 iff corner i lies above the level — lists pairs of edges between
# which a line segment is drawn. Corners are ordered 0=BL, 1=BR, 2=TR,
# 3=TL (counter-clockwise); edges 0=bottom, 1=right, 2=top, 3=left.
_MS_TABLE = (
    (),                         # 0000
    ((0, 3),),                  # 0001
    ((0, 1),),                  # 0010
    ((1, 3),),                  # 0011
    ((1, 2),),                  # 0100
    ((0, 1), (2, 3)),           # 0101 — saddle (two separate crossings)
    ((0, 2),),                  # 0110
    ((2, 3),),                  # 0111
    ((2, 3),),                  # 1000
    ((0, 2),),                  # 1001
    ((0, 3), (1, 2)),           # 1010 — saddle
    ((1, 2),),                  # 1011
    ((1, 3),),                  # 1100
    ((0, 1),),                  # 1101
    ((0, 3),),                  # 1110
    (),                         # 1111
)


def _edge_point(edge: int, x_l: float, x_r: float, y_b: float, y_t: float,
                f: Sequence[float]) -> Tuple[float, float]:
    """Linear interpolation of the zero-crossing on a cell edge.

    Cell corners (CCW from BL): ``f[0]=f00, f[1]=f10, f[2]=f11, f[3]=f01``.

    Caller (``marching_squares``) ensures only cells whose corner-sign
    pattern actually has a zero-crossing reach this function, so one
    endpoint is positive and the other negative. Still guard the
    denominator: near-coincident corner values can happen when two
    corners straddle zero by rounding (e.g. both ≈ 1e-17). In that case
    collapse to the mid-edge — visually indistinguishable from the true
    crossing and avoids propagating ``inf/nan`` into the output.
    """
    f00, f10, f11, f01 = f

    def _lerp(a, b):
        d = a - b
        if abs(d) < 1e-18:
            return 0.5
        return a / d

    if edge == 0:      # bottom: BL → BR
        t = _lerp(f00, f10)
        return (x_l + t * (x_r - x_l), y_b)
    if edge == 1:      # right: BR → TR
        t = _lerp(f10, f11)
        return (x_r, y_b + t * (y_t - y_b))
    if edge == 2:      # top: TL → TR  (indexed so t goes TL→TR, matching TABLE)
        t = _lerp(f01, f11)
        return (x_l + t * (x_r - x_l), y_t)
    # edge == 3: left: BL → TL
    t = _lerp(f00, f01)
    return (x_l, y_b + t * (y_t - y_b))


def marching_squares(
    F: Callable[[float, float], float],
    viewport: ViewportBounds,
    *,
    grid_n: int = 128,
    level: float = 0.0,
) -> List[np.ndarray]:
    """Extract the level set ``F(x, y) = level`` over ``viewport`` as
    line segments via the classical 16-case marching-squares algorithm.

    Args:
        F: scalar field callable ``(x, y) → float``. May return NaN for
           undefined regions; cells that include NaN corners are skipped.
        viewport: ``(left, bottom, right, top)`` in scene MU.
        grid_n: number of grid samples per axis. Work is O(grid_n²); the
            default 128 gives smooth curves for typical viewports without
            hanging.
        level: target value; default 0 (zero-level set).

    Returns:
        A list of ``(2, 2)`` ndarrays, each one a line segment
        ``[[x1, y1], [x2, y2]]``. No attempt is made to stitch
        neighbouring segments into continuous polylines.
    """
    left, bottom, right, top = viewport
    if right <= left or top <= bottom or grid_n < 2:
        return []

    xs = np.linspace(left, right, grid_n)
    ys = np.linspace(bottom, top, grid_n)

    # Vectorized evaluation via meshgrid, with per-cell fallback for
    # callables that can't broadcast.
    grid = np.full((grid_n, grid_n), np.nan, dtype=float)
    try:
        X, Y = np.meshgrid(xs, ys)
        grid_val = F(X, Y)
        grid_arr = np.asarray(grid_val, dtype=float)
        if grid_arr.shape == grid.shape:
            grid = grid_arr
        else:
            raise ValueError("broadcast shape mismatch")
    except Exception:
        for i, y in enumerate(ys):
            for j, x in enumerate(xs):
                try:
                    v = F(float(x), float(y))
                    grid[i, j] = float(v) if np.isfinite(v) else np.nan
                except Exception:
                    grid[i, j] = np.nan

    segments: List[np.ndarray] = []
    for i in range(grid_n - 1):
        for j in range(grid_n - 1):
            f00 = grid[i, j]
            f10 = grid[i, j + 1]
            f11 = grid[i + 1, j + 1]
            f01 = grid[i + 1, j]
            if not all(np.isfinite(v) for v in (f00, f10, f11, f01)):
                continue

            code = 0
            if f00 > level: code |= 1
            if f10 > level: code |= 2
            if f11 > level: code |= 4
            if f01 > level: code |= 8
            if code == 0 or code == 15:
                continue

            shifted = (f00 - level, f10 - level, f11 - level, f01 - level)
            for edge_a, edge_b in _MS_TABLE[code]:
                p1 = _edge_point(edge_a, xs[j], xs[j + 1],
                                 ys[i], ys[i + 1], shifted)
                p2 = _edge_point(edge_b, xs[j], xs[j + 1],
                                 ys[i], ys[i + 1], shifted)
                segments.append(np.array([p1, p2], dtype=float))

    return segments


def stitch_segments(
    segments: Sequence[np.ndarray],
    *,
    tol: float = 1e-9,
) -> List[np.ndarray]:
    """Join ``marching_squares`` segments that share endpoints into polylines.

    Neighbouring cells interpolate a shared edge from the same two corner
    values, so shared endpoints coincide; ``tol`` (scene MU) only absorbs
    rounding. Open chains are walked from their free ends first, then the
    remaining closed loops. A closed loop repeats its first point at the end.

    Returns a list of ``(n, 2)`` arrays (``n >= 2``). Needed for dashed
    implicit curves: a pattern restarts on every separate path, so a curve
    left as hundreds of cell-sized pieces would render solid.
    """
    segs = [np.asarray(s, dtype=float)[:2, :2] for s in segments
            if s is not None and len(s) >= 2]
    if not segs:
        return []
    scale = 1.0 / tol if tol > 0 else 1e9

    def key(p):
        return (int(round(p[0] * scale)), int(round(p[1] * scale)))

    ends = {}   # endpoint key → list of (segment index, end 0/1)
    for i, s in enumerate(segs):
        for e in (0, 1):
            ends.setdefault(key(s[e]), []).append((i, e))

    used = [False] * len(segs)

    def walk(i, e_start):
        """Follow the chain starting at segment i entering from end e_start."""
        pts = [segs[i][e_start], segs[i][1 - e_start]]
        used[i] = True
        cur_key = key(segs[i][1 - e_start])
        while True:
            nxt = None
            for j, e in ends.get(cur_key, ()):
                if not used[j]:
                    nxt = (j, e)
                    break
            if nxt is None:
                return pts
            j, e = nxt
            used[j] = True
            pts.append(segs[j][1 - e])
            cur_key = key(segs[j][1 - e])

    polylines: List[np.ndarray] = []
    # Open chains: start at endpoints touched by exactly one segment.
    for k, members in ends.items():
        if len(members) != 1:
            continue
        i, e = members[0]
        if not used[i]:
            polylines.append(np.array(walk(i, e)))
    # What is left forms closed loops.
    for i in range(len(segs)):
        if not used[i]:
            polylines.append(np.array(walk(i, 0)))
    return polylines
