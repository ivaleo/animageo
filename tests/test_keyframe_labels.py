"""Tests for keyframe-level label placement plumbing.

Covers the pure plumbing: LabelOffsetInterpolator interpolation,
KeyframeSequence.attach_label_layouts wiring. End-to-end integration with
play_keyframes is exercised manually in examples (it requires the full
manim scene); these tests ensure the in-memory data structures are correct.
"""
import sys
import types
import importlib

# Mirror tests/test_keyframes.py: avoid importing animageo.animageo (manim).
_pkg = types.ModuleType('animageo')
_pkg.__path__ = [__import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'animageo')]
_pkg.__package__ = 'animageo'
sys.modules.setdefault('animageo', _pkg)

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_elements import Point, Element
from animageo.keyframes import (
    KeyframeSequence, LabelOffsetInterpolator,
    _ease_linear, _ease_smooth,
)


def _mini_construction_two_points():
    """Two free points A, B. Valid input for KeyframeSequence.from_json."""
    g = Construction()
    g.add(Element('A', Point([0, 0])))
    g.add(Element('B', Point([1, 0])))
    g.rebuild(full=True)
    return g


class _FakeLabelPlacement:
    """Shape-only stand-in for label_placement.LabelPlacement.

    KeyframeSequence.attach_label_layouts only reads ``.kind``, ``.offset_ggb``,
    and ``.angle_params`` — we don't need the real dataclass here.
    """
    def __init__(self, offset_ggb, kind='static', angle_params=None):
        self.offset_ggb = offset_ggb
        self.kind = kind
        self.angle_params = angle_params


# ── LabelOffsetInterpolator ─────────────────────────────────────────────

class TestLabelOffsetInterpolator:
    def test_linear_midpoint(self):
        li = LabelOffsetInterpolator('A', (0.0, 0.0), (10.0, -4.0), easing=_ease_linear)
        assert np.allclose(li.at(0.0), [0.0, 0.0])
        assert np.allclose(li.at(0.5), [5.0, -2.0])
        assert np.allclose(li.at(1.0), [10.0, -4.0])

    def test_smooth_easing(self):
        li = LabelOffsetInterpolator('A', (0.0, 0.0), (10.0, 0.0), easing=_ease_smooth)
        assert np.allclose(li.at(0.0), [0.0, 0.0])
        assert np.allclose(li.at(1.0), [10.0, 0.0])
        # Smooth is slower than linear at edges
        assert li.at(0.1)[0] < 1.0
        assert li.at(0.9)[0] > 9.0

    def test_accepts_list_and_tuple(self):
        LabelOffsetInterpolator('A', [1.0, 2.0], (3.0, 4.0))
        LabelOffsetInterpolator('A', np.array([1.0, 2.0]), np.array([3.0, 4.0]))


# ── attach_label_layouts ─────────────────────────────────────────────────

class TestAttachLabelLayouts:
    def test_builds_static_interpolators(self):
        """Static label present at both keyframes → one interpolator per interval."""
        g = _mini_construction_two_points()
        data = {
            "keyframes": [
                {"t": 0, "values": {"A": [0, 0], "B": [1, 0]}},
                {"t": 1, "values": {"A": [2, 0], "B": [3, 0]}},
            ]
        }
        seq = KeyframeSequence.from_json(data, g)
        layouts = [
            {'A': _FakeLabelPlacement((0.0, 0.0)), 'B': _FakeLabelPlacement((0.0, 0.0))},
            {'A': _FakeLabelPlacement((5.0, 3.0)), 'B': _FakeLabelPlacement((-4.0, 2.0))},
        ]
        seq.attach_label_layouts(layouts)

        assert len(seq.intervals) == 1
        interval = seq.intervals[0]
        assert len(interval.label_interps) == 2
        by_name = {li.name: li for li in interval.label_interps}
        assert np.allclose(by_name['A'].start_offset, [0.0, 0.0])
        assert np.allclose(by_name['A'].end_offset, [5.0, 3.0])
        assert np.allclose(by_name['B'].end_offset, [-4.0, 2.0])
        assert interval.dynamic_angle_params == {}

    def test_dynamic_angle_skips_offset_interp(self):
        """Dynamic-angle labels get angle_params instead of offset interpolator."""
        g = _mini_construction_two_points()
        data = {
            "keyframes": [
                {"t": 0, "values": {"A": [0, 0]}},
                {"t": 1, "values": {"A": [2, 0]}},
            ]
        }
        seq = KeyframeSequence.from_json(data, g)
        ap_mock = object()  # stand-in for AngleParams
        layouts = [
            {'alpha': _FakeLabelPlacement((0.0, 0.0), kind='dynamic_angle', angle_params=ap_mock)},
            {'alpha': _FakeLabelPlacement((9.0, 9.0), kind='dynamic_angle', angle_params=ap_mock)},
        ]
        seq.attach_label_layouts(layouts)

        interval = seq.intervals[0]
        assert interval.label_interps == []
        assert interval.dynamic_angle_params == {'alpha': ap_mock}

    def test_missing_start_layout_skips_interp(self):
        """Label absent at start keyframe → no interpolator for that interval."""
        g = _mini_construction_two_points()
        data = {
            "keyframes": [
                {"t": 0, "values": {"A": [0, 0]}},
                {"t": 1, "values": {"A": [2, 0]}},
            ]
        }
        seq = KeyframeSequence.from_json(data, g)
        layouts = [
            {},                                           # no labels at kf0
            {'A': _FakeLabelPlacement((5.0, 3.0))},       # A appears at kf1
        ]
        seq.attach_label_layouts(layouts)
        assert seq.intervals[0].label_interps == []

    def test_length_mismatch_raises(self):
        g = _mini_construction_two_points()
        data = {
            "keyframes": [
                {"t": 0, "values": {"A": [0, 0]}},
                {"t": 1, "values": {"A": [2, 0]}},
            ]
        }
        seq = KeyframeSequence.from_json(data, g)
        with pytest.raises(ValueError):
            seq.attach_label_layouts([{}])  # one layout, two keyframes

    def test_easing_propagates_from_keyframe(self):
        """KeyframeInterval.easing_name flows through to LabelOffsetInterpolator."""
        g = _mini_construction_two_points()
        data = {
            "keyframes": [
                {"t": 0, "values": {"A": [0, 0]}},
                {"t": 1, "values": {"A": [1, 0]}, "easing": "linear"},
            ]
        }
        seq = KeyframeSequence.from_json(data, g)
        layouts = [
            {'A': _FakeLabelPlacement((0.0, 0.0))},
            {'A': _FakeLabelPlacement((10.0, 0.0))},
        ]
        seq.attach_label_layouts(layouts)
        li = seq.intervals[0].label_interps[0]
        # Under linear easing, mid is 5.0; under smooth it would be 5.0 too at t=0.5 (both 3*0.25-2*0.125 = 0.5),
        # but linear at t=0.25 = 0.25 whereas smooth at t=0.25 = 3*0.0625-2*0.015625 = 0.15625
        assert np.isclose(li.at(0.25)[0], 2.5)
