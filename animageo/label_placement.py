"""Automatic label placement — greedy solver with 8 candidate positions.

Places labels near their anchor points while minimizing overlaps with other
labels and with geometric objects. Enabled via overlay.label_placement.enabled.

Algorithm: priority-ordered greedy with 8 discrete candidate directions per
label. Most-constrained labels (fewest obstacle-free candidates) are placed
first. Preferred direction is computed per-label as the direction AWAY from
the local concentration of geometry. Deterministic.

Public API:
- ``auto_place_labels(scene)`` — one-shot: compute + apply + rerender.
- ``compute_label_layout(scene, *, cfg=None, canonicalize=False)`` — pure:
  returns ``dict[str, LabelPlacement]`` without mutating anything.
- ``apply_label_layout(scene, layout, *, rerender=True)`` — writes layout
  into ``elem.style`` and optionally rerenders geometry.
- ``compute_angle_label_center(ang, angle_params, ptUnit)`` —
  pure analytical bisector-based angle label center. For per-frame dynamic
  updates during animation. The two gaps (arc-side vs angle-sides) live on
  ``angle_params`` so callers don't re-thread them frame-to-frame.
- ``clear_bbox_cache()`` — invalidate the Tex bbox measurement cache.
"""
import logging
import re
import threading
import numpy as np
from dataclasses import dataclass, field
from math import pi, cos, sin, atan2, sqrt
from typing import Optional

from .style.resolver import resolve as _resolve_style
from .labels import resolve_label_text

logger = logging.getLogger(__name__)


def _style_ptUnit(style):
    export = getattr(style, 'export', {}) or {}
    return export.get('ptUnit_style', export.get('ptUnit', 1))


# ── Tex bbox measurement cache ────────────────────────────────────────
# Measuring a Tex bbox requires rendering via latex — the expensive step.
# The bbox depends only on (label_text, font_size, tex_template), so we
# cache aggressively. Keyframe snapshots reuse the same labels many times
# → cache is a big win.
#
# Thread-safety: the dict + its lock are module-level. Concurrent render
# jobs that share a Python process (e.g. web-service worker pools using
# threads) read/write through ``_bbox_lock``. The cache is not *scene-
# local*, so callers that want strict isolation should either use
# subprocesses or call ``clear_bbox_cache()`` between jobs.

_bbox_cache: dict = {}
_bbox_lock = threading.Lock()


def clear_bbox_cache():
    """Drop all cached Tex bbox measurements. Call after font or text changes
    (including between render jobs in a reused process)."""
    with _bbox_lock:
        _bbox_cache.clear()


# Rough glyph metrics for the degraded path below, measured against RusTex:
# a capital is ≈0.0075·font_size wide and ≈0.0077·font_size tall in scene MU.
_EST_CHAR_W = 0.0075
_EST_CAP_H = 0.0077
_TEX_MARKUP_RE = re.compile(r'\\[A-Za-z]+|[${}^_\\]')


def _estimate_label_bbox(label_text: str, font_size: float) -> tuple[float, float]:
    """Approximate a label bbox without LaTeX, for when the compile fails."""
    glyphs = max(len(_TEX_MARKUP_RE.sub('', label_text)), 1)
    return (glyphs * _EST_CHAR_W * font_size, _EST_CAP_H * font_size)


def _measure_label_bbox(label_text: str, font_size: float) -> tuple[float, float]:
    """Return (width, height) of a Tex label in scene MU. Cached, thread-safe.

    A label whose LaTeX does not compile falls back to an estimate: the layout
    is then approximate, but auto-placement must not take the render down with
    it (the renderer degrades the same label to plain text — see
    ``ui._compile_label_tex``).
    """
    from .ui import correctedLabel, RusTex
    # Template identity is part of the key so a future per-scene template
    # swap won't silently reuse the wrong bbox.
    key = (label_text, float(font_size), id(RusTex))
    with _bbox_lock:
        hit = _bbox_cache.get(key)
    if hit is not None:
        return hit
    from manim import Tex
    try:
        tex = Tex(correctedLabel(label_text), tex_template=RusTex)
        tex.set(font_size=font_size)
        dims = (float(tex.width), float(tex.height))
    except Exception as e:
        logger.warning("Label %r: bbox measurement failed (%s); "
                       "using an estimated size for placement", label_text, e)
        dims = _estimate_label_bbox(label_text, font_size)
    with _bbox_lock:
        _bbox_cache[key] = dims
    return dims


# ── Layout result dataclasses ─────────────────────────────────────────

@dataclass
class AngleParams:
    """Per-element parameters needed for bisector-based angle-label recompute.

    Captured at layout time; values depend only on Tex bbox and style (not
    on v1/v2/p which may change during animation), so they can be reused
    frame-to-frame to call ``compute_angle_label_center``.

    ``arc_r_px`` is the **effective** outer arc radius in pixels: it already
    includes the expansion from multiple concentric arcs
    (``arc_size_px + (lines - 1) * ang_rshift``), matching what the renderer
    draws in ``animageo.py:CreateMObject``.

    ``render_r_px`` is the renderer's base label radius in pixels, before
    ``label_offset_px`` is applied. It differs from ``arc_r_px`` for right-angle
    markers, whose square marker uses ``right_angle_size_px / sqrt(2)``.

    The two gaps are independent: ``gap_arc_px`` controls the clearance
    between the outer arc and the nearest edge of the label, and
    ``gap_sides_px`` enters the narrow-angle clamp that keeps the bbox clear
    of the two sides converging toward the vertex.

    ``angle_range`` mirrors ``elem.style['angle_range']`` ('minor' or 'reflex').
    The narrow-angle clamp uses it to derive the angle measure that is
    actually drawn, so reflex cases (raw > π rendered as supplementary on
    the narrow side) still get the correct clamp.
    """
    arc_r_px: float           # effective outer arc radius, pixels
    half_w: float             # half-width of label bbox in scene MU
    half_h: float             # half-height
    gap_arc_px: float         # gap between arc and label, pixels
    gap_sides_px: float       # gap between angle sides and label bbox, pixels
    angle_range: str = 'minor'  # 'minor' (non-reflex) or 'reflex'
    render_r_px: Optional[float] = None  # renderer base label radius, pixels
    exterior: bool = False    # FP-8: place on the OUTSIDE of the wedge (opposite
                              # the interior bisector) — used to honour a manual
                              # label the user placed outside a narrow angle.
    max_arm_fraction: Optional[float] = None  # round-10: cap the narrow-angle
                              # label distance to this fraction of the shorter arm
                              # so a narrow angle's wide value label doesn't drift
                              # far down the bisector toward a neighbouring angle.


@dataclass
class LeaderSpec:
    """A leader line connecting a displaced label back to its object (P2-A).

    Set when a label could not be placed without overlap near its anchor (a
    genuinely stuck/coincident case) and ``label_overflow='leader'`` moved it to
    a free spot. The renderer/exporters draw a thin connector ``attach → anchor``.
    All points are scene MU. Default-off feature: a normal label has ``leader=None``.
    """
    anchor: tuple   # the object point the label belongs to (scene MU)
    attach: tuple   # point on the label-bbox edge where the connector starts


@dataclass
class LabelPlacement:
    """Computed placement for a single label.

    ``offset_ggb`` is what goes into ``elem.style['label_offset_px']`` (ggb pixel units).
    ``label_anchor`` is one of TL/TC/TR/ML/MC/MR/BL/BC/BR.
    ``kind`` is 'static' (regular label) or 'dynamic_angle' (bisector tracked).
    ``angle_params`` is populated for ``kind='dynamic_angle'``.
    ``leader`` (P2-A) is set when the label was displaced and needs a connector.
    """
    name: str
    offset_ggb: tuple
    label_anchor: str
    kind: str = 'static'
    angle_params: Optional[AngleParams] = None
    leader: Optional['LeaderSpec'] = None

# 8 candidate directions (angle from positive-x, CCW):
# E, NE, N, NW, W, SW, S, SE
_DIRECTIONS = np.array([
    [cos(i * pi / 4), sin(i * pi / 4)]
    for i in range(8)
])

# For each direction index, the label anchor is the bbox point placed at the
# offset position so the whole label sits on the FAR side of that point (away
# from the feature). Cardinal dirs use a mid-edge anchor; diagonals use a CORNER
# anchor (FP-1) so a wide label does not reach a corner back over the marker —
# this is what keeps point labels clear of their dot regardless of label width.
#  idx:  E     NE    N     NW    W     SW    S     SE
_DIR_TO_ANCHOR = ['ML', 'BL', 'BC', 'BR', 'MR', 'TR', 'TC', 'TL']

# Upper bound on how far the narrow-angle clearance may push an angle label out
# along the bisector, as a multiple of the base distance (arc radius + label +
# gap). Without it, ``1/sin(half_angle)`` sends labels of very small angles far
# off the marker (e.g. a value label during an animation where the angle shrinks).
ANGLE_LABEL_NARROW_MAX_FACTOR = 2.5


# ── Canonical position-preference orders (P0-A) ───────────────────────
# Rank per direction index (lower = more preferred). Direction indices match
# _DIRECTIONS: 0=E, 1=NE(TR), 2=N(T), 3=NW(TL), 4=W(L), 5=SW(BL), 6=S(B),
# 7=SE(BR). A fixed a-priori order is what makes placement read as a *system*
# rather than chaos (docs/archive/label_placement_research.md §7). Off by default
# (config 'position_priority' = None) so existing output is byte-for-byte
# unchanged; enable + raise 'w_pref' to apply.
#   classic     — Yoeli 1972: TR > TL > BR > BL > R > L > T > B
#   perceptual  — Bobák/Čmolík/Čadík 2024 (PerceptPPO): T > B > R > TR > BR > L > TL > BL
#   geogebra    — NE-first, then cardinals/corners (familiar for .ggb imports)
POSITION_PRIORITY_ORDERS = {
    'classic':    [1, 3, 7, 5, 0, 4, 2, 6],
    'perceptual': [2, 6, 0, 1, 7, 4, 3, 5],
    'geogebra':   [1, 0, 2, 7, 3, 6, 4, 5],
}


def _ranks_from_order(order):
    """Direction-index → rank array (rank 0 = most preferred)."""
    ranks = np.full(8, float(len(order)), dtype=float)
    for rank, d in enumerate(order):
        ranks[int(d)] = float(rank)
    return ranks


POSITION_PRIORITY = {
    name: _ranks_from_order(order)
    for name, order in POSITION_PRIORITY_ORDERS.items()
}


def _resolve_position_priority(name):
    """Return the rank array for a named order, or None when disabled/unknown."""
    if not name:
        return None
    return POSITION_PRIORITY.get(str(name))


@dataclass
class LabelCostModel:
    """Candidate cost terms, decoupled from the solver (P0-C).

    Bundles the scoring so the greedy solver and the local-repair pass evaluate
    candidates identically (the "scorer ⟂ solver" principle —
    docs/archive/label_placement_research.md §6.3). Constructed with only ``weights`` +
    ``padding`` it reproduces :func:`_score_candidate` exactly, so the default
    code path and all snapshots are unchanged. Optional terms activate only when
    configured:

    - ``position_priority`` (rank array, lower=better) + ``w_pref`` adds the
      canonical a-priori position-preference term (P0-A — systematic placement);
    - ``soft_falloff_px`` > 0 adds a graded proximity penalty that decays with
      distance, so the solver always has a gradient and degrades gracefully
      instead of hitting flat plateaus (P0-B — CMS 1995, §6.1).
    """
    weights: tuple
    padding: float
    ptUnit: float = 1.0
    position_priority: Optional[np.ndarray] = None
    w_pref: float = 0.0
    soft_falloff_px: float = 0.0
    w_soft: float = 1.0
    w_inertia: float = 0.0
    w_fill: float = 0.0
    fills: tuple = ()
    geom_gap: float = 0.0
    w_assoc: float = 0.0
    anchors: Optional[np.ndarray] = None  # all label anchors (Nx2) for P-ASSOC
    seg_dashed: Optional[list] = None     # parallel dashed mask for P-DASHED
    dashed_factor: float = 1.0            # dashed-overlap cost multiplier (<1)

    def candidate_cost(self, center, hw, hh, placed, segments, circles, arc_pts,
                       preferred_dir, candidate_idx, current_center=None,
                       label_luminance=None, own_anchor=None,
                       cand_angle=None, pref_angle=None, seg_dashed=None) -> float:
        # ``seg_dashed`` override keeps the dashed mask aligned with a CULLED
        # ``segments`` subset (perf); falls back to the model's full mask.
        cost = _score_candidate(
            center, hw, hh, self.padding, placed, segments, circles, arc_pts,
            preferred_dir, candidate_idx, self.weights, geom_gap=self.geom_gap,
            seg_dashed=(seg_dashed if seg_dashed is not None else self.seg_dashed),
            dashed_factor=self.dashed_factor,
            cand_angle=cand_angle, pref_angle=pref_angle,
        )
        # Association (P-ASSOC, round-6): a label must read as belonging to ITS
        # object — never sit closer to a different labelled point than to its own
        # anchor (that creates a false visual attachment, e.g. label H landing by
        # point C). Penalise, in pixels, the amount by which the candidate is
        # closer to the nearest OTHER anchor than to its own.
        if self.w_assoc and self.anchors is not None and own_anchor is not None:
            cx, cy = float(center[0]), float(center[1])
            d_own = sqrt((cx - own_anchor[0]) ** 2 + (cy - own_anchor[1]) ** 2)
            ax, ay = self.anchors[:, 0], self.anchors[:, 1]
            other = np.hypot(ax - own_anchor[0], ay - own_anchor[1]) > 1e-6
            if other.any():
                d_other = float(np.min(np.hypot(ax[other] - cx, ay[other] - cy)))
                if d_other < d_own:
                    cost += self.w_assoc * (d_own - d_other) * self.ptUnit
        if self.position_priority is not None and self.w_pref:
            cost += self.w_pref * float(self.position_priority[candidate_idx])
        if self.soft_falloff_px > 0:
            cost += self.weights[2] * self.w_soft * self._soft_proximity(
                center, hw, hh, placed, segments, circles, arc_pts,
            )
        # Inertia (P1-D): penalise displacement from the existing manual/GGB
        # position so a good current placement is kept and the label does not
        # jump to the other side of its feature. Zero at the current position.
        if current_center is not None and self.w_inertia:
            dx = float(center[0]) - float(current_center[0])
            dy = float(center[1]) - float(current_center[1])
            cost += self.w_inertia * sqrt(dx * dx + dy * dy) * self.ptUnit
        # Fill contrast (P1-C): penalise sitting on an opaque fill whose
        # luminance is close to the label colour (hard to read).
        if self.w_fill and self.fills and label_luminance is not None:
            cost += self.w_fill * _fill_contrast_penalty(
                center, self.fills, label_luminance)
        return cost

    def max_overlap_free_cost(self) -> float:
        """Upper bound on the cost of an overlap-free candidate (early-break
        threshold for the nudge loop). Mirrors the legacy ``weights[0] * 4``
        plus the always-present preference/soft contributions."""
        base = self.weights[0] * 4.0
        if self.position_priority is not None and self.w_pref:
            base += self.w_pref * float(np.max(self.position_priority))
        if self.soft_falloff_px > 0:
            base += self.weights[2] * self.w_soft
        if self.w_fill and self.fills:
            base += self.w_fill
        return base

    def _soft_proximity(self, center, hw, hh, placed, segments, circles,
                        arc_pts) -> float:
        """exp(-gap/falloff) over the nearest obstacle gap (graded near-miss)."""
        cx, cy = float(center[0]), float(center[1])
        half = max(hw, hh) + self.padding
        best = float('inf')
        for pc, phw, phh in placed:
            d = sqrt((cx - pc[0]) ** 2 + (cy - pc[1]) ** 2) - half - max(phw, phh)
            best = min(best, d)
        for p1, p2 in segments:
            best = min(best, _point_segment_distance((cx, cy), p1, p2) - half)
        for cc, cr in circles:
            best = min(best, abs(sqrt((cx - cc[0]) ** 2 + (cy - cc[1]) ** 2) - cr) - half)
        if len(arc_pts) > 0:
            d = float(np.min(np.hypot(arc_pts[:, 0] - cx, arc_pts[:, 1] - cy))) - half
            best = min(best, d)
        if not np.isfinite(best):
            return 0.0
        gap_px = max(best, 0.0) * self.ptUnit
        return float(np.exp(-gap_px / self.soft_falloff_px))


@dataclass
class LabelInfo:
    name: str
    anchor: np.ndarray       # 2D point in scene coords
    half_w: float            # half-width of label bbox (scene MU)
    half_h: float            # half-height
    margin: float = 0.0      # extra distance from anchor (e.g. point visual radius)
    preferred_dir: int = 1   # computed: direction away from geometry density
    fixed_center: np.ndarray = None  # exact position (bypasses 8-candidate solver)
    fixed_anchor: str = None         # anchor string for fixed_center (e.g. 'MC')
    locked: bool = False
    current_center: np.ndarray = None  # existing (manual/GGB) label center, scene MU
                                       # (set only when respect_current_position is on)
    label_luminance: float = None      # resolved label-colour luminance 0..1
                                       # (set only when fill-contrast is on, P1-C)
    clear_radius: float = 0.0          # own point-marker clearance radius (FP-1),
                                       # scene MU; 0 for non-points
    bisector_dir: np.ndarray = None    # FP-3: exact unit direction of the widest
                                       # free gap between incident edges (points)
    blocked_wedges: tuple = ()         # R2: (start,end) rad angle-marker wedges at
                                       # this anchor; excluded by the direction
                                       # resolvers so labels avoid the marker


# ── Geometry helpers ──────────────────────────────────────────────────

def _bbox_overlap_area(cx1, cy1, hw1, hh1, cx2, cy2, hw2, hh2):
    """Intersection area of two AABBs: center (cx,cy) + half-sizes (hw,hh)."""
    dx = min(cx1 + hw1, cx2 + hw2) - max(cx1 - hw1, cx2 - hw2)
    dy = min(cy1 + hh1, cy2 + hh2) - max(cy1 - hh1, cy2 - hh2)
    if dx <= 0 or dy <= 0:
        return 0.0
    return dx * dy


def _point_in_bbox(px, py, cx, cy, hw, hh):
    """Check if point (px,py) is inside bbox centered at (cx,cy) with half-sizes."""
    return abs(px - cx) <= hw and abs(py - cy) <= hh


def _segment_bbox_overlap(p1, p2, cx, cy, hw, hh):
    """Exact length of segment p1→p2 inside an axis-aligned bbox (Liang-Barsky).

    Pure-Python float math — this is the placement hot path (hundreds of
    thousands of calls per dense layout); avoiding ``np.asarray``/``np.linalg.norm``
    per call cut a dense layout by ~3× (no behaviour change).
    """
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    dx, dy = x2 - x1, y2 - y1
    seg_len = sqrt(dx * dx + dy * dy)
    if seg_len <= 1e-12:
        return 0.0

    t0, t1 = 0.0, 1.0
    for delta, lo_p, lo, hi in ((dx, x1, cx - hw, cx + hw),
                                (dy, y1, cy - hh, cy + hh)):
        if -1e-12 <= delta <= 1e-12:
            if lo_p < lo or lo_p > hi:
                return 0.0
            continue
        a = (lo - lo_p) / delta
        b = (hi - lo_p) / delta
        if a > b:
            a, b = b, a
        if a > t0:
            t0 = a
        if b < t1:
            t1 = b
        if t0 >= t1:
            return 0.0

    return seg_len * (t1 - t0)


def _circle_bbox_intersects(circle_cx, circle_cy, circle_r, bbox_cx, bbox_cy, hw, hh):
    """Check if a circle (or arc) intersects an axis-aligned bbox.

    Returns True if the circle's circumference passes through or touches the bbox.
    Uses the nearest-point-on-bbox approach: find the closest point on the bbox
    to the circle center, then check if it's within radius range.
    """
    # Clamp circle center to bbox to find the nearest point on bbox boundary
    nearest_x = max(bbox_cx - hw, min(circle_cx, bbox_cx + hw))
    nearest_y = max(bbox_cy - hh, min(circle_cy, bbox_cy + hh))
    dist_nearest = (nearest_x - circle_cx) ** 2 + (nearest_y - circle_cy) ** 2

    # Farthest corner of bbox from circle center
    far_x = bbox_cx + hw if circle_cx < bbox_cx else bbox_cx - hw
    far_y = bbox_cy + hh if circle_cy < bbox_cy else bbox_cy - hh
    dist_farthest = (far_x - circle_cx) ** 2 + (far_y - circle_cy) ** 2

    r2 = circle_r ** 2
    # Circle passes through bbox if: nearest point is inside circle AND
    # farthest point is outside circle (or the whole bbox is inside the circle)
    # Simplified: circle intersects bbox if nearest_dist <= r² AND farthest_dist >= r²
    # OR if the center is inside the bbox
    center_inside = abs(circle_cx - bbox_cx) <= hw and abs(circle_cy - bbox_cy) <= hh
    return (dist_nearest <= r2 and dist_farthest >= r2) or center_inside


def _sample_arc(center, radius, angle_start, angle_span, n=12):
    """Return n sample points along a circular arc."""
    angles = np.linspace(angle_start, angle_start + angle_span, n)
    return np.column_stack([
        center[0] + radius * np.cos(angles),
        center[1] + radius * np.sin(angles),
    ])


def _point_segment_distance(p, a, b) -> float:
    """Shortest distance from 2D point ``p`` to segment ``a``→``b`` (scene MU)."""
    p = np.asarray(p, dtype=float)[:2]
    a = np.asarray(a, dtype=float)[:2]
    b = np.asarray(b, dtype=float)[:2]
    ab = b - a
    denom = float(ab @ ab)
    t = 0.0
    if denom > 1e-18:
        t = float(np.clip(((p - a) @ ab) / denom, 0.0, 1.0))
    proj = a + t * ab
    return float(np.linalg.norm(p - proj))


def _color_luminance(value, default=None):
    """Relative luminance in [0, 1] from a ``#rgb`` / ``#rrggbb`` hex string.

    Returns ``default`` for anything it cannot parse (named colours,
    ManimColor objects, ``None``) so the contrast feature degrades gracefully
    and ``label_placement`` stays import-light (no manim).
    """
    if not isinstance(value, str):
        return default
    s = value.strip().lstrip('#')
    try:
        if len(s) == 3:
            r, g, b = (int(c * 2, 16) for c in s)
        elif len(s) >= 6:
            r, g, b = (int(s[i:i + 2], 16) for i in (0, 2, 4))
        else:
            return default
    except ValueError:
        return default
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _point_in_polygon(p, verts) -> bool:
    """Ray-casting point-in-polygon test. ``verts`` is an (N, 2) array."""
    x, y = float(p[0]), float(p[1])
    n = len(verts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = verts[i][0], verts[i][1]
        xj, yj = verts[j][0], verts[j][1]
        if ((yi > y) != (yj > y)) and \
                (x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_disk(p, center, radius) -> bool:
    return (float(p[0]) - center[0]) ** 2 + (float(p[1]) - center[1]) ** 2 <= radius ** 2


def _candidate_has_overlap(center, hw_p, hh_p, segments, circles, arc_pts,
                           placed=(), geom_gap=0.0) -> bool:
    """True if a (padded) label bbox at ``center`` overlaps any obstacle.

    Shared by the greedy difficulty pre-pass (``placed=()``), the repair pass
    and the consistency pass so the "is this position free?" test is defined in
    exactly one place. ``hw_p``/``hh_p`` are already padding-inflated. ``geom_gap``
    (FP-2) additionally inflates the bbox against *geometry* (segments/circles/
    points) so labels keep a clearance from lines and circles, not just avoid
    crossing them — but does NOT inflate against other labels.
    """
    cx, cy = center[0], center[1]
    for pc, phw, phh in placed:
        if _bbox_overlap_area(cx, cy, hw_p, hh_p, pc[0], pc[1], phw, phh) > 0:
            return True
    ghw, ghh = hw_p + geom_gap, hh_p + geom_gap
    for p1, p2 in segments:
        if _segment_bbox_overlap(p1, p2, cx, cy, ghw, ghh) > 0:
            return True
    for cc, cr in circles:
        if _circle_bbox_intersects(cc[0], cc[1], cr, cx, cy, ghw, ghh):
            return True
    if len(arc_pts) > 0:
        inside_x = np.abs(arc_pts[:, 0] - cx) <= ghw
        inside_y = np.abs(arc_pts[:, 1] - cy) <= ghh
        if np.any(inside_x & inside_y):
            return True
    return False


# ── Obstacle collection ──────────────────────────────────────────────

def _scene_bounds_corners(scene, padding=0.1):
    """Return renderer-compatible viewport corners for line/ray clipping."""
    get_bounds = getattr(scene, '_get_scene_bounds', None)
    if callable(get_bounds):
        try:
            left, bottom, right, top = get_bounds(padding=padding)
            return [(left, bottom), (right, top)]
        except Exception:
            logger.debug("Could not read scene bounds for label obstacles", exc_info=True)
    return None


def _clipped_line_endpoints(scene, line_data):
    """Return visible line/ray endpoints using the same clipping API as rendering."""
    corners = _scene_bounds_corners(scene)
    if corners is None:
        return None
    get_endpoints = getattr(line_data, 'get_endpoints', None)
    if not callable(get_endpoints):
        return None
    endpoints = get_endpoints(corners)
    if endpoints is None:
        return None
    return [np.asarray(p, dtype=float)[:2] for p in endpoints]


def _is_dashed(scene, elem) -> bool:
    """True when an element is rendered dashed (carries ``stroke_dash_ratio``).
    Used for P-DASHED: overlapping a dashed line is preferable to a solid one."""
    r = _resolve_style(scene, elem, 'stroke_dash_ratio', default=None)
    try:
        return r is not None and float(r) > 0
    except (TypeError, ValueError):
        return False


def _collect_obstacles(scene, *, angle_marker_obstacle=False):
    """Collect obstacles: segments, circles (center+radius), and loose points.

    Returns ``(segments, circles, arc_pts, seg_dashed)`` where ``seg_dashed`` is a
    boolean list parallel to ``segments`` (True = dashed line, for P-DASHED). The
    segment elements stay 2-tuples ``(p1, p2)`` so all geometry consumers are
    unchanged; only the cost reads the parallel mask.

    ``angle_marker_obstacle`` (R1, default False → byte-identical): when True the
    drawn angle marker (right-angle square / arc) is registered at its *real*
    rendered pixel radius via :func:`_angle_marker_obstacle_segments` instead of
    the legacy coarse ``0.3·min(arm)`` arc approximation.
    """
    from .geo import lib_elements as geo

    segments = []   # list of (p1, p2) as 2D arrays
    seg_dashed = []  # parallel bool list (True = dashed)
    circles = []    # list of (center_2d, radius)
    circ_dashed = []  # parallel bool list (True = dashed circle/arc)
    arc_pts = []    # loose sample points (for points, angle arcs, etc.)

    for elem in scene.geo.elements:
        if not _resolve_style(scene, elem, 'visible', default=getattr(elem, 'visible', True)):
            continue
        d = elem.data
        dashed = _is_dashed(scene, elem)
        if isinstance(d, geo.Point):
            arc_pts.append(d.coords[:2])
        elif isinstance(d, geo.Segment):
            segments.append((d.endpoints[0][:2].copy(), d.endpoints[1][:2].copy()))
            seg_dashed.append(dashed)
        elif isinstance(d, (geo.Line, geo.Ray)):
            endpoints = _clipped_line_endpoints(scene, d)
            if endpoints is not None:
                segments.append((endpoints[0].copy(), endpoints[1].copy()))
                seg_dashed.append(dashed)
        elif isinstance(d, (geo.Arc, geo.CircleSector)):   # BEFORE Circle: both subclass it
            # Register the ARC ITSELF, not its full circle: the phantom part of
            # the circle blocked free space the reader sees as empty (В's label
            # sat past the arc's endpoint, yet the solid-circle rescue kicked it
            # to the other side — TZ-label-offset-ggb-fidelity §5.3). Sampled as
            # a polyline over the actual angular span, like angle markers.
            a_start, a_end = d.angles
            span = (a_end - a_start) % (2 * pi)
            if span < 1e-9:
                circles.append((d.center[:2].copy(), d.radius))
                circ_dashed.append(dashed)
            else:
                n = max(8, int(span / (pi / 12)))
                pts = _sample_arc(d.center[:2], d.radius, a_start, span, n)
                for k in range(len(pts) - 1):
                    segments.append((pts[k], pts[k + 1]))
                    seg_dashed.append(dashed)
                if isinstance(d, geo.CircleSector):
                    c2 = d.center[:2].copy()
                    segments.append((c2, pts[0].copy()))
                    seg_dashed.append(dashed)
                    segments.append((c2.copy(), pts[-1].copy()))
                    seg_dashed.append(dashed)
        elif isinstance(d, geo.Circle):
            circles.append((d.center[:2].copy(), d.radius))
            circ_dashed.append(dashed)
        elif isinstance(d, geo.Angle):
            if angle_marker_obstacle:
                # R1: the real drawn marker (square for a right angle, arc
                # otherwise) at its rendered pixel radius — mirrors _render_angle.
                for (q1, q2) in _angle_marker_obstacle_segments(scene, elem):
                    segments.append((q1, q2))
                    seg_dashed.append(dashed)
            else:
                r_ang = min(np.linalg.norm(d.side1), np.linalg.norm(d.side2)) * 0.3
                pts = _sample_arc(d.vertex[:2], r_ang, d.start_angle, d.size, 12)
                for k in range(len(pts) - 1):
                    segments.append((pts[k], pts[k + 1]))
                    seg_dashed.append(dashed)
        elif isinstance(d, geo.Polygon):
            pts = d.vertices
            for i in range(len(pts)):
                segments.append((pts[i][:2].copy(), pts[(i + 1) % len(pts)][:2].copy()))
                seg_dashed.append(dashed)
        elif isinstance(d, geo.Vector):
            if hasattr(d, 'endpoints') and d.endpoints is not None:
                segments.append((d.endpoints[0][:2].copy(), d.endpoints[1][:2].copy()))
                seg_dashed.append(dashed)

    arc_pts_arr = np.array(arc_pts) if arc_pts else np.empty((0, 2))
    return segments, circles, arc_pts_arr, seg_dashed, circ_dashed


def _angle_drawn_sector(scene, elem):
    """Geometry of the marker the renderer actually draws for an ``Angle`` (R1/R3).

    Mirrors ``animageo._render_angle`` / :func:`_angle_render_label_radius_px`:
    the right-angle detection, the real pixel radius (``right_angle_size_px/√2``
    for a square, the outer arc radius otherwise, with ``overlay.angle_radius``
    auto-scaling and multi-arc expansion), and the drawn sector start/span
    including the minor/reflex clockwise flip.

    Returns ``(vertex_2d, start_rad, span_rad, is_right, radius_mu, side1, side2)``
    or ``None`` for a degenerate (zero-length-arm) angle.
    """
    d = elem.data
    ptUnit = _style_ptUnit(scene.style)
    angle_range = _resolve_style(scene, elem, 'angle_range', default='minor') or 'minor'
    arc_size_resolved = _resolve_style(scene, elem, 'arc_size_px', default=17.0)
    base_arc = compute_effective_arc_size_px(
        elem, d, scene.style, base_px=arc_size_resolved, angle_range=angle_range,
        auto_radius=_resolve_style(scene, elem, 'auto_radius', default=True))
    ang_rshift_px = scene.style_config.defaults.get('angle', 'arc_shift_px', 0.0)
    lines = int(_resolve_style(scene, elem, 'tick_count', default=1) or 1)
    outer_arc_px = _angle_effective_arc_r_px(base_arc, lines, ang_rshift_px)
    render_r_px = _angle_render_label_radius_px(
        scene, elem, base_arc, outer_arc_px, angle_range)

    effective_angle = _effective_render_angle(d.size, angle_range)
    right_mark = _resolve_style(scene, elem, 'right_angle_marker', default=None)
    if right_mark is None:
        right_mark = bool(np.isclose(effective_angle, pi / 2))

    v = np.asarray(d.vertex[:2], dtype=float)
    s1 = np.asarray(d.side1[:2], dtype=float)
    s2 = np.asarray(d.side2[:2], dtype=float)
    if np.linalg.norm(s1) < 1e-9 or np.linalg.norm(s2) < 1e-9:
        return None

    size = float(d.size)
    start = float(d.start_angle)
    if angle_range == 'minor' and size > pi:
        start = float(atan2(s2[1], s2[0]))
        span = 2 * pi - size
    elif angle_range == 'reflex' and size < pi:
        start = float(atan2(s2[1], s2[0]))
        span = 2 * pi - size
    else:
        span = size

    radius_mu = (render_r_px if right_mark else outer_arc_px) / ptUnit
    return v, start % (2 * pi), span, right_mark, radius_mu, s1, s2


def _angle_marker_obstacle_segments(scene, elem):
    """Obstacle segments for the drawn angle marker (R1).

    Right angle → the two OUTER edges of the square marker (the two inner edges
    lie along the arms, which are already obstacle segments). Otherwise → the arc
    polyline. All at the real rendered radius from :func:`_angle_drawn_sector`.
    """
    info = _angle_drawn_sector(scene, elem)
    if info is None:
        return []
    v, start, span, is_right, r, s1, s2 = info
    if is_right:
        n1 = s1 * (r / np.linalg.norm(s1))
        n2 = s2 * (r / np.linalg.norm(s2))
        p1 = v + n1
        p2 = p1 + n2
        p3 = v + n2
        return [(p1, p2), (p2, p3)]
    pts = _sample_arc(v, r, start, span, 12)
    return [(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]


def _collect_angle_marker_wedges(scene):
    """Drawn-sector wedges of every visible angle marker, as ``(vertex_2d, start,
    end)`` rad (R2). A point label whose anchor matches a vertex treats that
    vertex's wedge(s) as blocked so it is not placed onto the marker."""
    from .geo import lib_elements as geo

    out = []
    for elem in scene.geo.elements:
        if not isinstance(elem.data, geo.Angle):
            continue
        if not _resolve_style(scene, elem, 'visible',
                              default=getattr(elem, 'visible', True)):
            continue
        info = _angle_drawn_sector(scene, elem)
        if info is None:
            continue
        v, start, span, *_ = info
        out.append((v, start, (start + span) % (2 * pi)))
    return out


def _cull_obstacles(segments, seg_dashed, circles, arc_pts, anchor, reach):
    """Return the obstacles within ``reach`` of ``anchor`` — the only ones that
    can overlap any candidate for that label. Exact (every candidate bbox stays
    within ``reach`` of the anchor by construction), just faster: in a dense scene
    a label sees ~20 local segments instead of all ~244, cutting the O(cands ×
    segments) hot loop by ~10× (2 s → ~0.2 s on scene6a/10-4_). Returns culled
    ``(segments, seg_dashed, circles, arc_pts)`` with ``seg_dashed`` kept aligned.
    """
    a0, a1 = float(anchor[0]), float(anchor[1])
    lsegs, ldash = [], ([] if seg_dashed is not None else None)
    for i in range(len(segments)):
        p1, p2 = segments[i]
        if _point_segment_distance((a0, a1), p1, p2) <= reach:
            lsegs.append(segments[i])
            if ldash is not None:
                ldash.append(seg_dashed[i] if i < len(seg_dashed) else False)
    lcirc = [(cc, cr) for (cc, cr) in circles
             if abs(sqrt((a0 - cc[0]) ** 2 + (a1 - cc[1]) ** 2) - cr) <= reach]
    if len(arc_pts) > 0:
        m = np.hypot(arc_pts[:, 0] - a0, arc_pts[:, 1] - a1) <= reach
        larc = arc_pts[m]
    else:
        larc = arc_pts
    return lsegs, ldash, lcirc, larc


# Luminance gap (0..1) above which a label/fill pair is considered legible; the
# fill-contrast penalty fades to zero once the gap reaches this.
FILL_CONTRAST_OK = 0.45


def _collect_fills(scene):
    """Collect filled regions for the contrast-aware penalty (P1-C).

    Returns a list of ``(kind, geom, opacity, luminance)`` where ``kind`` is
    ``'poly'`` (geom = (N,2) vertices) or ``'disk'`` (geom = (center_2d,
    radius)). Only visible elements with ``fill_opacity > 0`` are included.
    Luminance is parsed from the resolved ``fill`` hex colour (0.5 when
    unknown). Separate from :func:`_collect_obstacles` so its 3-tuple return
    (and the tests pinning it) stay unchanged.
    """
    from .geo import lib_elements as geo

    fills = []
    for elem in scene.geo.elements:
        if not _resolve_style(scene, elem, 'visible',
                              default=getattr(elem, 'visible', True)):
            continue
        try:
            op = float(_resolve_style(scene, elem, 'fill_opacity', default=0) or 0)
        except (TypeError, ValueError):
            op = 0.0
        if op <= 0:
            continue
        lum = _color_luminance(_resolve_style(scene, elem, 'fill', default=None),
                               default=0.5)
        d = elem.data
        if isinstance(d, geo.Polygon):
            fills.append(('poly', np.asarray(d.vertices)[:, :2].copy(), op, lum))
        elif isinstance(d, geo.CircleSector):
            a_start, a_end = d.angles
            pts = _sample_arc(d.center[:2], d.radius, a_start, a_end - a_start, 18)
            poly = np.vstack([np.asarray(d.center[:2]).reshape(1, 2), pts])
            fills.append(('poly', poly, op, lum))
        elif isinstance(d, geo.Circle):
            fills.append(('disk', (d.center[:2].copy(), float(d.radius)), op, lum))
    return fills


def _fill_contrast_penalty(center, fills, label_lum) -> float:
    """Sum of ``opacity × low-contrast-badness`` over fills containing ``center``.

    Badness is 1 when the fill and label luminances match and fades to 0 as
    their gap reaches ``FILL_CONTRAST_OK`` — i.e. a dark label on a dark, opaque
    fill is penalised most, while a light/transparent fill barely matters.
    """
    if label_lum is None:
        return 0.0
    total = 0.0
    for kind, geom, op, lum in fills:
        inside = (_point_in_polygon(center, geom) if kind == 'poly'
                  else _point_in_disk(center, geom[0], geom[1]))
        if inside:
            badness = max(0.0, 1.0 - abs(lum - label_lum) / FILL_CONTRAST_OK)
            total += op * badness
    return total


def _all_obstacle_points(segments, arc_pts, density=30):
    """Flatten all obstacles into a point cloud (for density computation)."""
    pts = list(arc_pts) if len(arc_pts) > 0 else []
    for p1, p2 in segments:
        n = max(4, int(np.linalg.norm(p2 - p1) * density) + 1)
        n = min(n, 80)
        t = np.linspace(0, 1, n).reshape(-1, 1)
        pts.extend(p1 + t * (p2 - p1))
    return np.array(pts) if pts else np.empty((0, 2))


# ── Label collection ─────────────────────────────────────────────────

def _get_anchor(elem, scene=None):
    """Return the 2D anchor point for a label based on element type."""
    from .geo import lib_elements as geo

    d = elem.data
    if isinstance(d, geo.Point):
        return d.coords[:2].copy()
    elif isinstance(d, geo.Segment):
        return ((d.endpoints[0] + d.endpoints[1]) / 2)[:2]
    elif isinstance(d, geo.Angle):
        return d.vertex[:2].copy()
    elif isinstance(d, (geo.Circle, geo.Arc, geo.CircleSector)):
        return d.center[:2].copy()
    elif isinstance(d, (geo.Line, geo.Ray)):
        if scene is not None:
            endpoints = _clipped_line_endpoints(scene, d)
            if endpoints is not None:
                return ((endpoints[0] + endpoints[1]) / 2)[:2]
        return np.zeros(2)
    elif isinstance(d, geo.Polygon):
        return np.mean(d.vertices[:, :2], axis=0)
    elif isinstance(d, geo.Vector):
        if hasattr(d, 'endpoints') and d.endpoints is not None:
            return ((d.endpoints[0] + d.endpoints[1]) / 2)[:2]
    return np.zeros(2)


def _compute_preferred_dir(anchor, obstacle_cloud, radius=2.0):
    """Compute preferred direction: AWAY from local geometry density.

    Finds the centroid of obstacle points within `radius` of the anchor,
    then returns the direction index (0-7) pointing away from that centroid.
    Falls back to NE (index 1) if no obstacles are nearby.
    """
    if len(obstacle_cloud) == 0:
        return 1  # default NE

    diffs = obstacle_cloud - anchor
    dists = np.linalg.norm(diffs, axis=1)
    mask = dists < radius
    if mask.sum() == 0:
        return 1

    # Weight by inverse distance (closer obstacles matter more)
    weights = 1.0 / (dists[mask] + 0.01)
    centroid = np.average(diffs[mask], axis=0, weights=weights)

    if np.linalg.norm(centroid) < 1e-6:
        return 1

    # Direction AWAY from centroid
    away_angle = atan2(-centroid[1], -centroid[0])
    if away_angle < 0:
        away_angle += 2 * pi

    # Snap to nearest of 8 directions
    idx = int(round(away_angle / (pi / 4))) % 8
    return idx


def compute_angle_label_center(ang, angle_params: AngleParams,
                               ptUnit: float) -> np.ndarray:
    """Analytical center of an angle label along the current bisector.

    Pure function of the Angle element's live fields (``ang.vertex, ang.side1, ang.side2,
    ang.size``) and cached ``AngleParams``. Safe to call every frame during
    animation — output is a continuous function of v1/v2/p, so no jumps.

    The two gap parameters on ``angle_params`` have independent roles:
    - ``gap_arc_px`` sets the clearance between the outer arc and the label:
      ``dist = arc_r + max(hw, hh) + gap_arc``.
    - ``gap_sides_px`` enters the narrow-angle clamp
      ``dist ≥ (half_diag + gap_sides) / sin(half_angle)`` which pushes the
      label further along the bisector as the two sides converge, keeping
      the bbox clear of both sides.

    ``arc_r_px`` is expected to be the **effective** outer radius — i.e.
    already inflated for multi-arc style (``lines > 1``) at layout time.

    Returns 2D center position in scene MU.
    """
    v1n = ang.side1[:2] / (np.linalg.norm(ang.side1[:2]) + 1e-12)
    v2n = ang.side2[:2] / (np.linalg.norm(ang.side2[:2]) + 1e-12)
    bisector = v1n + v2n
    bis_len = np.linalg.norm(bisector)
    if bis_len > 1e-6:
        bisector = bisector / bis_len
    else:
        bisector = v1n

    # For angle_range='reflex' (rendering the reflex side) the label lives on
    # the OPPOSITE side from the v1n+v2n bisector — flip direction.
    if angle_params.angle_range == 'reflex':
        bisector = -bisector
    # FP-8: a manual label placed outside the wedge stays outside.
    if angle_params.exterior:
        bisector = -bisector

    arc_r = angle_params.arc_r_px / ptUnit
    hw = angle_params.half_w
    hh = angle_params.half_h
    gap_arc = angle_params.gap_arc_px / ptUnit

    # FP-8 + round-6: on the EXTERIOR side there is no arc to clear and the wedge
    # opens away from the label, so place it close to the vertex (just its own
    # half-extent + a small gap) and skip the narrow-angle clamp below (which
    # assumes the label sits between converging interior sides). Without this the
    # exterior label inherited the interior distance (arc_r + clamp/​sin(θ/2)) and
    # flew far off the vertex ("почему 45 так далеко уехала?").
    if angle_params.exterior:
        return ang.vertex[:2] + bisector * (max(hw, hh) + gap_arc)

    base_dist = arc_r + max(hw, hh) + gap_arc
    dist = base_dist

    # Narrow-angle clamp uses the ANGLE-AS-DRAWN. For angle_range='minor' this
    # is the supplementary when raw is reflex; for angle_range='reflex' the
    # angle is always wide, so the clamp effectively disables itself
    # (half_angle > π/2 → sin() still positive but large → min_dist small).
    effective_angle = _effective_render_angle(ang.size, angle_params.angle_range)
    half_angle = effective_angle / 2
    if 0.01 < half_angle < pi / 2:
        half_diag = np.sqrt(hw * hw + hh * hh)
        min_clearance = half_diag + angle_params.gap_sides_px / ptUnit
        min_dist = min_clearance / sin(half_angle)
        # ``1/sin(half_angle)`` blows up as the angle → 0, so a value-label on a
        # shrinking angle (e.g. during an animation) would fly far off the
        # marker. Cap the narrow-angle push to a few times the base distance so
        # the label stays a reasonable distance from the vertex (it may then
        # slightly overlap the near-parallel sides — preferable to flying away).
        max_dist = base_dist * ANGLE_LABEL_NARROW_MAX_FACTOR
        dist = max(base_dist, min(min_dist, max_dist))

    # Round-10 (scene4): a narrow angle's wide value label ("30.4°") gets a large
    # narrow-clamp distance (∝ label width / sin(θ/2)) and flies far down the
    # bisector into the figure — landing closer to a NEIGHBOURING angle's vertex
    # than to its own (false attachment). Cap the distance to a fraction of the
    # shorter arm so the label stays near ITS vertex (it may then touch the near
    # sides — preferable to reading as another angle's label).
    if angle_params.max_arm_fraction is not None:
        min_arm = min(float(np.linalg.norm(ang.side1[:2])),
                      float(np.linalg.norm(ang.side2[:2])))
        if min_arm > 1e-9:
            arm_cap = angle_params.max_arm_fraction * min_arm
            dist = min(dist, max(arm_cap, arc_r + gap_arc))

    return ang.vertex[:2] + bisector * dist


def compute_angle_label_base_center(ang, angle_params: AngleParams,
                                    ptUnit: float) -> np.ndarray:
    """Renderer base point for an angle label before ``label_offset_px``.

    ``_render_angle`` places labels at the midpoint of the rendered marker
    radius, then applies ``label_offset_px``. Auto-placement computes an
    absolute desired center, so the stored offset must be relative to this
    base point rather than relative to the angle vertex.
    """
    v1n = ang.side1[:2] / (np.linalg.norm(ang.side1[:2]) + 1e-12)
    v2n = ang.side2[:2] / (np.linalg.norm(ang.side2[:2]) + 1e-12)
    bisector = v1n + v2n
    bis_len = np.linalg.norm(bisector)
    if bis_len > 1e-6:
        bisector = bisector / bis_len
    else:
        bisector = v1n

    if angle_params.angle_range == 'reflex':
        bisector = -bisector
    if angle_params.exterior:
        bisector = -bisector

    render_r_px = (angle_params.render_r_px
                   if angle_params.render_r_px is not None
                   else angle_params.arc_r_px)
    return ang.vertex[:2] + bisector * (render_r_px / ptUnit)


def compute_angle_label_offset_px(ang, angle_params: AngleParams,
                                  ptUnit: float, ptUnit_ggb: float) -> tuple[float, float]:
    """Return ``label_offset_px`` that makes the renderer hit the target.

    The renderer (`_render_angle`) always measures ``label_offset_px`` from the
    midpoint of the INTERIOR marker arc, so for an exterior target the offset is
    computed against that interior base — not the (mirrored) exterior base — or
    the renderer would land the label ``2·render_r`` off, back inside the wedge.
    """
    center = compute_angle_label_center(ang, angle_params, ptUnit)
    if angle_params.exterior:
        import dataclasses
        base_params = dataclasses.replace(angle_params, exterior=False)
    else:
        base_params = angle_params
    base = compute_angle_label_base_center(ang, base_params, ptUnit)
    off = center - base
    return (float(off[0] * ptUnit_ggb), float(off[1] * ptUnit_ggb))


def _angle_manual_exterior(scene, elem, angle_range, render_r_px, ptUnit,
                           ptUnit_ggb, respect_current, respect_min_offset_px) -> bool:
    """Decide whether a manual angle label should stay OUTSIDE the wedge (FP-8).

    Returns True only when ``respect_current`` is on, the angle carries a
    substantive (non-auto-placed) ``label_offset_px``, and the resulting label
    center sits on the far side of the vertex from the interior bisector — i.e.
    the user deliberately placed the label outside a (typically narrow) angle.
    Otherwise False, so default placement is unchanged.
    """
    if not respect_current or elem.style.get('_auto_placed'):
        return False
    # Read through the resolver so GGB-imported offsets (which live in the
    # style-config layer, not ``elem.style``) are seen.
    off = _resolve_style(scene, elem, 'label_offset_px', default=None)
    if off is None:
        return False
    if (float(off[0]) ** 2 + float(off[1]) ** 2) ** 0.5 < respect_min_offset_px:
        return False

    ang = elem.data
    v1n = ang.side1[:2] / (np.linalg.norm(ang.side1[:2]) + 1e-12)
    v2n = ang.side2[:2] / (np.linalg.norm(ang.side2[:2]) + 1e-12)
    bis = v1n + v2n
    nb = np.linalg.norm(bis)
    bis = bis / nb if nb > 1e-6 else v1n
    if angle_range == 'reflex':
        bis = -bis

    # Interior base point the renderer measures the manual offset from.
    base = ang.vertex[:2] + bis * (render_r_px / ptUnit)
    existing_center = base + np.array(
        [off[0] / ptUnit_ggb, off[1] / ptUnit_ggb], dtype=float)
    side = float(np.dot(existing_center - ang.vertex[:2], bis))
    return side < 0.0


DEFAULT_ANGLE_RADIUS_CONFIG = {
    'enabled': False,
    'exp': 0.25,              # scale factor is (pivot / angle)**exp
    'pivot_rad': pi / 2,      # angle at which scale = 1 (no change)
    'min_px': 12,             # lower floor on arc radius
    'max_arm_fraction': 0.65, # upper cap as fraction of shortest arm (pixels)
    'apply_to_right': False,  # also scale right-angle markers
}


def _effective_render_angle(raw_angle: float, angle_range: str = 'minor') -> float:
    """Return the angle measure that the renderer actually draws.

    Mirrors the `angle_range` handling in `animageo.CreateMObject`:
    - angle_range='minor' (default): renders the non-reflex (≤π) sector.
      If raw angle is reflex, flips to the supplementary `2π - raw`.
    - angle_range='reflex': renders the reflex (>π) sector. If raw is
      non-reflex, flips to `2π - raw`.

    Both auto-radius scaling and the narrow-angle clamp in
    ``compute_angle_label_center`` need this "as-drawn" measure — not the
    raw CCW span — because the narrow-side geometry is what pinches the
    arc and pushes the label.
    """
    raw = float(raw_angle)
    if angle_range == 'minor' and raw > pi:
        return 2 * pi - raw
    if angle_range == 'reflex' and raw < pi:
        return 2 * pi - raw
    return raw


def compute_effective_arc_size_px(
    elem, ang_data, scene_style, *, base_px: float = None,
    angle_range=None, auto_radius=None,
) -> float:
    """Resolve the base arc radius for an angle, with optional auto-scaling.

    When ``overlay.angle_radius.enabled=False`` (default), returns the raw
    ``elem.style['arc_size_px']`` unchanged — byte-for-byte identical to the
    previous behavior on GGB imports.

    When enabled, scales by ``(pivot / angle)**exp`` (narrower angles get a
    bigger radius so the arc doesn't disappear between close sides), then
    clamps to ``[min_px, max_arm_fraction * min(|v1|, |v2|) * ptUnit]``.

    Per-element ``elem.style['auto_radius'] = False`` opts out and returns
    the raw value, even when the global switch is on — escape hatch for
    manual overrides.

    ``base_px`` (optional): pre-resolved base radius, typically from the
    style resolver. When given, replaces direct ``elem.style`` lookup.
    This lets the renderer use builtin-defaults / overlay values for DSL
    angles whose ``elem.style`` is empty, without seeding elem.style.
    """
    base = float(base_px if base_px is not None
                 else elem.style.get('arc_size_px', 30))
    cfg = _overlay_angle_radius_config(scene_style)
    if not cfg.get('enabled', DEFAULT_ANGLE_RADIUS_CONFIG['enabled']):
        return base
    if auto_radius is None:
        auto_radius = elem.style.get('auto_radius', True)
    if auto_radius is False:
        return base

    exp = float(cfg.get('exp', DEFAULT_ANGLE_RADIUS_CONFIG['exp']))
    pivot = float(cfg.get('pivot_rad', DEFAULT_ANGLE_RADIUS_CONFIG['pivot_rad']))
    min_px = float(cfg.get('min_px', DEFAULT_ANGLE_RADIUS_CONFIG['min_px']))
    max_frac = float(cfg.get('max_arm_fraction',
                             DEFAULT_ANGLE_RADIUS_CONFIG['max_arm_fraction']))

    # Scale against the ANGLE-AS-DRAWN (supplementary when renderer flips).
    # Using raw ang.size would under-scale reflex cases where the visible
    # arc actually lives on the narrow supplementary side.
    angle_range = angle_range or elem.style.get('angle_range', 'minor') or 'minor'
    angle = max(_effective_render_angle(ang_data.size, angle_range), 0.01)
    scaled = base * (pivot / angle) ** exp

    style = getattr(scene_style, 'style', scene_style)
    ptUnit = _style_ptUnit(style)
    arm_min = float(min(np.linalg.norm(ang_data.side1), np.linalg.norm(ang_data.side2)))
    max_px = max_frac * arm_min * ptUnit

    lo = min_px
    hi = max(max_px, lo)  # guard degenerate arm_min ≈ 0
    return float(np.clip(scaled, lo, hi))


def _angle_effective_arc_r_px(base_arc_px: float, lines: int,
                              ang_rshift_px: float) -> float:
    """Outer arc radius in pixels including multi-arc expansion.

    Mirrors the renderer in ``animageo.py:CreateMObject``: with ``lines`` N,
    the outer radius is ``base_arc_px + (N - 1) * ang_rshift``.
    ``ang_rshift_px`` is ``scene.style.ang_rshift`` — in the same unit as
    ``base_arc_px`` (both get divided by ``ptUnit`` at render time).
    """
    lines = int(lines or 1)
    if lines <= 1:
        return base_arc_px
    return base_arc_px + (lines - 1) * ang_rshift_px


def _angle_render_label_radius_px(
    scene, elem, base_arc_px: float, outer_arc_px: float, angle_range: str,
) -> float:
    """Mirror ``_render_angle``'s label radius before label radial offset."""
    effective_angle = _effective_render_angle(elem.data.size, angle_range)
    right_mark = _resolve_style(scene, elem, 'right_angle_marker', default=None)
    if right_mark is None:
        right_mark = np.isclose(effective_angle, pi / 2)

    if not right_mark:
        return outer_arc_px

    ar_cfg = scene.style_config.overlay.angle_radius
    if ar_cfg.get('enabled', False) and ar_cfg.get('apply_to_right', False):
        right_px = compute_effective_arc_size_px(
            elem, elem.data, scene.style, base_px=base_arc_px,
            angle_range=angle_range,
            auto_radius=_resolve_style(scene, elem, 'auto_radius', default=True),
        )
    else:
        right_px = _resolve_style(scene, elem, 'right_angle_size_px', default=base_arc_px)
    return float(right_px) / sqrt(2)


def _collect_labels(scene, font_size, gap_arc_px=3, gap_sides_px=3, point_gap_px=0.0):
    """Collect LabelInfo for all visible elements with label_visible=True."""
    from .geo import lib_elements as geo

    ptUnit = _style_ptUnit(scene.style)
    ang_rshift_px = scene.style_config.defaults.get('angle', 'arc_shift_px', 0.0)
    scene_style = scene.style

    labels = []
    for elem in scene.geo.elements:
        if (not _resolve_style(scene, elem, 'visible', default=getattr(elem, 'visible', True))
                or _resolve_style(scene, elem, 'label_visible', default=False) != True):
            continue
        if _resolve_style(scene, elem, 'label_placement_locked', default=False):
            continue

        label_text = resolve_label_text(scene, elem)
        # Match the renderer: label size is the canonical pixel-unit
        # ``font_size_px`` resolved through the style layers.
        fs_px = _resolve_style(scene, elem, 'font_size_px', default=14.0)
        from .constants import GGB_FONT_SCALE
        font_px = fs_px * GGB_FONT_SCALE / ptUnit
        tex_w, tex_h = _measure_label_bbox(label_text, font_px)
        hw = tex_w / 2
        hh = tex_h / 2

        # Compute margin and preferred direction per element type
        margin = 0.0

        point_clear_radius = 0.0
        if isinstance(elem.data, geo.Point):
            point_size = _resolve_style(scene, elem, 'size_px', default=6.0)
            # FP-1: clear the drawn marker (radius) plus a fixed visible gap, so
            # the label never touches the dot — important for large points.
            margin = (point_size / 2 + point_gap_px) / ptUnit
            point_clear_radius = margin  # = marker radius + gap, in scene MU

        elif isinstance(elem.data, geo.Angle):
            # Angle labels: exact position along bisector, past the arc.
            # Delegate to the extracted pure helper so the math stays in one
            # place and can be reused per-frame during animation.
            anchor_pt = _get_anchor(elem, scene)
            angle_range = _resolve_style(scene, elem, 'angle_range', default='minor') or 'minor'
            base_arc_px = _resolve_style(scene, elem, 'arc_size_px', default=30)
            base_arc = compute_effective_arc_size_px(
                elem, elem.data, scene_style, base_px=base_arc_px,
                angle_range=angle_range,
                auto_radius=_resolve_style(scene, elem, 'auto_radius', default=True),
            )
            lines = int(_resolve_style(scene, elem, 'tick_count', default=1) or 1)
            outer_arc_px = _angle_effective_arc_r_px(base_arc, lines, ang_rshift_px)
            render_r_px = _angle_render_label_radius_px(
                scene, elem, base_arc, outer_arc_px, angle_range,
            )
            # The label target (arc_r_px) must hug the marker that's actually
            # drawn. For a right angle that's the square marker, whose outer
            # corner sits at ``right_angle_size_px`` (== render_r_px * sqrt(2)) —
            # NOT the non-right arc radius. Using outer_arc_px here detaches the
            # label and floats it out at the phantom arc distance whenever
            # right_angle_size_px differs from arc_size_px (or auto-radius has
            # enlarged the arc). Mirrors the right-mark test in _render_angle /
            # _angle_render_label_radius_px.
            effective_angle = _effective_render_angle(elem.data.size, angle_range)
            right_mark = _resolve_style(scene, elem, 'right_angle_marker', default=None)
            if right_mark is None:
                right_mark = bool(np.isclose(effective_angle, pi / 2))
            target_arc_px = (render_r_px * sqrt(2)) if right_mark else outer_arc_px
            label_radial_offset_px = _resolve_style(
                scene, elem, 'label_radial_offset_px', default=0.0,
            )
            ap = AngleParams(
                arc_r_px=target_arc_px,
                half_w=hw,
                half_h=hh,
                gap_arc_px=gap_arc_px,
                gap_sides_px=gap_sides_px,
                angle_range=angle_range,
                render_r_px=float(render_r_px) + float(label_radial_offset_px or 0.0),
            )
            fc = compute_angle_label_center(elem.data, ap, ptUnit)

            labels.append(LabelInfo(
                name=elem.name,
                anchor=anchor_pt,
                half_w=hw,
                half_h=hh,
                fixed_center=fc,
                fixed_anchor='MC',
            ))
            continue

        labels.append(LabelInfo(
            name=elem.name,
            anchor=_get_anchor(elem, scene),
            half_w=hw,
            half_h=hh,
            margin=margin,
            clear_radius=point_clear_radius,
        ))
    return labels


# ── Candidate generation & scoring ───────────────────────────────────

def _generate_candidates(anchor, distance):
    """Return 8 candidate label centers around the anchor."""
    return anchor + distance * _DIRECTIONS


def _nearest_dir_index(vec) -> int:
    """Snap an offset vector to the nearest of the 8 direction indices."""
    a = atan2(float(vec[1]), float(vec[0]))
    if a < 0:
        a += 2 * pi
    return int(round(a / (pi / 4))) % 8


def _octant_angle_dist(cand_angle, pref_angle) -> float:
    """Continuous analogue of the octant direction penalty: the angular distance
    between two directions expressed in OCTANT units (0..4), so continuous
    placement scores on the same scale as the 8-direction ``min(d, 8-d)`` term
    but without quantising to 45° steps."""
    d = abs(((cand_angle - pref_angle + pi) % (2 * pi)) - pi)
    return d / (pi / 4)


def _generate_candidates_continuous(anchor, distance, steps, extra_angle=None):
    """Return ``steps`` candidate centers evenly spaced around the anchor (plus
    an optional exact ``extra_angle``), as ``(center, dir_idx, angle)`` triples.
    ``dir_idx`` is the nearest octant (for the renderer's anchor/edge shift); the
    continuous ``angle`` drives position and the direction penalty."""
    angles = [2 * pi * k / steps for k in range(steps)]
    if extra_angle is not None:
        angles.append(float(extra_angle) % (2 * pi))
    out = []
    for t in angles:
        c = anchor + distance * np.array([cos(t), sin(t)])
        out.append((c, int(round(t / (pi / 4))) % 8, t))
    return out


def _incident_directions(anchor, segments, eps=1e-4):
    """Unit directions of edges emanating from a point at ``anchor`` (FP-3).

    For each obstacle segment that passes through ``anchor`` (endpoint or
    interior — e.g. a midpoint where two segments cross): add the direction
    toward the far endpoint(s). Covers polygon sides, segments, vectors and
    viewport-clipped lines/rays (which pass through interior points).
    """
    a = np.asarray(anchor, dtype=float)[:2]
    dirs = []
    for p1, p2 in segments:
        p1 = np.asarray(p1, dtype=float)[:2]
        p2 = np.asarray(p2, dtype=float)[:2]
        if _point_segment_distance(a, p1, p2) > eps:
            continue
        at_p1 = np.linalg.norm(a - p1) < eps
        at_p2 = np.linalg.norm(a - p2) < eps
        if at_p1 and at_p2:
            continue
        if at_p1:
            v = p2 - a
        elif at_p2:
            v = p1 - a
        else:  # interior point — both half-edges emanate
            for w in (p1 - a, p2 - a):
                n = np.linalg.norm(w)
                if n > 1e-9:
                    dirs.append(w / n)
            continue
        n = np.linalg.norm(v)
        if n > 1e-9:
            dirs.append(v / n)
    return dirs


def _angle_in_arc(theta, start, end, eps=1e-9) -> bool:
    """True when direction ``theta`` (rad) lies within the CCW arc from ``start``
    to ``end`` (rad), inclusive of both edges and correct across the 0/2π wrap.
    The arc spans ``(end - start) mod 2π`` CCW from ``start``."""
    span = (float(end) - float(start)) % (2 * pi)
    rel = (float(theta) - float(start)) % (2 * pi)
    return rel <= span + eps


def _bisector_of_largest_gap(dirs, blocked_arcs=None):
    """Unit direction bisecting the widest free angular gap between ``dirs``.

    A triangle vertex (2 incident sides) → the *external* bisector; a point on
    a line (dirs at θ and θ+π) → the perpendicular; a single edge → the opposite
    direction. Returns ``None`` for no directions. This is the "place the label
    where there's the most room, symmetric between the sides" rule (FP-3).

    ``blocked_arcs`` (R2) is a list of ``(start, end)`` rad sectors — the drawn
    angle-marker wedge(s) at this vertex. A gap whose bisector falls inside a
    blocked wedge is skipped (the marker sits there), so the label is steered to
    the widest *marker-free* gap. If every gap is blocked the overall-widest is
    returned (graceful degradation). ``None`` → byte-identical legacy behaviour.
    """
    if not dirs:
        return None
    if len(dirs) == 1:
        return -np.asarray(dirs[0], dtype=float)
    angs = sorted((atan2(float(d[1]), float(d[0])) % (2 * pi)) for d in dirs)
    n = len(angs)
    best_gap, best_mid = -1.0, 0.0
    fallback_gap, fallback_mid = -1.0, 0.0
    for i in range(n):
        gap = (angs[(i + 1) % n] - angs[i]) % (2 * pi)
        mid = angs[i] + gap / 2.0
        if gap > fallback_gap:
            fallback_gap, fallback_mid = gap, mid
        if blocked_arcs and any(_angle_in_arc(mid, s, e) for (s, e) in blocked_arcs):
            continue  # this gap is an angle-marker wedge
        if gap > best_gap:
            best_gap, best_mid = gap, mid
    mid = best_mid if best_gap >= 0 else fallback_mid
    return np.array([cos(mid), sin(mid)])


# Anchor code → sign vector (in half-extent units) from the anchor point to the
# label CENTRE. A GGB label defaults to anchor 'BL'/'DL' (the offset targets the
# text's bottom-left corner; glyphs extend up-right), so the VISUAL centre the
# reader sees is up-right of the raw offset point. Direction/sector reasoning must
# use that centre, not the corner (round-18: "ориентируйся на визуал надписи").
_ANCHOR_CENTER = {
    'BL': (1.0, 1.0), 'BC': (0.0, 1.0), 'BR': (-1.0, 1.0),
    'ML': (1.0, 0.0), 'MC': (0.0, 0.0), 'MR': (-1.0, 0.0),
    'TL': (1.0, -1.0), 'TC': (0.0, -1.0), 'TR': (-1.0, -1.0),
    'DL': (1.0, 1.0),  # GGB default (down-left) alias
}


def _unit_vec(v):
    """Normalize a 2-vector; harmless fallback for a near-zero input."""
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.array([1.0, 0.0])


def _label_visual_center_offset(off, anchor, half_w, half_h, ptUnit_ggb,
                                 descender_mu):
    """Visual glyph-CENTRE offset (scene MU) of a label whose raw ``off`` (GGB px)
    targets its ``anchor`` corner. Mirrors the renderer's ``move_to(aligned_edge)``
    + offset shift + descender pad, so direction/sector reasoning matches the text
    the reader actually sees rather than the anchor corner."""
    sx, sy = _ANCHOR_CENTER.get((anchor or 'BL'), (1.0, 1.0))
    return np.array([off[0] / ptUnit_ggb + sx * half_w,
                     off[1] / ptUnit_ggb + sy * half_h + descender_mu])


def _on_solid_circle_outward(anchor, circles, circ_dashed, eps_frac=0.06):
    """If ``anchor`` lies ON a SOLID circle (within ``eps_frac`` of its radius),
    return the unit direction radially OUTWARD from that circle's centre — the
    natural "outside the circle" direction a point-on-circle label should take
    (P5, scene18 O). Dashed circles (auxiliary) are ignored. ``None`` otherwise."""
    a = np.asarray(anchor, dtype=float)[:2]
    best, best_gap = None, None
    for i, (cc, cr) in enumerate(circles):
        if circ_dashed is not None and i < len(circ_dashed) and circ_dashed[i]:
            continue
        if cr <= 1e-6:
            continue
        d = float(np.hypot(a[0] - cc[0], a[1] - cc[1]))
        gap = abs(d - cr) / cr
        if gap < eps_frac and (best_gap is None or gap < best_gap):
            out = a - np.asarray(cc, dtype=float)[:2]
            n = float(np.hypot(out[0], out[1]))
            if n > 1e-9:
                best, best_gap = out / n, gap
    return best


def _bisector_of_gap_nearest(dirs, preferred,
                             snap_deg=35.0, align_deg=28.0, hug_deg=30.0,
                             blocked_arcs=None):
    """Bisector of the free angular gap that the user's ``preferred`` (GGB)
    direction points into (FP-11/round-11).

    ``blocked_arcs`` (R2) is a list of ``(start, end)`` rad angle-marker wedges
    at this vertex. When the user's ``preferred`` points INTO a marker wedge the
    hint is unusable (it targets the marker), so the label falls back to the
    widest *marker-free* gap — recovering the symmetric external placement
    instead of sitting on the marker. ``None`` → byte-identical legacy behaviour.

    ``preferred`` is the VISUAL glyph-centre direction (round-18) — where the text
    the reader sees actually sits, not the raw offset corner. The label is placed
    in the sector that direction POINTS INTO (the part of the crossing the user
    visually chose) and centred on that sector's bisector. Crucially this keeps a
    NARROW sector the user chose (scene27_3 A's 65° top wedge) instead of forcing
    the label into the widest gap — the old "widest only" rule moved A to the
    adjacent 115° left wedge = the wrong part. A sector too narrow to hold a label
    (< ~46°) falls back to the widest gap so the label still fits.

    Within the chosen sector, the bisector is the clean centre — UNLESS the visual
    direction is far from it AND hugs an incident edge (P-REGION): then keep the
    user's side, nudged ``align_deg`` off the edge.

    Returns the resolved unit direction, or ``None`` for a non-vertex (<2
    incident edges) so the caller falls back to the isolated-point path.

    Returns the resolved unit direction, or ``None`` for a non-vertex (<2
    incident edges) so the caller falls back to the isolated-point path.
    """
    if len(dirs) < 2:
        return None
    p = np.asarray(preferred, dtype=float)[:2]
    if float(np.linalg.norm(p)) < 1e-9:
        return _bisector_of_largest_gap(dirs)
    pang = atan2(float(p[1]), float(p[0])) % (2 * pi)
    angs = sorted(atan2(float(d[1]), float(d[0])) % (2 * pi) for d in dirs)
    n = len(angs)
    gaps = []  # (width, lo_edge, bisector_angle)
    for i in range(n):
        lo = angs[i]
        w = (angs[(i + 1) % n] - lo) % (2 * pi)
        gaps.append((w, lo, lo + w / 2.0))
    # Place the label in the sector its (VISUAL) direction actually points INTO —
    # the part of the crossing the user visually chose — and centre it on that
    # sector's bisector. round-18: keeping the user's sector even when it is NARROW
    # (scene27_3 A sits in the 65° TOP wedge; the old "widest gap only" rule forced
    # it into the adjacent 115° LEFT wedge = the wrong part). A sector too narrow to
    # hold the label falls back to the widest gap so the label still fits.
    def _gap_blocked(g):
        # a gap is a marker wedge when its bisector falls inside a blocked arc
        return bool(blocked_arcs) and any(
            _angle_in_arc(g[2], s, e) for (s, e) in blocked_arcs)

    pointed = None
    for g in gaps:
        if ((pang - g[1]) % (2 * pi)) <= g[0]:
            pointed = g
            break
    # R2: prefer the widest MARKER-FREE gap; fall back to overall-widest only if
    # every gap is blocked (graceful). A pointed gap that is a marker wedge is
    # rejected so the GGB hint can't pin the label onto the marker.
    free_gaps = [g for g in gaps if not _gap_blocked(g)]
    widest = (max(free_gaps, key=lambda g: g[0]) if free_gaps
              else max(gaps, key=lambda g: g[0]))
    MIN_SECTOR = 0.8  # rad (~46°): below this a sector can't hold a label → widest
    if pointed is None or pointed[0] < MIN_SECTOR or _gap_blocked(pointed):
        chosen = widest
    else:
        chosen = pointed
    w, lo, mid = chosen
    # P-REGION (FP-11, round-17): keep the user's side of a WIDE wedge when the
    # GGB direction is BOTH far from the wedge bisector (> snap_deg) AND hugging
    # an incident edge (< hug_deg) — a deliberate "this side" choice the bisector
    # would undo. Clamp it ``align_deg`` off the edges so it stays inside the
    # wedge and doesn't read as the edge's label.
    snap = snap_deg * pi / 180.0
    align = align_deg * pi / 180.0
    hug = hug_deg * pi / 180.0
    inside_chosen = ((pang - lo) % (2 * pi)) <= w   # GGB really in this wedge
    # Open-point gate (TZ-label-offset-ggb-fidelity §5.3): centring makes sense
    # while the gap still reads as a wedge/corner — scene4's 240° rhombus
    # corners look right on the external bisector. But when the BLOCKED part
    # spans < 90° (gap > 270°: an arc terminus, a near-endpoint) the point is
    # essentially open and "the middle" is arbitrary — В's bottom-left label
    # snapped to its 333°-gap centre and read as relocated. Keep the user's
    # own direction there, clamped ``align`` off the edges.
    if inside_chosen and w > 1.5 * pi:
        rel = min(max((pang - lo) % (2 * pi), align), w - align)
        mid = (lo + rel) % (2 * pi)
        return np.array([cos(mid), sin(mid)])
    d_bis = abs((pang - mid + pi) % (2 * pi) - pi)
    edge_d = min(abs((pang - a + pi) % (2 * pi) - pi) for a in angs)
    if inside_chosen and d_bis > snap and edge_d < hug and w > 2 * align:
        rel = min(max((pang - lo) % (2 * pi), align), w - align)
        mid = (lo + rel) % (2 * pi)
    return np.array([cos(mid), sin(mid)])


def _push_clear_of_marker(center, anchor, clear_radius, hw_p, hh_p, ptUnit):
    """Push ``center`` radially out from ``anchor`` until its bbox clears the
    own point marker (FP-1), preserving the label's direction (FP-4 — minimal
    change to a manual position). Returns the adjusted center."""
    c = np.asarray(center, dtype=float)
    a = np.asarray(anchor, dtype=float)[:2]
    d = c - a
    dist = float(np.linalg.norm(d))
    direction = d / dist if dist > 1e-9 else np.array([1.0, 0.0])
    step = max(1.0 / ptUnit, clear_radius * 0.15)
    for _ in range(40):
        if not _circle_bbox_intersects(a[0], a[1], clear_radius,
                                       c[0], c[1], hw_p, hh_p):
            break
        dist += step
        c = a + direction * dist
    return c


def _push_clear_along(center, anchor, clear_radius, hw_p, hh_p,
                      segments, circles, arc_pts, placed, ptUnit,
                      max_extra, geom_gap=0.0):
    """Push ``center`` radially out from ``anchor`` (same direction) until its
    bbox clears the own marker AND all obstacles/labels (FP-4 — keep a respected
    label in its sector by nudging out instead of relocating). Returns
    ``(center, cleared)``; ``cleared`` is False if it could not clear within
    ``max_extra`` (scene MU), in which case the caller should fall back to a
    full search.
    """
    c = np.asarray(center, dtype=float).copy()
    a = np.asarray(anchor, dtype=float)[:2]
    d = c - a
    dist = float(np.linalg.norm(d))
    direction = d / dist if dist > 1e-9 else np.array([1.0, 0.0])
    start = dist
    step = 1.0 / ptUnit
    for _ in range(80):
        on_marker = (clear_radius > 0 and _circle_bbox_intersects(
            a[0], a[1], clear_radius, c[0], c[1], hw_p, hh_p))
        if not on_marker and not _candidate_has_overlap(
                c, hw_p, hh_p, segments, circles, arc_pts, placed, geom_gap):
            return c, True
        if dist - start >= max_extra:
            break
        dist += step
        c = a + direction * dist
    return c, False


def _score_candidate(center, hw, hh, padding,
                     placed, segments, circles, arc_pts,
                     preferred_dir, candidate_idx, weights, geom_gap=0.0,
                     seg_dashed=None, dashed_factor=1.0,
                     cand_angle=None, pref_angle=None):
    """Score a candidate position. Lower is better.

    ``geom_gap`` (FP-2) inflates the bbox against geometry (segments/circles/
    points) so a near-miss to a line/circle is still penalised — labels keep a
    clearance instead of hugging the geometry. ``geom_gap=0`` reproduces the
    original behaviour exactly.

    ``seg_dashed`` (bool list parallel to ``segments``) + ``dashed_factor`` < 1
    implement **P-DASHED**: overlapping a dashed line costs ``dashed_factor`` ×
    a solid one, so when no overlap-free spot exists the label prefers crossing a
    dashed guide over a solid edge. ``dashed_factor=1.0`` (default) is unchanged.

    ``cand_angle`` + ``pref_angle`` (radians) switch the direction penalty to a
    CONTINUOUS angular distance (round-8 continuous placement); without them the
    quantised octant penalty ``min(|i−pref|, 8−…)`` is used (default).
    """
    w_anchor, w_label, w_geom = weights
    cx, cy = center
    hw_p, hh_p = hw + padding, hh + padding
    ghw, ghh = hw_p + geom_gap, hh_p + geom_gap

    # Direction penalty: angular distance from preferred direction
    if cand_angle is not None and pref_angle is not None:
        dir_penalty = _octant_angle_dist(cand_angle, pref_angle)
    else:
        dist = abs(candidate_idx - preferred_dir)
        dir_penalty = min(dist, 8 - dist)
    cost = w_anchor * dir_penalty

    # Label-label overlap (no geom_gap — only true overlaps between labels)
    for pc, phw, phh in placed:
        area = _bbox_overlap_area(cx, cy, hw_p, hh_p, pc[0], pc[1], phw, phh)
        if area > 0:
            cost += w_label * area

    # Label-geometry overlap: exact segment intersection (+ clearance gap)
    use_dash = seg_dashed is not None and dashed_factor != 1.0
    for i, (p1, p2) in enumerate(segments):
        seg_inside = _segment_bbox_overlap(p1, p2, cx, cy, ghw, ghh)
        if seg_inside > 0:
            w = w_geom
            if use_dash and i < len(seg_dashed) and seg_dashed[i]:
                w = w_geom * dashed_factor
            cost += w * (1.0 + seg_inside)

    # Label-geometry overlap: circles (analytical, + clearance gap)
    for cc, cr in circles:
        if _circle_bbox_intersects(cc[0], cc[1], cr, cx, cy, ghw, ghh):
            cost += w_geom * 2.0

    # Label-geometry overlap: loose point samples (+ clearance gap)
    if len(arc_pts) > 0:
        inside_x = np.abs(arc_pts[:, 0] - cx) <= ghw
        inside_y = np.abs(arc_pts[:, 1] - cy) <= ghh
        hits = int(np.sum(inside_x & inside_y))
        cost += w_geom * hits

    return cost


# ── Greedy solver ─────────────────────────────────────────────────────

def _solve_greedy(labels, segments, circles, arc_pts, distance, padding, weights,
                  ptUnit=1, cost_model=None, *,
                  respect_current=False, keep_current_if_free=False,
                  geom_gap=0.0, directional=False, directional_cap=0.0,
                  continuous_steps=0, dir_tol=None):
    """Place labels greedily. Returns list of (name, center, dir_idx) triples.

    When ``cost_model`` is None the scoring is byte-for-byte identical to the
    legacy ``_score_candidate`` path. Passing a :class:`LabelCostModel` routes
    scoring through it (enables canonical position preference / soft proximity).

    ``respect_current`` (P1-D): for labels carrying ``current_center`` (an
    existing manual/GGB position), keep it when it is collision-free
    (``keep_current_if_free``) and otherwise bias the search toward it via the
    cost model's inertia term, so a good placement is preserved and the label
    does not jump to the other side of its feature.
    """
    seg_dashed_full = cost_model.seg_dashed if cost_model is not None else None

    # Perf: cull obstacles to each label's reach (the only ones a candidate can
    # touch) — exact, but turns the O(cands × all-segments) hot loop into
    # O(cands × local-segments). Computed once per label, reused below.
    def _reach(lbl):
        return (3.0 * (distance + lbl.margin) + lbl.clear_radius
                + 3.0 * max(lbl.half_w, lbl.half_h) + padding + geom_gap
                + max(directional_cap, 10.0 / ptUnit) + 0.05)
    culled = {}
    for lbl in labels:
        if lbl.fixed_center is None:
            culled[lbl.name] = _cull_obstacles(
                segments, seg_dashed_full, circles, arc_pts, lbl.anchor,
                _reach(lbl))

    # Pre-compute difficulty: how many of 8 candidates have geometry overlaps
    # Fixed-center labels (angles) get highest priority (placed first)
    difficulties = []
    for lbl in labels:
        if lbl.fixed_center is not None:
            difficulties.append((-1, lbl.name))
            continue
        cseg, cdash, ccirc, carc = culled[lbl.name]
        candidates = _generate_candidates(lbl.anchor, distance + lbl.margin)
        hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
        free = sum(
            0 if _candidate_has_overlap(c, hw_p, hh_p, cseg, ccirc,
                                        carc, geom_gap=geom_gap)
            else 1
            for c in candidates
        )
        difficulties.append((8 - free, lbl.name))

    order = sorted(range(len(labels)), key=lambda i: difficulties[i])

    placed = []
    result = []

    for idx in order:
        lbl = labels[idx]

        # Fixed-center labels (angles): bypass candidate system entirely
        if lbl.fixed_center is not None:
            center = lbl.fixed_center
            # Use fixed_anchor direction for _DIR_TO_ANCHOR lookup
            bis_dir = center - lbl.anchor
            bis_angle = atan2(bis_dir[1], bis_dir[0])
            if bis_angle < 0:
                bis_angle += 2 * pi
            best = int(round(bis_angle / (pi / 4))) % 8
            placed.append((center, lbl.half_w + padding, lbl.half_h + padding))
            result.append((lbl.name, center, best))
            continue

        cseg, cdash, ccirc, carc = culled[lbl.name]  # obstacles in this label's reach

        # Respect an existing manual/GGB position (P1-D): if it is collision-free
        # keep it verbatim so a good placement is not disturbed (no side-flip).
        cur = lbl.current_center if respect_current else None
        if cur is not None and keep_current_if_free:
            hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
            # FP-1+FP-4: push the respected position straight out (same direction)
            # until it clears its marker AND all obstacles/labels. Keep it if it
            # clears within the cap — this preserves the angular sector instead of
            # relocating the label. Otherwise fall through to a full search. The
            # cap always allows clearing the own marker (radius + half-extent).
            max_extra = (lbl.clear_radius + max(hw_p, hh_p)
                         + (distance + lbl.margin) * 2.0)
            cur_kept, ok = _push_clear_along(
                cur, lbl.anchor, lbl.clear_radius, hw_p, hh_p,
                cseg, ccirc, carc, placed, ptUnit, max_extra, geom_gap)
            if ok:
                placed.append((cur_kept, hw_p, hh_p))
                result.append((lbl.name, cur_kept,
                               _nearest_dir_index(cur_kept - lbl.anchor)))
                continue

        # FP-4/FP-7 (keep-direction): place along the single preferred direction
        # (bisector for vertices, else the canonical/density direction) and nudge
        # OUT along it to clear, instead of scanning 8 directions. This keeps a
        # uniform, minimally-deviating layout (same side, just further out as
        # needed). Falls back to the full search only if that direction is
        # blocked beyond the cap.
        if directional and cur is None:
            pdir = (lbl.bisector_dir if lbl.bisector_dir is not None
                    else _DIRECTIONS[lbl.preferred_dir])
            npd = float(np.linalg.norm(pdir))
            if npd > 1e-9:
                pdir = np.asarray(pdir, dtype=float) / npd
                hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
                start = lbl.anchor + (distance + lbl.margin) * pdir
                placed_c, ok = _push_clear_along(
                    start, lbl.anchor, lbl.clear_radius, hw_p, hh_p,
                    cseg, ccirc, carc, placed, ptUnit,
                    directional_cap, geom_gap)
                if ok:
                    placed.append((placed_c, hw_p, hh_p))
                    result.append((lbl.name, placed_c, _nearest_dir_index(pdir)))
                    continue

        # Place at base distance. If overlaps, nudge outward in 1px steps.
        base_dist = distance + lbl.margin
        max_dir_penalty = (weights[0] * 4 if cost_model is None
                           else cost_model.max_overlap_free_cost())
        step = 1 / ptUnit  # 1px nudge step

        best_center = None
        best_dir = 0
        best_prev = float('inf')

        # Round-8 continuous placement: sweep ``continuous_steps`` angles instead
        # of the 8 octants, scoring the direction penalty continuously, so the
        # label lands at its exact resolved direction (or the closest FREE angle)
        # rather than snapping to a 45° octant. Only with a cost model.
        use_cont = cost_model is not None and continuous_steps > 0
        if use_cont:
            pvec = (lbl.bisector_dir if lbl.bisector_dir is not None
                    else _DIRECTIONS[lbl.preferred_dir])
            pref_angle = atan2(float(pvec[1]), float(pvec[0]))
        else:
            pref_angle = None

        for nudge in range(11):  # up to 10 nudge steps = +10px max
            d = base_dist + nudge * step
            if use_cont:
                cand_list = _generate_candidates_continuous(
                    lbl.anchor, d, continuous_steps, extra_angle=pref_angle)
            else:
                base_cands = _generate_candidates(lbl.anchor, d)
                cand_list = [(base_cands[i], i, None) for i in range(8)]
                # FP-3: add the exact free-gap bisector as a continuous-angle
                # candidate so the label lands precisely on the bisector when free.
                if cur is None and lbl.bisector_dir is not None:
                    cand_list.append((lbl.anchor + d * lbl.bisector_dir,
                                      _nearest_dir_index(lbl.bisector_dir), None))
            if cost_model is None:
                scores = [
                    _score_candidate(
                        c, lbl.half_w, lbl.half_h, padding,
                        placed, cseg, ccirc, carc,
                        lbl.preferred_dir, di, weights,
                    )
                    for (c, di, _a) in cand_list
                ]
            else:
                scores = [
                    cost_model.candidate_cost(
                        c, lbl.half_w, lbl.half_h,
                        placed, cseg, ccirc, carc,
                        lbl.preferred_dir, di, current_center=cur,
                        label_luminance=lbl.label_luminance,
                        own_anchor=lbl.anchor,
                        cand_angle=a, pref_angle=pref_angle,
                        seg_dashed=cdash,
                    )
                    for (c, di, a) in cand_list
                ]
            best_i = int(np.argmin(scores))
            best_s = scores[best_i]

            if best_s < best_prev:
                best_center, best_dir, _ba = cand_list[best_i]
                best_prev = best_s

            # Early-break: stop nudging once a good-enough spot is found. The
            # legacy threshold is ``max_dir_penalty`` (≈ the max possible cost),
            # i.e. it breaks on the FIRST overlap-free spot at ANY direction — so
            # it grabbed a free-but-wrong-direction base spot and never explored a
            # few px out where the PREFERRED direction is free (scene27_3 A took
            # down-left@base instead of up-left@+8px). With a tight ``dir_tol`` the
            # search only stops on a free spot whose direction penalty is within
            # tolerance; otherwise it keeps nudging (bounded by +10px) and the
            # global-min tracking above keeps the best-direction free spot found.
            brk = dir_tol if dir_tol is not None else max_dir_penalty
            if cur is None and best_s <= brk:
                break

        # Let the current position itself compete (inertia 0 there) so a slightly
        # imperfect-but-close placement wins over a distant "better" one.
        if cur is not None and cost_model is not None:
            cscore = cost_model.candidate_cost(
                cur, lbl.half_w, lbl.half_h, placed, cseg, ccirc, carc,
                lbl.preferred_dir, _nearest_dir_index(cur - lbl.anchor),
                current_center=cur, label_luminance=lbl.label_luminance,
                own_anchor=lbl.anchor, seg_dashed=cdash,
            )
            if cscore < best_prev:
                best_center = cur
                best_dir = _nearest_dir_index(cur - lbl.anchor)
                best_prev = cscore

        placed.append((best_center, lbl.half_w + padding, lbl.half_h + padding))
        result.append((lbl.name, best_center, best_dir))

    return result


def _repair_pass(labels, result, segments, circles, arc_pts, distance, padding,
                 cost_model, iterations, *, respect_current=False,
                 continuous_steps=0):
    """Discrete gradient-descent local repair (P0-B).

    Greedy is order-dependent and can leave a label in a sub-optimal anchor once
    its neighbours are placed. This sweeps every movable (non-angle) label and
    moves it to the lowest-cost of its base-distance candidates whenever that
    strictly beats its current position, repeating until stable or ``iterations``
    sweeps are exhausted. Deterministic. ``result`` is mutated in place.

    With ``respect_current`` the per-label inertia term (toward
    ``lbl.current_center``) is included, so repair will not drag a respected
    manual position away unless the gain clearly outweighs the displacement.
    ``continuous_steps`` > 0 sweeps that many angles (round-8) instead of the 8
    octants, matching the continuous greedy so repair doesn't requantise.
    """
    by_name = {lbl.name: lbl for lbl in labels}
    seg_dashed_full = cost_model.seg_dashed if cost_model is not None else None
    geom_gap = cost_model.geom_gap if cost_model is not None else 0.0
    # Perf: cull obstacles to each label's reach once (obstacles are static across
    # sweeps; only ``placed`` changes). Same exact culling as the greedy solver.
    culled = {}
    for lbl in labels:
        if lbl.fixed_center is None:
            reach = (3.0 * (distance + lbl.margin) + lbl.clear_radius
                     + 3.0 * max(lbl.half_w, lbl.half_h) + padding + geom_gap
                     + 10.0 / max(cost_model.ptUnit if cost_model else 1.0, 1e-9)
                     + 0.05)
            culled[lbl.name] = _cull_obstacles(
                segments, seg_dashed_full, circles, arc_pts, lbl.anchor, reach)
    for _ in range(max(0, int(iterations))):
        changed = False
        for k in range(len(result)):
            name, center, dir_idx = result[k]
            lbl = by_name.get(name)
            if lbl is None or lbl.fixed_center is not None:
                continue
            cseg, cdash, ccirc, carc = culled[name]
            cur = lbl.current_center if respect_current else None
            placed = [
                (result[j][1], by_name[result[j][0]].half_w + padding,
                 by_name[result[j][0]].half_h + padding)
                for j in range(len(result))
                if j != k and result[j][0] in by_name
            ]
            if continuous_steps > 0:
                pvec = (lbl.bisector_dir if lbl.bisector_dir is not None
                        else _DIRECTIONS[lbl.preferred_dir])
                pa = atan2(float(pvec[1]), float(pvec[0]))
                cand = _generate_candidates_continuous(
                    lbl.anchor, distance + lbl.margin, continuous_steps,
                    extra_angle=pa)
            else:
                pa = None
                base = _generate_candidates(lbl.anchor, distance + lbl.margin)
                cand = [(base[i], i, None) for i in range(8)]
            scores = [
                cost_model.candidate_cost(
                    c, lbl.half_w, lbl.half_h,
                    placed, cseg, ccirc, carc, lbl.preferred_dir, di,
                    current_center=cur, label_luminance=lbl.label_luminance,
                    own_anchor=lbl.anchor, cand_angle=a, pref_angle=pa,
                    seg_dashed=cdash,
                )
                for (c, di, a) in cand
            ]
            best_i = int(np.argmin(scores))
            cur_angle = (atan2(float(center[1] - lbl.anchor[1]),
                               float(center[0] - lbl.anchor[0]))
                         if pa is not None else None)
            cur_cost = cost_model.candidate_cost(
                center, lbl.half_w, lbl.half_h,
                placed, cseg, ccirc, carc, lbl.preferred_dir, dir_idx,
                current_center=cur, label_luminance=lbl.label_luminance,
                own_anchor=lbl.anchor, cand_angle=cur_angle, pref_angle=pa,
                seg_dashed=cdash,
            )
            if scores[best_i] < cur_cost - 1e-9:
                result[k] = (name, cand[best_i][0], cand[best_i][1])
                changed = True
        if not changed:
            break


def _consistency_pass(scene, labels, result, segments, circles, arc_pts,
                      distance, padding, *, respect_current=False):
    """Snap labels of the same element type to the group's majority direction
    when doing so introduces no overlap (P0-A — aesthetic consistency).

    This is what turns a technically-correct-but-scattered layout into a
    *systematic* one: identical objects (e.g. all free points) get the same
    anchor/offset unless geometry forces otherwise. ``result`` is mutated in
    place. Movable (non-angle) labels only.
    """
    from collections import Counter

    by_name = {lbl.name: lbl for lbl in labels}
    groups: dict = {}
    for k in range(len(result)):
        name = result[k][0]
        lbl = by_name.get(name)
        if lbl is None or lbl.fixed_center is not None:
            continue
        # Don't override a respected manual/GGB position (P1-D).
        if respect_current and lbl.current_center is not None:
            continue
        elem = scene.geo.element(name)
        if elem is None:
            continue
        groups.setdefault(type(elem.data).__name__, []).append(k)

    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        modal = Counter(result[k][2] for k in idxs).most_common(1)[0][0]
        for k in idxs:
            name, center, dir_idx = result[k]
            if dir_idx == modal:
                continue
            lbl = by_name[name]
            cand = _generate_candidates(lbl.anchor, distance + lbl.margin)[modal]
            hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
            placed = [
                (result[j][1], by_name[result[j][0]].half_w + padding,
                 by_name[result[j][0]].half_h + padding)
                for j in range(len(result))
                if j != k and result[j][0] in by_name
            ]
            if not _candidate_has_overlap(cand, hw_p, hh_p, segments, circles,
                                          arc_pts, placed):
                result[k] = (name, cand, modal)


def _cluster_consistency_pass(scene, labels, result, segments, circles, arc_pts,
                              distance, padding, *, align_tol=0.4, min_cluster=3):
    """Align label directions WITHIN an aligned cluster of free points — a row or
    column of similar points — so a grid doesn't get a scattered "разнобой" of
    directions (round-12, test6). Region-aware on purpose: it touches ONLY free
    points (no incident edges) that belong to a collinear run of >= ``min_cluster``
    members sharing an x (column) or y (row) within ``align_tol``. Scattered free
    points (scene5___) and vertices (triangle_grid3) are left alone — that is what
    the GLOBAL ``_consistency_pass`` got wrong (it yanked correct labels to the
    overall majority; the round-11 "в бок влево" bug).

    A column's labels go sideways (E/W), a row's go vertically (N/S); the side is
    the one overlap-free for the MOST members. Each member snaps to that octant at
    base distance only when overlap-free. ``result`` is mutated in place.
    """
    from .geo import lib_elements as geo
    by_name = {lbl.name: lbl for lbl in labels}

    free = []  # (k, anchor) for free movable point labels
    for k in range(len(result)):
        lbl = by_name.get(result[k][0])
        if lbl is None or lbl.fixed_center is not None:
            continue
        elem = scene.geo.element(result[k][0])
        if elem is None or not isinstance(elem.data, geo.Point):
            continue
        if len(_incident_directions(lbl.anchor, segments)) >= 2:
            continue  # vertex — keep its external bisector
        free.append((k, np.asarray(lbl.anchor, dtype=float)[:2]))
    if len(free) < min_cluster:
        return

    clusters = []  # (axis, [k, ...]) ; axis 0 = column (shared x), 1 = row (shared y)
    for axis in (0, 1):
        used = [False] * len(free)
        for i in range(len(free)):
            if used[i]:
                continue
            ci = free[i][1][axis]
            members = [free[i][0]]
            used[i] = True
            for j in range(i + 1, len(free)):
                if not used[j] and abs(free[j][1][axis] - ci) <= align_tol:
                    members.append(free[j][0])
                    used[j] = True
            if len(members) >= min_cluster:
                clusters.append((axis, members))

    for axis, members in clusters:
        cand_dirs = (0, 4) if axis == 0 else (2, 6)  # column→E/W, row→N/S
        best_side, best_centers, best_n = None, {}, -1
        for side in cand_dirs:
            centers, n = {}, 0
            for k in members:
                lbl = by_name[result[k][0]]
                c = _generate_candidates(lbl.anchor, distance + lbl.margin)[side]
                hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
                placed = [
                    (result[j][1], by_name[result[j][0]].half_w + padding,
                     by_name[result[j][0]].half_h + padding)
                    for j in range(len(result))
                    if j != k and result[j][0] in by_name
                ]
                if not _candidate_has_overlap(c, hw_p, hh_p, segments, circles,
                                              arc_pts, placed):
                    centers[k] = c
                    n += 1
            if n > best_n:
                best_n, best_side, best_centers = n, side, centers
        if best_side is None:
            continue
        # Place EVERY member on the chosen side so the whole column/row reads as one
        # direction (round-21, P6): a member whose base spot on that side is blocked
        # (test6 lower column E_13-16 — East blocked by the arc) is nudged OUT along
        # the side until it clears, up to a cap; only if it can't clear at all does
        # it keep its solver placement. Avoids the "разнобой" of the column's tail.
        sdir = _DIRECTIONS[best_side]
        step_mu = max(distance, 0.02) * 0.2
        for k in members:
            if k in best_centers:
                result[k] = (result[k][0], best_centers[k], best_side)
                continue
            lbl = by_name[result[k][0]]
            hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
            base_k = distance + lbl.margin
            cap_k = base_k + max(distance, 0.02) * 3.0
            placed = [(result[j][1], by_name[result[j][0]].half_w + padding,
                       by_name[result[j][0]].half_h + padding)
                      for j in range(len(result))
                      if j != k and result[j][0] in by_name]
            d = base_k
            while d <= cap_k + 1e-9:
                c = lbl.anchor + sdir * d
                if not _candidate_has_overlap(c, hw_p, hh_p, segments, circles,
                                              arc_pts, placed):
                    result[k] = (result[k][0], c, best_side)
                    break
                d += step_mu


def _bbox_edge_toward(cx, cy, hw, hh, tx, ty):
    """Point on the axis-aligned bbox (centre cx,cy half hw,hh) boundary in the
    direction of (tx,ty) — where a leader line from the label edge starts."""
    dx, dy = tx - cx, ty - cy
    if -1e-12 < dx < 1e-12 and -1e-12 < dy < 1e-12:
        return (cx, cy)
    sx = hw / abs(dx) if abs(dx) > 1e-12 else float('inf')
    sy = hh / abs(dy) if abs(dy) > 1e-12 else float('inf')
    s = min(sx, sy)
    return (cx + dx * s, cy + dy * s)


def _find_leader_target(anchor, lbl, segments, circles, arc_pts, placed,
                        base_dist, padding, ptUnit, max_push, prefer_dir,
                        steps=36, clear_margin=0.0):
    """Nearest overlap-free spot for a displaced label, searched over ALL
    directions (not just radially out from the current one) so a wide/stuck label
    whose only free space is off to the side still finds it. Distances sweep out
    in 1px steps; at each, angles are tried ordered by closeness to ``prefer_dir``
    so the leader stays short and points roughly the natural way. Returns the
    centre or ``None`` if nothing is free within ``max_push``."""
    # ``clear_margin`` inflates the bbox for the free test so a leader only fires
    # when the label reaches GENUINELY clear space (margin px from everything) —
    # not a barely-free spot still inside a dense node (scene6a O/C_1 landed 2–3px
    # from lines → read worse than overplotting; auto leaves them put).
    hw_p, hh_p = lbl.half_w + padding + clear_margin, lbl.half_h + padding + clear_margin
    pa = atan2(float(prefer_dir[1]), float(prefer_dir[0]))
    angs = sorted((2 * pi * i / steps for i in range(steps)),
                  key=lambda a: abs(((a - pa + pi) % (2 * pi)) - pi))
    a0, a1 = float(anchor[0]), float(anchor[1])
    n_d = int(max_push * ptUnit)
    for di in range(n_d + 1):
        d = base_dist + di / ptUnit
        for a in angs:
            c = np.array([a0 + d * cos(a), a1 + d * sin(a)])
            if not _candidate_has_overlap(c, hw_p, hh_p, segments, circles,
                                          arc_pts, placed):
                return c
    return None


def _leader_layout_pass(scene, labels, result, segments, circles, arc_pts,
                        distance, padding, ptUnit, *, max_push, coincident_px=0.0,
                        clear_margin=0.0, points_only=True):
    """P2-A: displace genuinely-stuck labels to a free spot and record a
    :class:`LeaderSpec` (the connector ``attach → anchor``). A label is "stuck"
    when its final position still overlaps geometry (no free spot was found near
    the anchor — the coincident-point / dense cases). It is pushed outward along
    its current direction (large cap ``max_push``) until it clears geometry AND
    other labels; only then is it moved and given a leader. Labels that can't be
    freed even far out are left in place (overplot fallback, no leader).

    Returns ``{name: LeaderSpec}`` and mutates ``result`` for moved labels.
    """
    from .geo import lib_elements as _geo
    by_name = {lbl.name: lbl for lbl in labels}
    specs = {}
    for k in range(len(result)):
        name, center, dir_idx = result[k]
        lbl = by_name.get(name)
        if lbl is None or lbl.fixed_center is not None:
            continue
        # Leaders are for POINT labels (a fixed anchor where the line clarifies
        # association). Segment/line/measure labels can slide along their own
        # geometry, so a leader back to it is redundant clutter (scene6a l_2/n_2).
        if points_only and scene is not None:
            el = scene.geo.element(name)
            if el is not None and not isinstance(el.data, _geo.Point):
                continue
        hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
        placed = [
            (result[j][1], by_name[result[j][0]].half_w + padding,
             by_name[result[j][0]].half_h + padding)
            for j in range(len(result)) if j != k and result[j][0] in by_name
        ]
        # Step 2a: "stuck" = the final position still overlaps geometry OR another
        # label (a near-merge the declutter pass could not resolve — E15/E16).
        # ``placed`` makes the same check catch both. Round-15: also treat a label
        # whose anchor is (near-)coincident with another label's anchor as stuck —
        # two labels for the same point read as one blob; a leader disambiguates.
        coincident = False
        if coincident_px > 0:
            for j in range(len(result)):
                lj = by_name.get(result[j][0])
                if j != k and lj is not None and lj.fixed_center is None and \
                        float(np.linalg.norm(lbl.anchor - lj.anchor)) * ptUnit < coincident_px:
                    coincident = True
                    break
        if not coincident and not _candidate_has_overlap(
                center, hw_p, hh_p, segments, circles, arc_pts, placed):
            continue  # not stuck — a normal, clear label
        d = np.asarray(center, dtype=float) - lbl.anchor
        nd = float(np.linalg.norm(d))
        direction = (d / nd) if nd > 1e-9 else _DIRECTIONS[lbl.preferred_dir]
        # Search ALL directions for the nearest free spot (a wide/stuck label's
        # only free space may be off to the side, not straight out — scene19
        # A_1=A_7 overlapped but a radial push missed its sideways free spot).
        moved = _find_leader_target(
            lbl.anchor, lbl, segments, circles, arc_pts, placed,
            distance + lbl.margin, padding, ptUnit, max_push, direction,
            clear_margin=clear_margin)
        if moved is None:
            continue  # no genuinely-clear spot — leave overplotted, no leader
        attach = _bbox_edge_toward(float(moved[0]), float(moved[1]),
                                   lbl.half_w, lbl.half_h,
                                   float(lbl.anchor[0]), float(lbl.anchor[1]))
        result[k] = (name, moved, _nearest_dir_index(moved - lbl.anchor))
        specs[name] = LeaderSpec(
            anchor=(float(lbl.anchor[0]), float(lbl.anchor[1])), attach=attach)
    return specs


def _recompact_pass(labels, result, segments, circles, arc_pts, distance,
                    padding, ptUnit, target_clear, *, max_push_px=14.0,
                    density_max=2, cone_deg=40.0, ang_steps=17,
                    seg_dashed=None, circ_dashed=None, overlap_tol=0.0):
    """Re-seat each label at the SMALLEST distance (≥ base) along a cone around its
    direction where it clears geometry by ``target_clear`` AND all other labels.

    Unifies two goals on one pass:
    - **pull in** a label that overshot a dense node back toward its point (scene19
      A_2/A_3/A_5/A_6 flew to ~25px though a closer spot exists just off their ray);
    - **nudge out** a label hugging the sides of a wedge to the same clearance
      (scene27_3 A "почти прилипание"). Because a wedge widens with distance, the
      push needed for ``target_clear`` GROWS as the wedge narrows — handled
      naturally by scanning distance outward — but is capped at ``base+max_push_px``.
    If the clearance can't be met in the label's own sector within the cap, a
    full-circle fallback re-seats it in ANOTHER sector at the nearest distance that
    works ("beyond the limit, consider another position"). Keeps the current
    position if nothing clears."""
    by_name = {l.name: l for l in labels}
    step = 1.0 / ptUnit
    cone = cone_deg * pi / 180.0
    cone_offs = sorted((-cone + 2 * cone * i / (ang_steps - 1)
                        for i in range(ang_steps)), key=abs)
    _empty = np.empty((0, 2))
    incident_eps = (distance + 6.0 / ptUnit)   # "through the point" radius
    # rescue search directions, ordered nearest-to-current-first (precomputed once)
    full_offs = sorted((-pi + 2 * pi * i / 48 for i in range(48)), key=abs)

    def _make_ok(a0, a1, csegs, cdash, ccirc, carc):
        # The clip tolerance applies ONLY to SOLID lines INCIDENT to this label's
        # own point (the lines its point sits on — clipping them is natural, e.g. an
        # intersection label). Everything else is a HARD obstacle (no clip):
        # non-incident lines, DASHED lines/circles, ALL circles and angle/point
        # markers. round-22: dashed lines are hard too — a clean spot is preferred
        # over sitting on a dashed line when space allows (10-4_ A/B/D).
        inc, hard = [], []
        for i, s in enumerate(csegs):
            dsh = (cdash[i] if cdash is not None and i < len(cdash) else False)
            if (not dsh) and _point_segment_distance((a0, a1), s[0], s[1]) < incident_eps:
                inc.append(s)
            else:
                hard.append(s)

        def _ok(c, hw, hh, placed_set):
            if _candidate_has_overlap(c, hw, hh, (), (), _empty, placed_set):
                return False  # never overlap another LABEL
            # incident solid lines: small clip allowed (shrink bbox)
            if _candidate_has_overlap(c, max(hw - overlap_tol, 0.02),
                                      max(hh - overlap_tol, 0.02), inc, (), _empty):
                return False
            # everything else (incl. dashed lines + ALL circles): hard, no clip
            return not _candidate_has_overlap(c, hw, hh, hard, ccirc, carc)
        return _ok

    for k in range(len(result)):
        name, center, dir_idx = result[k]
        lbl = by_name.get(name)
        if lbl is None or lbl.fixed_center is not None:
            continue
        d_vec = np.asarray(center, dtype=float) - lbl.anchor
        dist = float(np.linalg.norm(d_vec))
        if dist < 1e-9:
            continue
        cur_ang = atan2(float(d_vec[1]), float(d_vec[0]))
        hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
        base = distance + lbl.margin
        a0, a1 = float(lbl.anchor[0]), float(lbl.anchor[1])
        # Cull obstacles to this label's reach — every candidate centre stays within
        # base..max(dist, base+24px) of the anchor, so geometry farther than that
        # can't affect it. Keeps the per-candidate overlap tests O(near), not
        # O(all segments), on dense scenes (10-4_ 126 segs, scene6a 244).
        reach = max(dist, base + 24.0 / ptUnit) + max(hw_p, hh_p) + 2.0 / ptUnit
        idx = [i for i, s in enumerate(segments)
               if _point_segment_distance((a0, a1), s[0], s[1]) < reach]
        csegs = [segments[i] for i in idx]
        cdash = ([seg_dashed[i] for i in idx] if seg_dashed is not None else None)
        ccirc, csolid = [], []
        for i, (cc, cr) in enumerate(circles):
            if abs(float(np.hypot(a0 - cc[0], a1 - cc[1])) - cr) < reach + max(hw_p, hh_p):
                ccirc.append((cc, cr))
                if circ_dashed is None or not (i < len(circ_dashed) and circ_dashed[i]):
                    csolid.append((cc, cr))   # solid circles drive the rescue
        if len(arc_pts) > 0:
            m = ((np.abs(arc_pts[:, 0] - a0) < reach)
                 & (np.abs(arc_pts[:, 1] - a1) < reach))
            carc = arc_pts[m]
        else:
            carc = _empty
        placed = [(result[j][1], by_name[result[j][0]].half_w + padding,
                   by_name[result[j][0]].half_h + padding)
                  for j in range(len(result))
                  if j != k and result[j][0] in by_name]
        _ok = _make_ok(a0, a1, csegs, cdash, ccirc, carc)

        # Phase 1 — COMPACT IN: nearest position (cone, ≥ base, ≤ current) that is
        # label-free and at most lightly clips a solid line INCIDENT to its own
        # point (P3). Pulls a label that overshot a dense node back CLOSE to it.
        # A RESPECTED label (current_center pin = substantive manual position,
        # TZ-label-offset-ggb-fidelity §5.3) may only move radially: the cone
        # swung В's bottom-left label 40° across to bottom-right — trading the
        # user's side for a marginally nearer spot defeats the respect contract.
        label_offs = ((0.0,) if lbl.current_center is not None else cone_offs)
        best = np.asarray(center, dtype=float)
        d = base
        while d <= dist - step:
            hit = None
            for off in label_offs:
                a = cur_ang + off
                c = np.array([a0 + d * cos(a), a1 + d * sin(a)])
                if _ok(c, hw_p, hh_p, placed):
                    hit = c
                    break
            if hit is not None:
                best = hit
                break
            d += step
        # Rescue (round-22): overlapping a SOLID CIRCLE reads as an error the user
        # flagged "очень плохо" (scene18 L — on a circle with 6 edges, no clear spot
        # near its bisector). If ``best`` still hits a solid circle, search ALL
        # directions for the nearest tolerable spot (clears the circle; clipping an
        # incident line is fine) — e.g. radially outward, off the circle interior.
        if csolid and _candidate_has_overlap(best, hw_p, hh_p, (), csolid, _empty):
            dd = base
            hi = base + 24.0 / ptUnit
            while dd <= hi + 1e-9:
                got = None
                for off in full_offs:
                    a = cur_ang + off
                    c = np.array([a0 + dd * cos(a), a1 + dd * sin(a)])
                    if _ok(c, hw_p, hh_p, placed):
                        got = c
                        break
                if got is not None:
                    best = got
                    break
                dd += step
        # Phase 2 — ANTI-HUG: push OUT along the (compacted) direction to gain
        # ``target_clear`` clearance from geometry — but ONLY if that clearance is
        # actually reached within the cap. round-20 (feedback round-19): the push
        # is bounded by P1 ASSOCIATION — never move past the point where the label
        # would sit closer to ANOTHER point than its own (false attachment:
        # scene19 A_2 read as the blue segment's label). If clearance can't be had
        # inside the cap, KEEP the compact position — accept a small hug/overlap;
        # closeness + association beat a far push (the user's stated priority).
        # Gate: fire only in a SPARSE spot (≤ density_max lines passing within a
        # tight radius). The lines THROUGH the point are always counted, so a 2-line
        # wedge (scene27_3 A) passes and gains real clearance, while a 3+-line dense
        # node (scene19) is skipped → P3 keeps it CLOSE.
        gate_reach = base + 4.0 / ptUnit
        near_segs = sum(1 for p1, p2 in csegs
                        if _point_segment_distance((a0, a1), p1, p2) < gate_reach)
        if target_clear > 0 and near_segs <= density_max:
            bv = best - lbl.anchor
            bd = float(np.linalg.norm(bv))
            bdir = bv / bd if bd > 1e-9 else np.array([cos(cur_ang), sin(cur_ang)])
            assoc_cap = float('inf')   # Voronoi limit toward the nearest other point
            for ol in labels:
                if ol.name == name or ol.fixed_center is not None:
                    continue
                qp = np.asarray(ol.anchor, dtype=float)[:2] - lbl.anchor
                proj = float(bdir[0] * qp[0] + bdir[1] * qp[1])
                if proj > 1e-6:
                    assoc_cap = min(assoc_cap,
                                    float(qp[0] * qp[0] + qp[1] * qp[1]) / (2.0 * proj))
            cap = min(bd + max_push_px / ptUnit, assoc_cap)
            d2 = bd
            # push out toward clearance up to the cap (gaining visual space off the
            # lines), but NEVER past assoc_cap — so the label can't end up closer to
            # another point than its own (false attachment, round-19 P1). Stop if it
            # would meet another label (accept the tighter clearance there).
            while (d2 <= cap + 1e-9
                   and _candidate_has_overlap(lbl.anchor + bdir * d2, hw_p, hh_p,
                                              csegs, ccirc, carc, (),
                                              target_clear)):
                nxt = lbl.anchor + bdir * (d2 + step)
                if _candidate_has_overlap(nxt, hw_p, hh_p, (), (),
                                          np.empty((0, 2)), placed):
                    break
                d2 += step
            best = lbl.anchor + bdir * d2
        result[k] = (name, best, _nearest_dir_index(best - lbl.anchor))


def _declutter_pass(labels, result, segments, circles, arc_pts,
                    padding, gap, iterations=8):
    """Separate label pairs that overlap / sit flush together (FP-6).

    Near-coincident anchor points make the solver stack their labels until they
    merely touch (overlap area 0 → no penalty), which reads as a merged blob.
    This sweeps every movable pair whose padded bboxes are within ``gap`` and
    pushes them apart along the smaller-overlap axis (each moves half the
    deficit). A move is **committed only if it does not put the label onto
    geometry it was previously clear of** — so it never trades a label-label
    nuisance for a label-on-line error, and genuinely-coincident points (no free
    space) are left as-is rather than scattered onto lines. Deterministic;
    ``result`` is mutated in place. ``dir_idx`` is refreshed from the new
    offset so the anchor stays consistent.
    """
    by_name = {lbl.name: lbl for lbl in labels}
    movable = [k for k in range(len(result))
               if by_name.get(result[k][0]) is not None
               and by_name[result[k][0]].fixed_center is None]
    if len(movable) < 2:
        return

    def _geom_clear(lbl, center):
        hw_p, hh_p = lbl.half_w + padding, lbl.half_h + padding
        return not _candidate_has_overlap(center, hw_p, hh_p,
                                          segments, circles, arc_pts)

    for _ in range(max(0, int(iterations))):
        moved = False
        for a in range(len(movable)):
            for b in range(a + 1, len(movable)):
                ka, kb = movable[a], movable[b]
                na, ca, da = result[ka]
                nb, cb, db = result[kb]
                la, lb = by_name[na], by_name[nb]
                hwa, hha = la.half_w + padding, la.half_h + padding
                hwb, hhb = lb.half_w + padding, lb.half_h + padding
                dx = float(cb[0] - ca[0])
                dy = float(cb[1] - ca[1])
                ox = (hwa + hwb + gap) - abs(dx)
                oy = (hha + hhb + gap) - abs(dy)
                if ox <= 0 or oy <= 0:
                    continue  # already clear with gap
                # Push along the axis needing the smaller correction (minimal
                # displacement). Coincident centers (dx≈0) default to +/- so the
                # pair still separates.
                if ox <= oy:
                    s = 1.0 if dx >= 0 else -1.0
                    step = ox / 2.0
                    new_a = np.array([ca[0] - s * step, ca[1]])
                    new_b = np.array([cb[0] + s * step, cb[1]])
                else:
                    s = 1.0 if dy >= 0 else -1.0
                    step = oy / 2.0
                    new_a = np.array([ca[0], ca[1] - s * step])
                    new_b = np.array([cb[0], cb[1] + s * step])
                # Commit each end only if it does not newly hit geometry.
                if (_geom_clear(la, ca) and not _geom_clear(la, new_a)):
                    new_a = ca
                if (_geom_clear(lb, cb) and not _geom_clear(lb, new_b)):
                    new_b = cb
                if not np.array_equal(new_a, ca):
                    result[ka] = (na, new_a, _nearest_dir_index(new_a - la.anchor))
                    moved = True
                if not np.array_equal(new_b, cb):
                    result[kb] = (nb, new_b, _nearest_dir_index(new_b - lb.anchor))
                    moved = True
        if not moved:
            break


# ── Public API ────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    'distance_px': 6,           # distance from anchor to label center (pixels)
    'padding_px': 2,            # gap around label bbox (pixels)
    'point_gap_px': 3.0,        # FP-1: extra clearance from a point's marker (px)
    'geom_gap_px': 0.0,         # FP-2: clearance from lines/circles (px); >0 on
    'angle_gap_arc_px': 3,      # gap between arc and angle label (pixels)
    'angle_gap_sides_px': 3,    # gap between sides and angle label bbox (pixels)
    'w_anchor': 1.0,
    'w_label': 10.0,
    'w_geom': 8.0,
    # ── Phase-1 (P0) additions. All default to "off" so the computed layout is
    # byte-for-byte identical to the previous behaviour unless explicitly
    # enabled. See docs/archive/label_placement_improvement_plan.md.
    'position_priority': None,      # None | 'classic' | 'perceptual' | 'geogebra'
    'w_pref': 0.0,                  # weight of the canonical position-preference term
    'soft_falloff_px': 0.0,        # >0 enables graded proximity penalty (px)
    'w_soft': 1.0,                 # multiplier for the soft proximity term
    'repair_iterations': 0,        # >0 enables discrete gradient-descent repair
    'consistent_placement': False, # majority-anchor consistency pass per type
    # Round-12: region-aware consistency — align a row/column of free points only.
    'cluster_consistency': False,
    # P2-A leader lines: 'overplot' (default, no leaders) | 'leader' (displace
    # genuinely-stuck labels to a free spot + record a connector). >0 push cap px.
    'label_overflow': 'overplot',
    'leader_max_push_px': 60.0,
    # >0: also give a leader to labels whose anchor is within this many px of
    # another label's anchor (near-coincident points read as one blob).
    'leader_coincident_px': 0.0,
    # A leader only fires if the label can reach a spot this many px clear of all
    # geometry — avoids leadering into a still-dense node (scene6a). 0 = any free.
    'leader_min_clearance_px': 0.0,
    # Leaders only for POINT labels (fixed anchor). Segment/line/measure labels
    # slide along their own geometry, so a leader back to it is redundant clutter.
    'leader_points_only': True,
    # P1-D — respect an existing manual/GGB position (recommended default: true).
    # Off here to keep byte-for-byte behaviour until the global defaults are set.
    'respect_current_position': False,
    'keep_current_if_free': True,  # keep current verbatim when collision-free
    'w_inertia': 2.0,              # cost per px of displacement from current pos
    # FP-4: only respect a *substantive* manual offset. A near-zero offset is the
    # GGB default (label ~at the point), not a deliberate placement — treat it as
    # unplaced and lay it out fresh (so the bisector etc. apply).
    'respect_min_offset_px': 6.0,
    # P1-C — fill-contrast: penalise placing a label on an opaque fill whose
    # luminance is close to the label colour (hard to read). >0 enables.
    'w_fill': 0.0,
    # P-ASSOC (round-6) — penalise a label sitting closer to another labelled
    # point than to its own anchor (false visual attachment). >0 enables.
    'w_assoc': 0.0,
    # P-DASHED (round-7) — cost multiplier (<1) for overlapping a DASHED line vs
    # a solid one, so an unavoidable overlap prefers a dashed guide. 1.0 = off.
    'dashed_overlap_factor': 1.0,
    # Continuous placement (round-8) — sweep N angles instead of 8 octants so a
    # label lands at its exact resolved direction / closest FREE angle (removes
    # 45° quantisation). False = octant search (byte-identical default).
    'continuous_placement': False,
    'continuous_steps': 72,
    # Direction tolerance (round-9) — break threshold (in octant units, 0..4) for
    # accepting a free spot. With a tight value (e.g. 0.6) the search skips a
    # free-but-wrong-direction spot at base and nudges out (≤10px) to a
    # preferred-direction free spot. null = legacy (break on any free spot).
    'direction_tolerance': None,
    # Angle-label arm cap (round-10) — cap a narrow angle's label distance to this
    # fraction of the shorter arm so its wide value label stays near ITS vertex
    # instead of drifting down the bisector toward a neighbouring angle (scene4
    # 30.4°). null = uncapped (legacy).
    'angle_label_max_arm_fraction': None,
    # R1/R2 — treat the drawn angle marker (right-angle square / arc) as a real
    # obstacle at its rendered pixel radius AND exclude its wedge from the
    # point-label direction resolvers, so a vertex label is never steered into the
    # sector occupied by the marker. Off by default → byte-identical (legacy coarse
    # arc approximation, no sector exclusion). See docs/archive/TZ-label-placement-angle-markers.md.
    'angle_marker_obstacle': False,
    # FP-3 — prefer placing point labels on the bisector of the widest free gap
    # between incident sides (symmetric, "outside" the figure). Off by default.
    'point_bisector': False,
    # FP-4/FP-7 — place along the single preferred direction and nudge out to
    # clear (uniform, direction-preserving) instead of scanning 8 directions.
    'directional_placement': False,
    'directional_cap_px': 24.0,  # max push along the preferred direction (px)
    # FP-9 — keep a label's bbox inside the rendered viewport so it is never
    # cropped at the canvas edge (shifts the final center inward minimally).
    'viewport_clamp': False,
    # FP-6 — final declutter: push apart label pairs left flush/overlapping by
    # the solver (near-coincident anchors), only where it does not put a label
    # onto geometry. ``label_gap_px`` is the desired clearance between labels.
    'declutter_labels': False,
    'label_gap_px': 2.0,
    # round-18: re-seat each label at the nearest base-or-beyond distance with a
    # geom_gap clearance — pulls overshot labels in, nudges huggers out (uniform,
    # close, non-hugging). Off by default (byte-identical).
    'compact_labels': False,
    'compact_gap_px': 1.0,  # anti-hug target clearance from lines (0 = compact only)
    'compact_max_push_px': 4.0,  # cap on the outward anti-hug nudge (the "small limit")
    # P3: a label may CLIP a solid line by up to this (px) to stay close to its
    # point (dashed lines/circles are tolerated entirely). 0 = require no overlap.
    'overlap_tol_px': 2.5,
}


def _overlay_angle_radius_config(scene_or_style) -> dict:
    cfg = getattr(scene_or_style, 'style_config', None)
    overlay = getattr(cfg, 'overlay', None)
    return getattr(overlay, 'angle_radius', {}) or {}


def _overlay_label_placement_config(scene) -> dict:
    cfg = getattr(scene, 'style_config', None)
    overlay = getattr(cfg, 'overlay', None)
    return getattr(overlay, 'label_placement', {}) or {}


def compute_label_layout(scene, *, cfg=None, canonicalize: bool = False) -> dict:
    """Compute label placements for every visible labelled element. Pure.

    Does not mutate ``elem.style`` or the scene. Safe to call as part of
    keyframe snapshot passes (state is saved/restored by the caller) and
    for per-frame updates in animation-driven flows.

    Args:
        scene: AnimaGeoScene instance (read-only access to ``geo``/``style``).
        cfg: optional override for ``overlay.label_placement`` config dict.
            When ``None``, read from ``scene.style_config.overlay``.
        canonicalize: when ``True``, rewrite every non-angle placement to use
            ``label_anchor='MC'`` with an equivalent offset (bbox-corner
            displacement baked into the offset). This removes discrete anchor
            jumps when interpolating layouts between keyframes. Off by
            default so existing snapshot tests remain byte-for-byte stable.

    Returns:
        ``dict[name, LabelPlacement]`` — placements by element name. Angles
        are always ``kind='dynamic_angle'`` regardless of ``canonicalize``
        (they use MC anchor natively).
    """
    if cfg is None:
        cfg = _overlay_label_placement_config(scene)
    ptUnit = _style_ptUnit(scene.style)
    ptUnit_ggb = scene.style.export.get('ptUnit_ggb', ptUnit)
    font_size = 14.0

    distance = cfg.get('distance_px', DEFAULT_CONFIG['distance_px']) / ptUnit
    padding = cfg.get('padding_px', DEFAULT_CONFIG['padding_px']) / ptUnit
    gap_arc_px = cfg.get('angle_gap_arc_px', DEFAULT_CONFIG['angle_gap_arc_px'])
    gap_sides_px = cfg.get('angle_gap_sides_px', DEFAULT_CONFIG['angle_gap_sides_px'])
    point_gap_px = float(cfg.get('point_gap_px', DEFAULT_CONFIG['point_gap_px']) or 0.0)
    geom_gap = float(cfg.get('geom_gap_px', DEFAULT_CONFIG['geom_gap_px']) or 0.0) / ptUnit
    weights = (
        cfg.get('w_anchor', DEFAULT_CONFIG['w_anchor']),
        cfg.get('w_label', DEFAULT_CONFIG['w_label']),
        cfg.get('w_geom', DEFAULT_CONFIG['w_geom']),
    )

    # Phase-1 (P0) options — see docs/archive/label_placement_improvement_plan.md.
    position_priority = cfg.get('position_priority', DEFAULT_CONFIG['position_priority'])
    w_pref = float(cfg.get('w_pref', DEFAULT_CONFIG['w_pref']) or 0.0)
    soft_falloff_px = float(cfg.get('soft_falloff_px', DEFAULT_CONFIG['soft_falloff_px']) or 0.0)
    w_soft = float(cfg.get('w_soft', DEFAULT_CONFIG['w_soft']))
    repair_iterations = int(cfg.get('repair_iterations', DEFAULT_CONFIG['repair_iterations']) or 0)
    consistent_placement = bool(cfg.get('consistent_placement',
                                        DEFAULT_CONFIG['consistent_placement']))
    cluster_consistency = bool(cfg.get('cluster_consistency',
                                       DEFAULT_CONFIG['cluster_consistency']))
    label_overflow = cfg.get('label_overflow', DEFAULT_CONFIG['label_overflow'])
    leader_max_push = float(cfg.get('leader_max_push_px',
                                    DEFAULT_CONFIG['leader_max_push_px']) or 0.0)
    leader_coincident = float(cfg.get('leader_coincident_px',
                                      DEFAULT_CONFIG['leader_coincident_px']) or 0.0)
    leader_min_clear = float(cfg.get('leader_min_clearance_px',
                                     DEFAULT_CONFIG['leader_min_clearance_px']) or 0.0)
    leader_points_only = bool(cfg.get('leader_points_only',
                                      DEFAULT_CONFIG['leader_points_only']))
    respect_current = bool(cfg.get('respect_current_position',
                                   DEFAULT_CONFIG['respect_current_position']))
    keep_current_if_free = bool(cfg.get('keep_current_if_free',
                                        DEFAULT_CONFIG['keep_current_if_free']))
    w_inertia = float(cfg.get('w_inertia', DEFAULT_CONFIG['w_inertia']) or 0.0)
    respect_min_offset_px = float(cfg.get(
        'respect_min_offset_px', DEFAULT_CONFIG['respect_min_offset_px']) or 0.0)
    w_fill = float(cfg.get('w_fill', DEFAULT_CONFIG['w_fill']) or 0.0)
    w_assoc = float(cfg.get('w_assoc', DEFAULT_CONFIG['w_assoc']) or 0.0)
    dashed_factor = float(cfg.get('dashed_overlap_factor',
                                  DEFAULT_CONFIG['dashed_overlap_factor']) or 1.0)
    continuous = bool(cfg.get('continuous_placement',
                              DEFAULT_CONFIG['continuous_placement']))
    continuous_steps = (int(cfg.get('continuous_steps',
                                    DEFAULT_CONFIG['continuous_steps']) or 0)
                        if continuous else 0)
    dir_tol_cfg = cfg.get('direction_tolerance', DEFAULT_CONFIG['direction_tolerance'])
    dir_tol = float(dir_tol_cfg) if dir_tol_cfg is not None else None
    angle_arm_cfg = cfg.get('angle_label_max_arm_fraction',
                            DEFAULT_CONFIG['angle_label_max_arm_fraction'])
    angle_arm_cap = float(angle_arm_cfg) if angle_arm_cfg is not None else None
    point_bisector = bool(cfg.get('point_bisector', DEFAULT_CONFIG['point_bisector']))
    directional = bool(cfg.get('directional_placement',
                               DEFAULT_CONFIG['directional_placement']))
    directional_cap = float(cfg.get('directional_cap_px',
                                    DEFAULT_CONFIG['directional_cap_px']) or 0.0) / ptUnit
    viewport_clamp = bool(cfg.get('viewport_clamp', DEFAULT_CONFIG['viewport_clamp']))
    compact_labels = bool(cfg.get('compact_labels', DEFAULT_CONFIG['compact_labels']))
    compact_gap = float(cfg.get('compact_gap_px', DEFAULT_CONFIG['compact_gap_px']) or 0.0) / ptUnit
    compact_max_push = float(cfg.get('compact_max_push_px', DEFAULT_CONFIG['compact_max_push_px']) or 0.0)
    overlap_tol_px = float(cfg.get('overlap_tol_px', DEFAULT_CONFIG['overlap_tol_px']) or 0.0)
    declutter_labels = bool(cfg.get('declutter_labels',
                                    DEFAULT_CONFIG['declutter_labels']))
    label_gap_px = float(cfg.get('label_gap_px', DEFAULT_CONFIG['label_gap_px']) or 0.0)
    angle_marker_obstacle = bool(cfg.get('angle_marker_obstacle',
                                         DEFAULT_CONFIG['angle_marker_obstacle']))
    pref_ranks = _resolve_position_priority(position_priority)

    # FP-9: rendered viewport bounds (scene MU) for the optional edge clamp.
    clamp_bounds = None
    if viewport_clamp:
        try:
            clamp_bounds = scene._get_scene_bounds(padding=0)
        except Exception:
            logger.debug("viewport_clamp: scene bounds unavailable", exc_info=True)
            clamp_bounds = None

    labels = _collect_labels(
        scene, font_size,
        gap_arc_px=gap_arc_px, gap_sides_px=gap_sides_px,
        point_gap_px=point_gap_px,
    )
    if not labels:
        return {}

    ang_rshift_px = scene.style_config.defaults.get('angle', 'arc_shift_px', 0.0)

    segments, circles, arc_pts, seg_dashed, circ_dashed = _collect_obstacles(
        scene, angle_marker_obstacle=angle_marker_obstacle)

    # R2: per-label angle-marker wedges (matched by vertex ≈ anchor). The
    # direction resolvers exclude these so a vertex label is never steered into
    # the sector where the marker is drawn.
    if angle_marker_obstacle:
        marker_wedges = _collect_angle_marker_wedges(scene)
        for lbl in labels:
            lbl.blocked_wedges = tuple(
                (s, e) for (v, s, e) in marker_wedges
                if np.allclose(v, lbl.anchor[:2], atol=1e-6))

    # Preferred direction per label (away from local geometry density).
    # Skip labels with fixed center (angle bisectors — already positioned).
    obstacle_cloud = _all_obstacle_points(segments, arc_pts, density=10)
    for lbl in labels:
        if lbl.fixed_center is None:
            lbl.preferred_dir = _compute_preferred_dir(lbl.anchor, obstacle_cloud)

    # FP-3: for point-vertices, prefer the bisector of the widest free gap
    # between incident sides (symmetric, outward) over the density heuristic.
    if point_bisector:
        from .geo import lib_elements as geo
        for lbl in labels:
            if lbl.fixed_center is not None:
                continue
            elem = scene.geo.element(lbl.name)
            if elem is None or not isinstance(elem.data, geo.Point):
                continue
            bis = _bisector_of_largest_gap(
                _incident_directions(lbl.anchor, segments),
                blocked_arcs=lbl.blocked_wedges or None)
            if bis is not None:
                lbl.bisector_dir = bis
                lbl.preferred_dir = _nearest_dir_index(bis)

    # P1-D: snapshot the existing manual/GGB position (the "home" center) for each
    # movable label, so the solver can keep it / stay near it. Skip positions
    # that were produced by a previous auto-place pass (``_auto_placed``) — those
    # are not user intent and would lock the layout in over re-runs.
    if respect_current:
        from .geo import lib_elements as geo
        ggb_font_px = scene.style.export.get('fontSize')
        for lbl in labels:
            if lbl.fixed_center is not None:
                continue
            elem = scene.geo.element(lbl.name)
            if elem is None:
                continue
            ggb_raw = getattr(elem, 'ggb_raw', None) or {}
            recovered = False
            if elem.style.get('_auto_placed'):
                # A previous placement pass overwrote the style offset and set
                # our marker — but the user's ORIGINAL applet intent survives in
                # ``ggb_raw``. Re-runs (the web loads a scene twice for its
                # rendered-bounds auto-config; keyframe passes re-place too)
                # must keep respecting it instead of re-solving from scratch —
                # dropping it flipped В/Б to the opposite side on the second
                # load (TZ-label-offset-ggb-fidelity §5.3).
                raw = ggb_raw.get('label_offset_px')
                if raw is None:
                    continue
                off = [float(raw[0]), -float(raw[1])]
                recovered = True
            else:
                # Read through the resolver, not ``elem.style`` directly: GGB
                # label offsets land in the style-config layer
                # (per_name/defaults), not in ``elem.style`` — reading the
                # latter silently ignored every imported manual position.
                off = _resolve_style(scene, elem, 'label_offset_px', default=None)
            if off is None:
                continue
            mag = (float(off[0]) ** 2 + float(off[1]) ** 2) ** 0.5
            if mag < 1e-6:
                continue  # a truly zero offset carries no direction information
            # GGB semantics for imported point labels: the offset is relative to
            # the applet base (x + 4, y − 2·pointSize) up-right of the point,
            # and the renderer honours that base (part 1 of the TZ). The visual
            # position the user saw therefore includes the base — model it for
            # SUBSTANTIVE offsets below. A tiny nudge keeps the raw-offset
            # direction: it is an intent hint ("that way from the default"),
            # which the base would otherwise drown (FP-4 semantics unchanged).
            ggb_base = None
            if isinstance(elem.data, geo.Point) and ggb_raw:
                try:
                    ps_raw = float(ggb_raw.get('point_size', 5.0))
                except (TypeError, ValueError):
                    ps_raw = 5.0
                ggb_base = (4.0, 2.0 * ps_raw)
            # Sector preservation (FP-5/FP-7): bias the search toward the
            # ORIGINAL direction even for small/default GGB offsets, so the label
            # keeps its side of the feature when collision-free instead of being
            # relocated by the density/bisector heuristic. This is the dominant
            # feedback signal ("don't change the sector without need").
            # round-18: the direction is taken from the VISUAL glyph CENTRE, not
            # the raw offset vector. A GGB offset targets the text's bottom-left
            # corner (+ descender pad) and the glyphs extend up-right, so the text
            # the reader sees can sit in a DIFFERENT sector than the offset vector
            # points (scene27_3 A: offset 153° = left wedge, but the glyph is at
            # 116° = TOP wedge). Reasoning on the corner put A in the wrong part.
            # Apply the visual-centre correction only to a SUBSTANTIVE offset (a
            # deliberate placement — A). A tiny/default offset (≤ threshold) is a
            # weak directional HINT; there the half-extent would swamp the nudge
            # (a 2px north nudge → up-right), so keep the raw offset direction.
            if mag >= respect_min_offset_px:
                if ggb_base is not None:
                    # GGB-faithful labels render left-edge-on-baseline at
                    # base + offset with no descender pad (TZ part 1) — model
                    # exactly that. A recovered element carries the solver's
                    # own 'MC' anchor in elem.style; the RAW offset is
                    # 'BL'-semantic regardless.
                    off_vis = [off[0] + ggb_base[0], off[1] + ggb_base[1]]
                    cur_anchor = 'BL'
                    desc_mu = 0.0
                else:
                    off_vis = off
                    cur_anchor = _resolve_style(scene, elem, 'label_anchor', default=None)
                    desc_mu = (0.25 * ggb_font_px / ptUnit) if ggb_font_px else 0.0
                vis = _label_visual_center_offset(
                    off_vis, cur_anchor, lbl.half_w, lbl.half_h, ptUnit_ggb, desc_mu)
                vmag = float(np.linalg.norm(vis))
                unit = (vis / vmag if vmag > 1e-9
                        else _unit_vec(np.array([off[0], off[1]], dtype=float)))
            else:
                unit = _unit_vec(np.array([off[0], off[1]], dtype=float))
            # At a vertex/crossing (≥2 incident edges) centre the label on the
            # bisector of the sector its VISUAL direction points into (clean,
            # symmetric, like auto), keeping the user's chosen part of the crossing.
            inc_dirs = _incident_directions(lbl.anchor, segments)
            gap_bis = _bisector_of_gap_nearest(
                inc_dirs, unit, blocked_arcs=lbl.blocked_wedges or None)
            if gap_bis is not None:
                lbl.bisector_dir = gap_bis
                lbl.preferred_dir = _nearest_dir_index(gap_bis)
                # round-18: for a SUBSTANTIVE vertex offset, pin current_center
                # along the chosen sector bisector at BASE distance so the solver
                # commits to the user's sector and nudges OUT to clear instead of
                # grabbing a closer free spot in another sector (scene27_3 A: the
                # TOP wedge is on a line at base, free only at +~14px — "подвинуть
                # чуть вверх"). Base distance, not compact: a sector free at base
                # (scene4, rhombus) keeps the label AT base (no farther) since the
                # base candidate == the pin (0 inertia), so no regression.
                if mag >= respect_min_offset_px:
                    anchor_pt = _get_anchor(elem, scene)
                    lbl.current_center = anchor_pt + gap_bis * (distance + lbl.margin)
            else:
                # P5 (round-21): a point ON a circle reads best with its label
                # radially OUTWARD (symmetric "outside the circle"). If the GGB
                # direction is roughly outward, snap to the exact radial so the
                # label is symmetric (scene18 O: up-right → right).
                rad = _on_solid_circle_outward(lbl.anchor, circles, circ_dashed)
                if rad is not None and float(unit[0] * rad[0] + unit[1] * rad[1]) > 0.3:
                    unit = rad
                lbl.preferred_dir = _nearest_dir_index(unit)
                lbl.bisector_dir = unit
                # Isolated point (no corner): a *substantive* offset pins the
                # position (inertia / keep-if-free), but preserve the SIDE, not
                # GGB's (often large) magnitude — pinning it verbatim made labels
                # drift far ("почему все разъезжается?"). Clamp the pin distance to
                # the compact center-distance auto would produce; a near-zero
                # default offset only hints the direction and is laid out fresh.
                if mag >= respect_min_offset_px:
                    anchor_pt = _get_anchor(elem, scene)
                    mag_scene = mag / ptUnit_ggb
                    cap_scene = distance + lbl.margin + max(lbl.half_w, lbl.half_h)
                    pin_scene = min(mag_scene, cap_scene)
                    lbl.current_center = anchor_pt + unit * pin_scene

    # P1-C: per-label colour luminance + collected fills for the contrast term.
    fills = ()
    if w_fill > 0:
        fills = _collect_fills(scene)
        for lbl in labels:
            if lbl.fixed_center is not None:
                continue
            elem = scene.geo.element(lbl.name)
            lum = _color_luminance(
                _resolve_style(scene, elem, 'label_color', default=None)
                if elem is not None else None,
                default=0.2)  # assume a dark label when colour is unknown
            lbl.label_luminance = lum

    # Build a cost model only when a P0/P1 feature is active; otherwise pass None
    # so the solver takes the byte-for-byte-identical legacy ``_score_candidate``
    # path. A repair-only model (no pref/soft) is legacy-equivalent in scoring,
    # so greedy output is unchanged and repair purely improves on top.
    needs_model = (
        (pref_ranks is not None and w_pref)
        or soft_falloff_px > 0
        or repair_iterations > 0
        or respect_current
        or w_fill > 0
        or point_bisector
        or geom_gap > 0
        or directional
        or w_assoc > 0
        or dashed_factor != 1.0
        or continuous_steps > 0
    )
    cost_model = None
    if needs_model:
        # P-ASSOC: anchors of all movable (point-like) labels, so the association
        # term can keep each label nearer its own point than any other.
        assoc_anchors = (
            np.array([lbl.anchor[:2] for lbl in labels], dtype=float)
            if w_assoc > 0 else None)
        cost_model = LabelCostModel(
            weights=weights, padding=padding, ptUnit=ptUnit,
            position_priority=pref_ranks, w_pref=w_pref,
            soft_falloff_px=soft_falloff_px, w_soft=w_soft,
            w_inertia=(w_inertia if respect_current else 0.0),
            w_fill=w_fill, fills=fills, geom_gap=geom_gap,
            w_assoc=w_assoc, anchors=assoc_anchors,
            seg_dashed=seg_dashed, dashed_factor=dashed_factor,
        )

    result = _solve_greedy(
        labels, segments, circles, arc_pts, distance, padding, weights, ptUnit,
        cost_model=cost_model,
        respect_current=respect_current,
        keep_current_if_free=keep_current_if_free,
        geom_gap=geom_gap,
        directional=directional,
        directional_cap=directional_cap,
        continuous_steps=continuous_steps,
        dir_tol=dir_tol,
    )

    if cost_model is not None and repair_iterations > 0:
        _repair_pass(labels, result, segments, circles, arc_pts,
                     distance, padding, cost_model, repair_iterations,
                     respect_current=respect_current,
                     continuous_steps=continuous_steps)

    if consistent_placement:
        _consistency_pass(scene, labels, result, segments, circles, arc_pts,
                          distance, padding, respect_current=respect_current)

    # Round-12: region-aware consistency — align a row/column of free points so a
    # grid is systematic, without touching scattered points or vertices.
    if cluster_consistency:
        _cluster_consistency_pass(scene, labels, result, segments, circles,
                                  arc_pts, distance, padding)

    # FP-6: final declutter — separate label pairs left flush/overlapping by the
    # solver (near-coincident anchors), but only where free space allows.
    if declutter_labels:
        _declutter_pass(labels, result, segments, circles, arc_pts,
                        padding, label_gap_px / ptUnit)

    # round-18: pull overshot labels in toward their points (uniform closeness).
    # Uses a SMALL clearance (``compact_gap``) — the full geom_gap is what pushed
    # dense-node labels far out (scene19 A_2 to 26px while A_4 hugs at 13px); the
    # user prefers uniform closeness over a 2px gap at dense crossings.
    if compact_labels:
        _recompact_pass(labels, result, segments, circles, arc_pts,
                        distance, padding, ptUnit, compact_gap,
                        max_push_px=compact_max_push,
                        seg_dashed=seg_dashed, circ_dashed=circ_dashed,
                        overlap_tol=overlap_tol_px / ptUnit)

    # P2-A: displace genuinely-stuck labels and record leader connectors. Runs
    # last (sees final positions). Default 'overplot' → no-op (byte-identical).
    leader_specs = {}
    if label_overflow == 'leader':
        leader_specs = _leader_layout_pass(
            scene, labels, result, segments, circles, arc_pts,
            distance, padding, ptUnit, max_push=leader_max_push / ptUnit,
            coincident_px=leader_coincident,
            clear_margin=leader_min_clear / ptUnit,
            points_only=leader_points_only)

    from .geo import lib_elements as geo

    labels_by_name = {lbl.name: lbl for lbl in labels}
    placements: dict = {}

    for name, center, dir_idx in result:
        elem = scene.geo.element(name)
        if elem is None:
            continue
        lbl = labels_by_name[name]
        anchor_pt = _get_anchor(elem, scene)

        is_angle = isinstance(elem.data, geo.Angle)
        # FP-9: keep the label bbox inside the rendered viewport (static labels).
        # Angles position via their own offset math below, so they are left out.
        if clamp_bounds is not None and not is_angle:
            left, bottom, right, top = clamp_bounds
            cx = float(np.clip(center[0], left + lbl.half_w, right - lbl.half_w))
            cy = float(np.clip(center[1], bottom + lbl.half_h, top - lbl.half_h))
            center = np.array([cx, cy])
        offset_scene = center - anchor_pt
        if is_angle:
            label_anchor = lbl.fixed_anchor or 'MC'
            kind = 'dynamic_angle'
            angle_range = _resolve_style(scene, elem, 'angle_range', default='minor') or 'minor'
            base_arc_px = _resolve_style(scene, elem, 'arc_size_px', default=30)
            base_arc = compute_effective_arc_size_px(
                elem, elem.data, scene.style, base_px=base_arc_px,
                angle_range=angle_range,
                auto_radius=_resolve_style(scene, elem, 'auto_radius', default=True),
            )
            lines = int(_resolve_style(scene, elem, 'tick_count', default=1) or 1)
            outer_arc_px = _angle_effective_arc_r_px(base_arc, lines, ang_rshift_px)
            render_r_px = _angle_render_label_radius_px(
                scene, elem, base_arc, outer_arc_px, angle_range,
            )
            label_radial_offset_px = _resolve_style(
                scene, elem, 'label_radial_offset_px', default=0.0,
            )
            render_r_eff = float(render_r_px) + float(label_radial_offset_px or 0.0)
            # FP-8: honour a manual label the user placed OUTSIDE a narrow angle.
            # If we are respecting current positions and this angle carries a
            # substantive (non-auto) offset whose resulting center sits on the far
            # side of the vertex from the interior bisector, keep it outside the
            # wedge instead of snapping it back inside onto the arms.
            exterior = _angle_manual_exterior(
                scene, elem, angle_range, render_r_eff, ptUnit, ptUnit_ggb,
                respect_current, respect_min_offset_px,
            )
            angle_params = AngleParams(
                arc_r_px=outer_arc_px,
                half_w=lbl.half_w,
                half_h=lbl.half_h,
                gap_arc_px=gap_arc_px,
                gap_sides_px=gap_sides_px,
                angle_range=angle_range,
                render_r_px=render_r_eff,
                exterior=exterior,
                max_arm_fraction=angle_arm_cap,
            )
            offset_ggb = compute_angle_label_offset_px(
                elem.data, angle_params, ptUnit, ptUnit_ggb,
            )
        else:
            label_anchor = _DIR_TO_ANCHOR[dir_idx]
            kind = 'static'
            angle_params = None
            offset_ggb = (
                offset_scene[0] * ptUnit_ggb,
                offset_scene[1] * ptUnit_ggb,
            )
            if canonicalize and label_anchor != 'MC':
                # MC canonicalization: rewrite (anchor=A, offset=O_A) to
                # (anchor=MC, offset=O_mc) producing the same visual center.
                # See ui.create_label: visual_center = pos - edge_A * halfExtent
                # + O_A / ptUnit_ggb. Setting anchor=MC gives visual_center =
                # pos + O_mc / ptUnit_ggb, so O_mc = O_A - edge_A * halfExtent
                # * ptUnit_ggb (all per-axis).
                from .ui import LABEL_ANCHORS
                edge = LABEL_ANCHORS[label_anchor]  # 3D manim vector
                offset_ggb = (
                    offset_ggb[0] - float(edge[0]) * lbl.half_w * ptUnit_ggb,
                    offset_ggb[1] - float(edge[1]) * lbl.half_h * ptUnit_ggb,
                )
                label_anchor = 'MC'

        placements[name] = LabelPlacement(
            name=name,
            offset_ggb=offset_ggb,
            label_anchor=label_anchor,
            kind=kind,
            angle_params=angle_params,
            leader=leader_specs.get(name),
        )

    logger.debug("Computed layout for %d labels (canonicalize=%s)",
                 len(placements), canonicalize)
    return placements


def apply_label_layout(scene, layout: dict, *, rerender: bool = True) -> None:
    """Write a layout into ``elem.style`` and optionally rerender geometry.

    Args:
        scene: AnimaGeoScene instance.
        layout: dict returned by ``compute_label_layout``.
        rerender: when ``True`` (default), remove all mobjects and call
            ``scene.addAllGeometry(show=True)`` so labels pick up the new
            offsets. Callers that plan to rerender themselves later (e.g.
            keyframe snapshot pass) can pass ``False`` to skip the churn.
    """
    for name, pl in layout.items():
        elem = scene.geo.element(name)
        if elem is None:
            continue
        elem.style['label_offset_px'] = [pl.offset_ggb[0], pl.offset_ggb[1]]
        elem.style['label_anchor'] = pl.label_anchor
        elem.style['_auto_placed'] = True
        # P2-A: carry the leader connector (scene MU) for the renderer/exporters.
        if pl.leader is not None:
            elem.style['_leader'] = (pl.leader.anchor, pl.leader.attach)
        else:
            elem.style.pop('_leader', None)

    if rerender:
        for mobj in list(scene.mobjects):
            scene.remove(mobj)
        scene.addAllGeometry(show=True)


def apply_ema_step(prev_offset, target_offset, alpha: float) -> np.ndarray:
    """Exponential moving average step toward a target offset vector.

    Used by the dynamic LabelTracker to smooth per-frame solver output so
    small solver-score oscillations don't translate into visible jitter.
    ``alpha`` is the weight of the fresh target; smaller → smoother but
    slower convergence.
    """
    prev = np.asarray(prev_offset, dtype=float)
    target = np.asarray(target_offset, dtype=float)
    return (1.0 - alpha) * prev + alpha * target


def anchor_hysteresis_step(current_anchor: str, proposed_anchor: str,
                           counter: int, flip_frames: int):
    """Schmitt-trigger for discrete label-anchor flips.

    Returns ``(new_anchor, new_counter)``. The anchor switches only after
    ``flip_frames`` consecutive frames of the solver proposing a different
    anchor. Resets the counter whenever the proposal matches the current
    anchor or whenever a switch is committed.
    """
    if proposed_anchor == current_anchor:
        return current_anchor, 0
    counter = counter + 1
    if counter >= flip_frames:
        return proposed_anchor, 0
    return current_anchor, counter


def auto_place_labels(scene):
    """Automatically place all labels to minimize overlaps.

    Reads configuration from ``scene.style_config.overlay.label_placement``.
    Writes computed offsets back to each element's ``style['offset']``
    and refreshes the scene geometry.

    Thin wrapper around ``compute_label_layout`` + ``apply_label_layout``.
    MC canonicalization is controlled by ``canonicalize_anchor`` in the
    config (default ``False``).
    """
    cfg = _overlay_label_placement_config(scene)
    canonicalize = bool(cfg.get('canonicalize_anchor', False))
    layout = compute_label_layout(scene, cfg=cfg, canonicalize=canonicalize)
    if not layout:
        return
    apply_label_layout(scene, layout, rerender=True)
