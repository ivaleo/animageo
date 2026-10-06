"""Geometric element classes: Point, Line, Segment, Ray, Angle, Polygon, Circle, Arc, Vector.

Each class stores geometric data and a style dict for rendering configuration.
The Element wrapper associates a name and visibility state with any geometric object.
"""
import re

import numpy as np

from .lib_vars import *
from ..constants import Z_FILL, Z_ANGLE, Z_LINE, Z_STROKE, Z_POINT, Z_LABEL
from ..style.proxy import StyleProxy

#--------------------------------------------------------------------------

class Element:
    # Names on the Element wrapper itself. Anything not in here is
    # considered a forward to ``self.data`` (see __getattr__).
    _OWN_ATTRS = frozenset({
        'name', 'data', 'fixed', 'tparam', 'visible',
        '_visible', '_visible_explicit', '_visible_has_value',
        'style', 'ggb_style', 'ggb_raw',
    })

    def __init__(self, name, data = None, visible = True, fixed = False,
                 tparam = None, update_style = True):
        # ``tparam`` is the curve/locus parameter for a point
        # constrained to lie on a circle/segment/line/ray. For a
        # circle it's the angle in radians; for a segment/line/ray
        # it's a linear parameter ``t`` along the direction.
        self.name = name
        self.data = data
        self.fixed = fixed
        self.tparam = tparam
        self._visible = bool(visible)
        self._visible_explicit = False
        self._visible_has_value = (visible is not True)
        self.style = StyleProxy()
        # Visual style decoded from GeoGebra XML. This is intentionally kept
        # separate from ``style`` so the resolver can enable/disable the GGB
        # import layer without losing diagnostics or confusing parser values
        # with explicit DSL/Python writes.
        self.ggb_style = StyleProxy()
        # Raw GGB values as they appeared in the .ggb XML, before any
        # scaling conversion (populated by ggb_parser when loading a file).
        # Consumed by ImportPolicy to apply user-configured conversion rules.
        self.ggb_raw = {}
        if data is not None and update_style:
            if hasattr(data, 'style'):
                self.style = data.style
                if hasattr(self.style, 'mark_clean'):
                    self.style.mark_clean()

    def __repr__(self):
        return "{}:\t{}".format(self.name, self.data)

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = bool(value)
        self._visible_explicit = True
        self._visible_has_value = True

    def set_visible(self, value, *, explicit=False):
        """Set construction/runtime visibility without treating all sources as style."""
        self._visible = bool(value)
        self._visible_explicit = bool(explicit)
        self._visible_has_value = True

    def __getattr__(self, name):
        """Forward unknown attributes to ``self.data`` (if any).

        This enables the DSL-friendly reads ``elem.x`` (Point),
        ``elem.center`` (Circle), ``elem.length`` (Segment), etc. —
        they resolve against the underlying geometry class's
        ``@property``\\s (see :class:`Point`, :class:`Circle`, …).

        Note: ``__getattr__`` only fires after normal attribute
        lookup has failed, so the wrapper's own attrs
        (:attr:`name`, :attr:`data`, :attr:`style`, …) still win.

        When ``data`` is ``None`` (element exists in the construction
        but its build step failed or hasn't run), attribute access
        raises a specific ``AttributeError`` naming the element and
        hinting at the root cause — much easier to trace than the
        opaque ``AttributeError`` you got before, which looked like
        a missing method on a normal class.
        """
        # Avoid recursion during unpickling or partial init.
        if name.startswith('_') or name in self._OWN_ATTRS:
            raise AttributeError(name)
        data = self.__dict__.get('data')
        if data is None:
            ename = self.__dict__.get('name', '?')
            raise AttributeError(
                f"Element {ename!r} is unbuilt (data=None); cannot read "
                f".{name}. Check the rebuild log / command dispatch "
                f"warnings for errors affecting this element."
            )
        try:
            return getattr(data, name)
        except AttributeError:
            raise AttributeError(
                f"Element {self.__dict__.get('name', '?')!r}: "
                f"{type(data).__name__} has no attribute '{name}'"
            ) from None

    def is_drawable(self):
        from .lib_conic import Conic
        from .lib_function import Function
        from .lib_implicit import ImplicitCurve
        return isinstance(self.data, (Point, Line, Angle, Polygon, Circle, Vector,
                                      LocusCurve, Conic, Function, ImplicitCurve))

    def has_value(self):
        # Late import to avoid the ``lib_vars``↔``lib_elements`` circular
        # import — at module-load time the star-import here sees a
        # half-loaded ``lib_vars``, so ``Measure``/``AngleSize``/``Boolean``
        # are not yet bound in our module globals. By call time the other
        # module has finished loading; re-importing explicitly gives
        # reliable names.
        from .lib_vars import Measure, Boolean, AngleSize
        return isinstance(self.data, (Measure, Boolean, AngleSize, Angle, Segment, Polygon))

    def value(self):
        # See ``has_value`` for the circular-import rationale.
        from .lib_vars import Measure, Boolean, AngleSize
        if isinstance(self.data, (Measure, AngleSize)): return self.data.value
        elif isinstance(self.data, Boolean): return float(self.data.value)
        elif isinstance(self.data, Angle): return self.data.value
        elif isinstance(self.data, Segment): return self.data.length
        elif isinstance(self.data, Polygon): return self.data.area
        else: return None

#--------------------------------------------------------------------------

def interpolate(start, end, alpha):
    return (1-alpha)*start + alpha*end
def a_to_cpx(a):
    return complex(*a)
def cpx_to_a(cpx):
    return np.array((cpx.real, cpx.imag))
def vector_perp_rot(vec):
    return np.array((vec[1], -vec[0]))
def get_direction(alpha = None):
    return cpx_to_a(np.exp((alpha if alpha is not None else np.random.random()) * 1j))
def square_norm(x):
    return np.dot(x,x)
def rotate_vec(vec, alpha):
    return cpx_to_a(np.exp(alpha*1j) * a_to_cpx(vec))

#--------------------------------------------------------------------------

class Point:
    def __init__(self, a):
        self.coords = np.array(a, dtype = float)

        self.style = StyleProxy()

        self.style['label_visible'] = False
        self.style['label_offset_px'] = [0.5, 0]
        self.style['z_index'] = Z_POINT

    # ── Human-friendly scalar accessors ──
    @property
    def x(self): return float(self.coords[0])
    @property
    def y(self): return float(self.coords[1])

    def __repr__(self): return "Point({}, {})".format(self.coords[0], self.coords[1])

    def equivalent(self, other):
        if not isinstance(other, Point): return False
        return np.isclose(self.coords, other.coords).all()

    def translate(self, vec):
        self.coords += vec

    def scale(self, ratio):
        self.coords *= ratio

class Line:
    def __init__(self, n, c):
        self.normal = np.array(n, dtype=float)
        self.offset = float(c)

        if (self.normal != 0).any():
            norm = np.linalg.norm(self.normal)
            if not np.isclose(norm, 1):
                self.normal /= norm
                self.offset /= norm
            self.direction = vector_perp_rot(self.normal)

        self.style = StyleProxy()

        self.style['z_index'] = Z_LINE

    def translate(self, vec):
        self.offset += np.dot(vec, self.normal)
    def scale(self, ratio):
        self.offset *= ratio

    def __repr__(self):
        return "Line(n=({}, {}) c={})".format(self.normal[0], self.normal[1], self.offset)

    def equivalent(self, other):
        if not isinstance(other, Line): return False
        if np.isclose(self.normal, other.normal).all() and np.isclose(self.offset, other.offset):
            return True
        if np.isclose(self.normal, -other.normal).all() and np.isclose(self.offset, -other.offset):
            return True
        return False

    def get_endpoints(self, corners):
        result = [None, None]
        boundaries = list(zip(*corners))
        if np.prod(self.normal) > 0:
            boundaries[1] = boundaries[1][1], boundaries[1][0]

        for coor in (0,1):
            if self.normal[1-coor] == 0: continue
            for i, bound in enumerate(boundaries[coor]):
                p = np.zeros([2])
                p[coor] = bound
                p[1-coor] = (self.offset - bound*self.normal[coor])/self.normal[1-coor]
                if (p[1-coor] - boundaries[1-coor][0]) * (p[1-coor] - boundaries[1-coor][1]) <= 0:
                    result[i] = p

        if result[0] is None or result[1] is None: return None
        else: return result

    def random_point(self, corners):
        endpoints = self.get_endpoints(corners)
        if endpoints is None: return self.normal*self.offset
        return interpolate(endpoints[0], endpoints[1], np.random.random())

    def contains(self, x):
        return np.isclose(np.dot(x,self.normal), self.offset)

class Segment(Line):
    def __init__(self, p1, p2): # [x,y] in Line([a,b],c) <=> xa + yb == c
        # assert((p1 != p2).any())
        normal_vec = vector_perp_rot(p1 - p2)
        c = np.dot(p1, normal_vec)
        super().__init__(normal_vec, c)

        self.endpoints = np.array([p1, p2])
        self.length = np.linalg.norm(p1 - p2)

        self.style['z_index'] = Z_STROKE

    # ── Human-friendly accessors ──
    @property
    def start(self): return self.endpoints[0]
    @property
    def end(self): return self.endpoints[1]

    def translate(self, vec):
        self.offset += np.dot(vec, self.normal)
        self.endpoints += vec

    def scale(self, ratio):
        self.offset *= ratio
        self.endpoints *= ratio

    def __repr__(self):
        return 'Segment({}, {})'.format(self.endpoints[0], self.endpoints[1])

    def get_endpoints(self, corners):
        return self.endpoints

    def contains(self, x):
        if not Line.contains(self, x): return False
        p1, p2 = self.endpoints
        for x in (np.dot(p2-p1, x-p1), np.dot(p1-p2, x-p2)):
            if x < 0 and not np.isclose(x,0): return False
        return True

class Ray(Line):
    def __init__(self, start_point, vec):
        normal_vec = -vector_perp_rot(vec)
        c = np.dot(start_point, normal_vec)
        super().__init__(normal_vec, c)
        self.start = start_point

    def translate(self, vec):
        self.offset += np.dot(vec, self.normal)
        self.start += vec
    def scale(self, ratio):
        self.offset *= ratio
        self.start *= ratio
    def important_points(self):
        return [self.start]

    def __repr__(self):
        return 'Ray({}, ...)'.format(self.start)

    def get_endpoints(self, corners):
        line_endpoints = Line.get_endpoints(self, corners)
        if line_endpoints is None: return None
        pos_endpoints = [
            point
            for point in line_endpoints
            if np.dot(self.direction, point - self.start) > 0
        ]
        if len(pos_endpoints) == 0: return None
        elif len(pos_endpoints) == 1:
            return [self.start, pos_endpoints[0]]
        else: return pos_endpoints

    def contains(self, x):
        if not Line.contains(self, x): return False
        if np.dot(self.direction, x-self.start) >= 0:
            return True
        else:
            return np.isclose(self.start, x).all()

class Angle:
    def __init__(self, p, v1, v2):
        self.vertex = p
        self.size = np.arctan2(v2[1], v2[0]) - np.arctan2(v1[1], v1[0])  # radians

        if self.size < 0:
            self.size += 2*np.pi

        self.start_angle = np.angle(a_to_cpx(v1))
        self.end_angle = self.start_angle + self.size
        self.side1 = v1
        self.side2 = v2
        max_r = min(np.linalg.norm(v1), np.linalg.norm(v2))*0.65
        if self.size > 0.01:
            self.arc_radius = min(max_r, 0.8 / self.size**0.25)
        else:
            self.arc_radius = min(max_r, 0.8 / 0.01**0.25)

        self.style = StyleProxy()

        self.style['fill_opacity'] = 1
        self.style['tick_count'] = 1
        self.style['arc_shift_px'] = 0
        self.style['z_index'] = Z_ANGLE

    # ── Alias accessor ──
    @property
    def value(self): return self.size  # synonym for ``.size``

    def translate(self, vec):
        self.vertex += vec
    def scale(self, ratio):
        self.vertex *= ratio
        self.side1 *= ratio
        self.side2 *= ratio
    def important_points(self):
        return [self.vertex]

    def __repr__(self):
        return "Angle({}°)".format(self.size/np.pi * 180)

    def equivalent(self, other):
        from .lib_vars import AngleSize
        if isinstance(other, Angle): return np.isclose(self.value, other.value)
        if isinstance(other, AngleSize): return np.isclose(self.value, other.value)
        return False

class Polygon:
    def __init__(self, points):
        self.vertices = np.array(points, dtype = float)

        self.style = StyleProxy()

        self.style['stroke_opacity'] = 0
        self.style['z_index'] = Z_FILL

    def __repr__(self):
        return "Polygon(pp=[{}])".format(', '.join([str(p) for p in self.vertices]))

    def translate(self, vec):
        self.vertices += vec

    def scale(self, ratio):
        self.vertices *= ratio

    @property
    def area(self):
        x = self.vertices[:, 0]
        y = self.vertices[:, 1]
        return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2)

class Circle:
    def __init__(self, center, r):
        assert(r > 0)
        self.center = np.array(center)
        self.radius = r

        self.style = StyleProxy()

        self.style['fill_opacity'] = 0
        self.style['z_index'] = Z_LINE

    # ── Derived (no stale-cache risk) ──
    @property
    def radius_squared(self): return self.radius ** 2

    def translate(self, vec):
        self.center += vec

    def scale(self, ratio):
        self.center *= ratio
        self.radius *= ratio

    def __repr__(self):
        return "Circle(c=({}  {}) r={})".format(self.center[0], self.center[1], self.radius)

    def equivalent(self, other):
        if not isinstance(other, Circle): return False
        return np.isclose(self.center, other.center).all() and np.isclose(self.radius, other.radius)

    def contains(self, x):
        return np.isclose(np.linalg.norm(np.array(x) - self.center), self.radius)

class Arc(Circle):
    def __init__(self, center, r, angles):
        super().__init__(center, r)
        self.angles = [a % (2*np.pi) for a in angles]
        if self.angles[0] > self.angles[1]:
            self.angles[1] += 2*np.pi

        self.style['z_index'] = Z_STROKE

    # ── Human-friendly accessors ──
    @property
    def angle_start(self): return self.angles[0]
    @property
    def angle_end(self): return self.angles[1]

    def __repr__(self):
        return "Arc(c=({}  {}) r={} angles={})".format(self.center[0], self.center[1], self.radius, self.angles)

    def important_points(self):
        p1, p2 = [
            self.center + cpx_to_a(self.radius*np.exp(a*1j))
            for a in self.angles
        ]
        return [(p1+p2)/2]

    def contains(self, x):
        if not Circle.contains(self, x): return False
        a1,a2 = self.angles
        if np.isclose(a1, a2):
            return False
        x_angle = np.angle(a_to_cpx(x-self.center)) % (2*np.pi)
        if np.isclose(x_angle, a1 % (2*np.pi)) or np.isclose(x_angle, a2 % (2*np.pi)):
            return True
        if a2 > 2*np.pi and x_angle < a1:
            x_angle += 2*np.pi
        return a1 <= x_angle <= a2

class CircleSector(Circle):
    def __init__(self, center, r, angles):
        super().__init__(center, r)
        self.angles = [a % (2*np.pi) for a in angles]
        if self.angles[0] > self.angles[1]:
            self.angles[1] += 2*np.pi

        self.style['z_index'] = Z_STROKE
        
    def __repr__(self):
        return "CircleSector(c=({}  {}) r={} angles={})".format(self.center[0], self.center[1], self.radius, self.angles)

    def contains(self, x):
        pass

class Vector:
    def __init__(self, end_points):
        self.endpoints = np.array(end_points)
        self.direction = self.endpoints[1] - self.endpoints[0]

        self.style = StyleProxy()

        self.style['z_index'] = Z_STROKE

    # ── Human-friendly accessors ──
    @property
    def start(self): return self.endpoints[0]
    @property
    def end(self): return self.endpoints[1]

    def __repr__(self): return "Vector({}, {})".format(self.endpoints[0], self.endpoints[1])

    def translate(self, vec):
        self.endpoints += vec

    def scale(self, ratio):
        self.endpoints *= ratio
        self.direction *= ratio

    def equivalent(self, other):
        if not isinstance(other, Vector): return False
        return np.isclose(self.direction, other.direction).all()

class LocusCurve:
    """Sampled numeric locus represented as an ordered polyline."""

    def __init__(self, points):
        pts = np.array(points, dtype=float)
        if pts.ndim == 1:
            pts = pts.reshape((-1, 2))
        self.points = pts
        self.style = StyleProxy()
        self.style['z_index'] = Z_LINE

    def __repr__(self):
        return f"LocusCurve(n={len(self.points)})"

    def translate(self, vec):
        self.points += vec

    def scale(self, ratio):
        self.points *= ratio

    def point_at(self, tparam=None):
        if len(self.points) == 0:
            return None
        if len(self.points) == 1:
            return self.points[0]
        t = 0.0 if tparam is None else float(tparam)
        t = min(1.0, max(0.0, t))
        scaled = t * (len(self.points) - 1)
        i = int(np.floor(scaled))
        if i >= len(self.points) - 1:
            return self.points[-1]
        return interpolate(self.points[i], self.points[i + 1], scaled - i)

    def contains(self, x):
        if len(self.points) == 0:
            return False
        x = np.array(x, dtype=float)
        return np.min(np.linalg.norm(self.points - x, axis=1)) < 1e-6

#--------------------------------------------------------------------------
# Free text objects (GeoGebra ``<element type="text">``): static / LaTeX /
# dynamic-value labels placed at a coordinate or anchored to a point.

class Text:
    """A free text object.

    ``segments`` is an ordered list of ``('str', literal)`` and
    ``('obj', element_name)`` parts. ``obj`` parts are resolved against the
    live construction at render time (their displayed value is
    type-dependent — see :func:`format_object_value`), so dynamic texts like
    ``"Area = " + t1`` update as the construction changes.

    Position is either literal ``position`` coords **or** ``anchor_point``
    (the name of a point the text is attached to). ``is_latex`` selects LaTeX
    vs plain rendering; ``serif`` mirrors GeoGebra's font serif flag.
    ``latex_math_mode`` adds GeoGebra's implicit formula mode when importing
    LaTeX text without delimiters. Python-created Text keeps literal LaTeX.
    """

    def __init__(self, segments, position=None, anchor_point=None,
                 is_latex=False, serif=False, *, latex_math_mode=False):
        self.segments = list(segments)
        self.position = None if position is None else np.array(position, dtype=float)
        self.anchor_point = anchor_point
        self.is_latex = bool(is_latex)
        self.serif = bool(serif)
        self.latex_math_mode = bool(latex_math_mode)

        self.style = StyleProxy()
        self.style['z_index'] = Z_LABEL

    def __repr__(self):
        parts = ''.join(
            s if kind == 'str' else '{' + s + '}'
            for kind, s in self.segments
        )
        where = ('@' + self.anchor_point) if self.anchor_point else (
            '@({}, {})'.format(*self.position) if self.position is not None else '')
        return 'Text({!r}{}{})'.format(parts, ' LaTeX' if self.is_latex else '', where)

    def translate(self, vec):
        if self.position is not None:
            self.position = self.position + np.asarray(vec, dtype=float)

    def scale(self, ratio):
        if self.position is not None:
            self.position = self.position * ratio


def format_number(value, decimals):
    """Format a number the GeoGebra way: fixed to ``decimals`` places, then
    trailing zeros (and a bare trailing dot) stripped. ``-0`` collapses to
    ``0``.
    """
    s = '{:.{}f}'.format(float(value), int(decimals))
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s in ('-0', ''):
        s = '0'
    return s


def format_object_value(data, decimals):
    """GeoGebra ``toValueString`` for the object types that appear inside
    dynamic texts: Point → ``(x, y)``, Polygon → area, Segment → length,
    number/Measure → number, AngleSize → ``n°``, Boolean → ``true/false``.
    Unknown types fall back to ``str(data)``.
    """
    from .lib_vars import Measure, AngleSize, Boolean, Var

    if isinstance(data, str):
        return data
    if isinstance(data, bool):
        return 'true' if data else 'false'
    if isinstance(data, Boolean):
        return 'true' if data.value else 'false'
    if isinstance(data, (int, float)):
        return format_number(data, decimals)
    if isinstance(data, AngleSize):
        return format_number(data.value * 180.0 / np.pi, decimals) + '°'
    if isinstance(data, Measure):
        return format_number(data.value, decimals)
    if isinstance(data, Var):
        return format_object_value(data.data, decimals)
    if isinstance(data, Point):
        return '({}, {})'.format(
            format_number(data.coords[0], decimals),
            format_number(data.coords[1], decimals),
        )
    if isinstance(data, Polygon):
        return format_number(data.area, decimals)
    if isinstance(data, Segment):
        length = float(np.linalg.norm(data.endpoints[0] - data.endpoints[1]))
        return format_number(length, decimals)
    if isinstance(data, Vector):
        return '({}, {})'.format(
            format_number(data.coords[0], decimals),
            format_number(data.coords[1], decimals),
        )
    return str(data)


def _resolve_obj_value(construction, name, decimals):
    """Look up ``name`` in the construction and format its current value.
    Returns ``''`` (with a warning) when the object can't be resolved."""
    import logging
    obj = construction.objectByName(name) if construction is not None else None
    if obj is None:
        logging.getLogger(__name__).warning(
            "Text references unknown object '%s'", name)
        return ''
    data = getattr(obj, 'data', obj)
    if data is None:
        return ''
    return format_object_value(data, decimals)


def resolve_text_string(construction, text, decimals):
    """Build the final display string for a :class:`Text` by joining its
    segments; ``obj`` segments are formatted from the live construction."""
    out = []
    for kind, value in text.segments:
        if kind == 'str':
            out.append(value)
        else:
            out.append(_resolve_obj_value(construction, value, decimals))
    return ''.join(out)


def resolve_text_position(construction, text):
    """Resolve a :class:`Text`'s base position (math coords): its literal
    ``position``, or the current coords of its ``anchor_point``. The pixel
    ``labelOffset`` is applied by the renderer/exporter (which own ptUnit)."""
    if text.anchor_point is not None and construction is not None:
        obj = construction.objectByName(text.anchor_point)
        data = getattr(obj, 'data', obj) if obj is not None else None
        if data is not None and hasattr(data, 'coords'):
            return np.array(data.coords[:2], dtype=float)
    if text.position is not None:
        return np.array(text.position[:2], dtype=float)
    return np.array([0.0, 0.0])


_LATEX_TEXT_SPECIALS = {
    '\\': r'\textbackslash{}',
    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
    '_': r'\_', '{': r'\{', '}': r'\}',
    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
}


def latex_escape_text(s):
    """Escape LaTeX-special characters in plain text so it can be compiled as
    ``Tex`` / a TikZ node without breaking (``%``, ``&``, ``_``, ``#``, …)."""
    return ''.join(_LATEX_TEXT_SPECIALS.get(ch, ch) for ch in s)


# Cyrillic in *math* mode is not an error — it is worse. Under T2A the math
# alphabet has no Cyrillic glyphs, so ``$Б$`` compiles cleanly and draws
# **nothing** (``$Б_1$`` showed a lone "1"; a sentence lost the whole ``$…$``
# run). Verified for both the manim path (latex→dvisvgm) and TikZ (pdflatex).
# Text mode has the glyphs. Directly under ``_``/``^`` the wrap is braced too:
# ``A_\text{Б}`` would feed the script the bare ``\text`` token.
_CYRILLIC_RUN_RE = re.compile(r'(?:(?<!\\)([_^]))?([Ѐ-ԯ]+)')
_MATH_SEGMENT_RE = re.compile(r'(\$[^$]*\$)')


def _wrap_cyrillic_runs(math_segment):
    def wrap(m):
        script, run = m.group(1), m.group(2)
        text = r'\text{' + run + '}'
        return script + '{' + text + '}' if script else text
    return _CYRILLIC_RUN_RE.sub(wrap, math_segment)


def textify_cyrillic(s):
    """Typeset Cyrillic *inside math mode* as text: ``$Б$`` → ``$\\text{Б}$``.

    Cyrillic already in text mode is left exactly as it is — it renders fine
    there, and prose must not be chopped into ``\\mbox``es. Shared by the manim
    renderer and the TikZ exporter (JSXGraph renders labels via MathJax, which
    has Cyrillic in math and needs no rewriting).
    """
    parts = _MATH_SEGMENT_RE.split(s)
    return ''.join(_wrap_cyrillic_runs(p) if p.startswith('$') else p
                   for p in parts)


_EXPLICIT_MATH_RE = re.compile(
    r'(?<!\\)(?:\\\\)*(?:\$|\\[([]|\\begin\{'
    r'(?:math|displaymath|equation\*?|align\*?|alignat\*?|flalign\*?|gather\*?|multline\*?)\})'
)


def text_to_display_latex(construction, text, decimals):
    """Resolve a :class:`Text` to a LaTeX-ready display string, shared by the
    manim renderer and exporters. Plain texts are escaped. Imported GeoGebra
    formulas get math delimiters only when no explicit math scope exists;
    already-delimited or mixed LaTeX and Python-created texts pass through.
    Non-breaking spaces collapse to regular spaces.
    Returns ``''`` for empty/blank content."""
    content = resolve_text_string(construction, text, decimals).replace('\xa0', ' ')
    if not content.strip():
        return ''
    if not text.is_latex:
        return latex_escape_text(content)
    if getattr(text, 'latex_math_mode', False) and not _EXPLICIT_MATH_RE.search(content):
        return '$' + content + '$'
    return content


#--------------------------------------------------------------------------
# Re-export: keeps `from ..geo.lib_elements import *` a single entry point.

from .lib_conic import Conic, ConicType  # noqa: E402,F401
from .lib_function import Function  # noqa: E402,F401
from .lib_implicit import ImplicitCurve  # noqa: E402,F401
