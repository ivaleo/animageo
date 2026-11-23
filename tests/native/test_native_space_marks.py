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


def _classes_document(sizes):
    b = space.SpaceBuilder('classes', camera={'azimuthDeg': -64, 'elevationDeg': 33})
    for k, size in enumerate(sizes, 1):
        b.point(f'A{k}', 0, k * 2, 0)
        b.point(f'B{k}', size, k * 2, 0)
        b.segment(f's{k}', f'A{k}', f'B{k}')
        b.midpoint(f'M{k}', f'A{k}', f'B{k}')
    return b.data()


def test_a_fourth_class_of_equal_segments_is_not_drawn_as_a_third():
    doc = _classes_document([4, 5, 6, 7, 5, 8])
    marks = space.prepare_render(space.flat_scene(doc), doc)['marks']
    counts = {(g['source'], g['half']): g['count'] for g in marks['guides'] if g['kind'] == 'ticks'}
    assert counts == {('op-M1', 1): 1, ('op-M1', 2): 1, ('op-M2', 1): 2, ('op-M2', 2): 2,
                      ('op-M3', 1): 3, ('op-M3', 2): 3, ('op-M5', 1): 2, ('op-M5', 2): 2}
    assert marks['diagnostics'] == [{'code': 'mark_classes_exhausted', 'source': 'op-M4'},
                                    {'code': 'mark_classes_exhausted', 'source': 'op-M6'}]
    assert {m['source'] for m in space.resolve_paint(doc)['marks']} == {'op-M1', 'op-M2', 'op-M3', 'op-M5'}


def test_three_classes_raise_no_diagnostic():
    doc = _classes_document([4, 5, 6, 4])
    marks = space.prepare_render(space.flat_scene(doc), doc)['marks']
    assert marks['diagnostics'] == []
    assert len(marks['guides']) == 8


def test_the_check_reads_diagnostics_and_older_sidecars():
    bundle = _bundle()
    plane = as_document(bundle['document'])
    old = {k: v for k, v in bundle['marks'].items() if k != 'diagnostics'}
    assert checked_marks(old, plane) is not None
    for bad in ([{'code': 'mark_classes_exhausted'}], [{'code': 'other', 'source': 'op-M1'}],
                [{'code': 'mark_classes_exhausted', 'source': 1}], {'code': 'mark_classes_exhausted'}):
        with pytest.raises(ValueError, match='invalid space mark sidecar'):
            checked_marks({**bundle['marks'], 'diagnostics': bad}, plane)


@pytest.mark.manim
def test_the_render_report_carries_the_mark_diagnostics(tmp_path):
    pytest.importorskip('manim')
    from animageo.native import render
    doc = _classes_document([4, 5, 6, 7])
    result = render(doc, out=tmp_path / 'classes.svg')
    assert result.report['spaceMarkDiagnostics'] == [{'code': 'mark_classes_exhausted', 'source': 'op-M4'}]
    assert {m['source'] for m in result.report['spaceMarks']} == {'op-M1', 'op-M2', 'op-M3'}


def _perpendicular_document(shift, distance, projection):
    camera = {'projection': projection, 'azimuthDeg': -64, 'elevationDeg': 33, 'target': [shift] * 3}
    if projection == 'perspective':
        camera['distance'] = 20
    b = space.SpaceBuilder('square', camera=camera)
    b.point('A', shift, shift + 0.3, shift + 0.1)
    b.point('B', shift + 4.7, shift + 1.1, shift - 0.2)
    b.point('P', shift + 2.1, shift + 0.7, shift + distance)
    b.segment('s', 'A', 'B')
    b.line('l', 'A', 'B')
    b.perpendicular_line('q', 'P', 'l')
    return b.data()


@pytest.mark.parametrize('projection', ['orthographic', 'perspective'])
@pytest.mark.parametrize('distance', [3, 0.3])
@pytest.mark.parametrize('shift', [0, 1e7, 1e8])
def test_a_right_angle_survives_a_far_scene(shift, distance, projection):
    doc = _perpendicular_document(shift, distance, projection)
    bundle = space.prepare_render(space.flat_scene(doc), doc)
    right = [g for g in bundle['marks']['guides'] if g['kind'] == 'right_angle']
    assert [g['source'] for g in right] == ['op-q']
    assert checked_marks(bundle['marks'], as_document(bundle['document'])) is not None
    assert [m['kind'] for m in space.resolve_paint(doc)['marks']] == ['right_angle']


def test_prepare_render_takes_the_inputs_of_the_flat_scene():
    doc = construction()
    inputs = {'B1': {'kind': 'point3', 'value': [7.0, 2.0, 0.0]}, 'A2': {'kind': 'point3', 'value': [-1.0, 4.0, 0.0]}}
    ev = space.evaluate(doc, inputs=inputs)
    flat = space.flat_scene(doc, evaluated=ev)
    expected = space.prepare_render(flat, doc, evaluated=ev)
    assert space.prepare_render(flat, doc, inputs=inputs) == expected
    assert space.prepare_render(flat, doc)['marks'] != expected['marks']
    with pytest.raises(ValueError, match='inputs or evaluated'):
        space.prepare_render(flat, doc, inputs=inputs, evaluated=ev)
