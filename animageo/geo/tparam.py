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


def get_tparam_from_point_and_function(point, function):
    """Parameter of a point on ``y = f(x)``: the natural parameter is x.

    A point slightly off the graph projects along the y-axis (x is kept) —
    same convention as GeoGebra's ``GeoFunction.pathChanged`` (parameter = x).
    """
    return float(point.coords[0])


def tparam_from_point_and_path(point, path):
    """Unified coords -> tparam dispatcher for every supported path type.

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
