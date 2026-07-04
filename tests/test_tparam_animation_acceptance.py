"""Acceptance for docs/archive/TZ-conic-locus-point-keyframe-animation.md §5.

Real construction from https://animageo.ru/shared/tYwHUgEyock: D is a point
on ellipse c; the visible hexagon/triangle geometry derives from A,B,C,D,G.
Before this feature the export froze because D classified as 'unknown' and
its keyframe coords could not be converted to tparam.
"""
import os

import numpy as np
import pytest

from animageo.geo.construction import Construction
from animageo.parsers import ggb_parser

FIXTURE = os.path.join(
    os.path.dirname(__file__), '..', 'examples', '0_sample_scenes',
    'hex_tYwHUgEyock.ggb')

pytestmark = pytest.mark.skipif(
    not os.path.exists(FIXTURE),
    reason='hex_tYwHUgEyock.ggb not present (examples/ is untracked; '
           'fetch via GET https://animageo.ru/api/shared/tYwHUgEyock/ggb)')

# Keyframe D-coordinates from the real TimelineData (TZ §2)
D_TRACK = [[6.54, -1.04], [9.85, -0.38], [11.13, 1.05],
           [9.37, 2.84], [2.45, 0.31], [6.54, -1.04]]


@pytest.fixture()
def constr():
    c = Construction()
    view = {}
    ggb_parser.load(c, view, FIXTURE, debug=False)
    return c


def test_D_classified_as_ellipse(constr):
    info = constr.get_independents()['D']
    assert info['type'] == 'tparam_point'
    assert info['constraint'] == 'ellipse'          # TZ §5.1
    assert info['tparam'] is not None


def test_tparam_from_coords_matches_load_projection(constr):
    d = constr.element('D')
    t = constr.tparam_from_coords('D', list(d.data.coords))
    assert np.isclose(t, d.tparam, atol=1e-9)


def _depends_on(constr, name, target):
    """True if `name` transitively depends on `target` via state['inputs']."""
    seen = set()
    stack = [name]
    while stack:
        cur = stack.pop()
        if cur == target:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        info = constr.state.get(cur)
        if info is None:
            continue
        stack.extend(info['inputs'])
    return False


def test_keyframes_move_D_and_derived_geometry(constr):
    """TZ §5.2/§5.3 (library side): interpolators exist, D moves along the
    ellipse, and derived geometry recomputes."""
    from animageo.keyframes import KeyframeSequence, apply_parsed_value

    kfs = {"keyframes": [
        {"t": i * 1.0, "values": {"D": xy}} for i, xy in enumerate(D_TRACK)
    ]}
    seq = KeyframeSequence.from_json(kfs, constr)

    moving = [iv for iv in seq.intervals if iv.interpolators]
    assert moving, "D must produce interpolators (video was frozen before)"
    interp = moving[0].interpolators[0]
    assert interp.kind == 'tparam_circle'           # ellipse -> cyclic

    # Evaluate mid-interval, apply, rebuild: D and a derived vertex move.
    d_before = constr.element('D').data.coords.copy()
    # Any derived polygon vertex; hexagon vertices L/M/N/O per TZ. Pick the
    # first level>0 Point that is not D/G AND actually depends on D
    # transitively (excludes e.g. E = Center(c), which depends only on
    # A/B/C and is a level>0 Point but does not follow D's motion).
    derived_name = next(
        name for name, st in constr.state.items()
        if st['level'] > 0 and constr.element(name) is not None
        and constr.element(name).data is not None
        and type(constr.element(name).data).__name__ == 'Point'
        and name not in ('D', 'G')
        and _depends_on(constr, name, 'D'))
    derived_before = constr.element(derived_name).data.coords.copy()

    apply_parsed_value(constr, 'D', interp.kind, interp.at(0.5))
    constr.rebuild()

    d_after = constr.element('D').data.coords
    assert not np.allclose(d_before, d_after, atol=1e-6), "D must move"
    assert not np.allclose(
        derived_before, constr.element(derived_name).data.coords, atol=1e-6
    ), f"derived point {derived_name} must follow D"


def test_closed_ellipse_track_wraps_shortest_arc(constr):
    """TZ §5.3: cyclic interpolation on the closed conic — evaluating the
    full track never jumps by more than pi between adjacent samples."""
    from animageo.keyframes import KeyframeSequence
    kfs = {"keyframes": [
        {"t": i * 1.0, "values": {"D": xy}} for i, xy in enumerate(D_TRACK)
    ]}
    seq = KeyframeSequence.from_json(kfs, constr)
    for iv in seq.intervals:
        for interp in iv.interpolators:
            samples = [interp.at(u) for u in np.linspace(0, 1, 21)]
            steps = np.abs(np.diff(samples))
            assert (steps < np.pi).all(), "no >pi jumps: shortest-arc wrap"
