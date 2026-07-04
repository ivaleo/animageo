"""Scene-level initial-state behavior for play_keyframes."""

import numpy as np

from animageo.animageo import AnimaGeoScene
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import KeyframeSequence


def _scene_with_offset_saved_state():
    construction = Construction()
    construction.add(Element('A', Point([-4, -1])))
    construction.add(Element('B', Point([4, 0])))
    construction.add(Element('C', Point([0, 2]), visible=False))
    construction.add(Command('Midpoint', ['A', 'B'], ['M']))
    construction.rebuild(full=True)

    scene = AnimaGeoScene()
    scene.geo = construction
    return scene


def test_apply_keyframe_state_moves_scene_to_first_keyframe_before_playback():
    scene = _scene_with_offset_saved_state()
    updated = []
    scene.updateGeoElements = lambda updates=None: updated.append(set(updates or []))

    seq = KeyframeSequence.from_json({
        'keyframes': [
            {
                't': 0,
                'values': {'A': [-2.9689161444180607, 0.26454155243530675]},
                'show': ['C'],
                'hide': ['B'],
            },
            {'t': 1, 'values': {'A': [-2, 1]}},
        ],
    }, scene.geo)

    scene._apply_keyframe_state(seq.keyframes[0], seq.element_info)

    assert np.allclose(scene.geo.element('A').data.coords,
                       [-2.9689161444180607, 0.26454155243530675])
    assert np.allclose(scene.geo.element('M').data.coords,
                       [0.5155419277909696, 0.13227077621765337])
    assert scene.geo.element('B').visible is False
    assert scene.geo.element('C').visible is True
    assert updated
    assert {'A', 'M', 'B', 'C'}.issubset(updated[-1])


def test_keyframe_interval_redraws_interpolated_independent_point():
    scene = _scene_with_offset_saved_state()
    seq = KeyframeSequence.from_json({
        'keyframes': [
            {'t': 0, 'values': {'A': [-2, 0]}},
            {'t': 1, 'values': {'A': [2, 0]}},
        ],
    }, scene.geo)

    updated = []
    added = []

    scene.updateGeoElements = lambda updates=None: updated.append(set(updates or []))
    scene.add = lambda *mobjects: added.extend(mobjects)
    scene.remove = lambda *mobjects: None

    def fake_play(*_args, **_kwargs):
        for mob in list(added):
            for updater in getattr(mob, 'updaters', []):
                updater(mob)

    scene.play = fake_play
    scene._play_keyframe_interval(seq.intervals[0])

    assert updated
    assert {'A', 'M'}.issubset(updated[-1])
