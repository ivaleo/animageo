"""Compare generated JSON fixtures across libm implementations.

Only real numbers have a tolerance: 1e-12 absolute or relative, three
orders tighter than the kernel's scalar parity tolerance. Near zero an
absolute tolerance is necessary because cancellation magnifies ULP errors.
Keys, list order, strings, booleans and integer counters remain exact.
This comparison never changes the canonical JSON or the content hash.
"""
import math


def same_fixture(expected, actual):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    if isinstance(expected, int) and isinstance(actual, int):
        return expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return (math.isfinite(expected) and math.isfinite(actual)
                and math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-12))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return (expected.keys() == actual.keys()
                and all(same_fixture(expected[key], actual[key]) for key in expected))
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        return (len(expected) == len(actual)
                and all(same_fixture(e, a) for e, a in zip(expected, actual)))
    return type(expected) is type(actual) and expected == actual
