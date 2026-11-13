"""Kinds of marks: the pure geometry of animageo/mark_shapes.py."""
import math

import pytest

from animageo import mark_shapes as ms
from animageo.mark_shapes import ArcDecor, ParallelDecor


def _value(style):
    return lambda key, default=None: style.get(key, default)


def _radius(pt, vertex=(0.0, 0.0)):
    return math.hypot(pt[0] - vertex[0], pt[1] - vertex[1])


def _angle(pt, vertex=(0.0, 0.0)):
    return math.atan2(pt[1] - vertex[1], pt[0] - vertex[0])


# ── reading the style ────────────────────────────────────────────────────

def test_without_keys_the_arcs_are_plain():
    decor = ms.arc_decor(_value({}))
    assert decor == ArcDecor()
    assert decor.plain and not decor.forces_arcs


@pytest.mark.parametrize('style', [{'arc_style': 'wave'}, {'arc_style': 'dashed'}, {'arc_tick_count': 2},
                                   {'arrow_head': 'end'}])
def test_any_decoration_forces_arcs(style):
    assert ms.arc_decor(_value(style)).forces_arcs


def test_bad_values_fall_back():
    decor = ms.arc_decor(_value({'arc_style': 'zigzag', 'arc_tick_count': 9, 'arrow_head': 1,
                                 'tick_length_px': -1, 'arrow_length_px': 'x'}))
    assert (decor.style, decor.ticks, decor.arrow) == ('solid', 3, 'none')
    assert decor.tick_length_px == ms.TICK_PX[0]
    assert decor.arrow_length_px == ms.ANGLE_ARROW_PX[0]
    assert ms.arc_decor(_value({'arc_tick_count': True})).ticks == 0


def test_tick_defaults_are_given():
    decor = ms.arc_decor(_value({}), tick_length_px=12, tick_shift_px=3)
    assert (decor.tick_length_px, decor.tick_shift_px) == (12, 3)


def test_explicit_dash_only_for_a_dashed_arc():
    assert ms.arc_decor(_value({'stroke_dash_pattern_px': [3, 1]})).dash_px is None
    assert ms.arc_decor(_value({'arc_style': 'dashed', 'stroke_dash_pattern_px': [3, 1]})).dash_px == (3.0, 1.0)


# ── step, overhang ───────────────────────────────────────────────────────

def test_waves_are_spaced_by_two_amplitudes_and_a_gap():
    wave = ArcDecor(style='wave')
    assert ms.arc_step_px(wave, 1.5, 1) == 1.5
    # the board of 13.11: at least 2A + 2 px, never below the spacing of the arcs
    assert ms.arc_step_px(wave, 1.5, 2) == pytest.approx(2 * ms.WAVE_AMPLITUDE_PX + ms.WAVE_GAP_PX) == 4
    assert ms.arc_step_px(wave, 5, 3) == 5
    assert ms.arc_step_px(ArcDecor(style='dashed'), 1.5, 3) == 1.5


def test_several_waves_hold_three_periods_on_the_inner_arc():
    wave = ArcDecor(style='wave')
    assert ms.wave_periods(17, 0.3, 1) == 1                 # one wave: as before
    assert ms.wave_periods(17, 0.3, 2) == 3
    assert ms.wave_periods(60, 1.0, 3) == 10
    # the inner arc grows to three periods of 4 px: r = 12 / Δ
    assert ms.arc_base_px(wave, 10, 4, 3, 0.5) == pytest.approx(24)
    assert ms.arc_base_px(wave, 30, 4, 3, 0.5) == 30
    assert ms.arc_base_px(wave, 10, 4, 1, 0.5) == 10      # one wave is not grown
    marks = ms.angle_marks((0, 0), [(24 + 8) / UNIT, (24 + 4) / UNIT, 24 / UNIT], 0.0, 0.5, False, wave, UNIT)
    assert [arc.periods for arc in marks.arcs] == [3, 3, 3]
    inner = marks.arcs[2]
    assert inner.radius * UNIT * inner.span / inner.periods == pytest.approx(ms.WAVE_MIN_PERIOD_PX)


def test_a_decorated_dashed_arc_has_three_dashes():
    ticked = ArcDecor(style='dashed', ticks=1)
    assert ms.dash_period_px(ticked, 1, 9) == 4               # three dashes at 4 px already
    assert ms.dash_period_px(ticked, 1, 7.6) == pytest.approx(7.6 / 2.5)
    assert ms.dash_period_px(ticked, 1, 6) == ms.ARC_DASH_MIN_PERIOD_PX
    arc = ms.angle_marks((0, 0), [7.6 / UNIT], 0.0, 1.0, False, ticked, UNIT).arcs[0]
    assert (arc.dashes, arc.period_px) == (3, pytest.approx(3.04))
    # too short even at the floor: the radius grows to L = 2.5 · 3
    assert ms.arc_base_px(ticked, 6, 1.5, 1, 1.0) == pytest.approx(7.5)
    assert ms.angle_marks((0, 0), [7.5 / UNIT], 0.0, 1.0, False, ticked, UNIT).arcs[0].dashes == 3


@pytest.mark.parametrize('head, radius', [('end', 13.5), ('both', 15.0)])
def test_a_dashed_arc_with_heads_has_three_dashes_past_them(head, radius):
    decor = ArcDecor(style='dashed', arrow=head)
    assert ms.arc_base_px(decor, 10, 1.5, 1, 1.0) == pytest.approx(radius)
    outer = ms.angle_marks((0, 0), [radius / UNIT], 0.0, 1.0, False, decor, UNIT).arcs[0]
    assert outer.radius * UNIT * outer.span == pytest.approx(7.5)
    assert outer.dashes == 3
    # several arcs: the outer one is the step further out
    assert ms.arc_base_px(decor, 10, 1.5, 2, 1.0) == pytest.approx(max(7.5, radius - 1.5))


def test_a_plain_dashed_arc_keeps_its_dashes():
    plain = ArcDecor(style='dashed')
    assert ms.dash_period_px(plain, 1, 6) == 4
    assert ms.arc_base_px(plain, 6, 1.5, 1, 1.0) == 6
    assert ms.arc_base_px(ArcDecor(style='dashed', ticks=1, dash_px=(2.0, 2.0)), 6, 1.5, 1, 1.0) == 6
    # two plain dashed arcs are fitted to three
    assert ms.arc_base_px(plain, 6, 1.5, 2, 1.0) == pytest.approx(7.5)


def test_overhang():
    assert ms.angle_overhang_px(ArcDecor(), 17, 1.0) == 0
    assert ms.angle_overhang_px(ArcDecor(style='wave'), 17, 1.0) == ms.WAVE_AMPLITUDE_PX
    assert ms.angle_overhang_px(ArcDecor(style='wave', ticks=1), 17, 1.0) == pytest.approx(4.5)
    # a short arc: the head shrinks with the arc and so does its half width
    head = ArcDecor(arrow='end')
    assert ms.angle_overhang_px(head, 17, 1.0) == pytest.approx(2.0)
    short = 17 * 0.2 / 2
    assert ms.angle_overhang_px(head, 17, 0.2) == pytest.approx(4 * short / 6 / 2)
    assert ms.angle_label_overhang_px(head) == 0
    assert ms.angle_label_overhang_px(ArcDecor(style='wave', ticks=2, tick_length_px=4)) == 2


def test_arrow_fit():
    assert ms.arrow_fit(6, 4, 17, math.pi / 2) == (6, 4)
    length, width = ms.arrow_fit(6, 4, 10, 0.5)
    assert length == pytest.approx(2.5) and width == pytest.approx(4 * 2.5 / 6)
    assert ms.arrow_fit(6, 4, 10, 0.5, both=True)[0] == pytest.approx(1.25)
    assert ms.arrow_fit(0, 4, 10, 0.5) == (0.0, 0.0)


# ── arcs ─────────────────────────────────────────────────────────────────

UNIT = 50.0   # px per world unit


def test_wave_samples_period_and_ends():
    r = 17 / UNIT
    span = math.pi / 3
    marks = ms.angle_marks((1, 2), [r], 0.3, span, False, ArcDecor(style='wave'), UNIT)
    arc = marks.arcs[0]
    n = max(1, round(17 * span / ms.WAVE_PERIOD_PX))
    assert arc.periods == n
    assert len(arc.points) == ms.WAVE_SAMPLES * n + 1
    for pt in (arc.points[0], arc.points[-1]):
        assert _radius(pt, (1, 2)) == pytest.approx(r)
    assert _angle(arc.points[0], (1, 2)) == pytest.approx(0.3)
    assert _angle(arc.points[-1], (1, 2)) == pytest.approx(0.3 + span)
    radii = [_radius(p, (1, 2)) * UNIT for p in arc.points]
    assert max(radii) == pytest.approx(17 + ms.WAVE_AMPLITUDE_PX)
    assert min(radii) == pytest.approx(17 - ms.WAVE_AMPLITUDE_PX)


def test_waves_of_several_arcs_are_radial_shifts():
    radii = [20 / UNIT, 16.5 / UNIT, 13 / UNIT]
    marks = ms.angle_marks((0, 0), radii, 0.0, 1.0, False, ArcDecor(style='wave'), UNIT)
    assert len({arc.periods for arc in marks.arcs}) == 1
    outer, inner = marks.arcs[0].points, marks.arcs[2].points
    for a, b in zip(outer, inner):
        assert _angle(a) == pytest.approx(_angle(b))
        assert _radius(a) - _radius(b) == pytest.approx(radii[0] - radii[2])


def test_dashed_arcs_are_fitted_each():
    radii = [20 / UNIT, 18 / UNIT]
    marks = ms.angle_marks((0, 0), radii, 0.0, 1.0, False, ArcDecor(style='dashed'), UNIT)
    for arc, r in zip(marks.arcs, radii):
        length = r * 1.0
        n = arc.dashes
        # n dashes and n − 1 gaps fill the arc with a dash at both ends
        assert n * arc.dash.on + (n - 1) * arc.dash.off == pytest.approx(length)
        assert arc.dash.on / arc.dash.off == pytest.approx(1.0)
    assert marks.arcs[0].dash.on != pytest.approx(marks.arcs[1].dash.on)


def test_explicit_dash_is_drawn_as_it_is():
    decor = ArcDecor(style='dashed', dash_px=(3.0, 1.0))
    arc = ms.angle_marks((0, 0), [0.4], 0.0, 1.0, False, decor, UNIT).arcs[0]
    assert (arc.dash.on * UNIT, arc.dash.off * UNIT) == pytest.approx((3.0, 1.0))
    assert arc.dashes is None


def test_ticks_across_the_arcs():
    radii = [20 / UNIT, 18.5 / UNIT]
    decor = ArcDecor(ticks=2, tick_length_px=9, tick_shift_px=2)
    marks = ms.angle_marks((0, 0), radii, 0.0, 1.0, False, decor, UNIT)
    assert len(marks.ticks) == 2
    step = 2 / 20
    for j, (x1, y1, x2, y2) in enumerate(marks.ticks):
        assert _radius((x1, y1)) * UNIT == pytest.approx(18.5 - 4.5)
        assert _radius((x2, y2)) * UNIT == pytest.approx(20 + 4.5)
        assert _angle((x2, y2)) == pytest.approx(0.5 + step * (-0.5 + j))


def test_ticks_of_a_narrow_angle_stay_inside():
    decor = ArcDecor(ticks=3, tick_length_px=9, tick_shift_px=2)
    span = 0.08
    marks = ms.angle_marks((0, 0), [20 / UNIT], 0.0, span, False, decor, UNIT)
    angles = [_angle(t[2:]) for t in marks.ticks]
    assert angles[1] - angles[0] == pytest.approx(span / 4)
    assert all(0 < a < span for a in angles)


def test_ticks_never_cross_the_vertex():
    decor = ArcDecor(ticks=1, tick_length_px=40)
    (x1, y1, _, _), = ms.angle_marks((0, 0), [0.2], 0.0, 1.0, False, decor, UNIT).ticks
    assert _radius((x1, y1)) == pytest.approx(0.0)


@pytest.mark.parametrize('head,flipped,tip_at_end', [('end', False, True), ('start', False, False),
                                                     ('end', True, False), ('start', True, True)])
def test_arrow_on_the_arc(head, flipped, tip_at_end):
    r = 20 / UNIT
    marks = ms.angle_marks((0, 0), [r, r - 0.03], 0.0, 1.0, flipped, ArcDecor(arrow=head), UNIT)
    (tip,) = marks.tips
    assert marks.heads == [head]
    assert _angle(tip[:2]) == pytest.approx(1.0 if tip_at_end else 0.0)
    alpha = 6 / 20
    base = ((tip[2] + tip[4]) / 2, (tip[3] + tip[5]) / 2)
    assert _radius(base) == pytest.approx(r)
    assert _angle(base) == pytest.approx(1.0 - alpha if tip_at_end else alpha)
    assert math.hypot(tip[2] - tip[4], tip[3] - tip[5]) * UNIT == pytest.approx(4.0)
    outer, inner = marks.arcs
    assert outer.span == pytest.approx(1.0 - alpha)
    assert outer.start == pytest.approx(0.0 if tip_at_end else alpha)
    assert (inner.start, inner.span) == (0.0, 1.0)


def test_both_heads_and_a_short_arc():
    r = 10 / UNIT
    marks = ms.angle_marks((0, 0), [r], 0.0, 0.5, False, ArcDecor(arrow='both'), UNIT)
    assert marks.heads == ['start', 'end']
    alpha = 1.25 / 10
    assert marks.arcs[0].start == pytest.approx(alpha)
    assert marks.arcs[0].span == pytest.approx(0.5 - 2 * alpha)


def test_a_wave_with_a_head_counts_its_periods_on_the_shortened_arc():
    marks = ms.angle_marks((0, 0), [30 / UNIT], 0.0, 1.0, False, ArcDecor(style='wave', arrow='end'), UNIT)
    arc = marks.arcs[0]
    assert arc.periods == max(1, round(30 * (1.0 - 6 / 30) / ms.WAVE_PERIOD_PX))
    assert _angle(arc.points[-1]) == pytest.approx(1.0 - 6 / 30)


def test_degenerate_angle_draws_nothing():
    marks = ms.angle_marks((0, 0), [0.4], 0.0, 0.0, False, ArcDecor(style='wave', ticks=2, arrow='end'), UNIT)
    assert (marks.arcs, marks.ticks, marks.tips) == ([], [], [])
    assert ms.angle_marks((0, 0), [], 0.0, 1.0, False, ArcDecor(ticks=1), UNIT).ticks == []


# ── a segment ────────────────────────────────────────────────────────────

def test_segment_arrow_end():
    a, b, tips = ms.segment_arrow((0, 0), (2, 0), 'end', 11, 7.5, UNIT)
    assert a == [0, 0] and b == pytest.approx([2 - 11 / UNIT, 0])
    (tip,) = tips
    assert tip[:2] == [2, 0]
    assert tip[2:] == pytest.approx([2 - 11 / UNIT, 3.75 / UNIT, 2 - 11 / UNIT, -3.75 / UNIT])


def test_segment_arrow_both_on_a_short_segment():
    a, b, tips = ms.segment_arrow((0, 0), (0.1, 0), 'both', 11, 7.5, UNIT)
    assert a == pytest.approx([0.05, 0]) and b == pytest.approx([0.05, 0])
    assert [t[:2] for t in tips] == [[0, 0], [0.1, 0]]


def test_segment_arrow_none_and_zero():
    assert ms.segment_arrow((0, 0), (1, 0), 'none', 11, 7.5, UNIT) is None
    assert ms.segment_arrow((1, 1), (1, 1), 'end', 11, 7.5, UNIT) is None


def test_segment_arrow_defaults_of_a_vector():
    assert ms.segment_arrow_px(_value({'arrow_head': 'start'})) == ('start', 11.0, 7.5)
    assert ms.segment_arrow_px(_value({'arrow_length_px': 5}), length_px=9) == ('none', 5.0, 7.5)


# ── chevrons ─────────────────────────────────────────────────────────────

def test_parallel_decor():
    assert ms.parallel_decor(_value({})) == ParallelDecor()
    decor = ms.parallel_decor(_value({'parallel_count': 2, 'parallel_direction': 'backward',
                                      'parallel_size_px': 10, 'parallel_shift_px': 4}))
    assert decor == ParallelDecor(2, 10.0, 4.0, 'backward')


def test_one_chevron_is_centred():
    (ch,) = ms.chevrons((1, 1), (1, 0), ParallelDecor(count=1), UNIT)
    s, d = 8 / UNIT, 4 / UNIT
    tip = (1 + d / 2, 1)
    assert ch[2:4] == pytest.approx(list(tip))
    assert ch[:2] == pytest.approx([tip[0] - d, 1 + s / 2])
    assert ch[4:] == pytest.approx([tip[0] - d, 1 - s / 2])
    # the middle of the chevron's extent along the line is the centre
    assert (ch[0] + ch[2]) / 2 == pytest.approx(1)


def test_chevrons_are_spaced_along_the_direction():
    out = ms.chevrons((0, 0), (0, 2), ParallelDecor(count=3, shift_px=3.5), UNIT)
    tips = [c[3] for c in out]
    assert [c[2] for c in out] == pytest.approx([0, 0, 0])
    assert tips[1] - tips[0] == pytest.approx(3.5 / UNIT)
    assert tips[1] == pytest.approx(2 / UNIT)
    assert ms.chevrons((0, 0), (0, 0), ParallelDecor(count=1), UNIT) == []
    assert ms.chevrons((0, 0), (1, 0), ParallelDecor(count=0), UNIT) == []


def test_chevrons_step_past_the_ticks():
    decor = ParallelDecor(count=2)
    assert ms.chevron_center((0, 0), (1, 0), decor, UNIT) == [0, 0]
    c = ms.chevron_center((0, 0), (1, 0), decor, UNIT, tick_count=2, tick_shift_px=2, tick_width_px=1.5)
    t = 2 * 0.5 + 0.75
    assert c == pytest.approx([(t + 4 + (3.5 + 4) / 2) / UNIT, 0])


# ── a hollow point ───────────────────────────────────────────────────────

@pytest.mark.parametrize('shape,ring', [('circle', 1.5), ('square', 1.5 / math.sqrt(2)),
                                        ('diamond', 1.5 / math.sqrt(2)), ('triangle_up', 0.75)])
def test_hollow_point(shape, ring):
    hole = ms.point_hole(shape, 6, 'hollow')
    assert hole.shape == shape
    assert hole.radius_px == pytest.approx(1.5)
    assert hole.ring_px == pytest.approx(ring)


def test_solid_cross_and_plus_have_no_hole():
    assert ms.point_hole('circle', 6, 'solid') is None
    assert ms.point_hole('circle', 6, None) is None
    assert ms.point_hole('cross', 6, 'hollow') is None
    assert ms.point_hole('plus', 6, 'hollow') is None
    assert ms.point_hole('circle', 0, 'hollow') is None


@pytest.mark.parametrize('shape, size, scale, drawn', [
    ('triangle_up', 8, 1, 12.0), ('diamond', 8, 1, 6 * math.sqrt(2)), ('square', 8, 1, 6 * math.sqrt(2)),
    ('circle', 6, 1, 6.0), ('circle', 4, 1, 6.0), ('triangle_up', 8, 2, 8.0), ('triangle_left', 20, 1, 20.0)])
def test_a_hollow_point_is_large_enough_for_its_hole(shape, size, scale, drawn):
    assert ms.hollow_size_px(shape, size, 'hollow', scale) == pytest.approx(drawn)
    hole = ms.point_hole(shape, drawn, 'hollow')
    # the hole holds a disc of 3 output px
    assert 2 * hole.radius_px * ms.HOLLOW_INSCRIBED[shape] * scale >= ms.HOLLOW_MIN_HOLE_PX - 1e-9


def test_solid_and_other_points_keep_their_size():
    assert ms.hollow_size_px('triangle_up', 8, 'solid') == 8
    assert ms.hollow_size_px('cross', 4, 'hollow') == 4
    assert ms.hollow_size_px('circle', None, 'hollow') is None
    assert ms.hollow_size_px('circle', 0, 'hollow') == 0


def test_hole_outline():
    assert ms.hole_outline('circle', (0, 0), 1) == []
    sq = ms.hole_outline('square', (0, 0), math.sqrt(2))
    assert [c for p in sq for c in p] == pytest.approx([-1, -1, 1, -1, 1, 1, -1, 1])
    assert ms.hole_outline('triangle_up', (0, 0), 1)[0] == pytest.approx([0, 1])
    assert ms.hole_outline('triangle_right', (0, 0), 1)[0] == pytest.approx([1, 0])
