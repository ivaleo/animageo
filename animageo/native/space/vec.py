"""Vectors of space as tuples of three floats (no numpy: the browser kernel
repeats the same formulas operation for operation)."""
from __future__ import annotations

import math

__all__ = ['add', 'sub', 'mul', 'dot', 'cross', 'norm', 'unit', 'lerp', 'centroid', 'dist']


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def dist(a, b):
    return norm(sub(a, b))


def unit(a):
    """``a / |a|``; ``ValueError("zero_vector")`` for the zero vector."""
    length = norm(a)
    if length == 0.0 or not math.isfinite(length):
        raise ValueError('zero_vector')
    return (a[0] / length, a[1] / length, a[2] / length)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def centroid(points):
    """The mean of the points (not the centre of mass of a polygon)."""
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n, sum(p[2] for p in points) / n)
