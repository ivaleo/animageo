"""The space paint channel owns the renderer's projected pieces and marks."""
import math

import pytest

from animageo.native import space


from animageo.native.space.paint_fixtures import decorations_document as construction


def test_paint_reuses_plane_piece_and_projects_a_single_label():
    doc = construction()
    flat = space.flat_scene(doc)
    plane = space.to_document(flat, doc)
    assert plane['appearance']['s1--1']['label'] == {'mode': 'caption', 'text': 'Equal halves'}
    assert plane['elements']['l--1']['displayName'] == 'l'
    paint = space.resolve_paint(doc)
    assert paint['format'] == 'animageo-space-paint/v1'
    line = next(s for s in paint['strokes'] if s['id'] == 's1')
    stroke, = line['pieces']
    assert stroke['stroke']['cap'] == 'round'
    labels = {item['id']: item for item in paint['labels']}
    assert labels['s1']['kind'] == 'stroke'
    assert labels['s1']['label']['text'] == 'Equal halves'
    assert labels['l']['at'] == labels['l']['label']['spotWorld']


@pytest.mark.parametrize('projection', ['orthographic', 'oblique', 'perspective'])
@pytest.mark.parametrize('size', [[460, 340], [1200, 880]])
def test_midpoint_ticks_and_right_angle_stay_in_sheet_pixels(projection, size):
    doc = construction()
    camera = {**doc['viewDefaults']['camera'], 'projection': projection, 'distance': 20}
    out = space.resolve_paint(doc, camera=camera, export_layout={'export': {'size': size}})
    ticks = [m for m in out['marks'] if m['kind'] == 'ticks']
    assert [(m['source'], m['half'], m['count']) for m in ticks] == [
        ('op-M1', 1, 1), ('op-M1', 2, 1), ('op-M2', 1, 2),
        ('op-M2', 2, 2), ('op-M3', 1, 3), ('op-M3', 2, 3),
    ]
    for tick in ticks:
        for x1, y1, x2, y2 in tick['lines']:
            assert math.hypot(x2 - x1, y2 - y1) * out['ptUnitStyle'] == pytest.approx(tick['lengthPx'], abs=1e-6)
    square, = [m for m in out['marks'] if m['kind'] == 'right_angle']
    foot, first, _, second = square['corners']
    for arm in (first, second):
        assert math.dist(foot, arm) * out['ptUnitStyle'] == pytest.approx(18 / math.sqrt(2), abs=1e-6)


def test_suppression_and_visibility_are_checked_before_marks():
    doc = construction()
    doc['suppressedMarks'] = [{'source': 'op-M1', 'kind': 'equal_segments'}]
    doc['appearance']['s2'] = {'visible': False}
    doc['appearance']['l']['visible'] = False
    doc['viewDefaults']['autoMarks'] = {'rightAngles': False}
    marks = space.resolve_paint(doc)['marks']
    assert all(m['source'] not in ('op-M1', 'op-M2', 'op-q') for m in marks)
    assert {m['source'] for m in marks} == {'op-M3'}


def test_split_paint_matches_native_dash_and_visibility_roles():
    from animageo.native.space.fixtures import _camera, line_flat_themes

    _, scenes = line_flat_themes()[0]
    _, doc, target, _ = scenes[0]
    for look in ('dashpale', 'none'):
        out = space.resolve_paint(doc, {'space': {'hidden': {'look': look}}}, camera=_camera('front', target))
        stroke = next(s for s in out['strokes'] if s['id'] == 'l')
        assert [piece['visibility'] for piece in stroke['pieces']] == ['visible', 'hidden', 'visible']
        first, hidden, last = stroke['pieces']
        assert first['stroke']['dash'] is None and last['stroke']['dash'] is None
        if look == 'none':
            assert hidden['stroke'] is None
        else:
            paint = hidden['stroke']
            assert paint['cap'] == 'butt' and paint['dash']['drawn']
            assert paint['opacity'] < first['stroke']['opacity'] and paint['z'] < first['stroke']['z']


def test_missing_carriers_and_end_on_angle_do_not_leave_marks():
    doc = construction()
    doc['appearance']['s1']['visible'] = False
    doc['viewDefaults']['camera'] = {'projection': 'orthographic', 'azimuthDeg': 0, 'elevationDeg': 0}
    marks = space.resolve_paint(doc)['marks']
    assert not marks


def test_sidecar_checks_closed_shape_without_loading_renderer():
    doc = construction()
    bundle = space.prepare_render(space.flat_scene(doc), doc)
    bundle['marks']['guides'][0]['extra'] = 'not an allowed property'
    with pytest.raises(ValueError, match='invalid space mark geometry'):
        space.layout_plane_labels(bundle['document'], marks=bundle['marks'])


@pytest.mark.manim
@pytest.mark.parametrize('size', [[408, 304], [1270, 912]])
def test_actual_svg_draws_same_sheet_marks_through_both_entry_points(tmp_path, size):
    import json
    import re
    from animageo.native import render

    pytest.importorskip('manim')
    doc = construction()
    layout = {'export': {'size': size, 'fit': 'contain'},
              'content': {'source': 'rendered_bounds', 'padding': 20}}
    direct = render(doc, out=tmp_path / 'direct.svg', export_layout=layout)
    bundle = json.loads(json.dumps(space.prepare_render(space.flat_scene(doc), doc)))
    joined = space.render_plane(bundle['document'], out=tmp_path / 'joined.svg', marks=bundle['marks'],
                                export_layout=layout)
    marks = direct.report['spaceMarks']
    assert marks == joined.report['spaceMarks']
    assert len(marks) == 7
    svg = (tmp_path / 'joined.svg').read_text()
    tick = marks[0]
    unit = direct.report['canvas']['unit']
    x1, y1, x2, y2 = tick['lines'][0]
    assert math.hypot(x2 - x1, y2 - y1) * unit == pytest.approx(tick['lengthPx'], abs=1e-6)
    path_endpoints = []
    for path in re.findall(r'<path[^>]*stroke-width="[^"]+"[^>]*>', svg):
        commands = re.search(r' d="M ([^"]+)"', path)
        if commands:
            numbers = re.findall(r'-?[0-9.]+(?:e[+-]?[0-9]+)?', commands.group(1))
            path_endpoints.append(tuple(map(float, numbers[:2] + numbers[-2:])))
    expected = []
    for mark in marks:
        if mark['kind'] == 'ticks':
            expected.extend(mark['lines'])
        else:
            _, a, corner, b = mark['corners']
            expected.extend([a + corner, corner + b])
    for a, b, c, d in expected:
        assert min(math.dist((a, b, c, d), line) for line in path_endpoints) < 0.02 / unit
    assert svg == (tmp_path / 'direct.svg').read_text()
    label_defs = space.layout_plane_labels(bundle['document'], marks=bundle['marks'], export_layout=layout)
    assert label_defs['s1--1']['text'] == 'Equal halves'


def test_overlap_fixture_and_one_visible_half():
    from animageo.native.space.paint_fixtures import DEFAULT_PATH, build_fixture, fixture_text

    fixture = build_fixture()
    assert DEFAULT_PATH.read_text(encoding='utf-8') == fixture_text(fixture)
    cases = {case['name']: case for case in fixture['cases']}
    overlap = cases['overlap-ortho']
    perspective = cases['overlap-perspective-no-hidden']
    hidden_solid = cases['overlap-hidden-solid']
    half = cases['marks-occluded-half']
    for case in (overlap, perspective):
        assert case['diagnostics'] == [{'code': 'overlap_order', 'id': 'J', 'otherId': 'K'}]
        assert {f['id'] for f in case['expect']['fills']} == {'pl', 'triangle'}
    assert hidden_solid['diagnostics'] == []
    line = next(s for s in overlap['expect']['strokes'] if s['id'] == 'l')
    assert line['pieces'][1]['hiddenBy'] == ['J', 'K']
    assert line['pieces'][1]['stroke']['dash']['drawn']
    assert line['pieces'][0]['stroke']['color'] == '#3166a5'
    assert {label['id'] for label in overlap['expect']['labels'] if label['kind'] == 'fill'} == {'pl', 'triangle'}
    assert {label['id'] for label in hidden_solid['expect']['labels'] if label['kind'] == 'fill'} == {'pl', 'cut', 'triangle'}
    assert all(stroke['stroke'] is None for s in perspective['expect']['strokes'] if s['id'] == 'l'
               for stroke in s['pieces'] if stroke['visibility'] == 'hidden')
    tick, = half['expect']['marks']
    assert (tick['source'], tick['half'], tick['count']) == ('op-M', 1, 1)


@pytest.mark.parametrize('height,x,shown', [(2, 1, True), (0, 1, False), (2, 6, False)])
def test_perpendicular_plane_mark_needs_visible_finite_support(height, x, shown):
    b = space.SpaceBuilder('normal', camera={'azimuthDeg': -57, 'elevationDeg': 30})
    b.point('A', 0, 0, 0)
    b.point('B', 4, 0, 0)
    b.point('C', 0, 4, 0)
    b.point('P', x, 1, height)
    face = b.polygon('plane', 'A', 'B', 'C')
    b.perpendicular_plane('q', 'P', face.main)
    b.projection_plane('F', 'P', face.main)
    doc = b.data()
    marks = space.resolve_paint(doc)['marks']
    assert bool(marks) is shown
    if shown:
        assert marks[0]['source'] == 'op-q'
        doc['appearance'] = {'q': {'overrides': {'right_angle_marker': False}}}
        assert space.resolve_paint(doc)['marks'] == []


def test_labels_receive_visible_mark_strokes_on_the_final_sheet(monkeypatch):
    from animageo import label_placement

    actual = label_placement.compute_label_layout
    added = []

    def capture(scene, *args, **kwargs):
        added.extend(elem.name for elem in scene.geo.elements if elem.name.startswith('space_mark_'))
        return actual(scene, *args, **kwargs)

    monkeypatch.setattr(label_placement, 'compute_label_layout', capture)
    doc = construction()
    bundle = space.prepare_render(space.flat_scene(doc), doc)
    space.layout_plane_labels(bundle['document'], marks=bundle['marks'], place=True)
    assert len(added) == 14


@pytest.mark.manim
def test_tikz_draws_the_same_visible_decorations(tmp_path):
    pytest.importorskip('manim')
    doc = construction()
    plain = space.render(doc, out=tmp_path / 'marked.tex', fmt='tikz')
    doc['viewDefaults']['autoMarks'] = {'equalities': False, 'rightAngles': False}
    disabled = space.render(doc, out=tmp_path / 'disabled.tex', fmt='tikz')
    assert len(plain.report['spaceMarks']) == 7
    assert disabled.report['spaceMarks'] == []
    assert ((tmp_path / 'marked.tex').read_text().count(r'\draw[')
            - (tmp_path / 'disabled.tex').read_text().count(r'\draw[')) == 14
