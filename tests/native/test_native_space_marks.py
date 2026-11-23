"""Derived marks of space drawings: the sidecar check and the mark classes."""
from __future__ import annotations

import copy
import math

import pytest

from animageo.native import space
from animageo.native.document import as_document
from animageo.native.space.marks import checked_marks, projected_marks
from animageo.native.space.paint_fixtures import decorations_document as construction


def _bundle():
    doc = construction()
    return space.prepare_render(space.flat_scene(doc), doc)


def _guide(bundle, kind):
    return next(g for g in bundle['marks']['guides'] if g['kind'] == kind)


def _reject(bundle, match='invalid space mark geometry'):
    with pytest.raises(ValueError, match=match):
        checked_marks(bundle['marks'], as_document(bundle['document']))


def test_the_prepared_sidecar_passes_its_own_check():
    bundle = _bundle()
    assert checked_marks(bundle['marks'], as_document(bundle['document'])) is not None


@pytest.mark.parametrize('key,value', [
    ('at', ['1', 0.0]), ('at', [True, 0.0]), ('at', [math.nan, 0.0]), ('direction', [None, 1.0]),
    ('direction', [math.inf, 0.0]), ('count', 1.0), ('half', True),
])
def test_ticks_with_non_numbers_are_refused(key, value):
    bundle = _bundle()
    _guide(bundle, 'ticks')[key] = value
    _reject(bundle)


@pytest.mark.parametrize('key,value', [
    ('at', [1e308, 0.0]), ('at', [0.0, -1e12]), ('direction', [1e308, 1e308]), ('direction', [1e6, 0.0]),
])
def test_ticks_far_off_the_sheet_are_refused(key, value):
    bundle = _bundle()
    _guide(bundle, 'ticks')[key] = value
    _reject(bundle)


@pytest.mark.parametrize('key,value', [
    ('foot', [1e300, 0.0, 0.0]), ('foot', [0.0, 1e9, 0.0]), ('reach', [1e300, 1e300]),
    ('foot', ['0', 0.0, 0.0]), ('length', math.nan),
])
def test_right_angles_far_off_the_sheet_are_refused(key, value):
    bundle = _bundle()
    _guide(bundle, 'right_angle')[key] = value
    _reject(bundle)


@pytest.mark.parametrize('plane_id', ['A1', 'nothing', 'l--1--a', 42])
def test_a_carrier_must_be_a_segment_of_the_sheet(plane_id):
    bundle = _bundle()
    _guide(bundle, 'ticks')['planeId'] = plane_id
    _reject(bundle, 'invalid space mark carrier')


def test_a_sheet_without_a_frame_takes_no_marks():
    bundle = _bundle()
    del bundle['document']['viewDefaults']['bounds']
    _reject(bundle, 'invalid space mark sheet')


def test_projection_never_emits_non_finite_strokes():
    # Data that skipped the check (the renderer is called with it directly).
    bundle = _bundle()
    marks = copy.deepcopy(bundle['marks'])
    ticks, right = _guide({'marks': marks}, 'ticks'), _guide({'marks': marks}, 'right_angle')
    ticks['at'], ticks['direction'] = [1.7e308, 0.0], [1e308, 0.0]
    right['foot'] = [1e308, 1e308, 1e308]
    plane = as_document(bundle['document'])
    camera = checked_marks(bundle['marks'], plane)
    from animageo.native.paint import resolve_paint
    from animageo.style.config import StyleConfig
    elements = resolve_paint(plane, None)['elements']
    records = list(projected_marks(marks, camera, 1.0, elements, StyleConfig.load(None)))
    for record in records:
        numbers = [c for line in record.get('lines', ()) for c in line]
        numbers += [c for corner in record.get('corners', ()) for c in corner]
        assert numbers and all(math.isfinite(c) for c in numbers)
    emitted = {(r['kind'], r['source'], r.get('half')) for r in records}
    assert ('ticks', ticks['source'], ticks['half']) not in emitted
    assert ('right_angle', right['source'], None) not in emitted
    assert len(records) == len(marks['guides']) - 2
