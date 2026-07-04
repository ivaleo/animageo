"""Regression tests for GeoGebra-style indexed Conic intersections."""
import numpy as np

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_conic import Conic
from animageo.geo.lib_elements import Element, Point


def test_indexed_conic_line_intersection_uses_known_point_order():
    constr = Construction()
    constr.add(Element("K", Conic.from_coeffs(a=1 / 16, c=1 / 9, f=-1), fixed=True))
    constr.add(Element("F", Point([0, -3]), fixed=True))
    constr.add(Element("P", Point([4, -6]), fixed=True))
    constr.add(Command("Line", ["F", "P"], ["g"]))
    constr.add(Command("Intersect", ["K", "g", 2], ["C"]))

    constr.rebuild(full=True)

    f = constr.element("F")
    c = constr.element("C")
    assert f is not None
    assert c is not None
    assert not np.allclose(c.data.coords, f.data.coords)
    assert np.allclose(c.data.coords, [-4, 0], atol=1e-9)
