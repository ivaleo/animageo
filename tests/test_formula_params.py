"""Formula-defined curves that depend on construction numbers.

``f(x) = a x²`` must follow ``a``: the curve is a command
``Function("…", a)`` whose implementation re-reads the formula with the
current value on every rebuild (``geo/formula_params.py`` +
``lib_commands.*_Tn``). The DSL factories attach the parameters the same way.
"""
import numpy as np
import pytest

from animageo.geo.construction import Construction, Var
from animageo.geo.formula_params import (
    formula_parameters, parametric_inputs, bind_parameters, mentioned_numbers,
)
from animageo.geo.lib_commands import (
    Command, strFullCommand, COMMAND_REGISTRY,
    function_Tn, conic_Tn, implicit_curve_Tn, line_Tn,
)
from animageo.geo.lib_conic import Conic, ConicType
from animageo.keyframes import apply_parsed_value
from animageo.parsers import dsl


class TestFormulaParameters:
    def test_function_parameters_sorted_without_variable(self):
        assert formula_parameters('f(x) = b*x + a*x**2', 'function') == ['a', 'b']

    def test_conic_and_line_exclude_x_and_y(self):
        assert formula_parameters('y = (a * x**(2))', 'conic') == ['a']
        assert formula_parameters('y = (k * x) + 1', 'line') == ['k']

    def test_implicit(self):
        assert formula_parameters('x**3 + a*y = 1', 'implicit') == ['a']

    def test_no_parameters(self):
        assert formula_parameters('y = x**2', 'function') == []

    def test_called_function_is_a_parameter(self):
        assert formula_parameters('g(x) = f(x) + a', 'function') == ['a', 'f']

    def test_parse_error(self):
        assert formula_parameters('y = (', 'function') is None


class TestParametricInputs:
    def test_all_numeric_vars(self):
        c = Construction(); c.add(Var('a', 1.0))
        assert parametric_inputs(c, 'y = a*x**2', 'function') == ['a']

    def test_unknown_symbol_disables(self):
        c = Construction(); c.add(Var('a', 1.0))
        assert parametric_inputs(c, 'y = a*x**2 + q', 'function') is None

    def test_no_parameters_is_none(self):
        assert parametric_inputs(Construction(), 'y = x', 'function') is None

    def test_bind_parameters_count_mismatch(self):
        with pytest.raises(ValueError):
            bind_parameters('y = a*b*x', 'function', [1.0])

    def test_mentioned_numbers_whole_identifiers(self):
        c = Construction(); c.add(Var('a', 1.0)); c.add(Var('ab', 2.0))
        assert mentioned_numbers(c, 'y = ab*x') == ['ab']


class TestFormulaCommands:
    def test_dispatch_name(self):
        assert strFullCommand('Function', ['y = a*x', 1.0]) == 'function_Tn'
        assert strFullCommand('Line', ['y = a*x', 1.0, 2.0]) == 'line_Tn'
        assert strFullCommand('Function', ['y = x']) == 'function_T'
        for base in ('function', 'conic', 'implicit_curve', 'line'):
            assert f'{base}_Tn' in COMMAND_REGISTRY

    def test_function_Tn_uses_current_values(self):
        f = function_Tn('f(x) = (a * x**(2))', 3.0)
        assert f(2.0) == pytest.approx(12.0)

    def test_conic_Tn(self):
        k = conic_Tn('y = (a * x**(2))', 3.0)
        assert k.type == ConicType.PARABOLA
        assert k.evaluate(1.0, 3.0) == pytest.approx(0.0)

    def test_implicit_curve_Tn(self):
        ic = implicit_curve_Tn('x**3 + a*y = 1', 2.0)
        assert ic(1.0, 0.0) == pytest.approx(0.0)

    def test_line_Tn(self):
        g = line_Tn('y = (a * x) + 1', 2.0)
        for x in (0.0, 1.0):
            assert np.dot(g.normal, [x, 2 * x + 1]) == pytest.approx(g.offset)

    def test_line_Tn_degenerate_returns_none(self):
        assert line_Tn('a*x + a*y = 1', 0.0) is None

    def test_conic_from_string_rejects_unbound_symbol(self):
        with pytest.raises(ValueError):
            Conic.from_string('y = a*x^2')

    def test_command_rebuilds_on_parameter(self):
        c = Construction(); c.add(Var('a', 1.0))
        cmd = Command('Function', ['y = a*x**2', 'a'], ['f'])
        c.add(cmd); c.apply(cmd)
        assert c.element('f').data(2.0) == pytest.approx(4.0)
        apply_parsed_value(c, 'a', 'var', 3.0)
        c.rebuild()
        assert c.element('f').data(2.0) == pytest.approx(12.0)


class TestDslFormulas:
    def test_sugar_function_follows_number(self):
        c = Construction()
        dsl.run(c, "a = 1\nf(x) = a*x^2\n")
        assert c.element('f').data(2.0) == pytest.approx(4.0)
        apply_parsed_value(c, 'a', 'var', 3.0)
        c.rebuild()
        assert c.element('f').data(2.0) == pytest.approx(12.0)

    def test_conic_factory_follows_number(self):
        c = Construction()
        dsl.run(c, 'a = 1\np = Conic("y = a*x^2")\n')
        apply_parsed_value(c, 'a', 'var', 2.0)
        c.rebuild()
        assert c.element('p').data.evaluate(1.0, 2.0) == pytest.approx(0.0)

    def test_function_without_numbers_unchanged(self):
        c = Construction()
        dsl.run(c, "f(x) = x^2\n")
        assert c.commandByElementName('f').inputs == ['y = x^2']

    def test_calling_a_function_proxy(self):
        c = Construction()
        dsl.run(c, "a = 2\nf(x) = a*x^2\nv = f(3)\n")
        assert c.objectByName('v').data == pytest.approx(18.0)
        apply_parsed_value(c, 'a', 'var', 1.0)
        c.rebuild()
        assert c.objectByName('v').data == pytest.approx(9.0)

    def test_calling_a_non_function_raises(self):
        c = Construction()
        with pytest.raises(TypeError):
            dsl.run(c, "A = Point(0, 0)\nv = A(1)\n")
