"""Type stubs for the ``animageo.dsl`` super-module.

Explicit re-exports (no ``from X import *``) so Pylance/mypy can
resolve every name reliably.
"""

# Proxy types — the ``A: Point`` etc. declarations.
from .parsers.dsl.proxy import (
    Angle as Angle,
    Arc as Arc,
    Boolean as Boolean,
    Circle as Circle,
    CircleSector as CircleSector,
    Conic as Conic,
    ElementProxy as ElementProxy,
    Function as Function,
    ImplicitCurve as ImplicitCurve,
    Line as Line,
    Measure as Measure,
    Point as Point,
    Polygon as Polygon,
    Ray as Ray,
    Segment as Segment,
    Vector as Vector,
)

# Derived commands (produce elements from existing ones).
from .parsers.dsl.namespace import (
    AreCollinear as AreCollinear,
    AreComplementary as AreComplementary,
    AreConcurrent as AreConcurrent,
    AreConcyclic as AreConcyclic,
    AreCongruent as AreCongruent,
    AreEqual as AreEqual,
    AreParallel as AreParallel,
    ArePerpendicular as ArePerpendicular,
    Area as Area,
    AngularBisector as AngularBisector,
    Axes as Axes,
    Center as Center,
    Centroid as Centroid,
    CircleArc as CircleArc,
    CircumcircleArc as CircumcircleArc,
    CircumcircleSector as CircumcircleSector,
    Coefficients as Coefficients,
    ContainedBy as ContainedBy,
    Directrix as Directrix,
    Distance as Distance,
    Eccentricity as Eccentricity,
    Ellipse as Ellipse,
    Equality as Equality,
    Focus as Focus,
    Hyperbola as Hyperbola,
    Intersect as Intersect,
    LineBisector as LineBisector,
    LinearEccentricity as LinearEccentricity,
    MajorAxis as MajorAxis,
    Midpoint as Midpoint,
    MinorAxis as MinorAxis,
    Mirror as Mirror,
    OrthogonalLine as OrthogonalLine,
    Parabola as Parabola,
    Polar as Polar,
    Prove as Prove,
    Radius as Radius,
    Rotate as Rotate,
    Semicircle as Semicircle,
    SemiMajorAxisLength as SemiMajorAxisLength,
    SemiMinorAxisLength as SemiMinorAxisLength,
    Tangent as Tangent,
    Touches as Touches,
    Translate as Translate,
    Value as Value,
    Vertex as Vertex,
)

# Arithmetic lowered into Command form (used via operators on proxies,
# but exposed in case DSL code calls them explicitly).
from .parsers.dsl.namespace import (
    Abs as Abs,
    Add as Add,
    AngleSize as AngleSize,
    Assign as Assign,
    Cos as Cos,
    CpxTo as CpxTo,
    Ctan as Ctan,
    Div as Div,
    Mult as Mult,
    Pow as Pow,
    Sin as Sin,
    Sqrt as Sqrt,
    Sub as Sub,
    Tan as Tan,
    USub as USub,
)

# Helpers and math.
from .parsers.dsl.namespace import (
    TYPE_CHECKING as TYPE_CHECKING,
    acos as acos,
    asin as asin,
    atan as atan,
    atan2 as atan2,
    ceil as ceil,
    cos as cos,
    e as e,
    exp as exp,
    floor as floor,
    hide as hide,
    inf as inf,
    log as log,
    nan as nan,
    pi as pi,
    show as show,
    sin as sin,
    sqrt as sqrt,
    style as style,
    tan as tan,
)

# StyleProxy for ``A.style.stroke = ...`` patterns.
from .style.proxy import StyleProxy as StyleProxy
