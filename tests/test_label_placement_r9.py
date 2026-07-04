"""Round-9 fix: direction-tolerance break.

The nudge loop used to EARLY-BREAK on the first overlap-free spot at base
distance — in ANY direction — so it grabbed a free-but-wrong-direction spot and
never explored a few px out where the PREFERRED direction is free (scene27_3 A
took down-left at base instead of up-left at +8px). With a tight
``direction_tolerance`` the search only stops on a free spot whose direction
penalty is within tolerance; otherwise it keeps nudging (bounded by +10px).
"""
import numpy as np

from animageo.label_placement import (
    LabelInfo,
    LabelCostModel,
    _solve_greedy,
)

EMPTY = np.empty((0, 2))
W = (1.0, 10.0, 8.0)


def _north_label():
    lbl = LabelInfo(name='P', anchor=np.array([0.0, 0.0]),
                    half_w=0.05, half_h=0.05)
    lbl.preferred_dir = 2            # North octant
    lbl.bisector_dir = np.array([0.0, 1.0])
    return lbl


# A short horizontal wall that blocks NORTH at the base distance but is clear a
# few px further out.
BASE = 0.2
WALL = [(np.array([-0.3, BASE]), np.array([0.3, BASE]))]


def _solve(dir_tol):
    m = LabelCostModel(weights=W, padding=0.0, ptUnit=50.0)
    return _solve_greedy([_north_label()], WALL, [], EMPTY, BASE, 0.0, W, 50.0,
                         cost_model=m, dir_tol=dir_tol)[0][1]


class TestDirectionTolerance:
    def test_default_breaks_at_base_wrong_direction(self):
        # No tolerance → first free spot at base wins; North is blocked so the
        # label settles to a diagonal at base, NOT pushed North past the wall.
        c = _solve(None)
        assert c[1] < BASE          # not past the wall (stayed at base distance)

    def test_tight_tolerance_nudges_to_preferred_north(self):
        # Tight tolerance rejects the off-direction side spot and nudges North
        # out until it clears the wall.
        c = _solve(0.5)
        assert c[1] > BASE          # pushed North, past the wall
        assert abs(c[0]) < 0.05     # essentially on the North axis

    def test_tight_beats_default_on_direction(self):
        assert _solve(0.5)[1] > _solve(None)[1]
