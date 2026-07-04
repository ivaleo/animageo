"""P1-C (placement half): fill-contrast — penalise placing a label on an opaque
fill whose luminance is close to the label colour. Pure-geometry.
"""
import numpy as np
import pytest

from animageo.label_placement import (
    FILL_CONTRAST_OK,
    LabelCostModel,
    _color_luminance,
    _fill_contrast_penalty,
    _point_in_disk,
    _point_in_polygon,
)

EMPTY = np.empty((0, 2))
SQUARE = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])


class TestColorLuminance:
    def test_white_and_black(self):
        assert _color_luminance("#ffffff") == pytest.approx(1.0)
        assert _color_luminance("#000000") == pytest.approx(0.0)

    def test_three_digit_hex(self):
        assert _color_luminance("#fff") == pytest.approx(1.0)
        assert _color_luminance("#000") == pytest.approx(0.0)

    def test_midtone_between(self):
        lum = _color_luminance("#808080")
        assert 0.4 < lum < 0.6

    def test_unparseable_returns_default(self):
        assert _color_luminance("red", default=0.5) == 0.5
        assert _color_luminance(None, default=0.3) == 0.3
        assert _color_luminance(object(), default=0.7) == 0.7


class TestPointInRegion:
    def test_polygon(self):
        assert _point_in_polygon([0.0, 0.0], SQUARE)
        assert not _point_in_polygon([2.0, 0.0], SQUARE)

    def test_disk(self):
        assert _point_in_disk([0.0, 0.0], np.array([0.0, 0.0]), 1.0)
        assert not _point_in_disk([2.0, 0.0], np.array([0.0, 0.0]), 1.0)


class TestFillContrastPenalty:
    def test_dark_label_on_dark_opaque_fill_is_penalised(self):
        fills = [('poly', SQUARE, 1.0, 0.05)]  # near-black, opaque
        inside = _fill_contrast_penalty([0.0, 0.0], fills, label_lum=0.1)
        outside = _fill_contrast_penalty([5.0, 5.0], fills, label_lum=0.1)
        assert inside == pytest.approx(1.0 * (1.0 - abs(0.05 - 0.1) / FILL_CONTRAST_OK))
        assert inside > 0.8
        assert outside == 0.0

    def test_good_contrast_not_penalised(self):
        fills = [('poly', SQUARE, 1.0, 0.05)]  # dark fill
        # light label on dark fill → luminance gap exceeds FILL_CONTRAST_OK → 0
        assert _fill_contrast_penalty([0.0, 0.0], fills, label_lum=0.95) == 0.0

    def test_opacity_scales_penalty(self):
        opaque = [('poly', SQUARE, 1.0, 0.05)]
        faint = [('poly', SQUARE, 0.2, 0.05)]
        p1 = _fill_contrast_penalty([0.0, 0.0], opaque, 0.1)
        p2 = _fill_contrast_penalty([0.0, 0.0], faint, 0.1)
        assert p2 == pytest.approx(0.2 * p1)

    def test_disk_fill(self):
        fills = [('disk', (np.array([0.0, 0.0]), 1.0), 1.0, 0.0)]
        assert _fill_contrast_penalty([0.0, 0.0], fills, 0.1) > 0
        assert _fill_contrast_penalty([2.0, 0.0], fills, 0.1) == 0.0

    def test_no_label_luminance_is_zero(self):
        fills = [('poly', SQUARE, 1.0, 0.05)]
        assert _fill_contrast_penalty([0.0, 0.0], fills, label_lum=None) == 0.0


class TestCostModelFillTerm:
    def test_fill_term_added_inside_dark_fill(self):
        fills = (('poly', SQUARE, 1.0, 0.05),)
        m = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0, ptUnit=1.0,
                           w_fill=5.0, fills=fills)
        on_fill = m.candidate_cost(np.array([0.0, 0.0]), 0.1, 0.1, [], [], [],
                                   EMPTY, 0, 0, label_luminance=0.1)
        off_fill = m.candidate_cost(np.array([5.0, 5.0]), 0.1, 0.1, [], [], [],
                                    EMPTY, 0, 0, label_luminance=0.1)
        assert on_fill > off_fill
        assert off_fill == pytest.approx(0.0)

    def test_no_luminance_means_no_fill_term(self):
        fills = (('poly', SQUARE, 1.0, 0.05),)
        m = LabelCostModel(weights=(0.0, 10.0, 8.0), padding=0.0, ptUnit=1.0,
                           w_fill=5.0, fills=fills)
        c = m.candidate_cost(np.array([0.0, 0.0]), 0.1, 0.1, [], [], [], EMPTY, 0, 0)
        assert c == pytest.approx(0.0)  # label_luminance defaults None → no term

    def test_max_overlap_free_cost_includes_fill_headroom(self):
        fills = (('poly', SQUARE, 1.0, 0.05),)
        m = LabelCostModel(weights=(1.0, 10.0, 8.0), padding=0.0,
                           w_fill=5.0, fills=fills)
        assert m.max_overlap_free_cost() == pytest.approx(4.0 + 5.0)
