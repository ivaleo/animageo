"""The flicker gate of 3D-1 (spec §8): no blinking pieces on degenerate scenes
over the orbit — azimuth step 1°, elevations 0°, 20°, 89.5°, 32 samples on
every line."""
from __future__ import annotations

import pytest

from animageo.native.space import flicker
from animageo.native.space.flicker import ELEVATIONS, degenerate_scenes, flicker_events

SCENES = dict(degenerate_scenes())


def test_ten_degenerate_scenes():
    assert len(SCENES) == 10
    assert ELEVATIONS == (0.0, 20.0, 89.5)


@pytest.mark.parametrize('name', sorted(SCENES))
def test_no_flicker_on_the_orbit(name):
    assert flicker_events(SCENES[name], elevations=ELEVATIONS, step_deg=1.0, samples=32) == []


def test_the_metric_sees_short_pieces_without_the_merge():
    events = flicker_events(SCENES['cube_axes'], elevations=(20.0,), min_piece_px=0.0)
    assert events and {e['kind'] for e in events} == {'short'}


def test_the_metric_sees_a_blink(monkeypatch):
    real = flicker.flat_scene

    def blinking(doc, camera, **kwargs):
        flat = real(doc, camera, **kwargs)
        if camera['azimuthDeg'] == 10 and camera['elevationDeg'] == 20:
            for stroke in flat['strokes']:
                if stroke['id'] == 'K_edge_1':
                    for piece in stroke['pieces']:
                        piece['visibility'] = 'hidden' if piece['visibility'] == 'visible' else 'visible'
        return flat

    monkeypatch.setattr(flicker, 'flat_scene', blinking)
    events = flicker_events(SCENES['cube_axes'], elevations=(20.0,), samples=4)
    assert [(e['kind'], e['id'], e['azimuthDeg']) for e in events] == [('blink', 'K_edge_1', 10.0)] * 4
