# tparam Path Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make points constrained to conics/loci/functions fully animatable in keyframes, with a public coords→tparam API.

**Architecture:** New `animageo/geo/tparam.py` module owns all point↔parameter math (5 helpers moved from `ggb_parser.py` + new function helper + unified dispatcher). `get_independents` classifies path constraints; `keyframes.py` accepts `[x, y]` values for tparam points and adds cyclic (ellipse) and branch-aware (hyperbola) interpolation; `Construction.tparam_from_coords` is the public API.

**Tech Stack:** Python 3.13, numpy, pytest. No new dependencies.

**Spec:** `docs/archive/superpowers/specs/2026-07-03-tparam-path-animation-design.md`
**ТЗ:** `docs/archive/TZ-conic-locus-point-keyframe-animation.md`

## Global Constraints

- Work on branch `dev` (`git branch --show-current` must print `dev`).
- Interpreter for ALL test runs: `cd /Users/mac/Documents/_My_code/animageo && PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest …`
- **No AI-attribution trailers in commit messages** (project policy).
- Back-compat is sacred: `{"tparam": <float>}` keyframe dicts, `constraint='unknown'`→linear behavior for unrecognized paths, and `from animageo.parsers.ggb_parser import get_tparam_from_point_and_*` imports must all keep working.
- Do not touch animageo-web; library only.
- Hyperbola tparam is a tuple `(branch, t)`, `branch ∈ {+1.0, −1.0}` — never coerce it through `float()`.
- After EVERY task: run that task's tests AND `tests/test_keyframes.py tests/test_ggb_parser.py -q` (fast canaries).

---

### Task 1: Create `animageo/geo/tparam.py` (move 5 helpers, re-export from parser)

**Files:**
- Create: `animageo/geo/tparam.py`
- Modify: `animageo/parsers/ggb_parser.py` (delete lines ~202–272: the five `get_tparam_from_point_and_*` defs; add re-export import)
- Test: `tests/test_tparam_module.py`

**Interfaces:**
- Produces: module `animageo.geo.tparam` with `get_tparam_from_point_and_circle(point, circle)`, `..._line(point, line)`, `..._segment(point, segment)`, `..._conic(point, conic)`, `..._locus(point, locus)` — signatures and bodies identical to the current `ggb_parser.py` versions.
- `ggb_parser` continues to expose the same five names (now via import).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tparam_module.py
"""geo/tparam.py: unified point <-> path-parameter math.

The five classic helpers moved here from ggb_parser (which re-exports them
for backward compatibility); the module also owns the function-graph helper
and the tparam_from_point_and_path dispatcher (later tasks).
"""
import numpy as np
import pytest

from animageo.geo.lib_elements import Point, Circle


def test_helpers_importable_from_new_module():
    from animageo.geo import tparam as tp
    for fn in ('get_tparam_from_point_and_circle',
               'get_tparam_from_point_and_line',
               'get_tparam_from_point_and_segment',
               'get_tparam_from_point_and_conic',
               'get_tparam_from_point_and_locus'):
        assert callable(getattr(tp, fn))


def test_parser_reexports_same_objects():
    """Old import path (used by external code and the TZ repro) still works
    and points at the very same functions."""
    from animageo.geo import tparam as tp
    from animageo.parsers import ggb_parser as gp
    assert gp.get_tparam_from_point_and_conic is tp.get_tparam_from_point_and_conic
    assert gp.get_tparam_from_point_and_circle is tp.get_tparam_from_point_and_circle
    assert gp.get_tparam_from_point_and_locus is tp.get_tparam_from_point_and_locus


def test_circle_helper_smoke():
    from animageo.geo.tparam import get_tparam_from_point_and_circle
    c = Circle([0.0, 0.0], 2.0)
    t = get_tparam_from_point_and_circle(Point([0.0, 2.0]), c)
    assert np.isclose(t, np.pi / 2)
```

(Constructor verified: `Circle(center, r)` — `lib_elements.py:391`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_tparam_module.py -q`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'animageo.geo.tparam'`

- [ ] **Step 3: Create the module and re-export**

Create `animageo/geo/tparam.py` — move the five functions **verbatim** from `ggb_parser.py` lines ~202–272 (they are shown here in full; diff them against the parser before deleting there):

```python
"""Point <-> curve-parameter (tparam) math for every path type.

Single home for the coords -> parameter projections used by the GGB
importer, ``Construction.get_independents`` / ``tparam_from_coords`` and
the keyframe animation system. GeoGebra itself never stores the path
parameter in .ggb files: it re-projects the stored coords on load
(``pointChanged``), which is exactly what these helpers implement.
"""
import logging

import numpy as np

from .lib_elements import Circle, Line, Ray, Segment, LocusCurve
from .lib_conic import Conic, ConicType
from .lib_function import Function

logger = logging.getLogger(__name__)


def get_tparam_from_point_and_circle(point, circle):
    """Compute the curve parameter (angle in radians) for a point on a circle."""
    vector = point.coords - circle.center
    theta = np.arctan2(vector[1], vector[0])
    return theta % (2*np.pi)


def get_tparam_from_point_and_line(point, line):
    """Compute the linear t-parameter for a point on a line."""
    base_point = line.offset * line.normal
    t = np.dot(point.coords - base_point, line.direction)
    return t


def get_tparam_from_point_and_segment(point, segment):
    """Compute the linear t-parameter (0..1 for interior) for a point on a segment."""
    A = segment.endpoints[0]
    B = segment.endpoints[1]
    AB = B - A
    AP = point.coords - A
    t = np.dot(AP, AB) / np.dot(AB, AB)
    return t


def get_tparam_from_point_and_conic(point, conic):
    """Compute the canonical parameter for a point constrained to a conic."""
    if conic.type == ConicType.CIRCLE:
        circle = conic.as_circle()
        if circle is None:
            return None
        center, _ = circle
        vector = point.coords - center
        return np.arctan2(vector[1], vector[0]) % (2*np.pi)

    if conic.type == ConicType.ELLIPSE:
        params = conic.as_ellipse()
        if params is None:
            return None
        rel = point.coords - params['center']
        a, b = params['semi_axes']
        rot = params['rotation']
        axis_u = np.array([np.cos(rot), np.sin(rot)])
        axis_v = np.array([-np.sin(rot), np.cos(rot)])
        return np.arctan2(np.dot(rel, axis_v) / b, np.dot(rel, axis_u) / a) % (2*np.pi)

    if conic.type == ConicType.HYPERBOLA:
        params = conic.as_hyperbola()
        if params is None:
            return None
        rel = point.coords - params['center']
        _, b = params['semi_axes']
        rot = params['rotation']
        axis_u = np.array([np.cos(rot), np.sin(rot)])
        axis_v = np.array([-np.sin(rot), np.cos(rot)])
        branch = 1.0 if np.dot(rel, axis_u) >= 0 else -1.0
        t = np.arcsinh(np.dot(rel, axis_v) / (branch * b))
        return (branch, t)

    if conic.type == ConicType.PARABOLA:
        params = conic.as_parabola()
        if params is None:
            return None
        return np.dot(point.coords - params['vertex'], params['perp'])

    return None


def get_tparam_from_point_and_locus(point, locus):
    if len(locus.points) == 0:
        return None
    distances = np.linalg.norm(locus.points - point.coords, axis=1)
    idx = int(np.argmin(distances))
    if len(locus.points) <= 1:
        return 0.0
    return idx / (len(locus.points) - 1)
```

In `animageo/parsers/ggb_parser.py`: delete the five function definitions (lines ~202–272) and add to the import block at the top (after line 17 `from ..geo.utils import …`):

```python
from ..geo.tparam import (
    get_tparam_from_point_and_circle,
    get_tparam_from_point_and_line,
    get_tparam_from_point_and_segment,
    get_tparam_from_point_and_conic,
    get_tparam_from_point_and_locus,
)
```

Import-cycle note: `geo/tparam.py` imports only `lib_elements` / `lib_conic` / `lib_function` — none of them import `tparam`, and `ggb_parser` already imports `..geo.*`, so no cycle.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_tparam_module.py tests/test_ggb_parser.py tests/test_loadggb_snapshot.py -q`
Expected: ALL PASS (snapshot suite proves the move is byte-neutral for imports)

- [ ] **Step 5: Commit**

```bash
git add animageo/geo/tparam.py animageo/parsers/ggb_parser.py tests/test_tparam_module.py
git commit -m "refactor(geo): move tparam helpers to geo/tparam.py

ggb_parser re-exports the five get_tparam_from_point_and_* functions so
existing imports keep working. Groundwork for the unified coords->tparam
dispatcher (conic/locus/function keyframe animation, see docs/TZ-conic-
locus-point-keyframe-animation.md)."
```

---

### Task 2: Locus inverse — segment projection with fractional parameter

**Files:**
- Modify: `animageo/geo/tparam.py` (replace `get_tparam_from_point_and_locus`)
- Test: `tests/test_tparam_module.py` (append)

**Interfaces:**
- Produces: `get_tparam_from_point_and_locus(point, locus) -> float | None` returning `(i + frac) / (N − 1) ∈ [0, 1]` — nearest-**segment** projection (GeoGebra `GeoLocus.pointChanged` semantics), replacing nearest-vertex snap. Round-trips with `LocusCurve.point_at` (which already lerps between vertices).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tparam_module.py`:

```python
class TestLocusSegmentProjection:
    def _locus(self):
        from animageo.geo.lib_elements import LocusCurve
        # Open polyline: 4 points, 3 segments, unit spacing on a square path
        return LocusCurve([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]])

    def test_midpoint_of_first_segment(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        # (1, -0.1) projects onto segment 0 at fraction 0.5
        t = get_tparam_from_point_and_locus(Point([1.0, -0.1]), loc)
        assert np.isclose(t, 0.5 / 3)

    def test_roundtrip_with_point_at(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        t = get_tparam_from_point_and_locus(Point([2.1, 0.5]), loc)
        # foot of projection is (2, 0.5) on segment 1
        assert np.allclose(loc.point_at(t), [2.0, 0.5], atol=1e-9)

    def test_vertex_hits_exact_gridpoint(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        t = get_tparam_from_point_and_locus(Point([2.0, 2.0]), loc)
        assert np.isclose(t, 2 / 3)

    def test_clamps_beyond_ends(self):
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        loc = self._locus()
        assert np.isclose(
            get_tparam_from_point_and_locus(Point([-5.0, 0.0]), loc), 0.0)
        assert np.isclose(
            get_tparam_from_point_and_locus(Point([-5.0, 2.0]), loc), 1.0)

    def test_degenerate_empty_and_single(self):
        from animageo.geo.lib_elements import LocusCurve
        from animageo.geo.tparam import get_tparam_from_point_and_locus
        assert get_tparam_from_point_and_locus(
            Point([0, 0]), LocusCurve(np.empty((0, 2)))) is None
        assert get_tparam_from_point_and_locus(
            Point([5, 5]), LocusCurve([[1.0, 1.0]])) == 0.0
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_tparam_module.py -q`
Expected: `test_midpoint_of_first_segment` and `test_roundtrip_with_point_at` FAIL (old code snaps to the nearest vertex: 1/3 instead of 0.5/3, vertex coords instead of the segment foot). Vertex/degenerate tests may already pass.

- [ ] **Step 3: Replace the implementation**

In `animageo/geo/tparam.py` replace `get_tparam_from_point_and_locus` entirely:

```python
def get_tparam_from_point_and_locus(point, locus):
    """Project onto the locus polyline: nearest segment + fractional position.

    Mirrors GeoGebra's ``GeoLocus.pointChanged`` (closestPointIndex +
    fraction within that segment), normalized to [0, 1] so it stays
    compatible with ``LocusCurve.point_at`` which lerps between vertices.
    The old implementation snapped to the nearest *vertex*, which both
    quantized animation and shifted imported points off mid-segment
    positions.
    """
    pts = locus.points
    n = len(pts)
    if n == 0:
        return None
    if n == 1:
        return 0.0
    p = np.asarray(point.coords, dtype=float)
    a = pts[:-1]                          # segment starts, shape (n-1, 2)
    d = pts[1:] - a                       # segment vectors
    seg_len2 = np.einsum('ij,ij->i', d, d)
    safe_len2 = np.where(seg_len2 == 0.0, 1.0, seg_len2)  # zero-length guard
    t = np.clip(np.einsum('ij,ij->i', p - a, d) / safe_len2, 0.0, 1.0)
    foot = a + t[:, None] * d
    dist2 = np.einsum('ij,ij->i', foot - p, foot - p)
    i = int(np.argmin(dist2))
    return (i + float(t[i])) / (n - 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_tparam_module.py tests/test_ggb_parser.py tests/test_loadggb_snapshot.py tests/test_keyframes.py -q`
Expected: ALL PASS. If `test_loadggb_snapshot` drifts, a fixture has a point on a locus mid-segment — inspect the diff: expected drift is `tparam`-driven coords moving ONTO the polyline (closer to GGB's own rendering). If so, regenerate per the header of that test file (delete the affected JSON in `tests/snapshots/`, re-run once) and say so in the commit message.

- [ ] **Step 5: Commit**

```bash
git add animageo/geo/tparam.py tests/test_tparam_module.py
git commit -m "feat(geo): locus tparam via nearest-segment projection

Fractional parameter (i + frac)/(N-1) instead of nearest-vertex snap -
matches GeoGebra GeoLocus.pointChanged and makes the inverse symmetric
with LocusCurve.point_at (which already lerps)."
```

---

### Task 3: Function inverse + unified dispatcher `tparam_from_point_and_path`

**Files:**
- Modify: `animageo/geo/tparam.py` (append two functions)
- Test: `tests/test_tparam_module.py` (append)

**Interfaces:**
- Produces: `get_tparam_from_point_and_function(point, function) -> float` (returns `point.coords[0]`; GGB convention: function path parameter IS x).
- Produces: `tparam_from_point_and_path(point, path) -> float | tuple | None` — isinstance dispatcher over Circle / Segment / (Line, Ray) / Conic / LocusCurve / Function; `None` for anything else. **Order matters:** `Segment` and `Ray` subclass `Line`, and `Circle` must be checked before `Conic` only if `Circle` subclasses it (it does not — separate classes — but keep Circle first anyway for clarity). This is THE function Tasks 5, 7 build on.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tparam_module.py`:

```python
class TestFunctionHelperAndDispatcher:
    def test_function_tparam_is_x(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.tparam import get_tparam_from_point_and_function
        f = Function("y = x^2")
        assert get_tparam_from_point_and_function(Point([1.5, 2.25]), f) == 1.5
        # off-graph point projects along y: x is kept
        assert get_tparam_from_point_and_function(Point([1.5, 99.0]), f) == 1.5

    def test_dispatcher_all_types(self):
        from animageo.geo.lib_elements import (
            Circle, Line, Ray, Segment, LocusCurve)
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_function import Function
        from animageo.geo.tparam import tparam_from_point_and_path

        # circle: angle
        t = tparam_from_point_and_path(
            Point([0.0, 2.0]), Circle([0.0, 0.0], 2.0))
        assert np.isclose(t, np.pi / 2)

        # segment: 0..1 (Segment subclasses Line - must dispatch as segment).
        # NB: Segment(p1, p2) requires numpy arrays (does p1 - p2 internally).
        seg = Segment(np.array([0.0, 0.0]), np.array([4.0, 0.0]))
        assert np.isclose(tparam_from_point_and_path(Point([1.0, 0.0]), seg), 0.25)

        # ellipse conic: x^2/9 + y^2/4 = 1 -> t of (0, 2) is pi/2
        ell = Conic.from_coeffs(a=1/9, c=1/4, f=-1.0)
        assert np.isclose(
            tparam_from_point_and_path(Point([0.0, 2.0]), ell), np.pi / 2)

        # hyperbola conic: x^2/4 - y^2/9 = 1 -> tuple (branch, t)
        hyp = Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0)
        bt = tparam_from_point_and_path(Point([-2.0, 0.0]), hyp)
        assert isinstance(bt, tuple) and bt[0] == -1.0 and np.isclose(bt[1], 0.0)

        # locus
        loc = LocusCurve([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0]])
        assert np.isclose(
            tparam_from_point_and_path(Point([2.0, 1.0]), loc), 1.5 / 2)

        # function
        f = Function("y = x^2")
        assert tparam_from_point_and_path(Point([1.5, 2.25]), f) == 1.5

        # unsupported path type -> None
        assert tparam_from_point_and_path(Point([0, 0]), object()) is None
```

(Constructors verified: `Segment(p1, p2)` with **numpy arrays** — `lib_elements.py:242`; `Circle(center, r)` — `:391`; `Keyframe(t, values, show, hide, easing_name)` — `keyframes.py:149`.) Same for `Line`/`Ray` if you extend the test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_tparam_module.py -q`
Expected: FAIL — `ImportError`/`AttributeError` (new functions absent)

- [ ] **Step 3: Implement**

Append to `animageo/geo/tparam.py`:

```python
def get_tparam_from_point_and_function(point, function):
    """Parameter of a point on ``y = f(x)``: the natural parameter is x.

    A point slightly off the graph projects along the y-axis (x is kept) —
    same convention as GeoGebra's ``GeoFunction.pathChanged`` (parameter = x).
    """
    return float(point.coords[0])


def tparam_from_point_and_path(point, path):
    """Unified coords → tparam dispatcher for every supported path type.

    Returns a float for circle/line/segment/ray/ellipse/parabola/locus/
    function, a ``(branch, t)`` tuple for a hyperbola, or ``None`` when the
    path type is unsupported (degenerate conics also yield ``None`` via
    :func:`get_tparam_from_point_and_conic`).
    """
    if isinstance(path, Circle):
        return get_tparam_from_point_and_circle(point, path)
    if isinstance(path, Segment):          # before Line: Segment subclasses Line
        return get_tparam_from_point_and_segment(point, path)
    if isinstance(path, (Line, Ray)):      # Ray also subclasses Line
        return get_tparam_from_point_and_line(point, path)
    if isinstance(path, Conic):
        return get_tparam_from_point_and_conic(point, path)
    if isinstance(path, LocusCurve):
        return get_tparam_from_point_and_locus(point, path)
    if isinstance(path, Function):
        return get_tparam_from_point_and_function(point, path)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_tparam_module.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/geo/tparam.py tests/test_tparam_module.py
git commit -m "feat(geo): function tparam helper + unified path dispatcher

get_tparam_from_point_and_function (param = x, GGB GeoFunction convention)
and tparam_from_point_and_path covering circle/segment/ray/line/conic/
locus/function."
```

---

### Task 4: Forward `point_F` (point on a function graph)

**Files:**
- Modify: `animageo/geo/lib_commands.py` (insert after `point_L`, ~line 2253)
- Test: `tests/test_commands.py` (append) — follow that file's existing class style

**Interfaces:**
- Produces: `point_F(function, tparam=None) -> Point | None` — `Point([x, f(x)])`, `None` when `f(x)` is not finite. Auto-dispatched for GGB `Point[f]` commands via the `{command}_{shortcuts}` convention (`F` = Function).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands.py` (check its import block; `Point` and `lib_commands` are already imported there — mirror the local style):

```python
class TestPointOnFunction:
    def test_point_F_basic(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.lib_commands import point_F
        f = Function("y = x^2")
        p = point_F(f, 1.5)
        assert np.allclose(p.coords, [1.5, 2.25])

    def test_point_F_default_x_zero(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.lib_commands import point_F
        p = point_F(Function("y = x^2 + 1"))
        assert np.allclose(p.coords, [0.0, 1.0])

    def test_point_F_outside_domain_returns_none(self):
        from animageo.geo.lib_function import Function
        from animageo.geo.lib_commands import point_F
        assert point_F(Function("y = sqrt(x)"), -4.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_commands.py -k PointOnFunction -q`
Expected: FAIL — `ImportError: cannot import name 'point_F'`

- [ ] **Step 3: Implement**

In `animageo/geo/lib_commands.py`, directly after `point_L` (~line 2253):

```python
def point_F(function, tparam = None):
    """Point on a function graph ``y = f(x)``. ``tparam`` is the x-coordinate."""
    x = 0.0 if tparam is None else float(tparam)
    y = function(x)
    if not np.isfinite(y):
        return None
    return Point([x, float(y)])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_commands.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/geo/lib_commands.py tests/test_commands.py
git commit -m "feat(commands): point_F - point on a function graph by x"
```

---

### Task 5: Parser — recognize Function paths, use the dispatcher

**Files:**
- Modify: `animageo/parsers/ggb_parser.py` — two spots:
  1. the `tparam_locus` gate (~line 494): `isinstance(input0, (Circle, Line, Ray, Segment, Conic, LocusCurve))`
  2. the projection chain in the point-element handler (~lines 508–519)
- Test: `tests/test_ggb_parser_tparam_paths.py` (new)

**Interfaces:**
- Consumes: `tparam_from_point_and_path` (Task 3), `point_F` (Task 4).
- Produces: `.ggb` files with `Point[f]` on a function load with `elem.tparam == x`; conic/locus behavior unchanged (now routed through the dispatcher).

- [ ] **Step 1: Write the failing test**

Create `tests/test_ggb_parser_tparam_paths.py`. The in-memory-zip fixture pattern follows `tests/test_ggb_conditional_visibility.py`. GGB stores a function as `<expression type="function">` followed by a style-only companion `<element type="function">` which the parser skips via `xelems_left_to_pass` — the fixture MUST include that companion node.

```python
"""Parser: tparam detection for points on function graphs (and the
dispatcher-backed conic path, regression)."""
import os
import tempfile
import zipfile

import numpy as np

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser


def _make_ggb(body: str) -> str:
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<geogebra format="5.0">
<euclidianView>
    <size width="600" height="400"/>
    <coordSystem xZero="300" yZero="200" scale="50" yscale="50"/>
    <evSettings axes="false" grid="false"/>
    <bgColor r="255" g="255" b="255"/>
</euclidianView>
<construction>
{body}
</construction>
</geogebra>
"""
    fd, path = tempfile.mkstemp(suffix=".ggb")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("geogebra.xml", xml)
    return path


def _load(body: str) -> Construction:
    path = _make_ggb(body)
    try:
        c = Construction()
        view = {"ptUnit": 1, "ptWidth": 600, "ptHeight": 400,
                "ptXZero": 300, "ptYZero": 200}
        ggb_parser.load(c, view, path, debug=False)
        return c
    finally:
        os.remove(path)


FUNCTION_POINT = """
    <expression label="f" exp="f(x) = x^2" type="function"/>
    <element type="function" label="f">
        <show object="true" label="true"/>
        <objColor r="0" g="0" b="0" alpha="0"/>
    </element>
    <command name="Point">
        <input a0="f"/>
        <output a0="P"/>
    </command>
    <element type="point" label="P">
        <show object="true" label="true"/>
        <coords x="1.5" y="2.25" z="1"/>
    </element>
"""


def test_point_on_function_gets_tparam():
    c = _load(FUNCTION_POINT)
    p = c.element("P")
    assert p is not None
    assert p.tparam is not None
    assert np.isclose(p.tparam, 1.5)


def test_point_on_function_rebuilds_on_graph():
    c = _load(FUNCTION_POINT)
    c.update_tparam("P", 2.0)
    c.rebuild()
    assert np.allclose(c.element("P").data.coords, [2.0, 4.0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_ggb_parser_tparam_paths.py -q`
Expected: FAIL — `p.tparam is None` (Function not in the `tparam_locus` gate)

- [ ] **Step 3: Implement**

In `ggb_parser.py`:

1. The gate (~line 494) — add `Function` (available via the `lib_elements` star import):

```python
                    if isinstance(input0, (Circle, Line, Ray, Segment, Conic, LocusCurve, Function)):
                        tparam_locus = input0
```

2. The projection chain in the point-element handler — replace the whole isinstance ladder:

```python
                tparam = None
                if tparam_locus:
                    if isinstance(tparam_locus, Circle):
                        tparam = get_tparam_from_point_and_circle(Point(coords), tparam_locus)
                    elif isinstance(tparam_locus, Segment):
                        tparam = get_tparam_from_point_and_segment(Point(coords), tparam_locus)
                    elif isinstance(tparam_locus, (Line, Ray)):
                        tparam = get_tparam_from_point_and_line(Point(coords), tparam_locus)
                    elif isinstance(tparam_locus, Conic):
                        tparam = get_tparam_from_point_and_conic(Point(coords), tparam_locus)
                    elif isinstance(tparam_locus, LocusCurve):
                        tparam = get_tparam_from_point_and_locus(Point(coords), tparam_locus)
```

with:

```python
                tparam = None
                if tparam_locus:
                    tparam = tparam_from_point_and_path(Point(coords), tparam_locus)
```

and extend the Task-1 import to include the dispatcher:

```python
from ..geo.tparam import (
    get_tparam_from_point_and_circle,
    get_tparam_from_point_and_line,
    get_tparam_from_point_and_segment,
    get_tparam_from_point_and_conic,
    get_tparam_from_point_and_locus,
    tparam_from_point_and_path,
)
```

(NOTE: the current chain checks `isinstance(tparam_locus, Segment)` BEFORE `(Line, Ray)` — if the live code orders it differently, the dispatcher already fixes the order; just verify the snapshot suite below.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_ggb_parser_tparam_paths.py tests/test_ggb_parser.py tests/test_loadggb_snapshot.py tests/test_ggb_conditional_visibility.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/parsers/ggb_parser.py tests/test_ggb_parser_tparam_paths.py
git commit -m "feat(parser): points on function graphs get tparam at import

The tparam_locus gate accepts Function and the projection goes through
the unified tparam_from_point_and_path dispatcher."
```

---

### Task 6: `get_independents` — classify conic/locus/function constraints

**Files:**
- Modify: `animageo/geo/construction.py` (~lines 465–490 constraint loop; module-level map near top)
- Test: `tests/test_construction.py` (append)

**Interfaces:**
- Consumes: `ConicType` (star-imported into `construction.py` via `lib_elements`; verify `ConicType` resolves there — if not, add `from .lib_conic import ConicType` next to the existing imports).
- Produces: `get_independents()[name]['constraint'] ∈ {'circle','segment','ray','line','ellipse','hyperbola','parabola','locus','function','unknown'}` — Task 8's kind map consumes exactly these strings. Hyperbola `'tparam'` is emitted as `[branch, t]` list (JSON-safe).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_construction.py` (check its import header: it already imports `Construction`, `Element`, `Command`, `Point`; add the rest locally in the test):

```python
class TestTparamConstraintClassification:
    """Path-type classification for tparam points (conic/locus/function)."""

    def _constr_with_path(self, path_name, path_data, point_coords, tparam):
        from animageo.geo.lib_commands import Command
        c = Construction()
        c.add(Element(path_name, path_data, fixed=True))
        c.add(Element('D', Point(point_coords), tparam=tparam))
        c.add(Command('Point', [path_name], ['D']))
        return c

    def test_ellipse_constraint(self):
        from animageo.geo.lib_conic import Conic
        ell = Conic.from_coeffs(a=1/9, c=1/4, f=-1.0)
        c = self._constr_with_path('c', ell, [0.0, 2.0], np.pi / 2)
        info = c.get_independents()['D']
        assert info['type'] == 'tparam_point'
        assert info['constraint'] == 'ellipse'
        assert np.isclose(info['tparam'], np.pi / 2)

    def test_hyperbola_constraint_tuple_tparam(self):
        from animageo.geo.lib_conic import Conic
        hyp = Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0)
        c = self._constr_with_path('h', hyp, [-2.0, 0.0], (-1.0, 0.0))
        info = c.get_independents()['D']
        assert info['constraint'] == 'hyperbola'
        assert list(info['tparam']) == [-1.0, 0.0]   # JSON-safe list

    def test_parabola_constraint(self):
        from animageo.geo.lib_conic import Conic
        # y^2 = 4x  ->  -4x + y^2 = 0
        par = Conic.from_coeffs(c=1.0, d=-4.0)
        c = self._constr_with_path('p', par, [1.0, 2.0], 2.0)
        assert c.get_independents()['D']['constraint'] == 'parabola'

    def test_locus_constraint(self):
        from animageo.geo.lib_elements import LocusCurve
        loc = LocusCurve([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        c = self._constr_with_path('loc', loc, [1.0, 0.0], 0.5)
        assert c.get_independents()['D']['constraint'] == 'locus'

    def test_function_constraint(self):
        from animageo.geo.lib_function import Function
        f = Function("y = x^2")
        c = self._constr_with_path('f', f, [1.5, 2.25], 1.5)
        assert c.get_independents()['D']['constraint'] == 'function'

    def test_circle_constraint_unchanged(self):
        from animageo.geo.lib_elements import Circle
        circ = Circle([0.0, 0.0], 2.0)
        c = self._constr_with_path('k', circ, [0.0, 2.0], np.pi / 2)
        assert c.get_independents()['D']['constraint'] == 'circle'
```

(`np` import: `tests/test_construction.py` already imports numpy — verify, else add.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_construction.py -k TparamConstraint -q`
Expected: FAIL — conic/locus/function report `constraint == 'unknown'`

- [ ] **Step 3: Implement**

In `animageo/geo/construction.py`:

1. Module level (near other imports/constants; verify `ConicType` resolves — the file star-imports geometry via its existing imports; if `ConicType` is NOT in scope, add `from .lib_conic import ConicType`):

```python
# tparam_point constraint labels for non-degenerate conic types; degenerate
# conics keep 'unknown' (they are not sensible animation paths).
_CONIC_CONSTRAINTS = {
    ConicType.CIRCLE: 'circle',
    ConicType.ELLIPSE: 'ellipse',
    ConicType.HYPERBOLA: 'hyperbola',
    ConicType.PARABOLA: 'parabola',
}
```

2. Extend the classification loop (currently `Circle/Segment/Ray/Line` at ~472–483) with three new branches and make the emitted tparam JSON-safe:

```python
            if elem and isinstance(elem.data, Point) and elem.tparam is not None and st['input_commands']:
                cmd = self.commandByElementName(name)
                constraint = 'unknown'
                if cmd:
                    for inp_name in cmd.inputs:
                        inp_obj = self.objectByName(inp_name) if isinstance(inp_name, str) else inp_name
                        inp_data = inp_obj.data if hasattr(inp_obj, 'data') else inp_obj
                        if isinstance(inp_data, Circle):
                            constraint = 'circle'
                            break
                        elif isinstance(inp_data, Segment):
                            constraint = 'segment'
                            break
                        elif isinstance(inp_data, Ray):
                            constraint = 'ray'
                            break
                        elif isinstance(inp_data, Line):
                            constraint = 'line'
                            break
                        elif isinstance(inp_data, Conic):
                            constraint = _CONIC_CONSTRAINTS.get(inp_data.type, 'unknown')
                            break
                        elif isinstance(inp_data, LocusCurve):
                            constraint = 'locus'
                            break
                        elif isinstance(inp_data, Function):
                            constraint = 'function'
                            break
                tp = elem.tparam
                result[name] = {
                    'type': 'tparam_point',
                    'constraint': constraint,
                    'tparam': list(tp) if isinstance(tp, (tuple, list)) else tp,
                    'coords': elem.data.coords.tolist()
                }
                continue
```

(`Conic`, `LocusCurve`, `Function` are already referenced elsewhere in `construction.py` (see `update()` ~line 176), so they are in scope.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_construction.py tests/test_keyframes.py tests/test_jsxgraph_export.py -q`
Expected: ALL PASS (jsxgraph suite = canary that independents consumers survive)

- [ ] **Step 5: Commit**

```bash
git add animageo/geo/construction.py tests/test_construction.py
git commit -m "feat(construction): classify conic/locus/function tparam constraints

get_independents now reports ellipse/hyperbola/parabola (by ConicType),
locus and function instead of 'unknown'; hyperbola tparam emitted as a
JSON-safe [branch, t] list."
```

---

### Task 7: Public `Construction.tparam_from_coords`

**Files:**
- Modify: `animageo/geo/construction.py` (new method after `update_tparam`, ~line 443)
- Test: `tests/test_construction.py` (append)

**Interfaces:**
- Consumes: `tparam_from_point_and_path` (Task 3), `commandByElementName`, `objectByName`.
- Produces: `Construction.tparam_from_coords(name: str, coords) -> float | tuple | None` — THE public coords→tparam API (web replaces its converter with this; Task 8 uses it for `[x, y]` keyframes).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_construction.py` inside `TestTparamConstraintClassification` or as a new class:

```python
class TestTparamFromCoords:
    def _ellipse_constr(self):
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        ell = Conic.from_coeffs(a=1/9, c=1/4, f=-1.0)   # x^2/9 + y^2/4 = 1
        c.add(Element('c', ell, fixed=True))
        c.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        c.add(Command('Point', ['c'], ['D']))
        return c

    def test_ellipse_coords_roundtrip(self):
        c = self._ellipse_constr()
        t = c.tparam_from_coords('D', [0.0, 2.0])
        assert np.isclose(t, np.pi / 2)
        # slightly off-curve coords still project sanely
        t2 = c.tparam_from_coords('D', [0.0, 2.05])
        assert np.isclose(t2, np.pi / 2)

    def test_hyperbola_returns_tuple(self):
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        hyp = Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0)
        c.add(Element('h', hyp, fixed=True))
        c.add(Element('D', Point([2.0, 0.0]), tparam=(1.0, 0.0)))
        c.add(Command('Point', ['h'], ['D']))
        bt = c.tparam_from_coords('D', [-2.0, 0.0])
        assert isinstance(bt, tuple) and bt[0] == -1.0

    def test_free_point_returns_none(self):
        c = Construction()
        c.add(Element('A', Point([1.0, 1.0])))
        assert c.tparam_from_coords('A', [2.0, 2.0]) is None

    def test_unknown_name_returns_none(self):
        c = Construction()
        assert c.tparam_from_coords('nope', [0.0, 0.0]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_construction.py -k TparamFromCoords -q`
Expected: FAIL — `AttributeError: 'Construction' object has no attribute 'tparam_from_coords'`

- [ ] **Step 3: Implement**

In `animageo/geo/construction.py`, after `update_tparam` (~line 443):

```python
    def tparam_from_coords(self, name, coords):
        """Coords → path parameter for a path-constrained (tparam) point.

        Public API for animation clients: given captured ``[x, y]``
        coordinates of point ``name`` (constrained to a circle/segment/
        ray/line/conic/locus/function), compute the tparam that places
        the point at (the projection of) those coordinates. Returns a
        float — or a ``(branch, t)`` tuple for a hyperbola — or ``None``
        (with a warning) when the element is not a tparam point or its
        path is not recognized.
        """
        from .tparam import tparam_from_point_and_path
        elem = self.element(name)
        if elem is None or elem.tparam is None:
            logger.warning("tparam_from_coords('%s'): not a tparam point", name)
            return None
        cmd = self.commandByElementName(name)
        if not cmd:
            logger.warning("tparam_from_coords('%s'): no defining command", name)
            return None
        pt = Point(coords)
        for inp_name in cmd.inputs:
            inp_obj = self.objectByName(inp_name) if isinstance(inp_name, str) else inp_name
            inp_data = inp_obj.data if hasattr(inp_obj, 'data') else inp_obj
            t = tparam_from_point_and_path(pt, inp_data)
            if t is not None:
                return t
        logger.warning("tparam_from_coords('%s'): path input not recognized", name)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_construction.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/geo/construction.py tests/test_construction.py
git commit -m "feat(construction): public tparam_from_coords(name, coords) API

Single library entry point for coords->tparam over every path type;
lets animageo-web drop its partial per-type converter."
```

---

### Task 8: `_parse_value` — accept `[x, y]`, constraint-aware kinds, hyperbola values

**Files:**
- Modify: `animageo/keyframes.py` — `_parse_value` (~line 305) and `_get_current_value` (~line 457)
- Test: `tests/test_keyframes.py` (append)

**Interfaces:**
- Consumes: `Construction.tparam_from_coords` (Task 7), constraint strings (Task 6).
- Produces: `_parse_value(name, raw_value, info, construction=None) -> (kind, value, direction)` where kind ∈ `{'point','tparam_circle','tparam_linear','tparam_hyperbola','var','bool'}`. New module-level helper `_tparam_kind(constraint) -> str`. Task 9 threads `construction`; Task 10 updates scene call sites. **Signature is backward-compatible** (positional 3-arg calls keep working).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keyframes.py` (it already imports `_parse_value` internals or accesses via module — follow its existing import style; `from animageo.keyframes import _parse_value, _get_current_value`):

```python
class TestTparamPathParseValue:
    """[x,y] values + constraint-aware interpolation kinds (conic/locus/function)."""

    def _ellipse_constr(self):
        from animageo.geo.construction import Construction
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        c.add(Element('c', Conic.from_coeffs(a=1/9, c=1/4, f=-1.0), fixed=True))
        c.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        c.add(Command('Point', ['c'], ['D']))
        return c

    def test_kind_by_constraint(self):
        from animageo.keyframes import _parse_value
        cases = {
            'circle': 'tparam_circle',
            'ellipse': 'tparam_circle',
            'hyperbola': 'tparam_hyperbola',
            'parabola': 'tparam_linear',
            'segment': 'tparam_linear',
            'ray': 'tparam_linear',
            'line': 'tparam_linear',
            'locus': 'tparam_linear',
            'function': 'tparam_linear',
            'unknown': 'tparam_linear',
        }
        for constraint, expected in cases.items():
            info = {'type': 'tparam_point', 'constraint': constraint}
            value = {'tparam': [1.0, 0.5]} if constraint == 'hyperbola' \
                else {'tparam': 0.5}
            kind, _, _ = _parse_value('D', value, info)
            assert kind == expected, constraint

    def test_dict_tparam_still_works(self):
        from animageo.keyframes import _parse_value
        info = {'type': 'tparam_point', 'constraint': 'circle'}
        kind, val, direction = _parse_value(
            'D', {'tparam': 1.25, 'direction': 'ccw'}, info)
        assert (kind, val, direction) == ('tparam_circle', 1.25, 'ccw')

    def test_hyperbola_dict_list_value(self):
        from animageo.keyframes import _parse_value
        info = {'type': 'tparam_point', 'constraint': 'hyperbola'}
        kind, val, _ = _parse_value('D', {'tparam': [-1.0, 0.7]}, info)
        assert kind == 'tparam_hyperbola'
        assert val == (-1.0, 0.7)

    def test_xy_value_projects_via_construction(self):
        import numpy as np
        from animageo.keyframes import _parse_value
        c = self._ellipse_constr()
        info = c.get_independents()['D']
        kind, val, _ = _parse_value('D', [0.0, 2.0], info, c)
        assert kind == 'tparam_circle'
        assert np.isclose(val, np.pi / 2)

    def test_xy_without_construction_raises(self):
        import pytest
        from animageo.keyframes import _parse_value
        info = {'type': 'tparam_point', 'constraint': 'ellipse'}
        with pytest.raises(ValueError, match='construction'):
            _parse_value('D', [0.0, 2.0], info)

    def test_get_current_value_hyperbola_tuple(self):
        from animageo.keyframes import _get_current_value
        info = {'type': 'tparam_point', 'tparam': [-1.0, 0.5]}
        assert _get_current_value(info) == (-1.0, 0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_keyframes.py -k TparamPathParseValue -q`
Expected: FAIL — kind map wrong for ellipse ('tparam_linear' via old constraint check), `[x,y]` raises the old "requires {tparam}" error, `_get_current_value` crashes with `float()` on list.

- [ ] **Step 3: Implement**

In `animageo/keyframes.py`:

1. Module-level helper (above `_parse_value`):

```python
# Interpolation kind per path constraint. Closed paths (circle, ellipse)
# interpolate cyclically with 2*pi wrap; a hyperbola keeps its branch and
# lerps the scalar part; everything else (incl. 'unknown') lerps linearly.
_TPARAM_CYCLIC = frozenset({'circle', 'ellipse'})


def _tparam_kind(constraint):
    if constraint in _TPARAM_CYCLIC:
        return 'tparam_circle'
    if constraint == 'hyperbola':
        return 'tparam_hyperbola'
    return 'tparam_linear'
```

2. Replace the `tparam_point` branch of `_parse_value` and extend the signature:

```python
def _parse_value(name, raw_value, info, construction=None):
    """Convert raw JSON value to internal representation.

    Returns (kind, parsed_value, angle_direction).

    ``construction`` enables the ``[x, y]`` form for tparam points: the
    coordinates are projected onto the point's path via
    ``Construction.tparam_from_coords``.
    """
    etype = info['type']

    if etype == 'free_point':
        if not isinstance(raw_value, (list, tuple)) or len(raw_value) != 2:
            raise ValueError(f"'{name}': free_point requires [x, y], got {raw_value}")
        return 'point', np.array(raw_value, dtype=float), None

    if etype == 'tparam_point':
        constraint = info.get('constraint', 'line')
        kind = _tparam_kind(constraint)
        if isinstance(raw_value, dict):
            tparam = raw_value.get('tparam')
            direction = raw_value.get('direction', 'short')
            if tparam is None:
                raise ValueError(
                    f"'{name}': tparam_point dict requires 'tparam' key"
                )
            if isinstance(tparam, (list, tuple)):      # hyperbola [branch, t]
                tparam = (float(tparam[0]), float(tparam[1]))
            else:
                tparam = float(tparam)
            return kind, tparam, direction
        if (isinstance(raw_value, (list, tuple)) and len(raw_value) == 2
                and all(isinstance(v, (int, float)) for v in raw_value)):
            if construction is None:
                raise ValueError(
                    f"'{name}': [x, y] for a tparam_point needs the "
                    f"construction — pass keyframes through "
                    f"KeyframeSequence.from_json / play_keyframes"
                )
            tparam = construction.tparam_from_coords(name, list(raw_value))
            if tparam is None:
                raise ValueError(
                    f"'{name}': could not project {raw_value} onto the path"
                )
            return kind, tparam, 'short'
        raise ValueError(
            f"'{name}': tparam_point requires {{\"tparam\": value}} or [x, y], "
            f"got {raw_value}"
        )
```

(the `number/measure/angle/boolean` tail of the function is unchanged)

3. Fix `_get_current_value` (~line 457) — the `tparam_point` branch:

```python
    if etype == 'tparam_point':
        t = info['tparam']
        if isinstance(t, (list, tuple)):
            return (float(t[0]), float(t[1]))
        return float(t)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_keyframes.py tests/test_keyframe_labels.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/keyframes.py tests/test_keyframes.py
git commit -m "feat(keyframes): [x,y] values for tparam points + path-aware kinds

_parse_value(construction=...) projects coords via tparam_from_coords;
ellipse joins circle in cyclic interpolation, hyperbola gets its own
kind with (branch, t) values; _get_current_value survives tuples."
```

---

### Task 9: Interpolator hyperbola kind, interval threading, apply

**Files:**
- Modify: `animageo/keyframes.py` — `Interpolator` (~line 66), `_build_intervals` (~line 390), `KeyframeSequence.from_json` (~line 300), `apply_parsed_value` (~line 344)
- Test: `tests/test_keyframes.py` (append)

**Interfaces:**
- Consumes: `_parse_value(..., construction)` (Task 8).
- Produces: `Interpolator(kind='tparam_hyperbola').at(t)` → `(branch, t)` tuple (branch snaps at 0.5, scalar lerps); `Interpolator._hyperbola_pair(v) -> (branch, t)` staticmethod; `_build_intervals(keyframes, element_info, construction=None)`; `apply_parsed_value` routes `tparam_hyperbola` → `update_tparam`. End-to-end: `KeyframeSequence.from_json` with `[x, y]` values yields working interpolators.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_keyframes.py`:

```python
class TestHyperbolaInterpolatorAndPipeline:
    def test_interpolator_lerps_scalar_keeps_branch(self):
        from animageo.keyframes import Interpolator
        interp = Interpolator('D', 'tparam_hyperbola',
                              start=(1.0, 0.0), end=(1.0, 2.0),
                              easing=lambda t: t)
        b, t = interp.at(0.5)
        assert b == 1.0 and abs(t - 1.0) < 1e-12

    def test_interpolator_branch_snaps_at_half(self):
        from animageo.keyframes import Interpolator
        interp = Interpolator('D', 'tparam_hyperbola',
                              start=(1.0, 0.5), end=(-1.0, 0.5),
                              easing=lambda t: t)
        assert interp.at(0.25)[0] == 1.0
        assert interp.at(0.75)[0] == -1.0

    def _ellipse_constr(self):
        from animageo.geo.construction import Construction
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        c = Construction()
        c.add(Element('c', Conic.from_coeffs(a=1/9, c=1/4, f=-1.0), fixed=True))
        c.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        c.add(Command('Point', ['c'], ['D']))
        return c

    def test_from_json_with_xy_values_end_to_end(self):
        import numpy as np
        from animageo.keyframes import KeyframeSequence, apply_parsed_value
        c = self._ellipse_constr()
        seq = KeyframeSequence.from_json({
            "keyframes": [
                {"t": 0, "values": {"D": [3.0, 0.0]}},
                {"t": 2, "values": {"D": [0.0, 2.0]}, "easing": "linear"},
            ]
        }, c)
        interval = seq.intervals[0]
        assert len(interval.interpolators) == 1
        interp = interval.interpolators[0]
        assert interp.kind == 'tparam_circle'          # ellipse -> cyclic
        assert np.isclose(interp.at(0.0), 0.0)
        assert np.isclose(interp.at(1.0), np.pi / 2)
        # mid-interval: apply + rebuild moves D along the ellipse
        apply_parsed_value(c, 'D', interp.kind, interp.at(0.5))
        c.rebuild()
        x, y = c.element('D').data.coords
        assert np.isclose(x**2 / 9 + y**2 / 4, 1.0, atol=1e-9)
        assert x > 0 and y > 0                          # first quadrant
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_keyframes.py -k HyperbolaInterpolatorAndPipeline -q`
Expected: FAIL — `Interpolator.at` has no `tparam_hyperbola` branch (tuple lerp TypeError), `from_json` fails on `[x, y]` because `_build_intervals` doesn't pass the construction.

- [ ] **Step 3: Implement**

In `animageo/keyframes.py`:

1. `Interpolator` — extend the kind comment, add the staticmethod and the `at` branch (before the final scalar-lerp fallthrough):

```python
    @staticmethod
    def _hyperbola_pair(v):
        """Normalize a hyperbola tparam to (branch, t); bare scalars mean branch +1."""
        if isinstance(v, (tuple, list)):
            return (1.0 if float(v[0]) >= 0 else -1.0, float(v[1]))
        return (1.0, float(v))
```

```python
        if self.kind == 'tparam_hyperbola':
            b0, t0 = self._hyperbola_pair(self.start)
            b1, t1 = self._hyperbola_pair(self.end)
            branch = b0 if et < 0.5 else b1
            return (branch, (1 - et) * t0 + et * t1)
```

Also update the kind list comment in `__init__`:

```python
        #   'tparam_circle'    — angular t on a circle/ellipse (uses angle_direction)
        #   'tparam_linear'    — scalar t on segment/line/ray/parabola/locus/function
        #   'tparam_hyperbola' — (branch, t): branch snaps at 0.5, t lerps
```

2. `_build_intervals` — signature + threading + tuple-safe change guard. Replace the header and the two `_parse_value` calls, and the "skip if unchanged" block:

```python
def _build_intervals(keyframes, element_info, construction=None):
```

```python
    for name, raw_value in keyframes[0].values.items():
        info = element_info[name]
        current_values[name] = _parse_value(name, raw_value, info, construction)
```

```python
        for name, raw_value in kf_next.values.items():
            info = element_info[name]
            target_values[name] = _parse_value(name, raw_value, info, construction)
```

```python
            # Skip if value hasn't changed (for non-bool types)
            if kind == 'tparam_hyperbola':
                b0, t0 = Interpolator._hyperbola_pair(start_val)
                b1, t1 = Interpolator._hyperbola_pair(end_val)
                if b0 == b1 and np.isclose(t0, t1):
                    current_values[name] = (kind, end_val, direction)
                    continue
            elif kind != 'bool' and kind != 'point':
                if np.isclose(start_val, end_val):
                    current_values[name] = (kind, end_val, direction)
                    continue
            elif kind == 'point':
                if np.allclose(start_val, end_val):
                    current_values[name] = (kind, end_val, direction)
                    continue
```

3. `KeyframeSequence.from_json` (~line 300):

```python
        intervals = _build_intervals(keyframes, element_info, construction)
```

4. `apply_parsed_value` (~line 355):

```python
    if kind in ('tparam_circle', 'tparam_linear', 'tparam_hyperbola'):
        construction.update_tparam(name, val)
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_keyframes.py tests/test_keyframe_labels.py tests/test_dynamic_tracker.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/keyframes.py tests/test_keyframes.py
git commit -m "feat(keyframes): hyperbola interpolator kind + construction threading

Interpolator handles (branch, t) tuples (branch snaps mid-interval, t
lerps); _build_intervals/from_json thread the construction so [x,y]
keyframe values project onto the path; apply routes the new kind
through update_tparam."
```

---

### Task 10: Scene snapshot passes survive tuples, pass the construction

**Files:**
- Modify: `animageo/animageo.py` — `_snapshot_independents` (~line 1231), three `_parse_value` call sites (~lines 1253, 1323, 1352)
- Test: `tests/test_keyframes.py` (append; scene-level)

**Interfaces:**
- Consumes: `_parse_value(..., construction)` (Task 8).
- Produces: `_snapshot_independents` emits `{'tparam': [branch, t]}` for hyperbola points (no `float()` crash); all scene-side `_parse_value` calls pass `self.geo` so `[x, y]` keyframes work in `_apply_keyframe_state` and the label-snapshot pre-pass.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_keyframes.py`:

```python
class TestSceneSnapshotTparamPaths:
    def _scene_with_hyperbola_point(self):
        from animageo.animageo import AnimaGeoScene
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        scene = AnimaGeoScene()
        scene.geo.add(Element(
            'h', Conic.from_coeffs(a=1/4, c=-1/9, f=-1.0), fixed=True))
        scene.geo.add(Element('D', Point([2.0, 0.0]), tparam=(1.0, 0.0)))
        scene.geo.add(Command('Point', ['h'], ['D']))
        return scene

    def test_snapshot_keeps_hyperbola_tuple(self):
        scene = self._scene_with_hyperbola_point()
        raw, info_map = scene._snapshot_independents()
        assert raw['D'] == {'tparam': [1.0, 0.0]}
        assert info_map['D']['constraint'] == 'hyperbola'

    def test_apply_keyframe_state_accepts_xy(self):
        import numpy as np
        from animageo.animageo import AnimaGeoScene
        from animageo.geo.lib_elements import Element, Point
        from animageo.geo.lib_conic import Conic
        from animageo.geo.lib_commands import Command
        from animageo.keyframes import Keyframe
        scene = AnimaGeoScene()
        scene.geo.add(Element(
            'c', Conic.from_coeffs(a=1/9, c=1/4, f=-1.0), fixed=True))
        scene.geo.add(Element('D', Point([3.0, 0.0]), tparam=0.0))
        scene.geo.add(Command('Point', ['c'], ['D']))
        kf = Keyframe(t=0, values={'D': [0.0, 2.0]}, show=[], hide=[],
                      easing_name='smooth')
        scene._apply_keyframe_state(kf, scene.geo.get_independents(),
                                    update_scene=False)
        assert np.allclose(scene.geo.element('D').data.coords, [0.0, 2.0],
                           atol=1e-9)
```

(Constructor verified: `Keyframe(t, values=None, show=None, hide=None, easing_name='smooth')` — `keyframes.py:149`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_keyframes.py -k SceneSnapshotTparamPaths -q`
Expected: FAIL — `float(info['tparam'])` raises `TypeError` on the list; `_apply_keyframe_state` raises/warns "requires {tparam}" because the construction isn't passed.

- [ ] **Step 3: Implement**

In `animageo/animageo.py`:

1. `_snapshot_independents` (~line 1230):

```python
            elif etype == 'tparam_point':
                t = info['tparam']
                raw[name] = {
                    'tparam': list(t) if isinstance(t, (list, tuple)) else float(t)
                }
```

2. Three call sites — add the construction argument:

~line 1253 (`_apply_keyframe_state`):
```python
                kind, val, _dir = _parse_value(name, raw_value, info, self.geo)
```
~line 1323 (`_compute_keyframe_label_layouts`, apply loop):
```python
                    kind, val, _dir = _parse_value(name, raw_value, info, self.geo)
```
~line 1352 (same method, restore loop):
```python
                kind, val, _dir = _parse_value(name, raw_value, info, self.geo)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_keyframes.py tests/test_keyframe_labels.py tests/test_value_labels.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add animageo/animageo.py tests/test_keyframes.py
git commit -m "fix(scene): keyframe snapshot passes handle tuple tparams and [x,y]

_snapshot_independents no longer float()-coerces hyperbola (branch, t);
all scene-side _parse_value calls pass the construction."
```

---

### Task 11: Acceptance — real «вписанный шестиугольник» construction (TZ §2)

**Files:**
- Copy fixture: `examples/0_sample_scenes/hex_tYwHUgEyock.ggb` (from `GET https://animageo.ru/api/shared/tYwHUgEyock/ggb`, field `ggb_base64`; a copy already exists at the session scratchpad as `hex.ggb`). `examples/` is untracked — the test must skip when the file is absent.
- Test: `tests/test_tparam_animation_acceptance.py` (new)

**Interfaces:**
- Consumes: everything from Tasks 1–10.
- Produces: the TZ acceptance criteria as automated checks.

- [ ] **Step 1: Place the fixture**

```bash
OUT=/private/tmp/claude-501/-Users-mac-Documents--My-code-animageo/6eb0b49a-7650-419f-a4cb-442626756a99/scratchpad
cp "$OUT/hex.ggb" examples/0_sample_scenes/hex_tYwHUgEyock.ggb 2>/dev/null || \
  curl -s "https://animageo.ru/api/shared/tYwHUgEyock/ggb" | \
  python3 -c "import sys,json,base64; open('examples/0_sample_scenes/hex_tYwHUgEyock.ggb','wb').write(base64.b64decode(json.load(sys.stdin)['ggb_base64']))"
ls -la examples/0_sample_scenes/hex_tYwHUgEyock.ggb
```

- [ ] **Step 2: Write the test (fails on classification before, passes after — on a fixed tree it should pass immediately; treat it as the acceptance gate)**

```python
# tests/test_tparam_animation_acceptance.py
"""Acceptance for docs/archive/TZ-conic-locus-point-keyframe-animation.md §5.

Real construction from https://animageo.ru/shared/tYwHUgEyock: D is a point
on ellipse c; the visible hexagon/triangle geometry derives from A,B,C,D,G.
Before this feature the export froze because D classified as 'unknown' and
its keyframe coords could not be converted to tparam.
"""
import os

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser

FIXTURE = os.path.join(
    os.path.dirname(__file__), '..', 'examples', '0_sample_scenes',
    'hex_tYwHUgEyock.ggb')

pytestmark = pytest.mark.skipif(
    not os.path.exists(FIXTURE),
    reason='hex_tYwHUgEyock.ggb not present (examples/ is untracked; '
           'fetch via GET https://animageo.ru/api/shared/tYwHUgEyock/ggb)')

# Keyframe D-coordinates from the real TimelineData (TZ §2)
D_TRACK = [[6.54, -1.04], [9.85, -0.38], [11.13, 1.05],
           [9.37, 2.84], [2.45, 0.31], [6.54, -1.04]]


@pytest.fixture()
def constr():
    c = Construction()
    view = {}
    ggb_parser.load(c, view, FIXTURE, debug=False)
    return c


def test_D_classified_as_ellipse(constr):
    info = constr.get_independents()['D']
    assert info['type'] == 'tparam_point'
    assert info['constraint'] == 'ellipse'          # TZ §5.1
    assert info['tparam'] is not None


def test_tparam_from_coords_matches_load_projection(constr):
    d = constr.element('D')
    t = constr.tparam_from_coords('D', list(d.data.coords))
    assert np.isclose(t, d.tparam, atol=1e-9)


def test_keyframes_move_D_and_derived_geometry(constr):
    """TZ §5.2/§5.3 (library side): interpolators exist, D moves along the
    ellipse, and derived geometry recomputes."""
    from animageo.keyframes import KeyframeSequence, apply_parsed_value

    kfs = {"keyframes": [
        {"t": i * 1.0, "values": {"D": xy}} for i, xy in enumerate(D_TRACK)
    ]}
    seq = KeyframeSequence.from_json(kfs, constr)

    moving = [iv for iv in seq.intervals if iv.interpolators]
    assert moving, "D must produce interpolators (video was frozen before)"
    interp = moving[0].interpolators[0]
    assert interp.kind == 'tparam_circle'           # ellipse -> cyclic

    # Evaluate mid-interval, apply, rebuild: D and a derived vertex move.
    d_before = constr.element('D').data.coords.copy()
    # any derived polygon vertex; hexagon vertices L/M/N/O per TZ - pick
    # the first level>0 point that is not D/G
    derived_name = next(
        name for name, st in constr.state.items()
        if st['level'] > 0 and constr.element(name) is not None
        and constr.element(name).data is not None
        and type(constr.element(name).data).__name__ == 'Point'
        and name not in ('D', 'G'))
    derived_before = constr.element(derived_name).data.coords.copy()

    apply_parsed_value(constr, 'D', interp.kind, interp.at(0.5))
    constr.rebuild()

    d_after = constr.element('D').data.coords
    assert not np.allclose(d_before, d_after, atol=1e-6), "D must move"
    assert not np.allclose(
        derived_before, constr.element(derived_name).data.coords, atol=1e-6
    ), f"derived point {derived_name} must follow D"


def test_closed_ellipse_track_wraps_shortest_arc(constr):
    """TZ §5.3: cyclic interpolation on the closed conic — evaluating the
    full track never jumps by more than pi between adjacent samples."""
    from animageo.keyframes import KeyframeSequence
    kfs = {"keyframes": [
        {"t": i * 1.0, "values": {"D": xy}} for i, xy in enumerate(D_TRACK)
    ]}
    seq = KeyframeSequence.from_json(kfs, constr)
    for iv in seq.intervals:
        for interp in iv.interpolators:
            samples = [interp.at(u) for u in np.linspace(0, 1, 21)]
            steps = np.abs(np.diff(samples))
            assert (steps < np.pi).all(), "no >pi jumps: shortest-arc wrap"
```

- [ ] **Step 3: Run the acceptance suite**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/test_tparam_animation_acceptance.py -v`
Expected: 4 passed (or 4 skipped on a machine without the fixture)

- [ ] **Step 4: Full-suite regression gate**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q`
Expected: everything green (≈1000 tests). Investigate ANY failure before committing — the usual suspects are snapshot drift (Task 2 note) and keyframe canaries.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tparam_animation_acceptance.py
git commit -m "test: acceptance for conic tparam keyframe animation (TZ §5)

Real shared/tYwHUgEyock construction: D classifies as ellipse, coords
round-trip through tparam_from_coords, keyframes produce interpolators,
derived geometry follows, cyclic wrap takes the shortest arc. Skips when
the untracked .ggb fixture is absent."
```

---

### Task 12: Documentation — CLAUDE.md, CHANGELOG

**Files:**
- Modify: `CLAUDE.md` (Key Modules list + keyframe animation section)
- Modify: `CHANGELOG.md` (new entry at top; inspect the existing heading format first and match it — no AI attribution)

**Interfaces:** none (docs only).

- [ ] **Step 1: CLAUDE.md — Key Modules**

Add after the `geo/curve_sampling.py` line:

```markdown
- `geo/tparam.py` — point ↔ curve-parameter math for every path type: the five classic `get_tparam_from_point_and_*` helpers (moved from `ggb_parser`, which re-exports them), `get_tparam_from_point_and_function` (param = x, GGB convention), locus **segment**-projection inverse, and the unified `tparam_from_point_and_path` dispatcher. Public API: `Construction.tparam_from_coords(name, coords)`.
```

- [ ] **Step 2: CLAUDE.md — keyframe animation section**

In the "Keyframe Animation System" independent-types table, replace the two `alpha_point` rows with:

```markdown
| `tparam_point` (circle/ellipse) | `{"tparam": rad, "direction": "short"\|"cw"\|"ccw"}` **or** `[x, y]` | cyclic (2π wrap, shortest arc) |
| `tparam_point` (segment/line/ray/parabola/locus/function) | `{"tparam": value}` **or** `[x, y]` | linear |
| `tparam_point` (hyperbola) | `{"tparam": [branch, t]}` **or** `[x, y]` | branch snaps at 0.5, t linear |
```

And after the table add:

```markdown
`[x, y]` values are projected onto the point's path via `Construction.tparam_from_coords(name, coords)` (public API — clients may also call it directly). `get_independents()` reports the path type in `constraint`: `circle`/`segment`/`ray`/`line`/`ellipse`/`hyperbola`/`parabola`/`locus`/`function` (degenerate/unrecognized paths stay `unknown` → linear).
```

- [ ] **Step 3: CHANGELOG entry**

Open `CHANGELOG.md`, match its existing version-section format, add at the top (adjust the heading to the file's convention — likely an Unreleased/next-version section):

```markdown
### Added
- Points on **conics** (ellipse/hyperbola/parabola/circle-as-conic), **loci** and **function graphs** are now fully animatable in keyframes (TZ: conic/locus/function tparam animation). `get_independents()` reports the path type in `constraint`; ellipse interpolates cyclically (shortest arc), hyperbola carries `(branch, t)`.
- Keyframe values for tparam points may be plain `[x, y]` coordinates — the library projects them onto the path (`Construction.tparam_from_coords`, new public API).
- `animageo/geo/tparam.py`: unified point↔parameter module; `ggb_parser` re-exports the classic helpers.
- `point_F` — point on a function graph; GGB `Point[f]` imports with `tparam`.

### Changed
- Locus point parameter: nearest-**segment** projection with fractional position (GeoGebra `GeoLocus.pointChanged` semantics) instead of nearest-vertex snap.
```

- [ ] **Step 4: Verify docs render + full suite still green**

Run: `PYTHONPATH=. DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "docs: tparam path animation - keyframe formats, geo/tparam module, changelog"
```

---

## Out of scope (do NOT implement)

- Cyclic wrap for closed loci (linear interpolation is the documented behavior).
- Hyperbola branch change mid-interval beyond the 0.5-snap (degenerate through-infinity transition — documented).
- Function singularity crossing inside an interval (point vanishes where f(x) is undefined — inherent).
- Two-arg `Point(path, λ)` GGB command (`point_ci` etc.): GGB's λ is a **normalized [0,1]** PathNormalizer parameter, not the internal tparam — documented for the future, not built now.
- Any animageo-web change (its converter swap to `tparam_from_coords` is a separate task in that repo).
- PyPI release / version bump (separate release flow).
