"""Geometric command implementations with dynamic dispatch.

Functions follow the naming convention: command_name + '_' + type_shortcuts.
Type shortcuts: p=Point, l=Line, r=Ray, s=Segment, c=Circle, C=Arc,
S=CircleSector, a=Angle, v=Vector, P=Polygon, i=int/float, m=Measure,
A=AngleSize, b=Boolean.

Example: midpoint_pp(p1, p2) computes midpoint of two Points.
"""
import logging
import numpy as np
import re
from typing import Iterable

from .lib_vars import *
from .lib_elements import *
from .lib_conic import Conic, ConicType
from .lib_function import Function
from .lib_implicit import ImplicitCurve
from .formula_params import bind_parameters

logger = logging.getLogger(__name__)

#--------------------------------------------------------------------------

class Command:
    def __init__(self, name, inputs, outputs = None):
        self.name = name
        self.inputs = toObjArray(inputs)        # могут храниться сами объекты, а также строки с именами или выражениями
        self.outputs = toObjArray(outputs)

    def __repr__(self):
        inputs_str = ' '.join([obj.name if hasattr(obj, "name") else str(obj) for obj in self.inputs])
        outputs_str = ' '.join([obj.name if hasattr(obj, "name") else str(obj) for obj in self.outputs])
        return "{}:\t{}\t>> {}".format(self.name, inputs_str, outputs_str)

    def checkParamsPrepaired(self, params):
        for obj in params:
            if type(obj) not in type_to_shortcut:
                #raise Exception("In command <{}> param ({} as {}) is not prepaired.".format(self.name, obj, type(obj)))
                return False
        return True

    def func(self, log_unsupported=True):     # эта функция должна находить реализованную функцию в этом модуле и возвращать ссылку на нее
        #if not self.checkParamsPrepaired(self.inputs):
        #    raise Exception("In command <{}> inputs are not prepaired.".format(self.name))

        fname = strFullCommand(self.name, self.inputs)

        impl = COMMAND_REGISTRY.get(fname)
        if impl is not None:
            return impl
        impl = signature_alias(self.name, self.inputs)
        if impl is not None:
            return impl
        # Loud failure: a command name that survives construction but has
        # no implementation dispatch almost always means a typo in a DSL
        # script (``Intersect(A, B)`` against unexpected types) or a new
        # element type without a matching operation. Before this warning,
        # the call just returned None and the resulting element stayed
        # unbuilt with no diagnostic. Outputs go to the standard logger;
        # web-service integrators can surface it to their own observability.
        if log_unsupported:
            input_types = ', '.join(type(x).__name__ for x in self.inputs)
            logger.warning(
                "Command '%s' has no implementation for inputs [%s] "
                "(looked up %r). Affected outputs: %s",
                self.name, input_types, fname,
                [getattr(o, 'name', str(o)) for o in self.outputs],
            )
        return None

#--------------------------------------------------------------------------        

def toObjArray(params):
    if not params: return []
    elif not isinstance(params, Iterable) or isinstance(params, str): return [params]
    else: return list(params)

#--------------------------------------------------------------------------   

type_to_shortcut = {
    Point           : 'p',
    Polygon         : 'P',
    Circle          : 'c',
    Arc             : 'C',
    Line            : 'l',
    Ray             : 'r',
    Segment         : 's',
    Angle           : 'a',
    Vector          : 'v',
    CircleSector    : 'S',
    LocusCurve      : 'L',
    Conic           : 'K',
    Function        : 'F',
    ImplicitCurve   : 'I',

    int             : 'i',
    float           : 'i',
    Boolean         : 'b',
    Measure         : 'm',
    AngleSize       : 'A',
    str             : 'T'   # for DSL string literals: Function("y = x^2"), Conic("..."), etc.
}

# Formula constructors take the formula text followed by any number of
# parameters — numbers, points and vectors read through ``x()``/``y()``,
# functions it calls (``Function("y = a*x^2", a)``, ``Function("…", A, g)``);
# the count varies, so each base dispatches to a single ``<base>_Tn``
# implementation.
_FORMULA_BASES = ('function', 'conic', 'implicit_curve', 'line')
_FORMULA_PARAMS_RE = re.compile(r'^T[imAabpvF]+$')
_VARIADIC_DISPATCH = frozenset(f'{base}_Tn' for base in _FORMULA_BASES)

def strFullCommand(name, params): # "Polygon", [Point, Point, int] -> "polygon_ppi"
    command, shortcuts = strCommand(name), strParams(params)
    if command == "polygon" and re.match('^p*$', shortcuts):
        return command
    if command in _FORMULA_BASES and _FORMULA_PARAMS_RE.match(shortcuts):
        return f"{command}_Tn"
    return f"{command}_{shortcuts}"

def strParams(params): # [Point, Point, int] -> "ppi"
    for x in params:
        if type(x) not in type_to_shortcut:
            if x is not None:
                logger.warning("No type shortcut for '%s'", type(x).__name__)
    return ''.join(type_to_shortcut[type(x)] if type(x) in type_to_shortcut else '?' for x in params)

def strCommand(name): # "AreCollinear" -> "are_collinear"
    altered_name = [name[0].lower()]
    for x in name[1:]:
        if x.isupper(): altered_name += ['_', x.lower()]
        else: altered_name.append(x)
    return ''.join(altered_name)

#--------------------------------------------------------------------------

def order_points_by_reference(res, points_order=None):
    if points_order is None:
        return res
    if not hasattr(res, '__len__') or isinstance(res, str):
        return res

    # Создаем упорядоченный список точек
    ordered_points = []
    used = [False] * len(res)  # Отслеживаем использованные точки из res
    
    # Сначала добавляем точки из points_order в указанном порядке
    for order_point in points_order:
        if not hasattr(order_point, 'coords'):
            continue
        for i, res_point in enumerate(res):
            if used[i] or not hasattr(res_point, 'coords'):
                continue
            if np.isclose(order_point.coords, res_point.coords).all():
                ordered_points.append(res_point)
                used[i] = True
                break

    if not ordered_points:
        return res

    # Затем добавляем оставшиеся точки из res в исходном порядке
    for i, res_point in enumerate(res):
        if not used[i]:
            ordered_points.append(res_point)

    return ordered_points

def res_by_index(res, index, points_order=None):
    index = int(max(0, index - 1))
    
    if not hasattr(res, '__len__'):
        return res if index == 0 else None

    ordered_res = order_points_by_reference(res, points_order)
    return ordered_res[index] if index < len(ordered_res) else None

#--------------------------------------------------------------------------

def assign_p(x):
    return x
def assign_v(x):
    return x
def assign_i(x):
    return x

def angle_size_A(a):
    return AngleSize(a.value)

def angle_size_i(x):
    return AngleSize(x)

def angle_ppp(p1, p2, p3):
    return Angle(p2.coords, p1.coords-p2.coords, p3.coords-p2.coords)

def angle_size_ppp(p1, p2, p3):
    return AngleSize(np.angle(a_to_cpx(p3.coords-p2.coords) / a_to_cpx(p1.coords-p2.coords)))

def angular_bisector_ll(l1, l2):
    x = intersect_ll(l1, l2)
    # Parallel (or coincident) lines have no crossing: no bisectors, as in
    # GeoGebra (1.8.1; was an AttributeError inside the command).
    if x is None: return None
    n1, n2 = l1.normal, l2.normal
    if np.dot(n1, n2) > 0: n = n1 + n2
    else: n = n1 - n2
    return [
        Line(vec, np.dot(vec, x.coords))
        for vec in (n, vector_perp_rot(n))
    ]

def angular_bisector_ppp(p1, p2, p3):
    v1 = p2.coords - p1.coords
    v2 = p2.coords - p3.coords
    # A side of zero length (up to rounding, as in line_pp) has no direction.
    scale = max(1.0, *(float(np.linalg.norm(p.coords)) for p in (p1, p2, p3)))
    n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
    if n1 <= 1e-12 * scale or n2 <= 1e-12 * scale: return None
    v1 = v1 / n1
    v2 = v2 / n2
    if np.dot(v1, v2) < 0: n = v1-v2
    else: n = vector_perp_rot(v1+v2)
    return Line(n, np.dot(p2.coords, n))

def angular_bisector_ss(l1, l2):
    return angular_bisector_ll(l1, l2)

def arc_cpp(circle, p1, p2):
    if np.isclose(circle.center, p1.coords).all(): return None
    if np.isclose(circle.center, p2.coords).all(): return None
    return Arc(circle.center, circle.radius, [np.arctan2(p.coords[1] - circle.center[1], p.coords[0] - circle.center[0]) for p in (p1, p2)])

def circumcircle_arc_ppp(p1, p2, p3):
    if np.isclose(p1.coords, p2.coords).all(): return None
    if np.isclose(p1.coords, p3.coords).all(): return None
    if np.isclose(p2.coords, p3.coords).all(): return None
    circle = circle_ppp(p1, p2, p3)
    arc = Arc(circle.center, circle.radius, [np.arctan2(p.coords[1] - circle.center[1], p.coords[0] - circle.center[0]) for p in (p1, p3)])
    return arc if arc.contains(p2.coords) else Arc(circle.center, circle.radius, [np.arctan2(p.coords[1] - circle.center[1], p.coords[0] - circle.center[0]) for p in (p3, p1)])

def circle_arc_ppp(p1, p2, p3):
    if np.isclose(p1.coords, p2.coords).all(): return None
    if np.isclose(p1.coords, p3.coords).all(): return None
    if np.isclose(p2.coords, p3.coords).all(): return None
    circle = circle_pp(p1, p2)
    return Arc(circle.center, circle.radius, [np.arctan2(p.coords[1] - circle.center[1], p.coords[0] - circle.center[0]) for p in (p2, p3)])

def circumcircle_sector_ppp(p1, p2, p3):
    if np.isclose(p1.coords, p2.coords).all(): return None
    if np.isclose(p1.coords, p3.coords).all(): return None
    if np.isclose(p2.coords, p3.coords).all(): return None
    circle = circle_ppp(p1, p2, p3)
    arc = Arc(circle.center, circle.radius, [np.arctan2(p.coords[1] - circle.center[1], p.coords[0] - circle.center[0]) for p in (p1, p3)])
    return CircleSector(arc.center, arc.radius, arc.angles) if arc.contains(p2.coords) else CircleSector(arc.center, arc.radius, list(reversed(arc.angles)))

def circle_sector_ppp(p1, p2, p3):
    if np.isclose(p1.coords, p2.coords).all(): return None
    if np.isclose(p1.coords, p3.coords).all(): return None
    if np.isclose(p2.coords, p3.coords).all(): return None
    circle = circle_pp(p1, p2)
    return CircleSector(circle.center, circle.radius, [np.arctan2(p.coords[1] - circle.center[1], p.coords[0] - circle.center[0]) for p in (p2, p3)])

def circle_sector_ppA(p1, p2, ang):
    if np.isclose(p1.coords, p2.coords).all(): return None
    circle = circle_pp(p1, p2)
    ang0 = np.arctan2(p2.coords[1] - circle.center[1], p2.coords[0] - circle.center[0])
    return CircleSector(circle.center, circle.radius, [ang0, ang0 + ang.value])

def circle_sector_ppi(p1, p2, value):
    if np.isclose(p1.coords, p2.coords).all(): return None
    circle = circle_pp(p1, p2)
    ang0 = np.arctan2(p2.coords[1] - circle.center[1], p2.coords[0] - circle.center[0])
    return CircleSector(circle.center, circle.radius, [ang0, ang0 + value])

def are_collinear_ppp(p1, p2, p3):
    return Boolean(np.linalg.matrix_rank([p1.coords-p2.coords, p1.coords-p3.coords]) <= 1)

def are_concurrent_lll(l1, l2, l3):
    lines = l1,l2,l3

    differences = []
    for i in range(3):
        remaining = [l.normal for l in lines[:i]+lines[i+1:]]
        # Scalar 2D cross (``x1*y2 − y1*x2``). NumPy 2.0 dropped support
        # for 2D vectors in ``np.cross``.
        n1, n2 = remaining
        prod = np.abs(n1[0] * n2[1] - n1[1] * n2[0])
        differences.append((prod, i, lines[i]))

    l1, l2, l3 = tuple(zip(*sorted(differences)))[2]
    x = intersect_ll(l1, l2)
    return Boolean(np.isclose(np.dot(x.coords, l3.normal), l3.offset))

def are_concurrent(o1, o2, o3):
    cand = []
    try:
        #if True:
        if isinstance(o1, Line) and isinstance(o2, Line):
            cand = intersect_ll(o1, o2)
        elif isinstance(o1, Line) and isinstance(o2, Circle):
            cand = intersect_lc(o1, o2)
        elif isinstance(o1, Circle) and isinstance(o2, Line):
            cand = intersect_cl(o1, o2)
        elif isinstance(o1, Circle) and isinstance(o2, Circle):
            cand = intersect_cc(o1, o2)
    except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):
        pass

    if not isinstance(cand, Iterable) or isinstance(cand, str): cand = (cand,)

    for p in cand:
        for obj in (o1,o2,o3):
            if not obj.contains(p.coords): break
        else: return Boolean(True)

    return Boolean(False)

def are_concyclic_pppp(p1, p2, p3, p4):
    z1, z2, z3, z4 = (a_to_cpx(p.coords) for p in (p1, p2, p3, p4))
    cross_ratio = (z1-z3)*(z2-z4)*(((z1-z4)*(z2-z3)).conjugate())
    return Boolean(np.isclose(cross_ratio.imag, 0))

def are_congruent_aa(a1, a2):
    # ``.value`` is Angle's canonical accessor (== .size in radians).
    # The previous code used ``.angle`` which does not exist on Angle
    # → AttributeError → the command silently propagated a crash.
    result = np.isclose((a1.value - a2.value + 1) % (2 * np.pi), 1)
    result = (result or np.isclose((a1.value + a2.value + 1) % (2 * np.pi), 1))
    return Boolean(result)

def are_complementary_aa(a1, a2):
    result = np.isclose((a1.value - a2.value) % (2 * np.pi), np.pi)
    result = (result or np.isclose((a1.value + a2.value) % (2 * np.pi), np.pi))
    return Boolean(result)

def are_congruent_ss(s1, s2):
    l1, l2 = (
        np.linalg.norm(s.endpoints[1] - s.endpoints[0])
        for s in (s1, s2)
    )
    return Boolean(np.isclose(l1, l2))

def are_equal_mm(m1, m2):
    if m1.dimension != m2.dimension: return None
    return Boolean(np.isclose(m1.value, m2.value))

def are_equal_mi(m, i):
    if m.dimension != 0: return None
    return Boolean(np.isclose(m.value, i))

def are_equal_pp(p1, p2):
    return Boolean(np.isclose(p1.coords, p2.coords).all())

def are_parallel_ll(l1, l2):
    if np.isclose(l1.normal, l2.normal).all(): return Boolean(True)
    if np.isclose(l1.normal, -l2.normal).all(): return Boolean(True)
    return Boolean(False)

def are_parallel_ls(l, s):
    return are_parallel_ll(l, s)

def are_parallel_rr(r1, r2):
    return are_parallel_ll(r1, r2)

def are_parallel_sl(s, l):
    return are_parallel_ll(s, l)

def are_parallel_ss(s1, s2):
    return are_parallel_ll(s1, s2)

def are_perpendicular_ll(l1, l2):
    if np.isclose(l1.normal, l2.direction).all(): return Boolean(True)
    if np.isclose(l1.normal, -l2.direction).all(): return Boolean(True)
    return Boolean(False)

def are_perpendicular_lr(l, r):
    return are_perpendicular_ll(l, r)

def are_perpendicular_rl(r, l):
    return are_perpendicular_ll(r, l)

def are_perpendicular_sl(s, l):
    return are_perpendicular_ll(s, l)

def are_perpendicular_ls(l, s):
    return are_perpendicular_ll(l, s)

def are_perpendicular_ss(s1, s2):
    return are_perpendicular_ll(s1, s2)

def area(*points):
    # Triangulated area via 2D cross-product sum. ``np.cross`` on
    # 2-element arrays was deprecated in NumPy 2.0 (requires 3D input
    # now); we only need the z-component, which is ``x1*y2 − y1*x2``.
    p0 = points[0].coords
    vecs = [p.coords - p0 for p in points[1:]]
    cross_sum = sum(
        v1[0] * v2[1] - v1[1] * v2[0]
        for v1, v2 in zip(vecs, vecs[1:])
    )
    return Measure(abs(cross_sum) / 2, 2)

def area_P(polygon):
    points = [Point(p) for p in polygon.vertices]
    return area(*points)

def center_c(circle):
    return Point(circle.center)

def centroid_P(polygon):
    """Вычисляет центроид многоугольника и возвращает его как объект Point."""
    points = polygon.vertices
    n = len(points)
    
    # Если многоугольник имеет менее 3 точек, возвращаем среднее арифметическое
    if n < 3:
        centroid_coord = np.mean(points, axis=0)
        return Point(centroid_coord)
    
    # Вычисляем площадь по формуле шнурка
    area = 0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    area /= 2
    
    # Если площадь близка к нулю, возвращаем среднее арифметическое точек
    if abs(area) < 1e-10:
        centroid_coord = np.mean(points, axis=0)
        return Point(centroid_coord)
    
    # Вычисляем центроид
    Cx = Cy = 0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        Cx += (x1 + x2) * cross
        Cy += (y1 + y2) * cross
    
    Cx /= 6 * area
    Cy /= 6 * area
    
    return Point([Cx, Cy])

def _circle_or_none(center, r):
    """A circle, or None (undefined) for a radius that is not a positive number."""
    try:
        r = float(r)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(r) or r <= 0:
        return None
    return Circle(center, r)

def circle_pp(center, passing_point):
    return _circle_or_none(center.coords, np.linalg.norm(center.coords - passing_point.coords))

def circle_ppp(p1, p2, p3):
    # Collinear or coincident points have no circle: undefined, not an error.
    axis1 = line_bisector_pp(p1, p2)
    axis2 = line_bisector_pp(p1, p3)
    if axis1 is None or axis2 is None: return None
    center = intersect_ll(axis1, axis2)
    if center is None: return None
    return circle_pp(center, p1)

def circle_pm(p, m):
    if m.dimension != 1: return None
    return _circle_or_none(p.coords, m.value)

def circle_pi(p, i):
    return _circle_or_none(p.coords, i)

def circle_ps(p, s):
    return _circle_or_none(p.coords, s.length)

def contained_by_pc(point, by_circle):
    return Boolean(by_circle.contains(point.coords))

def contained_by_pl(point, by_line):
    return Boolean(by_line.contains(point.coords))

def distance_pp(p1, p2):
    return Measure(np.linalg.norm(p1.coords-p2.coords), 1)

def _distance_point_line(point, line):
    return abs(float(np.dot(line.normal, point.coords) - line.offset))

def _distance_point_segment(point, segment):
    a, b = segment.endpoints
    ab = b - a
    denom = float(np.dot(ab, ab))
    if np.isclose(denom, 0):
        return float(np.linalg.norm(point.coords - a))
    t = float(np.dot(point.coords - a, ab) / denom)
    t = min(1.0, max(0.0, t))
    return float(np.linalg.norm(point.coords - (a + t * ab)))

def _distance_point_ray(point, ray):
    t = float(np.dot(point.coords - ray.start, ray.direction))
    if t <= 0:
        return float(np.linalg.norm(point.coords - ray.start))
    return float(np.linalg.norm(point.coords - (ray.start + t * ray.direction)))

def distance_pl(point, line):
    return Measure(_distance_point_line(point, line), 1)

def distance_lp(line, point):
    return distance_pl(point, line)

def distance_ps(point, segment):
    return Measure(_distance_point_segment(point, segment), 1)

def distance_sp(segment, point):
    return distance_ps(point, segment)

def distance_pr(point, ray):
    return Measure(_distance_point_ray(point, ray), 1)

def distance_rp(ray, point):
    return distance_pr(point, ray)

def distance_pc(point, circle):
    return Measure(abs(float(np.linalg.norm(point.coords - circle.center) - circle.radius)), 1)

def distance_cp(circle, point):
    return distance_pc(point, circle)

def distance_pK(point, conic):
    if conic.type == ConicType.CIRCLE:
        circle = conic.as_circle()
        if circle is None:
            return None
        center, radius = circle
        return Measure(abs(float(np.linalg.norm(point.coords - center) - radius)), 1)
    return None

def distance_Kp(conic, point):
    return distance_pK(point, conic)

def distance_ll(line1, line2):
    if not are_parallel_ll(line1, line2).value:
        return Measure(0.0, 1)
    if np.dot(line1.normal, line2.normal) < 0:
        return Measure(abs(float(line1.offset + line2.offset)), 1)
    return Measure(abs(float(line1.offset - line2.offset)), 1)

def equality_aa(a1, a2):
    return are_congruent_aa(a1, a2)

def equality_mm(m1, m2):
    if m1.dimension != m2.dimension: return None
    return Boolean(np.isclose(m1.value, m2.value))

def equality_ms(m, s):
    if m.dimension != 1: return None
    return Boolean(np.isclose(m.value, s.length))

def equality_mi(m, i):
    if m.dimension != 0 and i != 0: return None
    return Boolean(np.isclose(m.value, i))

def equality_pp(p1, p2):
    return are_equal_pp(p1, p2)

def equality_Pm(polygon, m):
    if m.dimension != 2: return None
    return Boolean(np.isclose(area_P(polygon).value, m.value))

def equality_PP(poly1, poly2):
    return Boolean(np.isclose(area_P(poly1).value, area_P(poly2).value))

def equality_sm(s, m):
    return equality_ms(m,s)

def equality_ss(s1, s2):
    return Boolean(np.isclose(s1.length, s2.length))

def equality_si(seg, a):
    return Boolean(np.isclose(seg.length, a))

def intersect_ll(line1, line2):
    matrix = np.stack((line1.normal, line2.normal))
    b = np.array((line1.offset, line2.offset))
    if np.isclose(np.linalg.det(matrix), 0): return None
    return Point(np.linalg.solve(matrix, b))

def intersect_lc(line, circle):
    # shift circle to center
    y = line.offset - np.dot(line.normal, circle.center)
    x_squared = circle.radius_squared - y ** 2
    if np.isclose(x_squared, 0): return Point(y * line.normal + circle.center)
    if x_squared <= 0: return None

    x = np.sqrt(x_squared)
    return [
        Point(-x * line.direction + y * line.normal + circle.center),
        Point(x * line.direction + y * line.normal + circle.center)
    ]

def intersect_lci(line, circle, index, points_order=None):
    res = intersect_lc(line, circle)
    return res_by_index(res, index, points_order)

def intersect_cc(circle1, circle2):
    center_diff = circle2.center - circle1.center
    center_dist_squared = np.dot(center_diff, center_diff)
    if np.isclose(center_dist_squared, 0):
        return None  # concentric circles: no discrete intersection
    relative_center = (circle1.radius_squared - circle2.radius_squared) / center_dist_squared
    center = (circle1.center + circle2.center) / 2 + relative_center*center_diff / 2

    rad_sum  = circle1.radius + circle2.radius
    rad_diff = circle1.radius - circle2.radius
    det = (rad_sum ** 2 - center_dist_squared) * (center_dist_squared - rad_diff ** 2)
    if np.isclose(det, 0): return Point(center)
    if det <= 0: return None
    center_deviation = np.sqrt(det)
    center_deviation = np.array(((-center_deviation,),(center_deviation,)))

    return [
        Point(center + center_dev)
        for center_dev in center_deviation * 0.5 * vector_perp_rot(center_diff) / center_dist_squared
    ]

def intersect_cci(circle1, circle2, index, points_order=None):
    res = intersect_cc(circle1, circle2)
    return res_by_index(res, index, points_order)
    
def intersect_cl(circle, line):
    return intersect_lc(line, circle)

def intersect_cli(circle, line, index, points_order=None):
    return intersect_lci(line, circle, index, points_order)

def intersect_cr(circle, ray):
    return intersect_rc(ray, circle)

def intersect_cri(circle, ray, index, points_order=None):
    return intersect_rci(ray, circle, index, points_order)

def intersect_Cl(arc, line):
    results = intersect_lc(line,arc)
    if results is None:
        return None
    if not isinstance(results, Iterable) or isinstance(results, str): results = (results,)
    return [p for p in results if arc.contains(p.coords)]

def intersect_lC(line, arc):
    return intersect_Cl(arc, line)

def intersect_Cli(arc, line, index, points_order=None):
    res = intersect_Cl(arc, line)
    return res_by_index(res, index, points_order)

def intersect_lCi(line, arc, index, points_order=None):
    return intersect_Cli(arc, line, index, points_order)

def intersect_Cr(arc, ray):
    results = intersect_rc(ray, arc)
    if results is None:
        return None
    if not isinstance(results, Iterable) or isinstance(results, str): results = (results,)
    return [p for p in results if arc.contains(p.coords)]

def intersect_rC(ray, arc):
    return intersect_Cr(arc, ray)

def intersect_Cri(arc, ray, index, points_order=None):
    res = intersect_Cr(arc, ray)
    return res_by_index(res, index, points_order)

def intersect_rCi(ray, arc, index, points_order=None):
    return intersect_Cri(arc, ray, index, points_order)

def intersect_Cs(arc, segment):
    results = intersect_sc(segment, arc)
    if results is None:
        return None
    if not isinstance(results, Iterable) or isinstance(results, str): results = (results,)
    return [p for p in results if arc.contains(p.coords)]

def intersect_sC(segment, arc):
    return intersect_Cs(arc, segment)

def intersect_Csi(arc, segment, index, points_order=None):
    res = intersect_Cs(arc, segment)
    return res_by_index(res, index, points_order)

def intersect_sCi(segment, arc, index, points_order=None):
    return intersect_Csi(arc, segment, index, points_order)

def intersect_Cc(arc, circle):
    results = intersect_cc(arc, circle)
    if results is None:
        return None
    if not isinstance(results, Iterable) or isinstance(results, str): results = (results,)
    return [p for p in results if arc.contains(p.coords)] or None

def intersect_cC(circle, arc):
    return intersect_Cc(arc, circle)

def intersect_Cci(arc, circle, index, points_order=None):
    res = intersect_Cc(arc, circle)
    return res_by_index(res, index, points_order)

def intersect_cCi(circle, arc, index, points_order=None):
    return intersect_Cci(arc, circle, index, points_order)

def intersect_CC(arc1, arc2):
    results = intersect_cc(arc1, arc2)
    if results is None:
        return None
    if not isinstance(results, Iterable) or isinstance(results, str): results = (results,)
    return [p for p in results if arc1.contains(p.coords) and arc2.contains(p.coords)] or None

def intersect_CCi(arc1, arc2, index, points_order=None):
    res = intersect_CC(arc1, arc2)
    return res_by_index(res, index, points_order)

def intersect_Sl(sector, line):
    """The points of the boundary of the sector on the line: on its arc
    first, then on the radii to the start and to the end of the arc; a point
    already found (an end of the arc, the centre) is not repeated. Before
    1.8.1 only the arc was intersected."""
    points = list(intersect_Cl(Arc(sector.center, sector.radius, sector.angles), line) or [])
    for a in sector.angles[:2]:
        end = sector.center + sector.radius * np.array([np.cos(a), np.sin(a)])
        if np.allclose(end, sector.center):
            continue
        p = intersect_ls(line, Segment(np.array(sector.center, dtype=float), end))
        if p is not None and not any(np.allclose(p.coords, q.coords) for q in points):
            points.append(p)
    return points or None

def intersect_lS(line, sector):
    return intersect_Sl(sector, line)

def intersect_Sli(sector, line, index, points_order=None):
    res = intersect_Sl(sector, line)
    return res_by_index(res, index, points_order)

def intersect_lSi(line, sector, index, points_order=None):
    return intersect_Sli(sector, line, index, points_order)

def intersect_cs(circle, segment):
    results = intersect_lc(segment, circle)
    if results is None:
        return None
    if (not isinstance(results, Iterable)) or isinstance(results, str): results = (results,)
    filtered = [p for p in results if segment.contains(p.coords)]
    return filtered or None

def intersect_csi(circle, segment, index, points_order=None):
    res = intersect_cs(circle, segment)
    return res_by_index(res, index, points_order)

def intersect_rc(ray, circle):
    results = intersect_lc(ray, circle)
    if results is None:
        return None
    if (not isinstance(results, Iterable)) or isinstance(results, str): results = (results,)
    filtered = [p for p in results if ray.contains(p.coords)]
    return filtered or None

def intersect_rci(ray, circle, index, points_order=None):
    res = intersect_rc(ray, circle)
    return res_by_index(res, index, points_order)

def intersect_sc(segment, circle):
    return intersect_cs(circle, segment)

def intersect_sci(segment, circle, index, points_order=None):
    return intersect_csi(circle, segment, index, points_order)

def intersect_lr(line, ray):
    result = intersect_ll(line, ray)
    if result is None: return None
    return result if ray.contains(result.coords) else None

def intersect_ls(line, segment):
    result = intersect_ll(line, segment)
    if result is None: return None
    return result if segment.contains(result.coords) else None

def intersect_rl(ray, line):
    return intersect_lr(line, ray)

def intersect_rr(r1, r2):
    result = intersect_ll(r1, r2)
    if result is None: return None
    if not r1.contains(result.coords): return None
    if not r2.contains(result.coords): return None
    return result

def intersect_rs(ray, segment):
    result = intersect_ll(ray, segment)
    if result is None: return None
    if not ray.contains(result.coords): return None
    if not segment.contains(result.coords): return None
    return result

def intersect_sl(segment, line):
    return intersect_ls(line, segment)

def intersect_sr(segment, ray):
    return intersect_rs(ray, segment)

def intersect_ss(s1, s2):
    result = intersect_ll(s1, s2)
    if result is None: return None
    if not s1.contains(result.coords): return None
    if not s2.contains(result.coords): return None
    return result

# ── Conic intersections ───────────────────────────────────────────────

def _circle_to_conic(circle):
    """Lift a Circle (center c, radius r) to its Conic matrix form."""
    cx, cy = float(circle.center[0]), float(circle.center[1])
    return Conic.from_coeffs(
        a=1.0, c=1.0,
        d=-2.0 * cx, e=-2.0 * cy,
        f=cx * cx + cy * cy - circle.radius * circle.radius,
    )


def _point_on_both_conics(point, K1, K2, rel_tol=1e-6):
    """True when `point` satisfies both conic equations within tolerance.

    Tolerance is scaled by ``max|M|``: a point is on the curve when
    ``|xᵀMx| ≤ rel_tol · max|M|``. This rides out the rounding that
    accumulates in pencil solving without letting spurious candidates
    slip through.
    """
    v1 = abs(K1.evaluate(point.coords[0], point.coords[1]))
    v2 = abs(K2.evaluate(point.coords[0], point.coords[1]))
    s1 = max(float(np.max(np.abs(K1.matrix))), 1.0)
    s2 = max(float(np.max(np.abs(K2.matrix))), 1.0)
    return v1 <= rel_tol * s1 and v2 <= rel_tol * s2


def intersect_Kl(conic, line):
    """Conic ∩ Line.

    Substituting ``p(t) = p0 + t·v`` (where ``p0 = n·c`` is the closest
    point of the line to the origin and ``v = vector_perp_rot(n)`` —
    the same direction used elsewhere in lib_elements) into
    ``pᵀ M p = 0`` gives a quadratic in t. Returns None, a single Point
    (tangent), or a 2-element list.
    """
    M = conic.matrix
    n = line.normal
    c = line.offset
    p0 = np.array([n[0] * c, n[1] * c, 1.0])
    # Use the same perpendicular convention as Line.v — keeps the
    # intersection-order convention aligned with GGB's Intersect index.
    v = np.array([n[1], -n[0], 0.0])

    A = float(v @ M @ v)
    B = 2.0 * float(p0 @ M @ v)
    C = float(p0 @ M @ p0)

    tol = 1e-12

    if abs(A) > tol:
        disc = B * B - 4 * A * C
        if disc < -1e-9:
            return None
        if abs(disc) < 1e-9:
            t = -B / (2 * A)
            return Point([p0[0] + t * v[0], p0[1] + t * v[1]])
        sq = np.sqrt(disc)
        # Sort ascending: smaller-t point first, regardless of sign(A).
        # Matches GGB's "index 1 = leftmost along line direction" convention.
        t1, t2 = sorted(((-B - sq) / (2 * A), (-B + sq) / (2 * A)))
        return [
            Point([p0[0] + t1 * v[0], p0[1] + t1 * v[1]]),
            Point([p0[0] + t2 * v[0], p0[1] + t2 * v[1]]),
        ]
    if abs(B) > tol:
        t = -C / B
        return Point([p0[0] + t * v[0], p0[1] + t * v[1]])
    # A ≈ 0 and B ≈ 0: line is entirely on the conic, or parallel and outside.
    return None


def intersect_lK(line, conic):
    return intersect_Kl(conic, line)


def intersect_Kli(conic, line, index, points_order=None):
    res = intersect_Kl(conic, line)
    return res_by_index(res, index, points_order)


def intersect_lKi(line, conic, index, points_order=None):
    return intersect_Kli(conic, line, index, points_order)


def intersect_KK(K1, K2):
    """Intersect two conics using the pencil method.

    The family ``λ·M1 + M2`` (λ ∈ ℝ) contains every conic through the
    common points of K1 and K2. Pick λ so ``det(λM1 + M2) = 0`` — the
    resulting degenerate conic factors as a product of two (possibly
    coincident or imaginary) lines. Intersecting each real line with K1
    recovers the intersection points; tolerance-filtering against both
    originals strips any extraneous line ∩ K1 points.

    ``p(λ) = det(λM1 + M2)`` is a cubic. Its coefficients are recovered
    from 4 samples (λ → ±∞, 0, 1, −1) and the real roots via ``np.roots``.
    """
    M1, M2 = K1.matrix, K2.matrix
    a = float(np.linalg.det(M1))
    d = float(np.linalg.det(M2))
    p_plus = float(np.linalg.det(M1 + M2))
    p_minus = float(np.linalg.det(M2 - M1))
    b = (p_plus + p_minus) / 2 - d
    c = (p_plus - p_minus) / 2 - a

    coeffs = [a, b, c, d]
    while len(coeffs) > 1 and abs(coeffs[0]) < 1e-12:
        coeffs = coeffs[1:]
    if not coeffs or all(abs(x) < 1e-12 for x in coeffs):
        return None

    try:
        roots = np.roots(coeffs)
    except np.linalg.LinAlgError:
        return None

    real_roots = [float(r.real) for r in roots if abs(r.imag) < 1e-6]
    if not real_roots:
        return None

    candidates = []
    for lam in real_roots:
        K_deg = Conic(lam * M1 + M2)
        if not K_deg.is_degenerate():
            continue
        lines = K_deg.as_lines()
        if not lines:
            continue
        for line in lines:
            res = intersect_Kl(K1, line)
            if res is None:
                continue
            if isinstance(res, list):
                candidates.extend(res)
            else:
                candidates.append(res)
        if candidates:
            break

    if not candidates:
        return None

    # Deduplicate — a point lying on both decomposed lines appears twice.
    unique = []
    for p in candidates:
        if not any(np.allclose(p.coords, u.coords, atol=1e-6) for u in unique):
            unique.append(p)

    filtered = [p for p in unique if _point_on_both_conics(p, K1, K2)]
    if not filtered:
        return None
    if len(filtered) == 1:
        return filtered[0]
    return filtered


def intersect_KKi(K1, K2, index, points_order=None):
    res = intersect_KK(K1, K2)
    return res_by_index(res, index, points_order)


def intersect_Kc(conic, circle):
    return intersect_KK(conic, _circle_to_conic(circle))


def intersect_cK(circle, conic):
    return intersect_Kc(conic, circle)


def intersect_Kci(conic, circle, index, points_order=None):
    res = intersect_Kc(conic, circle)
    return res_by_index(res, index, points_order)


def intersect_cKi(circle, conic, index, points_order=None):
    return intersect_Kci(conic, circle, index, points_order)

def intersect_KC(conic, arc):
    res = intersect_Kc(conic, arc)
    if res is None:
        return None
    if not isinstance(res, list):
        return res if arc.contains(res.coords) else None
    return [p for p in res if arc.contains(p.coords)] or None


def intersect_CK(arc, conic):
    return intersect_KC(conic, arc)


def intersect_KCi(conic, arc, index, points_order=None):
    res = intersect_KC(conic, arc)
    return res_by_index(res, index, points_order)


def intersect_CKi(arc, conic, index, points_order=None):
    return intersect_KCi(conic, arc, index, points_order)


def intersect_Kr(conic, ray):
    res = intersect_Kl(conic, ray)
    if res is None:
        return None
    if not isinstance(res, list):
        return res if ray.contains(res.coords) else None
    return [p for p in res if ray.contains(p.coords)] or None


def intersect_rK(ray, conic):
    return intersect_Kr(conic, ray)


def intersect_Kri(conic, ray, index, points_order=None):
    res = intersect_Kr(conic, ray)
    return res_by_index(res, index, points_order)


def intersect_rKi(ray, conic, index, points_order=None):
    return intersect_Kri(conic, ray, index, points_order)


def intersect_Ks(conic, segment):
    res = intersect_Kl(conic, segment)
    if res is None:
        return None
    if not isinstance(res, list):
        return res if segment.contains(res.coords) else None
    return [p for p in res if segment.contains(p.coords)] or None


def intersect_sK(segment, conic):
    return intersect_Ks(conic, segment)


def intersect_Ksi(conic, segment, index, points_order=None):
    res = intersect_Ks(conic, segment)
    return res_by_index(res, index, points_order)


def intersect_sKi(segment, conic, index, points_order=None):
    return intersect_Ksi(conic, segment, index, points_order)


# ── Function intersections ───────────────────────────────────────────

def _bisect_root(g, a, b, xtol=1e-12, maxiter=100):
    fa = float(g(float(a)))
    fb = float(g(float(b)))
    if not (np.isfinite(fa) and np.isfinite(fb)):
        raise ValueError("root bracket contains non-finite values")
    if abs(fa) <= xtol:
        return float(a)
    if abs(fb) <= xtol:
        return float(b)
    if fa * fb > 0:
        raise ValueError("root is not bracketed")
    lo, hi = float(a), float(b)
    for _ in range(maxiter):
        mid = (lo + hi) / 2.0
        fm = float(g(mid))
        if not np.isfinite(fm):
            raise ValueError("non-finite midpoint value")
        if abs(fm) <= xtol or abs(hi - lo) <= xtol:
            return mid
        if fa * fm <= 0:
            hi, fb = mid, fm
        else:
            lo, fa = mid, fm
    return (lo + hi) / 2.0

def intersect_Fl(func, line):
    """Function y = f(x) ∩ Line n·p = c_line.

    Substituting y = f(x) into the line equation reduces to
    ``n[0]·x + n[1]·f(x) = c_line`` — one scalar equation in x.
    Symbolic via ``sympy.solve`` first; if sympy returns nothing real,
    numerical fallback scans for sign changes and refines with Brent's
    method. Vertical lines (n[1]=0) short-circuit to ``x = c_line/n[0]``.
    """
    import sympy as sp

    n = line.normal
    c_line = line.offset

    # Vertical line.
    if abs(n[1]) < 1e-12:
        if abs(n[0]) < 1e-12:
            return None  # degenerate
        x_val = c_line / n[0]
        y_val = func(x_val)
        if not np.isfinite(y_val):
            return None
        return Point([x_val, float(y_val)])

    # Symbolic attempt.
    real_solutions: list = []
    try:
        equation = sp.nsimplify(n[0]) * func.var + sp.nsimplify(n[1]) * func.expr - sp.nsimplify(c_line)
        sym_sols = sp.solve(equation, func.var)
        for s in sym_sols:
            try:
                val = complex(s)
                if abs(val.imag) < 1e-9 and np.isfinite(val.real):
                    real_solutions.append(float(val.real))
            except (TypeError, ValueError):
                continue
    except Exception:
        pass

    # Numerical fallback if sympy found nothing.
    if not real_solutions:
        def g(xv):
            try:
                fv = float(func(xv))
                if not np.isfinite(fv):
                    return float('nan')
                return float(n[0]) * xv + float(n[1]) * fv - float(c_line)
            except Exception:
                return float('nan')

        search_range = (-100.0, 100.0)
        xs = np.linspace(search_range[0], search_range[1], 501)
        gs = np.array([g(float(xv)) for xv in xs])
        for i in range(len(xs) - 1):
            a_val, b_val = gs[i], gs[i + 1]
            if not (np.isfinite(a_val) and np.isfinite(b_val)):
                continue
            if a_val * b_val < 0:
                try:
                    root = _bisect_root(g, xs[i], xs[i + 1], xtol=1e-12, maxiter=100)
                    real_solutions.append(float(root))
                except (ValueError, RuntimeError):
                    continue
            elif abs(a_val) < 1e-9:
                real_solutions.append(float(xs[i]))

    # Deduplicate nearby roots.
    dedup: list = []
    for x_sol in sorted(real_solutions):
        if not dedup or abs(x_sol - dedup[-1]) > 1e-6:
            dedup.append(x_sol)

    points = []
    for x_sol in dedup:
        y_sol = func(x_sol)
        if not np.isfinite(y_sol):
            continue
        points.append(Point([float(x_sol), float(y_sol)]))

    if not points:
        return None
    if len(points) == 1:
        return points[0]
    return points


def intersect_lF(line, func):
    return intersect_Fl(func, line)


def intersect_Fli(func, line, index, points_order=None):
    res = intersect_Fl(func, line)
    return res_by_index(res, index, points_order)


def intersect_lFi(line, func, index, points_order=None):
    return intersect_Fli(func, line, index, points_order)


def intersect_Fs(func, segment):
    res = intersect_Fl(func, segment)
    if res is None:
        return None
    if not isinstance(res, list):
        return res if segment.contains(res.coords) else None
    return [p for p in res if segment.contains(p.coords)] or None


def intersect_sF(segment, func):
    return intersect_Fs(func, segment)


def intersect_Fsi(func, segment, index, points_order=None):
    res = intersect_Fs(func, segment)
    return res_by_index(res, index, points_order)


def intersect_sFi(segment, func, index, points_order=None):
    return intersect_Fsi(func, segment, index, points_order)


def intersect_Fr(func, ray):
    res = intersect_Fl(func, ray)
    if res is None:
        return None
    if not isinstance(res, list):
        return res if ray.contains(res.coords) else None
    return [p for p in res if ray.contains(p.coords)] or None


def intersect_rF(ray, func):
    return intersect_Fr(func, ray)


def intersect_Fri(func, ray, index, points_order=None):
    res = intersect_Fr(func, ray)
    return res_by_index(res, index, points_order)


def intersect_rFi(ray, func, index, points_order=None):
    return intersect_Fri(func, ray, index, points_order)


# ── Numeric root-finding helpers ──────────────────────────────────────

def _find_roots_1d(g, x_range=(-50.0, 50.0), n_samples=401,
                   tol=1e-12, dedup_tol=1e-8):
    """Real roots of a scalar callable ``g`` on ``x_range``.

    Strategy: sample on a uniform grid, scan for sign changes or explicit
    zeros, refine with Brent's method. NaN values break continuity
    (skip the interval). Returns sorted, deduplicated roots.
    """
    lo, hi = float(x_range[0]), float(x_range[1])
    xs = np.linspace(lo, hi, n_samples)
    gs = np.empty(len(xs), dtype=float)
    for i, x in enumerate(xs):
        try:
            v = float(g(float(x)))
        except Exception:
            v = float('nan')
        gs[i] = v if np.isfinite(v) else float('nan')

    roots = []
    for i in range(len(xs) - 1):
        a, b = gs[i], gs[i + 1]
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        if a == 0:
            roots.append(float(xs[i]))
        elif a * b < 0:
            try:
                r = _bisect_root(g, xs[i], xs[i + 1], xtol=tol, maxiter=100)
                roots.append(float(r))
            except (ValueError, RuntimeError):
                continue
    if np.isfinite(gs[-1]) and gs[-1] == 0:
        roots.append(float(xs[-1]))

    roots.sort()
    dedup: list = []
    for r in roots:
        if not dedup or abs(r - dedup[-1]) > dedup_tol:
            dedup.append(r)
    return dedup


# ── Function ∩ Conic / Circle / Function ──────────────────────────────

def _g_func_vs_conic(func, M):
    """Return g(x) = pᵀ M p for p = (x, f(x), 1)."""
    A, B, D = M[0, 0], M[0, 1], M[0, 2]
    C, E = M[1, 1], M[1, 2]
    F_const = M[2, 2]

    def g(x_val):
        y_val = func(x_val)
        if not np.isfinite(y_val):
            return float('nan')
        return (A * x_val * x_val + 2.0 * B * x_val * y_val
                + C * y_val * y_val
                + 2.0 * D * x_val + 2.0 * E * y_val
                + F_const)
    return g


def intersect_FK(func, conic):
    """Function ∩ Conic via 1D numeric root-finding on ``pᵀMp = 0``."""
    g = _g_func_vs_conic(func, conic.matrix)
    xs = _find_roots_1d(g)
    points = []
    for x_sol in xs:
        y_sol = func(x_sol)
        if np.isfinite(y_sol):
            points.append(Point([float(x_sol), float(y_sol)]))
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    return points


def intersect_KF(conic, func):
    return intersect_FK(func, conic)


def intersect_FKi(func, conic, index, points_order=None):
    res = intersect_FK(func, conic)
    return res_by_index(res, index, points_order)


def intersect_KFi(conic, func, index, points_order=None):
    return intersect_FKi(func, conic, index, points_order)


def intersect_Fc(func, circle):
    return intersect_FK(func, _circle_to_conic(circle))


def intersect_cF(circle, func):
    return intersect_Fc(func, circle)


def intersect_Fci(func, circle, index, points_order=None):
    res = intersect_Fc(func, circle)
    return res_by_index(res, index, points_order)


def intersect_cFi(circle, func, index, points_order=None):
    return intersect_Fci(func, circle, index, points_order)


def intersect_FF(func1, func2):
    """Function ∩ Function: roots of f₁(x) − f₂(x) = 0."""
    def g(x_val):
        a = func1(x_val)
        b = func2(x_val)
        if not (np.isfinite(a) and np.isfinite(b)):
            return float('nan')
        return a - b
    xs = _find_roots_1d(g)
    points = []
    for x_sol in xs:
        y_sol = func1(x_sol)
        if np.isfinite(y_sol):
            points.append(Point([float(x_sol), float(y_sol)]))
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    return points


def intersect_FFi(func1, func2, index, points_order=None):
    res = intersect_FF(func1, func2)
    return res_by_index(res, index, points_order)


# ── ImplicitCurve intersections ───────────────────────────────────────

def _implicit_search_box():
    """Default 2D search range for implicit-curve intersections.

    Used when the caller doesn't supply one. Large enough to cover
    typical construction bounds while keeping the grid cheap.
    """
    return (-50.0, -50.0, 50.0, 50.0)


def intersect_Il(curve, line):
    """ImplicitCurve ∩ Line.

    Substitute the line parametrization ``p(t) = p0 + t·v`` into the
    implicit ``F(x, y)`` and root-find in t.
    """
    n = line.normal
    c_line = line.offset
    p0 = np.array([n[0] * c_line, n[1] * c_line])
    v = np.array([n[1], -n[0]])

    def g(t):
        x = p0[0] + t * v[0]
        y = p0[1] + t * v[1]
        try:
            val = float(curve(x, y))
            return val if np.isfinite(val) else float('nan')
        except Exception:
            return float('nan')

    ts = _find_roots_1d(g, x_range=(-100.0, 100.0), n_samples=801)
    points = []
    for t in ts:
        points.append(Point([float(p0[0] + t * v[0]),
                             float(p0[1] + t * v[1])]))
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    return points


def intersect_lI(line, curve):
    return intersect_Il(curve, line)


def intersect_Ili(curve, line, index, points_order=None):
    res = intersect_Il(curve, line)
    return res_by_index(res, index, points_order)


def intersect_lIi(line, curve, index, points_order=None):
    return intersect_Ili(curve, line, index, points_order)


def intersect_Is(curve, segment):
    res = intersect_Il(curve, segment)
    if res is None:
        return None
    if not isinstance(res, list):
        return res if segment.contains(res.coords) else None
    return [p for p in res if segment.contains(p.coords)] or None


def intersect_sI(segment, curve):
    return intersect_Is(curve, segment)


def intersect_Isi(curve, segment, index, points_order=None):
    res = intersect_Is(curve, segment)
    return res_by_index(res, index, points_order)


def intersect_sIi(segment, curve, index, points_order=None):
    return intersect_Isi(curve, segment, index, points_order)


def intersect_Ir(curve, ray):
    res = intersect_Il(curve, ray)
    if res is None:
        return None
    if not isinstance(res, list):
        return res if ray.contains(res.coords) else None
    return [p for p in res if ray.contains(p.coords)] or None


def intersect_rI(ray, curve):
    return intersect_Ir(curve, ray)


def intersect_Iri(curve, ray, index, points_order=None):
    res = intersect_Ir(curve, ray)
    return res_by_index(res, index, points_order)


def intersect_rIi(ray, curve, index, points_order=None):
    return intersect_Iri(curve, ray, index, points_order)


def _intersect_two_zero_level_sets(F1, F2, viewport=None, grid_n=128):
    """Points where F₁ = 0 and F₂ = 0.

    Algorithm:
    1. Extract F₁'s zero contour as marching-squares line segments.
    2. Along each segment, find a point with F₂ = 0 via Brent on the
       [0, 1] parameter.
    3. Refine the candidate with a small finite-difference 2D Newton solve so
       the final accuracy isn't limited by the marching-squares grid.

    Works uniformly for ImplicitCurve ∩ Conic, ∩ Circle, ∩ Function,
    and ∩ ImplicitCurve.
    """
    from .curve_sampling import marching_squares

    if viewport is None:
        viewport = _implicit_search_box()

    segments = marching_squares(F1, viewport, grid_n=grid_n)

    def _system(xy):
        try:
            v1 = float(F1(xy[0], xy[1]))
            v2 = float(F2(xy[0], xy[1]))
        except Exception:
            return [1e12, 1e12]
        if not np.isfinite(v1):
            v1 = 1e12
        if not np.isfinite(v2):
            v2 = 1e12
        return [v1, v2]

    def _norm(vals):
        return float(np.linalg.norm(np.asarray(vals, dtype=float), ord=2))

    def _refine_candidate(xy):
        xy = np.asarray(xy, dtype=float)
        vals = np.asarray(_system(xy), dtype=float)
        best_norm = _norm(vals)
        if not np.isfinite(best_norm):
            return None

        for _ in range(20):
            if best_norm < 1e-10:
                return (float(xy[0]), float(xy[1]))

            h_x = 1e-5 * max(1.0, abs(float(xy[0])))
            h_y = 1e-5 * max(1.0, abs(float(xy[1])))
            fx1 = np.asarray(_system([xy[0] + h_x, xy[1]]), dtype=float)
            fx0 = np.asarray(_system([xy[0] - h_x, xy[1]]), dtype=float)
            fy1 = np.asarray(_system([xy[0], xy[1] + h_y]), dtype=float)
            fy0 = np.asarray(_system([xy[0], xy[1] - h_y]), dtype=float)
            jac = np.column_stack(((fx1 - fx0) / (2.0 * h_x),
                                   (fy1 - fy0) / (2.0 * h_y)))
            if not np.all(np.isfinite(jac)):
                break

            try:
                step = np.linalg.solve(jac, -vals)
            except np.linalg.LinAlgError:
                try:
                    step = np.linalg.lstsq(jac, -vals, rcond=None)[0]
                except np.linalg.LinAlgError:
                    break
            if not np.all(np.isfinite(step)):
                break

            accepted = False
            scale = 1.0
            for _ in range(8):
                nxt = xy + scale * step
                nxt_vals = np.asarray(_system(nxt), dtype=float)
                nxt_norm = _norm(nxt_vals)
                if np.isfinite(nxt_norm) and nxt_norm < best_norm:
                    xy = nxt
                    vals = nxt_vals
                    best_norm = nxt_norm
                    accepted = True
                    break
                scale *= 0.5
            if not accepted or np.linalg.norm(scale * step) < 1e-10:
                break

        return (float(xy[0]), float(xy[1])) if best_norm < 1e-6 else None

    raw = []
    for seg in segments:
        p1, p2 = seg[0], seg[1]

        def line_g(t, p1=p1, p2=p2):
            x = p1[0] + t * (p2[0] - p1[0])
            y = p1[1] + t * (p2[1] - p1[1])
            try:
                val = float(F2(x, y))
                return val if np.isfinite(val) else float('nan')
            except Exception:
                return float('nan')

        a, b = line_g(0.0), line_g(1.0)
        cand = None
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        # Tolerance-based near-zero tests. Exact float equality here used
        # to miss cases where rounding made a true zero read back as ±1e-17
        # — the segment endpoint was silently skipped as a valid root.
        _ZTOL = 1e-12
        if abs(a) < _ZTOL:
            cand = (p1[0], p1[1])
        elif abs(b) < _ZTOL:
            cand = (p2[0], p2[1])
        elif a * b < 0:
            try:
                t = _bisect_root(line_g, 0.0, 1.0, xtol=1e-10, maxiter=100)
                cand = (p1[0] + t * (p2[0] - p1[0]),
                        p1[1] + t * (p2[1] - p1[1]))
            except (ValueError, RuntimeError):
                continue
        if cand is None:
            continue

        refined = _refine_candidate(cand)
        raw.append(refined or cand)

    dedup: list = []
    for x, y in raw:
        if not any(abs(x - q[0]) < 1e-5 and abs(y - q[1]) < 1e-5 for q in dedup):
            dedup.append((x, y))
    return [Point([x, y]) for x, y in dedup]


def intersect_IK(curve, conic):
    """ImplicitCurve ∩ Conic."""
    def F2(x, y):
        return (conic.matrix[0, 0] * x * x
                + 2.0 * conic.matrix[0, 1] * x * y
                + conic.matrix[1, 1] * y * y
                + 2.0 * conic.matrix[0, 2] * x
                + 2.0 * conic.matrix[1, 2] * y
                + conic.matrix[2, 2])

    points = _intersect_two_zero_level_sets(curve, F2)
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    return points


def intersect_KI(conic, curve):
    return intersect_IK(curve, conic)


def intersect_IKi(curve, conic, index, points_order=None):
    res = intersect_IK(curve, conic)
    return res_by_index(res, index, points_order)


def intersect_KIi(conic, curve, index, points_order=None):
    return intersect_IKi(curve, conic, index, points_order)


def intersect_Ic(curve, circle):
    return intersect_IK(curve, _circle_to_conic(circle))


def intersect_cI(circle, curve):
    return intersect_Ic(curve, circle)


def intersect_Ici(curve, circle, index, points_order=None):
    res = intersect_Ic(curve, circle)
    return res_by_index(res, index, points_order)


def intersect_cIi(circle, curve, index, points_order=None):
    return intersect_Ici(curve, circle, index, points_order)


def intersect_IF(curve, func):
    """ImplicitCurve ∩ Function via the two-level-set algorithm with
    F₂(x, y) = y − f(x).
    """
    def F2(x, y):
        fv = func(x)
        if not np.isfinite(fv):
            # Treat as "outside the domain": return a large value so
            # sign never flips there.
            return float('nan')
        return y - fv

    points = _intersect_two_zero_level_sets(curve, F2)
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    return points


def intersect_FI(func, curve):
    return intersect_IF(curve, func)


def intersect_IFi(curve, func, index, points_order=None):
    res = intersect_IF(curve, func)
    return res_by_index(res, index, points_order)


def intersect_FIi(func, curve, index, points_order=None):
    return intersect_IFi(curve, func, index, points_order)


def intersect_II(curve1, curve2):
    points = _intersect_two_zero_level_sets(curve1, curve2)
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    return points


def intersect_IIi(curve1, curve2, index, points_order=None):
    res = intersect_II(curve1, curve2)
    return res_by_index(res, index, points_order)


# ── Conic properties: Center, Focus, Vertex, Axes, Directrix ──────────

def center_K(conic):
    """Center of ellipse/hyperbola/circle; vertex of parabola (GGB convention);
    the single point of a point-type degenerate. Returns None for families
    with no geometrically meaningful center (double line, empty, etc.)."""
    t = conic.type
    if t == ConicType.CIRCLE:
        res = conic.as_circle()
        return Point(res[0]) if res else None
    if t == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        return Point(p['center']) if p else None
    if t == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        return Point(p['center']) if p else None
    if t == ConicType.PARABOLA:
        p = conic.as_parabola()
        return Point(p['vertex']) if p else None
    if t == ConicType.POINT:
        return conic.as_point()
    return None


def focus_K(conic):
    """Foci of the conic: 2 for ellipse/hyperbola, 1 for parabola,
    the center for circles (degenerate)."""
    t = conic.type
    if t == ConicType.CIRCLE:
        res = conic.as_circle()
        return Point(res[0]) if res else None
    if t == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        if p is None:
            return None
        a, b = p['semi_axes']
        cc = np.sqrt(max(0.0, a * a - b * b))
        rot = p['rotation']
        u = np.array([np.cos(rot), np.sin(rot)])
        return [Point(p['center'] + cc * u), Point(p['center'] - cc * u)]
    if t == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        if p is None:
            return None
        a, b = p['semi_axes']
        cc = np.sqrt(a * a + b * b)
        rot = p['rotation']
        u = np.array([np.cos(rot), np.sin(rot)])
        return [Point(p['center'] + cc * u), Point(p['center'] - cc * u)]
    if t == ConicType.PARABOLA:
        p = conic.as_parabola()
        if p is None:
            return None
        return Point(p['vertex'] + p['focal_parameter'] * p['axis'])
    return None


def vertex_K(conic):
    """Vertices on the principal axes: 4 for ellipse, 2 for hyperbola,
    1 for parabola, none for circle (any point is a vertex)."""
    t = conic.type
    if t == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        if p is None:
            return None
        a, b = p['semi_axes']
        rot = p['rotation']
        u = np.array([np.cos(rot), np.sin(rot)])
        w = np.array([-np.sin(rot), np.cos(rot)])
        return [
            Point(p['center'] + a * u), Point(p['center'] - a * u),
            Point(p['center'] + b * w), Point(p['center'] - b * w),
        ]
    if t == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        if p is None:
            return None
        a, _ = p['semi_axes']
        rot = p['rotation']
        u = np.array([np.cos(rot), np.sin(rot)])
        return [Point(p['center'] + a * u), Point(p['center'] - a * u)]
    if t == ConicType.PARABOLA:
        p = conic.as_parabola()
        return Point(p['vertex']) if p else None
    return None


def axes_K(conic):
    """Returns [major_axis, minor_axis] as Lines for ellipse/hyperbola;
    the single symmetry axis for parabola."""
    t = conic.type
    if t in (ConicType.ELLIPSE, ConicType.HYPERBOLA):
        p = (conic.as_ellipse() if t == ConicType.ELLIPSE
             else conic.as_hyperbola())
        if p is None:
            return None
        center = p['center']
        rot = p['rotation']
        u = np.array([np.cos(rot), np.sin(rot)])
        perp = np.array([-np.sin(rot), np.cos(rot)])
        # Major axis has direction u → normal is perp. Line equation:
        # perp · x = perp · center.
        major = Line(perp, float(np.dot(perp, center)))
        minor = Line(u, float(np.dot(u, center)))
        return [major, minor]
    if t == ConicType.PARABOLA:
        p = conic.as_parabola()
        if p is None:
            return None
        # Axis line through vertex along 'axis' direction → normal = perp.
        return Line(p['perp'], float(np.dot(p['perp'], p['vertex'])))
    return None


def major_axis_K(conic):
    res = axes_K(conic)
    if res is None:
        return None
    return res[0] if isinstance(res, list) else res


def minor_axis_K(conic):
    res = axes_K(conic)
    if res is None or not isinstance(res, list) or len(res) < 2:
        return None
    return res[1]


def semi_major_axis_length_K(conic):
    t = conic.type
    if t == ConicType.CIRCLE:
        res = conic.as_circle()
        return Measure(float(res[1]), 1) if res else None
    if t == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        return Measure(float(p['semi_axes'][0]), 1) if p else None
    if t == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        return Measure(float(p['semi_axes'][0]), 1) if p else None
    return None


def semi_minor_axis_length_K(conic):
    t = conic.type
    if t == ConicType.CIRCLE:
        res = conic.as_circle()
        return Measure(float(res[1]), 1) if res else None
    if t == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        return Measure(float(p['semi_axes'][1]), 1) if p else None
    if t == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        return Measure(float(p['semi_axes'][1]), 1) if p else None
    return None


def eccentricity_K(conic):
    t = conic.type
    if t == ConicType.CIRCLE:
        return Measure(0.0, 0)
    if t == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        if p is None:
            return None
        a, b = p['semi_axes']
        if a <= 0:
            return None
        c = np.sqrt(max(0.0, a * a - b * b))
        return Measure(float(c / a), 0)
    if t == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        if p is None:
            return None
        a, b = p['semi_axes']
        if a <= 0:
            return None
        c = np.sqrt(a * a + b * b)
        return Measure(float(c / a), 0)
    if t == ConicType.PARABOLA:
        return Measure(1.0, 0)
    return None


def linear_eccentricity_K(conic):
    t = conic.type
    if t == ConicType.CIRCLE:
        return Measure(0.0, 1)
    if t == ConicType.ELLIPSE:
        p = conic.as_ellipse()
        if p is None:
            return None
        a, b = p['semi_axes']
        return Measure(float(np.sqrt(max(0.0, a * a - b * b))), 1)
    if t == ConicType.HYPERBOLA:
        p = conic.as_hyperbola()
        if p is None:
            return None
        a, b = p['semi_axes']
        return Measure(float(np.sqrt(a * a + b * b)), 1)
    return None


def directrix_K(conic):
    """Directrix line(s): 1 for parabola, 2 for ellipse/hyperbola."""
    t = conic.type
    if t == ConicType.PARABOLA:
        p = conic.as_parabola()
        if p is None:
            return None
        # Directrix is perpendicular to the axis at distance p behind the vertex.
        point_on_directrix = p['vertex'] - p['focal_parameter'] * p['axis']
        n = p['axis']
        return Line(n, float(np.dot(n, point_on_directrix)))
    if t in (ConicType.ELLIPSE, ConicType.HYPERBOLA):
        p = (conic.as_ellipse() if t == ConicType.ELLIPSE
             else conic.as_hyperbola())
        if p is None:
            return None
        a, b = p['semi_axes']
        if t == ConicType.ELLIPSE:
            c = np.sqrt(max(0.0, a * a - b * b))
        else:
            c = np.sqrt(a * a + b * b)
        if c <= 0:
            return None
        # Directrix distance from center: a²/c = a/e.
        d = a * a / c
        rot = p['rotation']
        u = np.array([np.cos(rot), np.sin(rot)])
        pt1 = p['center'] + d * u
        pt2 = p['center'] - d * u
        return [
            Line(u, float(np.dot(u, pt1))),
            Line(u, float(np.dot(u, pt2))),
        ]
    return None


def coefficients_K(conic):
    """Returns (A, B, C, D, E, F) for A x² + B xy + C y² + D x + E y + F = 0,
    matching GGB's Coefficients() convention."""
    M = conic.matrix
    return [
        float(M[0, 0]),
        2.0 * float(M[0, 1]),
        float(M[1, 1]),
        2.0 * float(M[0, 2]),
        2.0 * float(M[1, 2]),
        float(M[2, 2]),
    ]


# ── Polar and Tangent ─────────────────────────────────────────────────

def polar_pK(point, conic):
    """Polar line of a point with respect to a conic: ``pᵀ M q = 0``."""
    M = conic.matrix
    p = np.array([point.coords[0], point.coords[1], 1.0])
    coeffs = p @ M
    n = coeffs[:2]
    if np.linalg.norm(n) < 1e-12:
        return None
    return Line(n, -float(coeffs[2]))


def polar_Kp(conic, point):
    return polar_pK(point, conic)


def tangent_pK(point, conic):
    """Tangent line(s) from a point to a conic.

    - Point on conic: polar line IS the tangent (single line).
    - Point outside conic: the polar intersects the conic in 2 points —
      the tangent chord's endpoints — and each of these is where a
      tangent from the external point meets the conic. The tangent at
      each such point is that point's own polar.
    - Point inside conic: no real tangents (returns None).
    """
    M = conic.matrix
    p = np.array([point.coords[0], point.coords[1], 1.0])
    val = float(p @ M @ p)
    polar = polar_pK(point, conic)
    if polar is None:
        return None

    scale = max(float(np.max(np.abs(M))), 1.0)
    if abs(val) < 1e-6 * scale:
        return polar

    touch_points = intersect_Kl(conic, polar)
    if touch_points is None:
        return None
    if not isinstance(touch_points, list):
        touch_points = [touch_points]

    tangents = []
    for tp in touch_points:
        tl = polar_pK(tp, conic)
        if tl is not None:
            tangents.append(tl)
    if not tangents:
        return None
    if len(tangents) == 1:
        return tangents[0]
    return tangents


def tangent_Kp(conic, point):
    return tangent_pK(point, conic)


# ── Conic(p1, p2, p3, p4, p5): conic through 5 points ─────────────────

def conic_ppppp(p1, p2, p3, p4, p5):
    """Unique (up to scale) conic through 5 points.

    Each point (xᵢ, yᵢ) gives a linear constraint on the coefficients
    (A, B, C, D, E, F) in ``A x² + B xy + C y² + D x + E y + F = 0``.
    The 5×6 system has a one-dimensional null space; the conic's
    coefficients are any non-trivial vector in that null space,
    recovered via SVD.
    """
    pts = [p1, p2, p3, p4, p5]
    A = np.array([
        [p.coords[0] ** 2, p.coords[0] * p.coords[1], p.coords[1] ** 2, p.coords[0], p.coords[1], 1.0]
        for p in pts
    ])
    try:
        _, _, V = np.linalg.svd(A)
    except np.linalg.LinAlgError:
        return None
    coeffs = V[-1]
    return Conic.from_coeffs(
        a=coeffs[0], b=coeffs[1], c=coeffs[2],
        d=coeffs[3], e=coeffs[4], f=coeffs[5],
    )


# ── Geometric conic constructors (GGB: Ellipse, Hyperbola, Parabola) ─

def _build_focal_conic(f1_arr, f2_arr, a, kind):
    """Construct ellipse / hyperbola from foci and semi-major axis.

    ``kind`` is 'ellipse' (a > c, real ellipse) or 'hyperbola'
    (a < c, real hyperbola). Builds the matrix in canonical form then
    applies the rigid motion ``A = [R | center]`` via the congruence
    ``M_world = A⁻ᵀ · M_canon · A⁻¹``.
    """
    center = (f1_arr + f2_arr) / 2.0
    focus_diff = f2_arr - f1_arr
    c_lin = float(np.linalg.norm(focus_diff)) / 2.0

    if kind == 'ellipse':
        if a <= c_lin:
            return None
        b_sq = a * a - c_lin * c_lin
        M_canon = np.diag([1.0 / (a * a), 1.0 / b_sq, -1.0])
    else:  # hyperbola
        if a >= c_lin:
            return None
        b_sq = c_lin * c_lin - a * a
        M_canon = np.diag([1.0 / (a * a), -1.0 / b_sq, -1.0])

    if c_lin < 1e-12:
        theta = 0.0
    else:
        theta = float(np.arctan2(focus_diff[1], focus_diff[0]))
    cs, sn = np.cos(theta), np.sin(theta)
    A = np.eye(3)
    A[:2, :2] = np.array([[cs, -sn], [sn, cs]])
    A[:2, 2] = center
    A_inv = np.linalg.inv(A)
    return Conic(A_inv.T @ M_canon @ A_inv)


def ellipse_ppi(f1, f2, a):
    return _build_focal_conic(np.asarray(f1.coords), np.asarray(f2.coords), float(a), 'ellipse')


def ellipse_ppm(f1, f2, m):
    return ellipse_ppi(f1, f2, m.value)


def ellipse_ppp(f1, f2, p):
    """Ellipse with foci ``f1``, ``f2`` and a third point on the curve.

    For an ellipse, ``2a = |f1p| + |f2p|`` for any point p on the curve
    (the focal-radii sum definition).
    """
    a = (np.linalg.norm(f1.coords - p.coords) + np.linalg.norm(f2.coords - p.coords)) / 2.0
    return ellipse_ppi(f1, f2, float(a))


def hyperbola_ppi(f1, f2, a):
    return _build_focal_conic(np.asarray(f1.coords), np.asarray(f2.coords), float(a), 'hyperbola')


def hyperbola_ppm(f1, f2, m):
    return hyperbola_ppi(f1, f2, m.value)


def hyperbola_ppp(f1, f2, p):
    """Hyperbola with foci ``f1``, ``f2`` and a third point on the curve.

    ``2a = ||f1p| − |f2p||``.
    """
    a = abs(np.linalg.norm(f1.coords - p.coords) - np.linalg.norm(f2.coords - p.coords)) / 2.0
    return hyperbola_ppi(f1, f2, float(a))


def parabola_pl(focus, directrix):
    """Parabola defined by focus + directrix line.

    vertex = midpoint of focus and its projection on the directrix.
    axis points from directrix to focus.
    focal parameter p = distance(vertex, focus).

    In the local frame ``(u, v)`` aligned with (perp, axis), the
    canonical equation is ``u² = 4 p v`` → matrix
    ``[[1, 0, 0], [0, 0, −2p], [0, −2p, 0]]``.
    """
    n = directrix.normal
    c_line = directrix.offset
    dist_signed = float(np.dot(n, focus.coords)) - c_line
    if abs(dist_signed) < 1e-12:
        return None  # focus on directrix → degenerate
    projection = focus.coords - dist_signed * n
    vertex = (focus.coords + projection) / 2.0
    axis_vec = focus.coords - projection
    axis_norm = float(np.linalg.norm(axis_vec))
    if axis_norm < 1e-12:
        return None
    axis_vec = axis_vec / axis_norm
    p_focal = abs(dist_signed) / 2.0

    M_canon = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -2.0 * p_focal],
        [0.0, -2.0 * p_focal, 0.0],
    ])

    perp = np.array([axis_vec[1], -axis_vec[0]])
    A = np.eye(3)
    A[:2, :2] = np.column_stack([perp, axis_vec])
    A[:2, 2] = vertex
    A_inv = np.linalg.inv(A)
    parabola = Conic(A_inv.T @ M_canon @ A_inv)
    # GeoGebra orients a Parabola(F, d) by the directrix normal ("avoid
    # flip"); Point(parabola, t) travels accordingly (Conic.ggb_frame).
    parabola.ggb_axis_hint = np.array(directrix.normal, dtype=float)
    return parabola


def parabola_ps(focus, segment):
    """Parabola with focus and a directrix segment (uses the underlying line)."""
    return parabola_pl(focus, segment)


def parabola_pr(focus, ray):
    return parabola_pl(focus, ray)


def line_bisector_pp(p1, p2):
    p = (p1.coords + p2.coords) / 2
    n = p2.coords - p1.coords
    if (n == 0).all(): return None
    return Line(n, np.dot(n, p))

def line_bisector_s(segment):
    p1, p2 = segment.endpoints
    p = (p1 + p2) / 2
    n = p2 - p1
    return Line(n, np.dot(n, p))

def length_s(segment):
    return Measure(segment.length, 1)

def length_v(vector):
    return Measure(float(np.linalg.norm(vector.direction)), 1)

def length_C(arc):
    return Measure(float(arc.radius * (arc.angles[1] - arc.angles[0])), 1)

def length_c(circle):
    return circumference_c(circle)

def line_pl(point, line):
    return Line(line.normal, np.dot(line.normal, point.coords))

def line_pp(p1, p2):
    # Coincident within rounding: |p1 - p2| <= 1e-12 * max(1, |p1|, |p2|).
    scale = max(1.0, float(np.linalg.norm(p1.coords)), float(np.linalg.norm(p2.coords)))
    if float(np.linalg.norm(p1.coords - p2.coords)) <= 1e-12 * scale: return None
    n = vector_perp_rot(p1.coords - p2.coords)
    return Line(n, np.dot(p1.coords, n))

def line_pv(pt, vec):
    if (vec.direction == 0).all(): return None
    n = vector_perp_rot(vec.direction)
    return Line(n, np.dot(pt.coords, n))

def line_pr(point, ray):
    return line_pl(point, ray)

def line_ps(point, segment):
    return line_pl(point, segment)

def line_s(segment):
    return Line(segment.normal, segment.offset)

def midpoint_pp(p1, p2):
    return Point((p1.coords+p2.coords)/2)

def midpoint_s(segment):
    p1, p2 = segment.endpoints
    return Point((p1 + p2) / 2)

def mirror_cc(circle, by_circle):
    center_v = circle.center - by_circle.center
    denom = square_norm(center_v) - circle.radius_squared
    if np.isclose(denom, 0):
        return Line(center_v, circle.radius_squared / 2 + np.dot(center_v, by_circle.center))
    else:
        return Circle(
            center = (by_circle.radius_squared/denom) * center_v + by_circle.center,
            r = by_circle.radius_squared * circle.radius / abs(denom)
        )

def mirror_cl(circle, by_line):
    return Circle(
        center = circle.center + by_line.normal*2*(by_line.offset - np.dot(circle.center, by_line.normal)),
        r = circle.radius,
    )

def mirror_cp(circle, by_point):
    return Circle(
        center = 2 * by_point.coords - circle.center,
        r = circle.radius
    )

def mirror_ll(line, by_line):
    n = line.normal - by_line.normal * 2 * np.dot(line.normal, by_line.normal)
    return Line(n, line.offset + 2 * by_line.offset * np.dot(n, by_line.normal) )

def mirror_ls(line, by_segment):
    return mirror_ll(line, by_segment)

def mirror_lp(line, by_point):
    return Line(line.normal, 2 * np.dot(by_point.coords, line.normal) - line.offset)

def mirror_pc(point, by_circle):
    v = point.coords - by_circle.center
    if np.isclose(v, 0).all(): return None
    return Point(by_circle.center + v * (by_circle.radius_squared / square_norm(v)) )

def mirror_pl(point, by_line):
    return Point(point.coords + by_line.normal * 2 * (by_line.offset - np.dot(point.coords, by_line.normal)))

def mirror_pp(point, by_point):
    return Point(2 * by_point.coords - point.coords)

def mirror_ps(point, by_segment):
    return mirror_pl(point, by_segment)

def orthogonal_line_pl(point, line):
    return Line(-line.direction, np.dot(-line.direction, point.coords))

def orthogonal_line_pr(point, ray):
    return orthogonal_line_pl(point, ray)

def orthogonal_line_ps(point, segment):
    return orthogonal_line_pl(point, segment)

def point_():
    return Point(current_rng().normal(size = 2))

def point_ii(x, y):
    return Point([x,y])

def point_im(x, y):
    """``(x, y)`` with a measure among the coordinates — ``(0, -Radius(c))``."""
    return Point([_num(x), _num(y)])

point_mi = point_mm = point_im

def point_c(circle, tparam = None):
    """Point on a circle. ``tparam`` is the angle in radians."""
    return Point(circle.center + circle.radius * get_direction(tparam))

def point_l(line, tparam = None):
    """Point on a line. ``tparam`` is the linear parameter along direction."""
    return Point(line.offset * line.normal + line.direction * (tparam if tparam is not None else current_rng().normal()) )

def point_r(ray, tparam = None):
    """Point on a ray. ``tparam`` is distance along the ray direction."""
    t = tparam if tparam is not None else current_rng().random()
    return Point(ray.start + ray.direction * max(0.0, float(t)))

def point_s(segment, tparam = None):
    """Point on a segment. ``tparam`` is the linear parameter (0..1 for interior)."""
    return Point(interpolate(segment.endpoints[0], segment.endpoints[1], tparam if tparam is not None else current_rng().random()))

def point_C(arc, tparam = None):
    """Point on an arc. ``tparam`` is the absolute angle in radians."""
    a1, a2 = arc.angles
    angle = (a1 + a2) / 2 if tparam is None else float(tparam)
    if angle < a1 and a2 > 2 * np.pi:
        angle += 2 * np.pi
    angle = min(max(angle, a1), a2)
    return Point(arc.center + arc.radius * get_direction(angle))

def point_S(sector, tparam = None):
    """Point on a circular sector boundary arc."""
    return point_C(Arc(sector.center, sector.radius, sector.angles), tparam)

def point_P(polygon, tparam = None):
    """Point on a polygon boundary.

    ``tparam`` walks the perimeter: the integer part selects the edge
    (vertex ``i`` → vertex ``i+1``) and the fractional part interpolates along
    it; ``tparam=None`` yields the first vertex.

    animageo has no coords→perimeter inverse yet, so a GeoGebra
    ``Point(Polygon)`` is materialised by the parser at its serialized
    coordinates (a fixed point). This creator exists so ``Point(Polygon)``
    dispatches to a valid default position instead of being flagged
    unsupported (which would hard-fail in ``--strict`` mode)."""
    verts = np.asarray(polygon.vertices, dtype=float)
    n = len(verts)
    if n == 0:
        return None
    if tparam is None:
        return Point(verts[0].copy())
    t = float(tparam) % n
    i = int(np.floor(t))
    frac = t - i
    a, b = verts[i], verts[(i + 1) % n]
    return Point(a + frac * (b - a))

def point_L(locus, tparam = None):
    point = locus.point_at(tparam)
    return Point(point) if point is not None else None

def point_F(function, tparam = None):
    """Point on a function graph ``y = f(x)``. ``tparam`` is the x-coordinate."""
    x = 0.0 if tparam is None else float(tparam)
    y = function(x)
    if not np.isfinite(y):
        return None
    return Point([x, float(y)])

def _ggb_path_t(t):
    """GeoGebra ``Point(path, t)``: the number is a normalised path parameter
    clamped to [0, 1] (``PathNormalizer.toParentPathParameter``)."""
    return min(max(_num(t), 0.0), 1.0)


def point_ci(circle, t):
    """``Point(circle, t)``: GeoGebra maps ``t ∈ [0, 1]`` onto the angle
    range [−π, π] measured from the +x axis."""
    angle = -np.pi + 2.0 * np.pi * _ggb_path_t(t)
    return Point(circle.center + circle.radius * get_direction(angle))


def point_si(segment, t):
    """``Point(segment, t)``: ``A + t·(B − A)`` with ``t`` clamped to [0, 1]."""
    return Point(interpolate(segment.endpoints[0], segment.endpoints[1], _ggb_path_t(t)))


def _ggb_inf(t):
    """GeoGebra ``PathNormalizer.infFunction``: (−1, 1) → (−∞, ∞)."""
    return t / (1.0 - abs(t)) if abs(t) < 1.0 else None


def point_Ki(conic, t):
    """``Point(conic, t)`` — the normalised parameter mapped onto the conic in
    GeoGebra's own frame (``Conic.ggb_frame``): a circle/ellipse runs over the
    angle −π … π from the first axis, a hyperbola over its right branch then
    its left one, a parabola over ``(−∞, ∞)``. ``None`` at infinity and on
    degenerate conics."""
    frame = conic.ggb_frame()
    if frame is None:
        return None
    tn = _ggb_path_t(t)
    kind = frame['type']
    if kind in ('circle', 'ellipse'):
        a, b = frame['half_axes']
        angle = -np.pi + 2.0 * np.pi * tn
        u, v = a * np.cos(angle), b * np.sin(angle)
    elif kind == 'hyperbola':
        a, b = frame['half_axes']
        tp = -1.0 + 4.0 * tn                     # right branch (−1, 1), left (1, 3)
        left = tp > 1.0
        s = _ggb_inf(tp - 2.0 if left else tp)
        if s is None:
            return None
        u, v = a * np.cosh(s), b * np.sinh(s)
        if left:
            u = -u
    else:                                        # parabola
        s = _ggb_inf(2.0 * tn - 1.0)
        if s is None:
            return None
        v = frame['p'] * s
        u = v * s / 2.0
    return Point(frame['center'] + u * frame['e0'] + v * frame['e1'])


def point_Fiii(function, t, x_min, x_max):
    """``Point(f, t)`` — GeoGebra maps ``t ∈ [0, 1]`` onto the x-range of the
    view showing the graph (the parser passes the saved view's bounds),
    narrowed to the function's explicit domain."""
    lo, hi = float(x_min), float(x_max)
    if function.explicit_domain is not None:
        lo = max(lo, float(function.explicit_domain[0]))
        hi = min(hi, float(function.explicit_domain[1]))
    tn = _ggb_path_t(t)
    return point_F(function, (1.0 - tn) * lo + tn * hi)


point_Fmii = point_Fiii
point_cm, point_sm, point_Km = point_ci, point_si, point_Ki


def point_K(conic, tparam=None):
    """Point on a conic in its canonical parametrization."""
    if conic.type == ConicType.CIRCLE:
        circle = conic.as_circle()
        if circle is None:
            return None
        center, radius = circle
        t = 0.0 if tparam is None else float(tparam)
        return Point(center + radius * get_direction(t))

    if conic.type == ConicType.ELLIPSE:
        params = conic.as_ellipse()
        if params is None:
            return None
        center = params['center']
        a, b = params['semi_axes']
        rot = params['rotation']
        axis_u = np.array([np.cos(rot), np.sin(rot)])
        axis_v = np.array([-np.sin(rot), np.cos(rot)])
        t = 0.0 if tparam is None else float(tparam)
        return Point(center + a * np.cos(t) * axis_u + b * np.sin(t) * axis_v)

    if conic.type == ConicType.HYPERBOLA:
        params = conic.as_hyperbola()
        if params is None:
            return None
        center = params['center']
        a, b = params['semi_axes']
        rot = params['rotation']
        axis_u = np.array([np.cos(rot), np.sin(rot)])
        axis_v = np.array([-np.sin(rot), np.cos(rot)])
        if tparam is None:
            branch, t = 1.0, 0.0
        elif isinstance(tparam, (tuple, list)):
            branch, t = float(tparam[0]), float(tparam[1])
            branch = 1.0 if branch >= 0 else -1.0
        else:
            branch, t = 1.0, float(tparam)
        return Point(center + branch * (a * np.cosh(t) * axis_u + b * np.sinh(t) * axis_v))

    if conic.type == ConicType.PARABOLA:
        params = conic.as_parabola()
        if params is None:
            return None
        vertex = params['vertex']
        axis = params['axis']
        perp = params['perp']
        p = params['focal_parameter']
        t = 0.0 if tparam is None else float(tparam)
        return Point(vertex + t * perp + (t * t / (4 * p)) * axis)

    if conic.type == ConicType.POINT:
        return conic.as_point()

    return None

def polar_pc(point, circle):
    n = point.coords - circle.center
    if np.isclose(n, 0).all(): return None
    return Line(n, np.dot(n, circle.center) + circle.radius_squared)

# Regular polygons have at most this many vertices: a larger (or not finite) n
# from a file is undefined instead of n points built in memory (1.10.0a2).
MAX_REGULAR_POLYGON_VERTICES = 10000


def polygon_ppi(p1, p2, n):
    if not n <= MAX_REGULAR_POLYGON_VERTICES:
        raise ValueError(f'a regular polygon of {n} vertices (at most {MAX_REGULAR_POLYGON_VERTICES})')
    p1c, p2c = (a_to_cpx(p.coords) for p in (p1, p2))
    alpha = 2 * np.pi / n
    center = p2c + (p1c - p2c) / (1 - np.exp(-alpha * 1j))
    v = p2c - center
    points = [Point(cpx_to_a(center + v * np.exp(i * alpha * 1j))) for i in range(1, int(n) - 1)]
    raw_points = [p.coords for p in [p1, p2] + points]
    segments = [
        Segment(p1, p2)
        for p1, p2 in zip(raw_points, raw_points[1:] + raw_points[:1])
    ]
    return [Polygon(raw_points)] + segments + points

def polygon(*points):
    raw_points = [p.coords for p in points]
    segments = [
        Segment(p1, p2)
        for p1, p2 in zip(raw_points, raw_points[1:] + raw_points[:1])
    ]
    return [Polygon(raw_points)] + segments

def prove_b(x):
    logger.info("Prove: %s", x.value)
    return x

def radius_c(circle):
    return Measure(circle.radius, 1)

def radius_K(conic):
    if conic.type != ConicType.CIRCLE:
        return None
    circle = conic.as_circle()
    if circle is None:
        return None
    return Measure(float(circle[1]), 1)

def area_K(conic):
    if conic.type == ConicType.CIRCLE:
        circle = conic.as_circle()
        return Measure(float(np.pi * circle[1] * circle[1]), 2) if circle else None
    if conic.type == ConicType.ELLIPSE:
        params = conic.as_ellipse()
        if params is None:
            return None
        a, b = params['semi_axes']
        return Measure(float(np.pi * a * b), 2)
    return None

def perimeter_P(polygon):
    vertices = polygon.vertices
    if len(vertices) < 2:
        return Measure(0.0, 1)
    total = 0.0
    for p1, p2 in zip(vertices, np.roll(vertices, -1, axis=0)):
        total += float(np.linalg.norm(p2 - p1))
    return Measure(total, 1)

def circumference_c(circle):
    return Measure(float(2 * np.pi * circle.radius), 1)

def circumference_K(conic):
    if conic.type == ConicType.CIRCLE:
        circle = conic.as_circle()
        return Measure(float(2 * np.pi * circle[1]), 1) if circle else None
    if conic.type == ConicType.ELLIPSE:
        params = conic.as_ellipse()
        if params is None:
            return None
        a, b = params['semi_axes']
        h = ((a - b) ** 2) / ((a + b) ** 2)
        # Ramanujan's second approximation.
        value = np.pi * (a + b) * (1 + 3 * h / (10 + np.sqrt(4 - 3 * h)))
        return Measure(float(value), 1)
    return None

def ray_pp(p1, p2):
    return Ray(p1.coords, p2.coords - p1.coords)

def rotate_pap(point, angle, by_point):
    return Point(by_point.coords + rotate_vec(point.coords - by_point.coords, angle.size))

def rotate_pAp(point, angle_size, by_point):
    return Point(by_point.coords + rotate_vec(point.coords - by_point.coords, angle_size.value))

def rotate_pip(point, angle_value, by_point):
    return Point(by_point.coords + rotate_vec(point.coords - by_point.coords, angle_value))

def rotate_vAp(vec, angle_size, by_point):
    # Both ends turn about the centre (1.8.1; the centre used to be ignored
    # and the vector turned about its own start).
    c = by_point.coords
    return Vector([c + rotate_vec(e - c, angle_size.value) for e in vec.endpoints])

def rotate_vap(vec, angle, by_point):
    return rotate_vAp(vec, AngleSize(angle.value), by_point)

def rotate_lAp(line, angle_size, by_point):
    n_rotated = rotate_vec(line.normal, angle_size.value)
    
    point_on_line = line.normal * line.offset
    point_rotated = by_point.coords + rotate_vec(point_on_line - by_point.coords, angle_size.value)
    c_rotated = np.dot(point_rotated, n_rotated)
    
    return Line(n_rotated, c_rotated)

def segment_pp(p1, p2):
    return Segment(p1.coords, p2.coords)

def segment_pv(p, vec):
    return Segment(p.coords, p.coords + vec.direction)

def semicircle_pp(p1, p2):
    vec = a_to_cpx(p1.coords - p2.coords)
    return Arc(
        (p1.coords + p2.coords) / 2,
        abs(vec) / 2,
        [np.angle(v) for v in (-vec, vec)]
    )

def tangent_pc(point, circle):
    polar = polar_pc(point, circle)
    if polar is None: return None
    intersections = intersect_lc(polar, circle)
    # A point inside the circle has no tangent (GeoGebra: undefined); before
    # 1.8.1 its polar came out as the "tangent". On the circle the polar is
    # the tangent at the point.
    if intersections is None: return None
    if isinstance(intersections, Iterable) and not isinstance(intersections, str) and len(intersections) == 2:
        return [line_pp(point, x) for x in intersections]
    else: return polar

def tangent_pci(point, circle, index):
    res = tangent_pc(point, circle)
    index = int(max(0, index-1))
    
    if not hasattr(res, '__len__'):
        if index == 0: return res
        else: return None
        
    if len(res) > index: return res[len(res) - index - 1]
    else: return None

def touches_cc(c1, c2):
    lens = c1.radius, c2.radius, np.linalg.norm(c1.center-c2.center)
    return Boolean(np.isclose(sum(lens), 2 * max(lens)))

def touches_lc(line, circle):
    return Boolean(
        np.isclose(circle.radius, np.abs(np.dot(line.normal, circle.center) - line.offset) )
    )

def touches_cl(circle, line):
    return touches_lc(line, circle)

def translate_pv(point, vector):
    return Point(point.coords + vector.direction)

def translate_sv(segment, vector):
    return Segment(*(segment.endpoints + vector.direction))

def translate_cv(circle, vector):
    return Circle(circle.center + vector.direction, circle.radius)

def vector_pp(p1, p2):
    return Vector((p1.coords, p2.coords))

def vector_p(p1):
    return Vector(([0, 0], p1.coords))

def vector_ii(x, y):
    return Vector(([0, 0], [x, y]))

def vector_vi(vec, mod):
    # From the start of the vector, along it, of length ``mod`` (1.8.1; the
    # ends used to be scaled from the origin).
    k = mod / np.linalg.norm(vec.direction)
    start = np.array(vec.endpoints[0], dtype=float)
    return Vector([start, start + k * vec.direction])

def vector_v(vec):
    """``Vector(<vector expression>)``: GeoGebra wraps a vector-valued
    expression used as a command input — ``Translate(P, a*u)`` is saved as
    ``Vector[(a * u)]``. The value is the vector itself."""
    return Vector(np.array(vec.endpoints, dtype=float))

# ── GeoGebra public-name aliases ──────────────────────────────────────
#
# GeoGebra XML and manual names are not always identical. The existing
# implementation historically matched XML names such as OrthogonalLine,
# LineBisector, Mirror, CircleSector and CircumcircleArc. These aliases make
# public manual names dispatch to the same stable algorithms.

def perpendicular_line_pl(point, line):
    return orthogonal_line_pl(point, line)

def perpendicular_line_pr(point, ray):
    return orthogonal_line_pr(point, ray)

def perpendicular_line_ps(point, segment):
    return orthogonal_line_ps(point, segment)

def perpendicular_bisector_pp(p1, p2):
    return line_bisector_pp(p1, p2)

def perpendicular_bisector_s(segment):
    return line_bisector_s(segment)

def reflect_cc(circle, by_circle):
    return mirror_cc(circle, by_circle)

def reflect_cl(circle, by_line):
    return mirror_cl(circle, by_line)

def reflect_cp(circle, by_point):
    return mirror_cp(circle, by_point)

def reflect_ll(line, by_line):
    return mirror_ll(line, by_line)

def reflect_lp(line, by_point):
    return mirror_lp(line, by_point)

def reflect_ls(line, by_segment):
    return mirror_ls(line, by_segment)

def reflect_pc(point, by_circle):
    return mirror_pc(point, by_circle)

def reflect_pl(point, by_line):
    return mirror_pl(point, by_line)

def reflect_pp(point, by_point):
    return mirror_pp(point, by_point)

def reflect_ps(point, by_segment):
    return mirror_ps(point, by_segment)

def circular_arc_ppp(p1, p2, p3):
    return circle_arc_ppp(p1, p2, p3)

def circular_sector_ppp(p1, p2, p3):
    return circle_sector_ppp(p1, p2, p3)

def circular_sector_ppA(p1, p2, angle):
    return circle_sector_ppA(p1, p2, angle)

def circular_sector_ppi(p1, p2, value):
    return circle_sector_ppi(p1, p2, value)

def circumcircular_arc_ppp(p1, p2, p3):
    return circumcircle_arc_ppp(p1, p2, p3)

def circumcircular_sector_ppp(p1, p2, p3):
    return circumcircle_sector_ppp(p1, p2, p3)

#--------------------------------------------------------

def abs_i(a):
    return np.abs(a)

def abs_m(m):
    return Measure(np.abs(m.value), m.dimension)

def value_A(ang_size):
    return float(ang_size.value)

def u_sub_i(a):
    return float(-a)

def u_sub_v(vector):
    return Vector(-(vector.endpoints))

def u_sub_p(point):
    return Point(-(point.coords))

def u_sub_a(angle):
    return AngleSize(-angle.size)

def u_sub_A(anglesize):
    return AngleSize(-anglesize.value)

def u_sub_m(m):
    return Measure(-m.value, m.dimension)

def sub_ii(a, b):
    return float(a - b)

def sub_AA(a1, a2):
    return AngleSize(a1.value - a2.value)

def sub_aA(a, A):
    return AngleSize(a.size - A.value)

def sub_Aa(A, a):
    return AngleSize(A.value - a.size)

def sub_vv(v1, v2):
    return Vector(v1.endpoints - v2.endpoints)

def sub_pv(point, vector):
    return Point(point.coords - vector.direction)

def sub_pp(p1, p2):
    return Point(p1.coords - p2.coords)

def sub_mm(m1, m2):
    if m1.dimension != m2.dimension: return None
    return Measure(m1.value - m2.value, m1.dimension)

def sub_ms(m, s):
    if m.dimension != 1: return None
    return Measure(m.value - s.length, 1)

def sub_sm(s, m):
    if m.dimension != 1: return None
    return Measure(s.length - m.value, 1)

def sub_ss(s1, s2):
    return Measure(s1.length - s2.length, 1)

def pow_ii(a, b):
    return float(a ** b)

def pow_mi(m, i):
    if i != 2: return None
    return Measure(m.value ** i, m.dimension*i)

def pow_si(s, i):
    return Measure(s.length ** i, i)

def mult_mi(m, b):
    return float(m.value * b)

def mult_im(a, m):
    return float(a * m.value)

def mult_ii(a, b):
    return float(a * b)

def mult_vi(vector, a):
    return Vector(vector.endpoints * a)

def mult_iv(a, vector):
    return mult_vi(vector, a)

def mult_ip(a, point):
    return Point(point.coords * a)

def mult_pi(point, a):
    return Point(point.coords * a)

def mult_mm(m1, m2):
    return Measure(m1.value * m2.value, m1.dimension + m2.dimension)

def mult_ms(m, s):
    return Measure(m.value * s.length, m.dimension + 1)

def mult_sm(s, m):
    return mult_ms(m,s)

def mult_ss(s1, s2):
    return Measure(s1.length * s2.length, 2)

def mult_iA(i, angle_size):
    return AngleSize(angle_size.value * i)

def mult_Ai(a, i):
    return mult_iA(i, a)

def mult_is(i, s):
    return Measure(i * s.length, 1)

def div_ii(a, b):
    if b == 0: return None
    return float(a / b)

def div_Ai(angle_size, i):
    return AngleSize(angle_size.value / i)

def div_mm(m1, m2):
    if np.isclose(m2.value, 0): return None
    return Measure(m1.value / m2.value, m1.dimension - m2.dimension)

def div_ms(m, s):
    return Measure(m.value / s.length, m.dimension - 1)

def div_mi(m, i):
    if np.isclose(i, 0): return None
    return Measure(m.value / i, m.dimension)

def div_sm(s, m):
    if np.isclose(m.value, 0): return None
    return Measure(s.length / m.value, 1 - m.dimension)

def div_ss(s1, s2):
    return Measure(s1.length / s2.length, 0)

def div_si(s, i):
    if np.isclose(i, 0): return None
    return Measure(s.length / i, 1)

def div_vi(vector, a):
    return Vector(vector.endpoints / a)

def div_pi(point, a):
    return Point(point.coords / a)

def add_ii(a, b):
    return float(a + b)

def add_vv(v1, v2):
    return Vector(v1.endpoints + v2.endpoints)

def add_pv(point, vector):
    return Point(point.coords + vector.direction)

def add_vp(vector, point):
    return add_pv(point, vector)

def add_pp(p1, p2):
    return Point(p1.coords + p2.coords)

def add_mm(m1, m2):
    if m1.dimension != m2.dimension: return None
    return Measure(m1.value + m2.value, m1.dimension)

def add_ms(m, s):
    if m.dimension != 1: return None
    return Measure(m.value + s.length, 1)

def add_mi(m, i):
    if m.dimension != 0: return None
    return Measure(m.value + i, 0)

def add_ss(s1, s2):
    return Measure(s1.length + s2.length, 1)

#--------------------------------------------------------

def cos_i(x): return float(np.cos(x))
def sin_i(x): return float(np.sin(x))
def tan_i(x): return float(np.tan(x))
def ctan_i(x): return float(1 / np.tan(x))
def sqrt_i(x): return float(np.sqrt(x))

#--------------------------------------------------------
# String-argument constructors: enable DSL forms like
#     f = Function("y = x^2 + 1")
#     g = Conic("x^2 + y^2 = 4")
#     h = ImplicitCurve("sin(x) + cos(y) = 0.5")
#     l = Line("y = 2x + 1")
# The `str` type is registered as shortcut 'T', so these dispatch by
# name as usual.

def function_T(expr_str):
    try:
        return Function.from_string(expr_str)
    except ValueError as e:
        logger.warning("Function parse failed for %r: %s", expr_str, e)
        return None


def conic_T(expr_str):
    try:
        return Conic.from_string(expr_str)
    except ValueError as e:
        logger.warning("Conic parse failed for %r: %s", expr_str, e)
        return None


def implicit_curve_T(expr_str):
    try:
        return ImplicitCurve.from_string(expr_str)
    except ValueError as e:
        logger.warning("ImplicitCurve parse failed for %r: %s", expr_str, e)
        return None


def _formula_line(expr_str, parameters=None):
    """Line from its equation (``y = 2x + 1``, ``x = 3``); ``None`` when
    the equation, at the current values, is no line (``0 = 1``, a curve).
    ``ValueError`` when it doesn't parse."""
    conic = Conic.from_string(expr_str, parameters=parameters)
    M = conic.matrix
    if not np.allclose(M[:2, :2], 0.0):
        return None
    normal = np.array([2.0 * M[0, 2], 2.0 * M[1, 2]])
    if np.allclose(normal, 0.0):
        return None
    return Line(normal, -M[2, 2])


def line_T(expr_str):
    try:
        return _formula_line(expr_str)
    except ValueError as e:
        logger.warning("Line parse failed for %r: %s", expr_str, e)
        return None


def function_Tn(expr_str, *params):
    """Function whose formula refers to construction objects: ``f(x) = a x²``,
    ``g(t) = y(A) t``, ``f(t) = g(t) + k`` re-read with the current values on
    every rebuild (see ``geo/formula_params.py``)."""
    try:
        return Function.from_string(
            expr_str, parameters=bind_parameters(expr_str, 'function', params))
    except ValueError as e:
        logger.warning("Function parse failed for %r: %s", expr_str, e)
        return None


def conic_Tn(expr_str, *params):
    try:
        return Conic.from_string(
            expr_str, parameters=bind_parameters(expr_str, 'conic', params))
    except ValueError as e:
        logger.warning("Conic parse failed for %r: %s", expr_str, e)
        return None


def implicit_curve_Tn(expr_str, *params):
    try:
        return ImplicitCurve.from_string(
            expr_str, parameters=bind_parameters(expr_str, 'implicit', params))
    except ValueError as e:
        logger.warning("ImplicitCurve parse failed for %r: %s", expr_str, e)
        return None


def function_value_Fi(function, x):
    """``f(x)`` inside an expression (GeoGebra ``(1, f(1))``). ``None`` where
    the function is undefined, so the dependents become undefined too."""
    try:
        y = float(function(float(x)))
    except (TypeError, ValueError):
        return None
    return y if np.isfinite(y) else None


def function_value_Fm(function, m):
    return function_value_Fi(function, m.value)


def function_value_FA(function, angle_size):
    return function_value_Fi(function, angle_size.value)


def line_Tn(expr_str, *params):
    """Line from an equation that mentions numbers (``g: y = a x + 1``).
    ``None`` when the current values leave no line (``0 = 1``) or a curve."""
    try:
        return _formula_line(
            expr_str, bind_parameters(expr_str, 'line', params))
    except ValueError as e:
        logger.warning("Line parse failed for %r: %s", expr_str, e)
        return None


def locus_pp(dependent_point, mover_point):
    return LocusCurve([dependent_point.coords])


def incircle_ppp(p1, p2, p3):
    """Incircle of the triangle through three points."""
    a = float(np.linalg.norm(p2.coords - p3.coords))
    b = float(np.linalg.norm(p1.coords - p3.coords))
    c = float(np.linalg.norm(p1.coords - p2.coords))
    perimeter = a + b + c
    if np.isclose(perimeter, 0):
        return None
    area2 = abs((p2.coords[0] - p1.coords[0]) * (p3.coords[1] - p1.coords[1])
                - (p2.coords[1] - p1.coords[1]) * (p3.coords[0] - p1.coords[0]))
    if np.isclose(area2, 0):
        return None
    center = (a * p1.coords + b * p2.coords + c * p3.coords) / perimeter
    radius = area2 / perimeter
    return Circle(center, radius)


def isogonal_conjugation_pppp(a, b, c, p):
    """Isogonal conjugate of point ``p`` with respect to triangle ABC.

    Uses barycentric coordinates: if ``p = (x:y:z)``, the isogonal
    conjugate is ``(a²/x : b²/y : c²/z)`` where side lengths are opposite
    the corresponding vertices.
    """
    mat = np.array([
        [a.coords[0], b.coords[0], c.coords[0]],
        [a.coords[1], b.coords[1], c.coords[1]],
        [1.0, 1.0, 1.0],
    ])
    rhs = np.array([p.coords[0], p.coords[1], 1.0])
    try:
        bary = np.linalg.solve(mat, rhs)
    except np.linalg.LinAlgError:
        return None
    if np.any(np.isclose(bary, 0.0)):
        return None
    side_a = float(np.linalg.norm(b.coords - c.coords))
    side_b = float(np.linalg.norm(a.coords - c.coords))
    side_c = float(np.linalg.norm(a.coords - b.coords))
    iso = np.array([side_a * side_a, side_b * side_b, side_c * side_c]) / bary
    denom = float(np.sum(iso))
    if np.isclose(denom, 0.0):
        return None
    coords = (iso[0] * a.coords + iso[1] * b.coords + iso[2] * c.coords) / denom
    return Point(coords)


def _trilinear_scalar(v):
    """Coerce a trilinear ratio to ``float``.

    Ratios usually arrive as literal numbers, but a named number reference
    resolves to a ``Measure`` (or ``AngleSize``) whose value lives on
    ``.value`` — accept both so slider-driven ratios work too.
    """
    return float(getattr(v, 'value', v))


def trilinear_pppiii(a, b, c, x, y, z):
    """Point with trilinear coordinates ``x : y : z`` w.r.t. triangle ABC.

    GeoGebra ``Trilinear(A, B, C, x, y, z)``. Trilinears are converted to
    barycentric weights by scaling each ratio with the length of the side
    opposite the corresponding vertex (``sa = |BC|``, ``sb = |CA|``,
    ``sc = |AB|``), then to Cartesian coordinates::

        P = (sa·x·A + sb·y·B + sc·z·C) / (sa·x + sb·y + sc·z)

    Sanity checks: ``1:1:1`` → incenter; ``1/sa:1/sb:1/sc`` → centroid;
    ``cos A:cos B:cos C`` → circumcenter. Returns ``None`` for a degenerate
    triangle or when the weights sum to zero (the point lies at infinity).
    """
    x = _trilinear_scalar(x)
    y = _trilinear_scalar(y)
    z = _trilinear_scalar(z)
    ca, cb, cc = a.coords, b.coords, c.coords
    area2 = abs((cb[0] - ca[0]) * (cc[1] - ca[1])
                - (cb[1] - ca[1]) * (cc[0] - ca[0]))
    if np.isclose(area2, 0.0):
        return None                       # degenerate (collinear/coincident)
    sa = float(np.linalg.norm(cb - cc))   # side opposite A
    sb = float(np.linalg.norm(cc - ca))   # side opposite B
    sc = float(np.linalg.norm(ca - cb))   # side opposite C
    wa, wb, wc = sa * x, sb * y, sc * z
    denom = wa + wb + wc
    if np.isclose(denom, 0.0):
        return None                       # point at infinity
    return Point((wa * ca + wb * cb + wc * cc) / denom)


# Trilinear ratios may also be named numbers (``Measure``/``AngleSize``) — e.g.
# a slider driving an animation — so the dispatch suffix isn't always ``iii``.
# Register every i/m combination for the three ratio slots, all sharing the
# float implementation above (``_trilinear_scalar`` normalizes each argument).
for _t_sfx in ('iim', 'imi', 'imm', 'mii', 'mim', 'mmi', 'mmm'):
    globals()['trilinear_ppp' + _t_sfx] = trilinear_pppiii
del _t_sfx


# ── Tier A / Tier B GeoGebra commands ────────────────────────────────────
#
# Vector / scalar / point helpers with existing-type results. Semantics
# verified against the GeoGebra manual (AffineRatio/CrossRatio/Direction/
# UnitVector/PerpendicularVector/Conic-6-numbers examples).

def _num(v):
    """Coerce a numeric argument to float (raw number or Measure/AngleSize)."""
    return float(getattr(v, 'value', v))


def _free_vector(d):
    """A free Vector anchored at the origin with direction ``d``."""
    return Vector(([0.0, 0.0], [float(d[0]), float(d[1])]))


def _perp(d):
    """Rotate a 2-vector by −90° (GeoGebra PerpendicularVector convention)."""
    return np.array([d[1], -d[0]], dtype=float)


def _unit(d):
    """Unit vector along ``d``; ``None`` for a zero vector."""
    n = float(np.linalg.norm(d))
    return None if np.isclose(n, 0.0) else np.asarray(d, dtype=float) / n


# ── A1: Slope(Line) ──
def slope_l(line):
    """Slope dy/dx of a line; ``None`` for a vertical line (undefined)."""
    dx, dy = line.direction
    if np.isclose(dx, 0.0):
        return None
    return Measure(float(dy / dx), 0)


# ── A2: Direction(Line/Segment/Ray/Vector) → direction vector ──
def direction_l(line):
    # GeoGebra: direction vector (b, −a) of line a x + b y = c → line.direction.
    return _free_vector(line.direction)


def direction_r(ray):
    return _free_vector(ray.direction)


def direction_v(vec):
    return _free_vector(vec.direction)


def direction_s(seg):
    # Segment direction keeps the segment's length (end − start).
    return _free_vector(seg.end - seg.start)


# ── A3: UnitVector(Vector/Line/Segment/Ray) → unit-length direction ──
def unit_vector_l(line):
    return _free_vector(line.direction)          # line.direction already unit


def unit_vector_r(ray):
    return _free_vector(ray.direction)


def unit_vector_v(vec):
    u = _unit(vec.direction)
    return None if u is None else _free_vector(u)


def unit_vector_s(seg):
    u = _unit(seg.end - seg.start)
    return None if u is None else _free_vector(u)


# ── A4: PerpendicularVector → 90°-rotated direction, magnitude preserved ──
def perpendicular_vector_v(vec):
    return _free_vector(_perp(vec.direction))


def perpendicular_vector_s(seg):
    return _free_vector(_perp(seg.end - seg.start))   # same length as segment


def perpendicular_vector_l(line):
    return _free_vector(line.normal)             # GeoGebra (a, b); unit here


# ── A5: UnitPerpendicularVector → normalized perpendicular ──
def unit_perpendicular_vector_v(vec):
    u = _unit(_perp(vec.direction))
    return None if u is None else _free_vector(u)


def unit_perpendicular_vector_s(seg):
    u = _unit(_perp(seg.end - seg.start))
    return None if u is None else _free_vector(u)


def unit_perpendicular_vector_l(line):
    return _free_vector(line.normal)             # normal already unit


def unit_perpendicular_vector_r(ray):
    return _free_vector(_perp(ray.direction))    # ray.direction already unit


# ── A6: Dot / Cross of two vectors ──
def dot_vv(v1, v2):
    return Measure(float(np.dot(v1.direction, v2.direction)), 0)


def cross_vv(v1, v2):
    d1, d2 = v1.direction, v2.direction
    return Measure(float(d1[0] * d2[1] - d1[1] * d2[0]), 0)


# ── A7: AffineRatio(A, B, C) = (C − A)/(B − A) along the line ──
def affine_ratio_ppp(a, b, c):
    ab = b.coords - a.coords
    denom = float(np.dot(ab, ab))
    if np.isclose(denom, 0.0):
        return None                              # A == B
    return Measure(float(np.dot(c.coords - a.coords, ab) / denom), 0)


# ── A8: CrossRatio(A, B, C, D) = AffineRatio(B,C,D) / AffineRatio(A,C,D) ──
def cross_ratio_pppp(a, b, c, d):
    r1 = affine_ratio_ppp(b, c, d)
    r2 = affine_ratio_ppp(a, c, d)
    if r1 is None or r2 is None or np.isclose(r2.value, 0.0):
        return None
    return Measure(r1.value / r2.value, 0)


# ── A9: Midpoint(Conic) — GeoGebra name for the conic centre ──
midpoint_K = center_K


# ── A10: Conic(6 Numbers) ──
def conic_iiiiii(a, b, c, d, e, f):
    """GeoGebra ``Conic(a, b, c, d, e, f)``:
    ``a x² + d x y + b y² + e x + f y + c = 0``.
    """
    return Conic.from_coeffs(
        a=_num(a),   # x²
        b=_num(d),   # xy
        c=_num(b),   # y²
        d=_num(e),   # x
        e=_num(f),   # y
        f=_num(c),   # constant
    )


# ── A11: Ray(Point, Vector) / Point(Point, Vector) ──
def ray_pv(p, v):
    return Ray(np.asarray(p.coords, dtype=float), v.direction)


def point_pv(p, v):
    return Point(p.coords + v.direction)


# ── B1: ClosestPoint(Path, Point) → nearest point on the path ──
def closest_point_lp(line, p):
    n = line.normal                              # unit normal
    return Point(p.coords - (float(np.dot(p.coords, n)) - line.offset) * n)


def closest_point_sp(seg, p):
    a, b = seg.endpoints
    ab = b - a
    denom = float(np.dot(ab, ab))
    if np.isclose(denom, 0.0):
        return Point(np.array(a, dtype=float))
    t = float(np.dot(p.coords - a, ab) / denom)
    t = max(0.0, min(1.0, t))                    # clamp to the segment
    return Point(a + t * ab)


def closest_point_rp(ray, p):
    a = np.asarray(ray.start, dtype=float)
    d = ray.direction
    denom = float(np.dot(d, d))
    if np.isclose(denom, 0.0):
        return Point(a)
    t = max(0.0, float(np.dot(p.coords - a, d) / denom))   # clamp to t ≥ 0
    return Point(a + t * d)


def closest_point_cp(circle, p):
    c = circle.center
    v = p.coords - c
    nv = float(np.linalg.norm(v))
    if np.isclose(nv, 0.0):
        return Point(c + np.array([circle.radius, 0.0]))   # centre → arbitrary
    return Point(c + circle.radius * v / nv)


# ── B2: Dilate(Object, factor [, center]) — homothety ──
def _dilate_coords(coords, r, center):
    return center + r * (np.asarray(coords, dtype=float) - center)


def dilate_pip(p, r, center):
    return Point(_dilate_coords(p.coords, _num(r), center.coords))


def dilate_pi(p, r):
    return Point(_dilate_coords(p.coords, _num(r), np.zeros(2)))


def dilate_sip(seg, r, center):
    r, c = _num(r), center.coords
    return Segment(_dilate_coords(seg.endpoints[0], r, c),
                   _dilate_coords(seg.endpoints[1], r, c))


def dilate_si(seg, r):
    r = _num(r)
    z = np.zeros(2)
    return Segment(_dilate_coords(seg.endpoints[0], r, z),
                   _dilate_coords(seg.endpoints[1], r, z))


def dilate_cip(circle, r, center):
    r = _num(r)
    if np.isclose(r, 0.0):
        return None                              # collapses to a point
    return Circle(_dilate_coords(circle.center, r, center.coords),
                  abs(r) * circle.radius)


def dilate_ci(circle, r):
    r = _num(r)
    if np.isclose(r, 0.0):
        return None
    return Circle(_dilate_coords(circle.center, r, np.zeros(2)),
                  abs(r) * circle.radius)


def dilate_Pip(poly, r, center):
    r, c = _num(r), center.coords
    return Polygon([_dilate_coords(v, r, c) for v in poly.vertices])


def dilate_Pi(poly, r):
    r = _num(r)
    z = np.zeros(2)
    return Polygon([_dilate_coords(v, r, z) for v in poly.vertices])


def dilate_lip(line, r, center):
    # n·x = d maps to n·x = r·d + (1 − r)(n·center) under x ↦ c + r(x − c).
    r = _num(r)
    n = np.asarray(line.normal, dtype=float)
    return Line(n, r * line.offset + (1.0 - r) * float(np.dot(n, center.coords)))


def dilate_li(line, r):
    r = _num(r)
    n = np.asarray(line.normal, dtype=float)
    return Line(n, r * line.offset)


# A Measure factor (slider-driven dilation) is common; register the ``m``
# variants of every factor slot, delegating to the float implementations.
for _obj in ('p', 's', 'c', 'P', 'l'):
    globals()['dilate_' + _obj + 'm'] = globals()['dilate_' + _obj + 'i']
    globals()['dilate_' + _obj + 'mp'] = globals()['dilate_' + _obj + 'ip']
del _obj


# ── Transformations of formula curves (Conic / Function / ImplicitCurve) ──
# GeoGebra transforms conics and graphs like any other object; with a slider
# as the factor (``Dilate(f, a, O)``) the image follows it on rebuild.

def _copy_curve(curve):
    if isinstance(curve, Function):
        return Function(curve.expr, curve.var, source=curve.source,
                        domain=curve.explicit_domain)
    if isinstance(curve, ImplicitCurve):
        return ImplicitCurve(curve.expr, curve.var_x, curve.var_y,
                             source=curve.source)
    return Conic(curve.matrix.copy())


def _dilate_curve(curve, r, center):
    """Homothety ``p ↦ c + r(p − c)`` of a curve; ``None`` for ``r = 0``
    (the curve collapses to a point)."""
    r = _num(r)
    if np.isclose(r, 0.0):
        return None
    c = np.asarray(center, dtype=float)
    out = _copy_curve(curve)
    out.translate(-c)
    out.scale(r)
    out.translate(c)
    if isinstance(out, Function) and curve.explicit_domain is not None:
        lo, hi = (float(c[0] + r * (v - c[0])) for v in curve.explicit_domain)
        out.explicit_domain = (min(lo, hi), max(lo, hi))
    return out


def _dilate_curve_about(curve, r, center):
    return _dilate_curve(curve, r, center.coords)


def _dilate_curve_origin(curve, r):
    return _dilate_curve(curve, r, np.zeros(2))


def _translate_curve(curve, vector):
    d = np.asarray(vector.direction, dtype=float)
    out = _copy_curve(curve)
    out.translate(d)
    if isinstance(out, Function) and curve.explicit_domain is not None:
        lo, hi = curve.explicit_domain
        out.explicit_domain = (lo + float(d[0]), hi + float(d[0]))
    return out


def _reflect_curve_in_point(curve, point):
    return _dilate_curve(curve, -1.0, point.coords)


for _obj in ('K', 'F', 'I'):
    globals()['dilate_' + _obj + 'ip'] = _dilate_curve_about
    globals()['dilate_' + _obj + 'mp'] = _dilate_curve_about
    globals()['dilate_' + _obj + 'i'] = _dilate_curve_origin
    globals()['dilate_' + _obj + 'm'] = _dilate_curve_origin
    globals()['translate_' + _obj + 'v'] = _translate_curve
    globals()['reflect_' + _obj + 'p'] = _reflect_curve_in_point
del _obj


def _conic_affine(conic, H):
    """Image of ``conic`` under the affine point map ``p ↦ H·p`` (homogeneous
    3×3): ``M' = H⁻ᵀ M H⁻¹``."""
    H_inv = np.linalg.inv(H)
    return Conic(H_inv.T @ conic.matrix @ H_inv)


def _about(center, linear):
    """Homogeneous matrix of ``p ↦ c + L(p − c)``."""
    c = np.asarray(center, dtype=float)
    H = np.eye(3)
    H[:2, :2] = linear
    H[:2, 2] = c - linear @ c
    return H


def _rotation(alpha):
    ca, sa = np.cos(alpha), np.sin(alpha)
    return np.array([[ca, -sa], [sa, ca]])


def reflect_Kl(conic, line):
    """Mirror image of a conic in a line (segment/ray: their carrier line)."""
    n = np.asarray(line.normal, dtype=float)
    return _conic_affine(conic, _about(n * line.offset, np.eye(2) - 2.0 * np.outer(n, n)))


reflect_Ks = reflect_Kl


def rotate_Kip(conic, alpha, center):
    return _conic_affine(conic, _about(center.coords, _rotation(_num(alpha))))


def rotate_KAp(conic, angle_size, center):
    return rotate_Kip(conic, angle_size.value, center)


def rotate_Ki(conic, alpha):
    return _conic_affine(conic, _about(np.zeros(2), _rotation(_num(alpha))))


def rotate_KA(conic, angle_size):
    return rotate_Ki(conic, angle_size.value)


# ── B3: Polar(Line, Conic) → pole point ──
def polar_lK(line, conic):
    """Pole of a line with respect to a conic: ``M⁻¹ · ℓ`` (homogeneous)."""
    ell = np.array([line.normal[0], line.normal[1], -line.offset], dtype=float)
    try:
        pole = np.linalg.solve(conic.matrix, ell)
    except np.linalg.LinAlgError:
        return None                              # degenerate conic
    if np.isclose(pole[2], 0.0):
        return None                              # pole at infinity
    return Point(pole[:2] / pole[2])


def polar_Kl(conic, line):
    return polar_lK(line, conic)


# ── Tier C: Tangent(Line, Conic) / Tangent(Point|x, Function) ────────────

def _adjugate3(m):
    """Classical adjoint (adjugate) of a 3×3 matrix — the dual-conic matrix.

    Defined even when ``m`` is singular (unlike ``det·inv``), keeping the
    tangency test robust for near-degenerate conics.
    """
    cof = np.empty((3, 3))
    for i in range(3):
        for j in range(3):
            minor = np.delete(np.delete(m, i, axis=0), j, axis=1)
            cof[i, j] = ((-1) ** (i + j)) * float(np.linalg.det(minor))
    return cof.T


def tangent_lK(line, conic):
    """Tangent line(s) to a conic parallel to a given line.

    A line ``a x + b y + c = 0`` with the fixed direction ``(a, b)`` of the
    given line is tangent to conic ``M`` iff ``ℓᵀ · adj(M) · ℓ = 0`` — a
    quadratic in ``c``. Returns up to two parallel tangents (a single line, a
    list of two, or ``None`` when that direction admits no real tangent).
    """
    a, b = float(line.normal[0]), float(line.normal[1])
    ms = _adjugate3(conic.matrix)
    qa = ms[2, 2]
    qb = 2.0 * (ms[0, 2] * a + ms[1, 2] * b)
    qc = ms[0, 0] * a * a + ms[1, 1] * b * b + 2.0 * ms[0, 1] * a * b

    if np.isclose(qa, 0.0):
        if np.isclose(qb, 0.0):
            return None                       # no line of this direction is tangent
        cs = [-qc / qb]
    else:
        disc = qb * qb - 4.0 * qa * qc
        if disc < -1e-9:
            return None                       # direction never tangent (e.g. secant-only)
        root = float(np.sqrt(max(disc, 0.0)))
        cs = [(-qb + root) / (2.0 * qa)]
        if not np.isclose(root, 0.0):
            cs.append((-qb - root) / (2.0 * qa))
    lines = [Line(np.array([a, b]), -c) for c in cs]   # a x + b y = −c
    return lines[0] if len(lines) == 1 else lines


def tangent_Kl(conic, line):
    return tangent_lK(line, conic)


def _tangent_function(x0, func):
    """Tangent line to ``y = f(x)`` at ``x = x0`` (through ``(x0, f(x0))``)."""
    import sympy as sp
    y0 = func(x0)
    if y0 is None or not np.isfinite(y0):
        return None                           # x0 outside the domain
    try:
        d_expr = sp.diff(func.expr, func.var)
        d_call = sp.lambdify(func.var, d_expr,
                             modules=['numpy', {'Abs': np.abs}])
        slope = float(d_call(x0))
    except (TypeError, ValueError, ZeroDivisionError, FloatingPointError):
        return None
    if not np.isfinite(slope):
        return None                           # vertical tangent / non-differentiable
    # y = slope·(x − x0) + y0  →  slope·x − y = slope·x0 − y0
    return Line(np.array([slope, -1.0]), slope * x0 - y0)


def tangent_pF(point, func):
    return _tangent_function(float(point.coords[0]), func)


def tangent_iF(x, func):
    return _tangent_function(_num(x), func)


tangent_mF = tangent_iF


def _tangent_lines_point_circle(p, o, r):
    """Tangent lines from point ``p`` to circle (centre ``o``, radius ``r``).

    Returns 0/1/2 ``Line``s depending on whether ``p`` is inside / on /
    outside the circle. The tangent points sit at angle ``±arccos(r/|p−o|)``
    off the ``o→p`` direction; the line's normal is the radial direction there.
    """
    w = np.asarray(p, dtype=float) - o
    dist = float(np.linalg.norm(w))
    if dist < r - 1e-9:
        return []                                   # p strictly inside
    if np.isclose(dist, r):
        n = w / dist                                # p on circle → tangent at p
        return [Line(n, float(np.dot(n, o)) + r)]
    gamma = float(np.arccos(np.clip(r / dist, -1.0, 1.0)))
    base = float(np.arctan2(w[1], w[0]))
    lines = []
    for s in (+1.0, -1.0):
        ang = base + s * gamma
        n = np.array([np.cos(ang), np.sin(ang)])    # radial normal at tangent pt
        lines.append(Line(n, float(np.dot(n, o)) + r))
    return lines


def tangent_cc(c1, c2):
    """Common tangent lines of two circles (up to four).

    External tangents come from the external homothety centre (parallel when
    the radii are equal); internal tangents from the internal centre. Because
    each reduces to tangents-from-a-point, degenerate configurations (nested,
    tangent, overlapping) fall out via the point-in-circle count. Returns a
    single line, a list, or ``None`` (concentric circles / no common tangent).
    """
    o1, r1 = np.asarray(c1.center, dtype=float), float(c1.radius)
    o2, r2 = np.asarray(c2.center, dtype=float), float(c2.radius)
    d_vec = o2 - o1
    d = float(np.linalg.norm(d_vec))
    if np.isclose(d, 0.0):
        return None                                 # concentric

    tangents = []
    # External tangents.
    if np.isclose(r1, r2):
        u = d_vec / d
        n = np.array([u[1], -u[0]])                 # unit normal ⊥ centre line
        base = float(np.dot(n, o1))
        tangents += [Line(n.copy(), base + r1), Line(n.copy(), base - r1)]
    else:
        e_center = (r2 * o1 - r1 * o2) / (r2 - r1)
        tangents += _tangent_lines_point_circle(e_center, o1, r1)
    # Internal tangents (internal homothety centre always exists; r1 + r2 > 0).
    i_center = (r2 * o1 + r1 * o2) / (r1 + r2)
    tangents += _tangent_lines_point_circle(i_center, o1, r1)

    if not tangents:
        return None
    return tangents[0] if len(tangents) == 1 else tangents


# ── Command registry ─────────────────────────────────────────────────────
#
# An explicit dict of ``{dispatch_name: impl}`` built once at module import
# from the functions defined in this module. Before this, ``Command.func``
# did a full ``globals()`` lookup per call — slower and, more importantly,
# gave no place to validate that command names use legal shortcut
# characters. A typo like ``intersect_Kf`` (lowercase f is not a type
# shortcut) previously only surfaced as a silent no-match at runtime.
#
# The registry is also exposed for introspection (stub generators, doc
# tooling, web-service auto-discovery) — see ``list_commands`` below.

def _build_command_registry():
    """Walk module globals, register functions whose name matches the
    dispatch naming convention. Validates shortcut characters against
    ``type_to_shortcut`` values; emits a warning on any mismatch."""
    valid_shortcuts = set(type_to_shortcut.values())
    registry: dict[str, object] = {}
    invalid: list[str] = []

    for name, obj in list(globals().items()):
        if not callable(obj) or name.startswith('_'):
            continue
        # Only functions defined here are commands: the helpers this module
        # star-imports from ``lib_elements`` (``cpx_to_a`` — a complex number
        # to an array) matched the naming convention and became the DSL
        # factory ``CpxTo`` of one angle (kernel spec §15, removed in 1.11.0rc1).
        if getattr(obj, '__module__', None) != __name__:
            continue
        # Special no-suffix case for polygon(p, p, p, ...).
        if name == 'polygon' or name in _VARIADIC_DISPATCH:
            registry[name] = obj
            continue
        if '_' not in name:
            continue
        base, _, suffix = name.rpartition('_')
        if not base or not suffix:
            continue
        # A dispatch name has a snake_case base and a shortcut suffix of
        # single-character type codes.
        if not all(c in valid_shortcuts for c in suffix):
            # Non-dispatch helper (e.g. res_by_index, toObjArray) — skip
            # silently. Track it only if the base looks command-like so
            # a genuine typo in a future addition shows up in logs.
            if re.match(r'^[a-z][a-z0-9_]*$', base) and base not in {
                'res_by_index', 'to_obj_array', 'str_full_command',
                'str_params', 'str_command',
            }:
                invalid.append(name)
            continue
        registry[name] = obj

    if invalid:
        logger.debug(
            "lib_commands: %d function(s) match dispatch shape but use "
            "unregistered shortcut chars (unreachable from Command.func): %s",
            len(invalid), ', '.join(sorted(invalid)[:10]),
        )
    logger.debug("lib_commands: %d commands registered", len(registry))
    return registry


COMMAND_REGISTRY: dict = _build_command_registry()


# ── Signature aliases (1.8.1) ─────────────────────────────────────────────
#
# The dispatcher picks an implementation by the exact types of the inputs,
# so a segment was not a line and a circle was not a conic: no slope of a
# segment, no tangents to a circle parallel to a line, and a circle given by
# its equation (a Conic) missed the commands of circles. When the exact
# signature has no implementation, ``signature_alias`` tries, as GeoGebra
# reads them:
#
# - a segment or a ray as its carrier line, only for the commands below
#   where every line input is a carrier (for ``Mirror``/``Reflect`` only the
#   axis, the last input — the object keeps its type);
# - a circle as a conic;
# - a conic that is a circle as a circle.
#
# Only signatures without an implementation get an alias, so no classic
# result changes. The aliases are not in COMMAND_REGISTRY (stubs and
# ``list_commands`` list the implementations).

_CARRIER_LINE_BASES = frozenset({
    'slope', 'are_parallel', 'are_perpendicular', 'are_concurrent', 'angular_bisector',
    'tangent', 'polar', 'line', 'orthogonal_line', 'perpendicular_line',
})
_AXIS_LINE_BASES = frozenset({'mirror', 'reflect'})


def _circle_as_conic(circle):
    cx, cy = (float(v) for v in circle.center)
    r = float(circle.radius)
    return Conic.from_coeffs(1.0, 0.0, 1.0, -2.0 * cx, -2.0 * cy, cx * cx + cy * cy - r * r)


def _conic_as_circle(conic):
    found = conic.as_circle()
    return None if found is None else Circle(found[0], found[1])


def signature_alias(name, inputs):
    """An implementation of ``name`` for ``inputs`` through the aliases
    above, wrapped to convert the inputs it reads differently; ``None`` when
    no alias has one."""
    import itertools

    command = strCommand(name)
    codes = [type_to_shortcut.get(type(x)) for x in inputs]
    if None in codes or not codes:
        return None
    options = []
    for i, (code, x) in enumerate(zip(codes, inputs)):
        opts = [(code, None)]
        if code in 'sr' and (command in _CARRIER_LINE_BASES
                             or (command in _AXIS_LINE_BASES and i == len(codes) - 1)):
            opts.append(('l', None))
        elif code == 'c':
            opts.append(('K', _circle_as_conic))
        elif code == 'K' and isinstance(x, Conic) and x.as_circle() is not None:
            opts.append(('c', _conic_as_circle))
        options.append(opts)
    for combo in itertools.product(*options):
        if all(c == code for (c, _), code in zip(combo, codes)):
            continue
        impl = COMMAND_REGISTRY.get(f"{command}_{''.join(c for c, _ in combo)}")
        if impl is None:
            continue
        converts = [conv for _, conv in combo]
        if not any(converts):
            return impl

        def aliased(*args, _impl=impl, _converts=converts):
            head = [a if conv is None else conv(a) for a, conv in zip(args, _converts)]
            return _impl(*head, *args[len(_converts):])

        aliased.__name__ = impl.__name__
        return aliased
    return None


def list_commands() -> list[str]:
    """Return sorted list of all dispatchable command names.

    Useful for stub generation, documentation, or web-service integrators
    who need to enumerate the available geometric operations.
    """
    return sorted(COMMAND_REGISTRY.keys())
