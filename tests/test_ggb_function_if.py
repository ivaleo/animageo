"""``Function(If(...), a, b)`` of a GGB file: the formula is read as text (with
its ``If`` and the numbers it refers to), ``a``, ``b`` are its domain."""
import os

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser
from animageo.keyframes import apply_parsed_value

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'functions_if.ggb')
VIEW = {'ptUnit': 1, 'ptWidth': 640, 'ptHeight': 480, 'ptXZero': 0, 'ptYZero': 0}


def load():
    c = Construction()
    ggb_parser.load(c, VIEW, FIXTURE, debug=False)
    return c


def test_loads_and_follows_the_formula():
    c = load()
    f = c.element('f').data
    assert f.explicit_domain == (-2.0, 2.0)
    # u = a + 1 = 3: u*x left of zero, x + u right of it
    assert f(-1.0) == -3.0
    assert f(-2.0) == -6.0
    assert f(0.0) == 3.0
    assert f(1.5) == 4.5


def test_follows_the_number_it_refers_to():
    c = load()
    apply_parsed_value(c, 'a', 'var', 4)        # u = 5
    c.rebuild()
    f = c.element('f').data
    assert f(-1.0) == -5.0 and f(1.0) == 6.0


def test_point_on_function_is_built():
    c = load()
    assert c.element('P') is not None
    assert tuple(c.element('P').data.coords) == (1.0, 3.0)
