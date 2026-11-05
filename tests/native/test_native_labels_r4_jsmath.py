"""``Math`` of JavaScript for the R4 port (``animageo/native/labels/_jsmath.py``).

``Math.hypot`` and ``Math.round`` are checked against V8's values;
``atan2``, ``atan``, ``sin``, ``cos`` (fdlibm) against special values and
within an ulp of the platform library.
"""
from __future__ import annotations

import math

import pytest

from animageo.native.labels import _jsmath

# Math.hypot of V8 (Node 25) — several differ from sqrt(x² + y²) and from math.hypot.
HYPOT_V8 = [
    (-0.0799297389098179, 0.10442474562693262, 0.13150395682807892),
    (293.2498604121417, 1.832585954602685, 293.25558648220425),
    (0.16460461754983724, 0.3034872591376375, 0.3452523665054357),
    (0.0014390005296762262, -3.7904421525180707, 3.790442425668586),
    (0.039269621686806165, 0.0299318510389539, 0.04937629890993251),
    (-1.8001053386130736, 0.011137772331620754, 1.8001397945925757),
    (0.02171536987831608, 1548.9015393742586, 1548.9015395264817),
    (123.456, 0.001, 123.45600000405001),
    (3, 4, 5),
    (1e-310, 0, 1e-310),
    (0, 0, 0),
]


@pytest.mark.parametrize(('x', 'y', 'expected'), HYPOT_V8)
def test_hypot_as_v8(x, y, expected):
    assert _jsmath.hypot(x, y) == expected


def test_round_halves_up():
    assert [_jsmath.js_round(v) for v in (-2.5, -0.5, 0.5, 2.5, 0.49999999999999994, -3.5000000000000004)] == [-2, 0, 1, 3, 0, -4]


def test_fdlibm_special_values():
    assert _jsmath.atan2(0.0, -1.0) == math.pi
    assert _jsmath.atan2(-0.0, -1.0) == -math.pi
    assert math.copysign(1, _jsmath.atan2(-0.0, 1.0)) == -1
    assert _jsmath.atan2(1.0, 0.0) == math.pi / 2
    assert _jsmath.atan2(1.0, 1.0) == math.pi / 4
    assert _jsmath.atan2(0.0, 0.0) == 0
    assert _jsmath.cos(0.0) == 1 and _jsmath.sin(0.0) == 0
    assert _jsmath.cos(math.pi) == -1


def test_fdlibm_within_an_ulp_of_the_platform():
    for i in range(-2000, 2001):
        a = i * 0.00731
        pairs = ((_jsmath.sin(a), math.sin(a)), (_jsmath.cos(a), math.cos(a)), (_jsmath.atan(a * 50), math.atan(a * 50)))
        for mine, ref in pairs:
            assert abs(mine - ref) <= 1.01 * math.ulp(ref)
        y = math.sin(i * 0.37) * 10 ** (i % 7 - 3)
        x = math.cos(i * 0.53) * 100
        assert abs(_jsmath.atan2(y, x) - math.atan2(y, x)) <= 1.01 * math.ulp(math.atan2(y, x))
