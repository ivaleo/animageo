"""Where GeoGebra puts an element's label — the applet's own rule, per type.

GeoGebra draws a label with its LEFT edge on the BASELINE at a base point that
each ``Draw*`` class computes for its type, then adds the stored
``labelOffset`` (screen px). A label the user placed in the applet is only
reproduced if the renderer starts from that same base point: starting from a
type-agnostic spot (a segment's midpoint, bottom-centred) put hand-placed
labels onto the very line they label.

``ggb_label_anchor`` returns ``(anchor_xy, base_px)``:

* ``anchor_xy`` — the geometric point the label hangs off, construction units;
* ``base_px`` — the applet's fixed pixel step from it (x right, y UP), before
  ``labelOffset``.

The rules transcribe GeoGebra's ``DrawPoint`` / ``DrawSegment`` /
``DrawVectorModel`` / ``DrawRay`` / ``DrawPolygon`` / ``DrawConic`` /
``DrawConicPart`` and are checked against label ink measured on the live
applet (``tests/fixtures/label_anchor_types.*``). ``None`` means "no applet
rule to reproduce": a line's label depends on the applet WINDOW border, which
an export frame does not have, and angle labels follow animageo's own angle
logic.
"""
from __future__ import annotations

import math

import numpy as np

from .geo import construction as geo


def _unit(dx, dy):
    length = math.hypot(dx, dy)
    return (dx / length, dy / length, length) if length > 1e-12 else (0.0, 0.0, 0.0)


def _point(elem, construction, ptUnit_ggb):
    # DrawPoint: xLabel = x + 4, yLabel = yUL - pointSize with yUL = y - pointSize,
    # i.e. 4 px right and 2·pointSize px above the point.
    raw = getattr(elem, 'ggb_raw', None) or {}
    try:
        size = float(raw.get('point_size', 5.0))
    except (TypeError, ValueError):
        size = 5.0
    return elem.data.coords[:2], (4.0, 2.0 * size)


def _segment(elem, construction, ptUnit_ggb):
    # DrawSegment: midpoint + 16 px along the unit normal (Ay-By, Bx-Ax) in
    # screen coords (y down) → (dy, -dx)/|AB| with y up.
    p1, p2 = elem.data.endpoints
    ux, uy, length = _unit(float(p2[0] - p1[0]), float(p2[1] - p1[1]))
    mid = (np.asarray(p1[:2], dtype=float) + np.asarray(p2[:2], dtype=float)) / 2
    if length == 0.0:
        return mid, (0.0, -16.0)
    return mid, (16.0 * uy, -16.0 * ux)


def _vector(elem, construction, ptUnit_ggb):
    # DrawVectorModel: midpoint + (v_y, -v_x)/4 in screen coords, where v is
    # the direction scaled to the arrow factor (12 + thickness, or 3·thickness
    # from 8 up), capped at the vector's own screen length.
    p1, p2 = elem.data.endpoints
    ux, uy, length = _unit(float(p2[0] - p1[0]), float(p2[1] - p1[1]))
    mid = (np.asarray(p1[:2], dtype=float) + np.asarray(p2[:2], dtype=float)) / 2
    raw = getattr(elem, 'ggb_raw', None) or {}
    try:
        thickness = float(raw.get('line_thickness', 5.0))
    except (TypeError, ValueError):
        thickness = 5.0
    factor = 12.0 + thickness if thickness < 8 else 3.0 * thickness
    if ptUnit_ggb:
        factor = min(factor, length * float(ptUnit_ggb))
    return mid, (-uy * factor / 4.0, ux * factor / 4.0)


def _ray(elem, construction, ptUnit_ggb):
    # DrawRay: start + v/2 + 16·(v_x, -v_y)/|v| in screen coords, v = the
    # ray's direction vector. For Ray(A, B) GeoGebra's direction is B - A, so
    # the anchor is the midpoint of A and B (the stored Line keeps only a unit
    # direction — the defining point comes from the command inputs).
    start = np.asarray(elem.data.start[:2], dtype=float)
    through = None
    state = getattr(construction, 'state', {}).get(elem.name) if construction is not None else None
    inputs = (state or {}).get('inputs') or []
    if len(inputs) >= 2:
        second = construction.element(inputs[1])
        data = getattr(second, 'data', None)
        if isinstance(data, geo.Point):
            through = np.asarray(data.coords[:2], dtype=float)
        elif isinstance(data, geo.Vector):
            through = start + np.asarray(data.direction[:2], dtype=float)
    if through is None:
        through = start + np.asarray(elem.data.direction[:2], dtype=float)
    ux, uy, length = _unit(*(through - start))
    if length == 0.0:
        return start, (0.0, -16.0)
    return (start + through) / 2, (16.0 * ux, -16.0 * uy)


def _polygon(elem, construction, ptUnit_ggb):
    # DrawPolygon: the plain average of the vertices, no pixel step.
    return np.mean(np.asarray(elem.data.vertices)[:, :2], axis=0), (0.0, 0.0)


def _ellipse_rule(center, a, b, rotation):
    # DrawConic.updateEllipse: local (-a/2, 0.85·b - 20/yscale) in the conic's
    # own axes, i.e. a point of the conic frame plus 20 px against its second
    # axis. A circle is the unrotated case.
    e0 = np.array([math.cos(rotation), math.sin(rotation)])
    e1 = np.array([-math.sin(rotation), math.cos(rotation)])
    anchor = np.asarray(center[:2], dtype=float) - (a / 2.0) * e0 + 0.85 * b * e1
    return anchor, (-20.0 * float(e1[0]), -20.0 * float(e1[1]))


def _circle(elem, construction, ptUnit_ggb):
    r = float(elem.data.radius)
    return _ellipse_rule(elem.data.center, r, r, 0.0)


def _conic(elem, construction, ptUnit_ggb):
    try:
        params = elem.data.as_ellipse()
    except Exception:
        params = None
    if not params:
        return None
    a, b = params['semi_axes']
    return _ellipse_rule(params['center'], float(a), float(b), float(params['rotation']))


def arc_mid_angle(elem):
    """Mid-parameter of the drawn arc/sector (the sweep its renderer draws)."""
    a1, a2 = elem.data.angles
    if isinstance(elem.data, geo.CircleSector):
        sweep = a2 - a1
    else:
        sweep = (a2 - a1) % (2 * math.pi)
    return a1 + sweep / 2.0


def _conic_part(elem, construction, ptUnit_ggb):
    # DrawConicPart: the arc point at the mid parameter, then (+6, -6) screen px.
    mid = arc_mid_angle(elem)
    c = np.asarray(elem.data.center[:2], dtype=float)
    r = float(elem.data.radius)
    return c + r * np.array([math.cos(mid), math.sin(mid)]), (6.0, 6.0)


# Order matters: Arc/CircleSector subclass Circle, Ray subclasses Line.
_RULES = (
    (geo.Point, _point),
    (geo.Segment, _segment),
    (geo.Vector, _vector),
    (geo.Ray, _ray),
    (geo.Polygon, _polygon),
    ((geo.Arc, geo.CircleSector), _conic_part),
    (geo.Circle, _circle),
    (geo.Conic, _conic),
)


def ggb_label_anchor(elem, construction=None, ptUnit_ggb=None):
    """``(anchor_xy, base_px)`` GeoGebra would start this element's label
    from, or ``None`` when there is no applet rule to reproduce."""
    data = getattr(elem, 'data', None)
    if data is None:
        return None
    for types, rule in _RULES:
        if isinstance(data, types):
            try:
                return rule(elem, construction, ptUnit_ggb)
            except Exception:
                return None
    return None
