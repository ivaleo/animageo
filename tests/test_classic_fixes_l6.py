"""Classic fixes of L6 (§15 of the kernel spec), 1.11.0rc1: ``Equality`` of a
polygon reads the value of its area, the value of a vector in a dynamic text
is its direction, and the helpers ``lib_commands`` imports from
``lib_elements`` (``cpx_to_a``) are no commands — the DSL factory ``CpxTo``
goes, and with it ``Signature`` (``signature_alias``), which the DSL found
the same way. Each one is a line of CHANGELOG «1.8 → 1.11: native»."""
import numpy as np
import pytest

from animageo.geo import lib_commands
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import COMMAND_REGISTRY, Command, equality_PP, equality_Pm
from animageo.geo.lib_elements import Element, Point, Polygon, Text, Vector, format_object_value, resolve_text_string
from animageo.geo.lib_vars import Boolean, Measure, Var


def square(x0, y0, side):
    return Polygon([[x0, y0], [x0 + side, y0], [x0 + side, y0 + side], [x0, y0 + side]])


class TestEqualityOfPolygons:
    """``equality_Pm``/``equality_PP`` read ``.x`` of a ``Measure`` — there is
    no such attribute, so the command was always undefined."""

    def test_polygon_and_its_area(self):
        out = equality_Pm(square(0, 0, 2), Measure(4.0, 2))
        assert isinstance(out, Boolean) and out.value

    def test_polygon_and_another_area(self):
        out = equality_Pm(square(0, 0, 2), Measure(5.0, 2))
        assert isinstance(out, Boolean) and not out.value

    def test_a_length_is_no_area(self):
        assert equality_Pm(square(0, 0, 2), Measure(4.0, 1)) is None

    def test_two_polygons(self):
        assert equality_PP(square(0, 0, 2), square(5, 5, 2)).value
        assert not equality_PP(square(0, 0, 2), square(5, 5, 3)).value

    def test_through_the_construction(self):
        c = Construction(seed=0)
        for name, poly in (('p', square(0, 0, 2)), ('q', square(3, 0, 2)), ('r', square(0, 3, 1))):
            c.add(Element(name, poly))
        c.add(Var('m', Measure(4.0, 2)))
        for cmd in (Command('Equality', ['p', 'q'], ['e1']), Command('Equality', ['p', 'r'], ['e2']),
                    Command('Equality', ['p', 'm'], ['e3'])):
            c.add_and_build(cmd)
        values = {name: c.objectByName(name).data for name in ('e1', 'e2', 'e3')}
        assert all(isinstance(v, Boolean) for v in values.values()), values
        assert (values['e1'].value, values['e2'].value, values['e3'].value) == (True, False, True)


class TestVectorValueInText:
    """``format_object_value`` read ``coords`` of a ``Vector``; a vector has
    ``direction`` — GeoGebra prints its components."""

    def test_components(self):
        v = Vector([[1.0, 2.0], [4.0, 6.5]])
        assert format_object_value(v, 2) == '(3, 4.5)'

    def test_rounding(self):
        v = Vector([[0.0, 0.0], [1 / 3, -2 / 3]])
        assert format_object_value(v, 2) == '(0.33, -0.67)'

    def test_in_a_dynamic_text(self):
        c = Construction(seed=0)
        c.add(Element('v', Vector([[0.0, 0.0], [2.0, -1.0]])))
        text = Text([('str', 'v = '), ('obj', 'v')], position=(0, 0))
        assert resolve_text_string(c, text, 2) == 'v = (2, -1)'


class TestHelpersAreNoCommands:
    """``_build_command_registry`` scanned every global of ``lib_commands``,
    so ``cpx_to_a`` of ``lib_elements`` (a complex number → an array) became
    the command ``CpxTo`` of one angle."""

    def test_cpx_to_a_is_not_registered(self):
        assert 'cpx_to_a' not in COMMAND_REGISTRY

    def test_every_command_is_defined_in_lib_commands(self):
        foreign = sorted(name for name, func in COMMAND_REGISTRY.items()
                         if getattr(func, '__module__', None) != lib_commands.__name__)
        assert foreign == []

    def test_no_dsl_factory(self):
        from animageo.parsers.dsl.namespace import _DISCOVERED_COMMANDS
        assert 'CpxTo' not in _DISCOVERED_COMMANDS and 'Signature' not in _DISCOVERED_COMMANDS
        assert len(_DISCOVERED_COMMANDS) == 99

    @pytest.mark.parametrize('factory', ['CpxTo', 'Signature'])
    def test_the_dsl_does_not_know_it(self, factory):
        # ``Signature`` came from ``signature_alias`` the same way and could
        # never dispatch either
        from animageo.parsers import dsl
        from animageo.parsers.dsl.namespace import _can_dispatch
        assert not _can_dispatch(factory)
        with pytest.raises(NameError, match=factory):
            dsl.run(Construction(seed=0), f'a = {factory}(1)')

    def test_the_helper_itself_still_works(self):
        from animageo.geo.lib_elements import a_to_cpx, cpx_to_a
        assert np.allclose(cpx_to_a(a_to_cpx(np.array([1.5, -2.0]))), [1.5, -2.0])

    def test_the_other_commands_are_unchanged(self):
        assert len(COMMAND_REGISTRY) == 476
        assert {'equality_Pm', 'equality_PP', 'area_P', 'vector_pp', 'polygon'} <= set(COMMAND_REGISTRY)
