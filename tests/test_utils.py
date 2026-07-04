"""Tests for shared utilities (geo/utils.py)."""
from animageo.geo.utils import is_number, is_angle_degrees, is_boolean, boolean


class TestIsNumber:
    def test_int(self):
        assert is_number(42)
        assert is_number(0)
        assert is_number(-5)

    def test_float(self):
        assert is_number(3.14)
        assert is_number(-0.001)

    def test_string_numeric(self):
        assert is_number('3.14')
        assert is_number('-2')
        assert is_number('0')

    def test_string_non_numeric(self):
        assert not is_number('abc')
        assert not is_number('')
        assert not is_number('12abc')

    def test_none(self):
        assert not is_number(None)

    def test_list(self):
        assert not is_number([1, 2])


class TestIsAngleDegrees:
    def test_valid(self):
        assert is_angle_degrees('90°')
        assert is_angle_degrees('0°')
        assert is_angle_degrees('180.5°')
        assert is_angle_degrees('-45°')

    def test_invalid(self):
        assert not is_angle_degrees('90')
        assert not is_angle_degrees('abc°')
        assert not is_angle_degrees('')
        assert not is_angle_degrees(None)
        assert not is_angle_degrees(90)

    def test_missing_degree_sign(self):
        assert not is_angle_degrees('90deg')


class TestIsBoolean:
    def test_true(self):
        assert is_boolean('true')
        assert is_boolean('True')
        assert is_boolean('TRUE')

    def test_false(self):
        assert is_boolean('false')
        assert is_boolean('False')

    def test_not_boolean(self):
        assert not is_boolean('yes')
        assert not is_boolean('0')
        assert not is_boolean('')


class TestBoolean:
    def test_true(self):
        assert boolean('true')
        assert boolean('True')

    def test_false(self):
        assert not boolean('false')
        assert not boolean('anything')
