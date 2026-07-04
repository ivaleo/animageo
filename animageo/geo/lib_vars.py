"""Variable types for geometric constructions: Measure, AngleSize, Boolean."""
from typing import Optional
import numpy as np

from .lib_elements import Angle
from ..style.proxy import StyleProxy

#--------------------------------------------------------------------------

class Var:
    """Named variable in a construction (holds a numeric/angle/boolean value)."""

    def __init__(self, name: str, data=None):
        self.name = name
        self.data = data
        self.style = StyleProxy()

    def __repr__(self):
        return f"{self.name}:\t{self.data}"

#--------------------------------------------------------------------------

class Measure:
    """A dimensioned numeric value (dimension=0: scalar, 1: length, 2: area)."""

    def __init__(self, value: float, dimension: int = 0):
        self.value = value
        self.dimension = dimension

    def __repr__(self):
        return "Measure{}({})".format(self.dimension, self.value)

    def translate(self, vec):
        pass

    def scale(self, ratio: float):
        if self.dimension != 0:
            self.value *= ratio ** self.dimension

    def equivalent(self, other) -> bool:
        if not isinstance(other, Measure): return False
        return np.isclose(self.value, other.value)


class AngleSize:
    """An angle value in radians."""

    def __init__(self, x: float):
        self.value = x

    def __repr__(self):
        return "AngleSize({:.4f}°)".format(self.value * 180 / np.pi)

    def translate(self, vec):
        pass

    def scale(self, ratio: float):
        pass

    def equivalent(self, other) -> bool:
        if isinstance(other, Angle): return np.isclose(self.value, other.value)
        if isinstance(other, AngleSize): return np.isclose(self.value, other.value)
        return False


def AngleSizeFromStr(text: str) -> Optional['AngleSize']:
    """Parse an angle from a degree string like '90°'. Returns None on failure."""
    if text.endswith('°'):
        return AngleSize(float(text[:-1]) * np.pi / 180)
    return None


class Boolean:
    """A boolean value wrapper for geometric proofs."""

    def __init__(self, value: bool):
        self.value = value

    def __repr__(self):
        return "Boolean({})".format(self.value)

    def translate(self, vec):
        pass

    def scale(self, ratio: float):
        pass

    def equivalent(self, other) -> bool:
        if not isinstance(other, Boolean): return False
        return self.value == other.value


def BooleanFromStr(text: str) -> 'Boolean':
    """Parse a boolean from string ('true'/'false')."""
    return Boolean(text.lower() == 'true')
