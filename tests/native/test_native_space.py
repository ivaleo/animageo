"""``animageo.native.space`` — the space (3D) prototype: camera and projection,
visibility of convex polyhedra, plane sections and the flat scene.

The visibility of edges is checked against an independent oracle: a ray
from a point of the edge towards the eye, intersected with the faces of the
solid (``_ray_hidden``)."""
import json
import math

import pytest

from animageo import native
from animageo.native import space
from animageo.native.space import vec

# ── helpers ─────────────────────────────────────────────────────────────


def approx_point(value, expected, abs_tol=1e-9):
    assert len(value) == len(expected)
    for a, b in zip(value, expected):
        assert a == pytest.approx(b, abs=abs_tol)


def ortho(az, el, target=(1, 1, 1)):
    return space.Camera(projection='orthographic', azimuth_deg=az, elevation_deg=el, target=target)


def persp(az, el, distance, target=(1, 1, 1)):
    return space.Camera(projection='perspective', azimuth_deg=az, elevation_deg=el, target=target,
                        distance=distance)


def labels_of(poly, edge):
    return frozenset((poly.labels[edge.a], poly.labels[edge.b]))


def hidden_edges(poly, projector):
    states = space.edge_visibility(poly, projector)
    return {labels_of(poly, e) for e, visible in zip(poly.edges, states) if not visible}


def _inside_face(poly, k, p, tol):
    n = poly.normals[k]
    ring = [poly.vertices[i] for i in poly.faces[k]]
    for i, a in enumerate(ring):
        b = ring[(i + 1) % len(ring)]
        if vec.dot(vec.cross(vec.sub(b, a), vec.sub(p, a)), n) < -tol:
            return False
    return True


def _ray_hidden(poly, projector, p):
    """The oracle: the ray from ``p`` towards the eye meets a face of ``poly``."""
    scale = poly.scale
    eye = projector.eye
    for k, n in enumerate(poly.normals):
        a = poly.vertices[poly.faces[k][0]]
        d = projector.toward_eye(p)
        den = vec.dot(n, d)
        if abs(den) < 1e-12:
            continue
        s = vec.dot(n, vec.sub(a, p)) / den
        if s <= 1e-7 * scale:
            continue
        if eye is not None and s >= vec.norm(vec.sub(eye, p)):
            continue
        if _inside_face(poly, k, vec.add(p, vec.mul(d, s)), 1e-9 * scale):
            return True
    return False


CAMERAS = [
    ortho(-60, 25), ortho(30, 20), ortho(120, 35), ortho(-150, 15), ortho(-60, -25), ortho(75, 70),
    ortho(10, 5), persp(-60, 25, 9), persp(30, 40, 6), persp(-120, -20, 7), persp(160, 10, 5),
]


# ── camera and projection ───────────────────────────────────────────────

def test_orthographic_front_view_axes():
    proj = space.Projector(ortho(-90, 0, target=(0, 0, 0)))
    approx_point(proj.project((1, 0, 0))[:2], (1, 0))
    approx_point(proj.project((0, 0, 1))[:2], (0, 1))
    approx_point(proj.project((0, 5, 0))[:2], (0, 0))
    assert proj.project((0, 1, 0))[2] > proj.project((0, 0, 0))[2]      # farther from the eye
    approx_point(proj.toward_eye((3, 3, 3)), (0, -1, 0))


def test_orthographic_keeps_midpoints_and_parallels():
    proj = space.Projector(ortho(-37, 23))
    a, b, c = (0.3, -1.2, 2.0), (2.5, 0.7, -0.4), (-1.0, 2.0, 1.0)
    pa, pb = proj.project(a)[:2], proj.project(b)[:2]
    approx_point(proj.project(vec.lerp(a, b, 0.5))[:2], ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2))
    d = vec.add(c, vec.sub(b, a))                   # cd ∥ ab
    pc, pd = proj.project(c)[:2], proj.project(d)[:2]
    cross = (pb[0] - pa[0]) * (pd[1] - pc[1]) - (pb[1] - pa[1]) * (pd[0] - pc[0])
    assert cross == pytest.approx(0, abs=1e-9)


def test_top_view_is_defined():
    proj = space.Projector(ortho(0, 90, target=(0, 0, 0)))
    x, y, _ = proj.project((1, 0, 0))
    assert math.isfinite(x) and math.isfinite(y)
    assert math.hypot(x, y) == pytest.approx(1)
    approx_point(proj.toward_eye((0, 0, 0)), (0, 0, 1))


def test_perspective_scale_at_the_target_and_beyond():
    proj = space.Projector(persp(-90, 0, 10, target=(0, 0, 0)))
    approx_point(proj.project((0, 0, 0))[:2], (0, 0))
    approx_point(proj.project((1, 0, 0))[:2], (1, 0))                      # 1:1 at the target depth
    far = proj.project((1, 10, 0))
    assert far[0] == pytest.approx(0.5)                                     # twice as far: half as large
    approx_point(proj.eye, (0, -10, 0))
    approx_point(proj.toward_eye((0, 0, 0)), (0, -1, 0))


def test_oblique_cabinet_projection():
    proj = space.Projector(space.Camera(projection='oblique', target=(0, 0, 0)))
    approx_point(proj.project((1, 0, 0))[:2], (1, 0))
    approx_point(proj.project((0, 0, 1))[:2], (0, 1))
    k = 0.5 * math.sqrt(0.5)
    approx_point(proj.project((0, 1, 0))[:2], (k, k))
    assert proj.project((0, 1, 0))[2] > proj.project((0, 0, 0))[2]
    # moving along the projection direction does not move the image
    w = vec.mul(proj.toward_eye((0, 0, 0)), -3.0)
    approx_point(proj.project(vec.add((0.4, 0.2, 0.9), w))[:2], proj.project((0.4, 0.2, 0.9))[:2])


def test_camera_dict_round_trip_and_errors():
    cam = space.Camera(projection='perspective', azimuth_deg=-50, elevation_deg=20, target=(1, 2, 3),
                       distance=12)
    data = cam.to_dict()
    assert data == {'projection': 'perspective', 'azimuthDeg': -50, 'elevationDeg': 20,
                    'target': [1, 2, 3], 'distance': 12}
    assert space.Camera.from_dict(data) == cam
    oblique = space.Camera(projection='oblique').to_dict()
    assert oblique['oblique'] == {'angleDeg': 45.0, 'ratio': 0.5}
    with pytest.raises(ValueError, match='projection'):
        space.Camera(projection='fisheye')
    with pytest.raises(ValueError, match='distance'):
        space.Camera(projection='perspective', distance=0)


# ── solids ──────────────────────────────────────────────────────────────

def test_cube_structure():
    cube = space.cube(size=2)
    assert cube.labels == ('A', 'B', 'C', 'D', 'A_1', 'B_1', 'C_1', 'D_1')
    assert len(cube.vertices) == 8 and len(cube.faces) == 6 and len(cube.edges) == 12
    for k, n in enumerate(cube.normals):                     # outward
        centre = vec.centroid([cube.vertices[i] for i in cube.faces[k]])
        assert vec.dot(n, vec.sub(centre, (1, 1, 1))) > 0
    assert all(len(e.faces) == 2 for e in cube.edges)


def test_prism_by_base_and_vector_is_oblique():
    prism = space.prism([(0, 0, 0), (3, 0, 0), (1, 2, 0)], (0.8, 0.5, 2.5))
    assert prism.labels == ('A', 'B', 'C', 'A_1', 'B_1', 'C_1')
    approx_point(prism.vertices[3], (0.8, 0.5, 2.5))
    assert len(prism.faces) == 5 and len(prism.edges) == 9


def test_pyramid_and_tetrahedron():
    pyr = space.pyramid([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)], (1, 1, 3))
    assert pyr.labels == ('A', 'B', 'C', 'D', 'S')
    assert len(pyr.faces) == 5 and len(pyr.edges) == 8
    tet = space.tetrahedron((0, 0, 0), (3, 0, 0), (1, 2.5, 0), (1.2, 0.9, 2.8))
    assert tet.labels == ('A', 'B', 'C', 'D') and len(tet.edges) == 6


def test_bad_solids_are_refused():
    with pytest.raises(ValueError, match='not_convex'):
        space.prism([(0, 0, 0), (2, 0, 0), (1, 0.3, 0), (1, 2, 0)], (0, 0, 1))   # a dent in the base
    with pytest.raises(ValueError, match='flat'):
        space.pyramid([(0, 0, 0), (2, 0, 0), (0, 2, 0)], (1, 1, 0))


# ── visibility of edges ─────────────────────────────────────────────────

def test_cube_hidden_corner_from_above_and_below():
    cube = space.cube(size=2)
    above = hidden_edges(cube, space.Projector(ortho(-60, 25)))
    assert above == {frozenset(p) for p in (('A', 'D'), ('C', 'D'), ('D', 'D_1'))}
    below = hidden_edges(cube, space.Projector(ortho(-60, -25)))
    assert below == {frozenset(p) for p in (('A_1', 'D_1'), ('C_1', 'D_1'), ('D', 'D_1'))}


@pytest.mark.parametrize('az', [-150, -60, 30, 120])
def test_cube_hides_the_corner_away_from_the_eye(az):
    cube = space.cube(size=2)
    proj = space.Projector(ortho(az, 20))
    eye = proj.toward_eye((1, 1, 1))
    far = min(range(8), key=lambda i: vec.dot(vec.sub(cube.vertices[i], (1, 1, 1)), eye))
    expected = {labels_of(cube, e) for e in cube.edges if far in (e.a, e.b)}
    assert hidden_edges(cube, proj) == expected


def test_perspective_close_to_the_front_face_differs_from_parallel():
    cube = space.cube(size=2)
    # the eye is below the plane of the top face: in perspective the top is a back face
    assert len(hidden_edges(cube, space.Projector(persp(-90, 10, 2.5)))) == 8
    assert len(hidden_edges(cube, space.Projector(ortho(-90, 10)))) == 5


def test_tetrahedron_apex_in_front_and_behind():
    tet = space.pyramid([(0, 0, 0), (3, 0, 0), (1, 2.6, 0)], (1.3, 0.9, 3.0))
    assert hidden_edges(tet, space.Projector(ortho(-60, 80))) == set()
    assert hidden_edges(tet, space.Projector(ortho(-60, -80))) == {
        frozenset(('A', 'S')), frozenset(('B', 'S')), frozenset(('C', 'S'))}


SOLIDS = {
    'cube': space.cube(size=2),
    'tetrahedron': space.tetrahedron((0, 0, 0), (3, 0, 0), (1, 2.6, 0), (1.3, 0.9, 3.0)),
    'prism': space.prism([(0, 0, 0), (3, 0, 0), (1, 2, 0)], (0.8, 0.5, 2.5)),
    'pentagonal prism': space.prism([(math.cos(a) * 1.5 + 1, math.sin(a) * 1.5 + 1, 0)
                                     for a in (i * 2 * math.pi / 5 for i in range(5))], (0, 0, 2)),
    'pyramid': space.pyramid([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)], (1, 1, 3)),
}


@pytest.mark.parametrize('name', sorted(SOLIDS))
@pytest.mark.parametrize('cam', CAMERAS, ids=lambda c: f'{c.projection[:5]}{c.azimuth_deg:+g},{c.elevation_deg:+g}')
def test_edge_visibility_matches_ray_casting(name, cam):
    poly = SOLIDS[name]
    proj = space.Projector(cam)
    states = space.edge_visibility(poly, proj)
    for edge, visible in zip(poly.edges, states):
        mid = vec.lerp(poly.vertices[edge.a], poly.vertices[edge.b], 0.5)
        assert visible == (not _ray_hidden(poly, proj, mid)), labels_of(poly, edge)


@pytest.mark.parametrize('name', sorted(SOLIDS))
@pytest.mark.parametrize('cam', CAMERAS, ids=lambda c: f'{c.projection[:5]}{c.azimuth_deg:+g},{c.elevation_deg:+g}')
def test_shadow_volume_agrees_with_face_normals(name, cam):
    poly = SOLIDS[name]
    proj = space.Projector(cam)
    occ = space.ConvexOccluder(poly, proj)
    for edge, visible in zip(poly.edges, space.edge_visibility(poly, proj)):
        a, b = poly.vertices[edge.a], poly.vertices[edge.b]
        interval = occ.hidden_interval(a, b)
        if visible:
            assert interval is None
        else:
            assert interval is not None
            assert interval[0] == pytest.approx(0, abs=1e-6) and interval[1] == pytest.approx(1, abs=1e-6)


# ── occlusion of other segments ─────────────────────────────────────────

def test_segment_behind_the_cube_is_cut_into_three_pieces():
    cube = space.cube(size=2)
    proj = space.Projector(ortho(-90, 0))
    occ = space.ConvexOccluder(cube, proj)
    a, b = (-1, 4, 1), (3, 4, 1)
    t0, t1 = occ.hidden_interval(a, b)
    assert (t0, t1) == (pytest.approx(0.25), pytest.approx(0.75))
    pieces = space.pieces([(t0, t1)], min_t=1e-3)
    assert [(p.hidden, round(p.t0, 6), round(p.t1, 6)) for p in pieces] == [
        (False, 0.0, 0.25), (True, 0.25, 0.75), (False, 0.75, 1.0)]
    assert occ.hidden_interval((-1, -1, 1), (3, -1, 1)) is None           # in front of the cube


def test_diagonal_inside_the_cube_is_hidden():
    cube = space.cube(size=2)
    proj = space.Projector(ortho(-60, 25))
    occ = space.ConvexOccluder(cube, proj)
    b, d1 = cube.vertex('B'), cube.vertex('D_1')
    pieces = space.pieces([occ.hidden_interval(b, d1)], min_t=0.01)
    assert [(p.hidden, p.t0, p.t1) for p in pieces] == [(True, 0.0, 1.0)]


@pytest.mark.parametrize('cam', CAMERAS, ids=lambda c: f'{c.projection[:5]}{c.azimuth_deg:+g},{c.elevation_deg:+g}')
def test_occlusion_of_foreign_segments_matches_ray_casting(cam):
    cube = space.cube(size=2)
    proj = space.Projector(cam)
    occ = space.ConvexOccluder(cube, proj)
    segments = [((-2, -1, 0.5), (4, 3, 1.5)), ((1, 1, -2), (1, 1, 4)), ((-1, 3, 2.5), (3, -1, -0.5)),
                ((0.5, -3, 1), (1.5, 5, 1))]
    for a, b in segments:
        interval = occ.hidden_interval(a, b)
        for i in range(1, 40):
            t = i / 40
            if interval and min(abs(t - interval[0]), abs(t - interval[1])) < 1e-3:
                continue
            hidden = bool(interval) and interval[0] < t < interval[1]
            assert hidden == _ray_hidden(cube, proj, vec.lerp(a, b, t)), (a, b, t)


def test_pieces_merge_short_gaps_and_drop_short_bits():
    merged = space.pieces([(0.2, 0.4), (0.405, 0.6)], min_t=0.01)
    assert [(p.hidden, p.t0, p.t1) for p in merged] == [(False, 0, 0.2), (True, 0.2, 0.6), (False, 0.6, 1)]
    assert [p.hidden for p in space.pieces([(0.5, 0.503)], min_t=0.01)] == [False]
    tail = space.pieces([(0.1, 0.995)], min_t=0.01)
    assert [(p.hidden, p.t0, p.t1) for p in tail] == [(False, 0, 0.1), (True, 0.1, 1)]
    assert [(p.hidden, p.occluders) for p in space.pieces([(0.2, 0.8), (0.3, 0.5)], min_t=0.01)] == [
        (False, 0), (True, 2), (False, 0)]


# ── sections ────────────────────────────────────────────────────────────

def area(polygon):
    total = (0.0, 0.0, 0.0)
    for i, p in enumerate(polygon):
        total = vec.add(total, vec.cross(p, polygon[(i + 1) % len(polygon)]))
    return vec.norm(total) / 2


def test_cube_sections_square_triangle_hexagon_rectangle():
    cube = space.cube(size=2)
    square = space.section(cube, space.Plane((0, 0, 1), (0, 0, 1)))
    assert square.state == 'defined' and len(square.polygon) == 4 and area(square.polygon) == pytest.approx(4)
    tri = space.section(cube, space.Plane.through((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert len(tri.polygon) == 3 and area(tri.polygon) == pytest.approx(math.sqrt(3) / 2)
    hexagon = space.section(cube, space.Plane((1, 1, 1), (1, 1, 1)))
    assert len(hexagon.polygon) == 6 and area(hexagon.polygon) == pytest.approx(3 * math.sqrt(3))
    for p in hexagon.polygon:                      # the midpoints of six edges
        assert sorted(round(c, 9) for c in p) in ([0, 1, 2],)
    diagonal = space.section(cube, space.Plane.through(cube.vertex('A'), cube.vertex('C'), cube.vertex('C_1')))
    assert len(diagonal.polygon) == 4 and area(diagonal.polygon) == pytest.approx(4 * math.sqrt(2))


def test_section_by_three_points_on_edges():
    cube = space.cube(size=2)
    m = vec.lerp(cube.vertex('A'), cube.vertex('B'), 0.5)
    n = vec.lerp(cube.vertex('B'), cube.vertex('C'), 0.5)
    k = vec.lerp(cube.vertex('C'), cube.vertex('C_1'), 0.5)
    cut = space.section(cube, space.Plane.through(m, n, k))
    assert cut.state == 'defined' and len(cut.polygon) == 6
    for p in cut.polygon:
        assert cut.plane.distance(p) == pytest.approx(0, abs=1e-12)
    # every edge of the section lies on a face of the cube
    for (p, q), faces in zip(cut.edges(), cut.edge_faces):
        assert faces
        for f in faces:
            a = cube.vertices[cube.faces[f][0]]
            assert vec.dot(cube.normals[f], vec.sub(p, a)) == pytest.approx(0, abs=1e-9)
            assert vec.dot(cube.normals[f], vec.sub(q, a)) == pytest.approx(0, abs=1e-9)


def test_tetrahedron_midsection():
    tet = space.pyramid([(0, 0, 0), (4, 0, 0), (1, 3, 0)], (1.5, 1, 4))
    mids = [vec.lerp(tet.vertex('S'), tet.vertex(v), 0.5) for v in 'ABC']
    cut = space.section(tet, space.Plane.through(*mids))
    assert len(cut.polygon) == 3
    assert area(cut.polygon) == pytest.approx(area([tet.vertex(v) for v in 'ABC']) / 4)


def test_section_outside_touch_and_face():
    cube = space.cube(size=2)
    outside = space.section(cube, space.Plane((0, 0, 3), (0, 0, 1)))
    assert (outside.state, outside.reason, outside.polygon) == ('undefined', 'outside', ())
    touch = space.section(cube, space.Plane((0, 0, 0), (1, 1, 1)))
    assert (touch.state, touch.reason) == ('undefined', 'touch')
    face = space.section(cube, space.Plane((0, 0, 2), (0, 0, 1)))
    assert face.state == 'defined' and len(face.polygon) == 4 and area(face.polygon) == pytest.approx(4)


def test_section_edges_take_the_visibility_of_their_faces():
    cube = space.cube(size=2)
    proj = space.Projector(ortho(-60, 25))           # hidden corner D = (0, 2, 0)
    hexagon = space.section(cube, space.Plane((1, 1, 1), (1, 1, 1)))
    states = space.section_visibility(cube, hexagon, proj)
    assert sorted(states) == [False, False, False, True, True, True]
    facing = space.face_facing(cube, proj)
    for visible, faces in zip(states, hexagon.edge_faces):
        assert visible == any(facing[f] == 'front' for f in faces)


# ── flat scene and the native document ──────────────────────────────────

def cube_scene():
    cube = space.cube(size=2)
    m = vec.lerp(cube.vertex('A'), cube.vertex('B'), 0.5)
    n = vec.lerp(cube.vertex('B'), cube.vertex('C'), 0.5)
    k = vec.lerp(cube.vertex('C'), cube.vertex('C_1'), 0.5)
    return space.SpaceScene(
        solids=[space.SceneSolid('cube', cube)],
        sections=[space.SceneSection('cut', 'cube', space.Plane.through(m, n, k))],
        segments=[space.SceneSegment('diag', cube.vertex('B'), cube.vertex('D_1'))],
        points=[space.ScenePoint('M', 'M', m), space.ScenePoint('N', 'N', n), space.ScenePoint('K', 'K', k)],
    )


def test_flat_scene_of_a_cube():
    flat = space.flat_scene(cube_scene(), ortho(-60, 25))
    assert flat['format'] == space.FLAT_SCENE_FORMAT
    edges = [s for s in flat['strokes'] if s['role'] == 'edge']
    assert len(edges) == 12
    hidden = sorted(s['id'] for s in edges if all(p['visibility'] == 'hidden' for p in s['pieces']))
    assert hidden == ['cube.edge.A-D', 'cube.edge.C-D', 'cube.edge.D-D_1']
    section = [s for s in flat['strokes'] if s['role'] == 'section']
    assert len(section) == 6
    diag = next(s for s in flat['strokes'] if s['id'] == 'diag')
    assert [p['visibility'] for p in diag['pieces']] == ['hidden']
    # fills: back faces, then the section, then the front faces
    order = [(f['role'], f.get('facing')) for f in flat['fills']]
    assert order == [('face', 'back')] * 3 + [('section', None)] + [('face', 'front')] * 3
    names = {p['name']: p for p in flat['points']}
    assert names['D']['visibility'] == 'hidden' and names['B']['visibility'] == 'visible'
    xmin, ymin, xmax, ymax = flat['bounds']
    for p in flat['points']:
        assert xmin < p['at'][0] < xmax and ymin < p['at'][1] < ymax


def test_flat_scene_is_deterministic_json():
    a = json.dumps(space.flat_scene(cube_scene(), persp(-50, 30, 9)), sort_keys=True)
    b = json.dumps(space.flat_scene(cube_scene(), persp(-50, 30, 9)), sort_keys=True)
    assert a == b


def test_flat_scene_refuses_points_behind_the_eye():
    with pytest.raises(ValueError, match='behind_eye'):
        space.flat_scene(cube_scene(), persp(-60, 25, 0.5))


def test_document_of_the_flat_scene_is_valid_native():
    flat = space.flat_scene(cube_scene(), ortho(-60, 25))
    doc = space.to_document(flat)
    loaded = native.load(doc)
    assert [i for i in native.validate(loaded) if i.severity == 'error'] == []
    result = native.evaluate(loaded)
    assert all(r['state'] == 'defined' for r in result.elements.values())
    pieces = [p for s in flat['strokes'] for p in s['pieces']]
    segments = [e for e in doc['elements'].values() if e['type'] == 'segment']
    assert len(segments) == len(pieces)
    dashed = [i for i, e in doc['elements'].items()
              if e['type'] == 'segment' and 'stroke_dash_ratio' in doc['appearance'][i].get('overrides', {})]
    assert len(dashed) == sum(p['visibility'] == 'hidden' for p in pieces)
    polygons = [e for e in doc['elements'].values() if e['type'] == 'polygon']
    assert len(polygons) == len(flat['fills'])
    named = sorted(e['displayName'] for e in doc['elements'].values() if e['type'] == 'point' and e['displayName'])
    assert named == sorted(['A', 'B', 'C', 'D', 'A_1', 'B_1', 'C_1', 'D_1', 'M', 'N', 'K'])
    assert doc['viewDefaults']['bounds'] == flat['bounds']


def test_document_of_the_flat_scene_sets_only_keys_its_elements_read():
    flat = space.flat_scene(cube_scene(), ortho(-60, 25))
    paint = native.resolve_paint(space.to_document(flat))
    assert [d for d in paint['diagnostics'] if d['code'] == 'style_key_ineffective'] == []
    # a polygon is layered by z_index alone: the fill lies at it
    fills = [e for e in paint['elements'].values() if e['type'] == 'polygon']
    assert len(fills) == len(flat['fills'])
    assert all(e['fill']['z'] == e['z'] for e in fills)


def test_hidden_look_none_drops_hidden_pieces():
    flat = space.flat_scene(cube_scene(), ortho(-60, 25))
    doc = space.to_document(flat, look={'hidden': 'none'})
    pieces = [p for s in flat['strokes'] for p in s['pieces'] if p['visibility'] == 'visible']
    assert len([e for e in doc['elements'].values() if e['type'] == 'segment']) == len(pieces)
    with pytest.raises(ValueError, match='hidden'):
        space.to_document(flat, look={'hidden': 'sparkle'})


def test_planes_hide_nothing_and_have_three_looks():
    cube = space.cube(size=2)
    plane = space.Plane((0, 0, 1), (0, 0, 1))
    around = space.section(cube, plane).polygon
    cam = ortho(-60, 25)

    def flat_with(look):
        scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                                 planes=[space.ScenePlane('alpha', plane, around, look=look)])
        return space.flat_scene(scene, cam)

    sheet = flat_with('sheet')
    assert sheet['fills'][0]['role'] == 'plane'
    borders = [s for s in sheet['strokes'] if s['role'] == 'plane']
    assert len(borders) == 4
    # the sheet passes through the cube: its back part is hidden by the cube, the cube is not
    assert any(p['visibility'] == 'hidden' for s in borders for p in s['pieces'])
    edges = [s for s in sheet['strokes'] if s['role'] == 'edge']
    assert sum(all(p['visibility'] == 'hidden' for p in s['pieces']) for s in edges) == 3
    corners = flat_with('corners')
    assert [f['role'] for f in corners['fills']].count('plane') == 0
    assert len([s for s in corners['strokes'] if s['role'] == 'plane']) == 8
    trace = flat_with('trace')
    assert [s for s in trace['strokes'] if s['role'] == 'plane'] == []
    with pytest.raises(ValueError, match='look'):
        flat_with('glow')


def test_the_trace_look_draws_the_line_on_the_ground():
    cube = space.cube(size=2)
    m = vec.lerp(cube.vertex('A'), cube.vertex('B'), 0.5)
    n = vec.lerp(cube.vertex('B'), cube.vertex('C'), 0.5)
    k = vec.lerp(cube.vertex('C'), cube.vertex('C_1'), 0.5)
    plane = space.Plane.through(m, n, k)
    around = space.section(cube, plane).polygon
    cam = ortho(-60, 22)
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                             planes=[space.ScenePlane('alpha', plane, around, look='trace', margin=0.5)])
    flat = space.flat_scene(scene, cam)
    traces = [s for s in flat['strokes'] if s['role'] == 'plane']
    assert [s['id'] for s in traces] == ['alpha.trace']
    assert flat['fills'] == [f for f in flat['fills'] if f['role'] != 'plane']
    pieces = traces[0]['pieces']
    a, b = pieces[0]['a'], pieces[-1]['b']
    proj = space.Projector(cam)
    for p in (m, n):                                   # the trace is the line MN on the ground
        x, y, _ = proj.project(p)
        assert abs((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])) < 1e-9
    # inside the cube it runs along the hidden bottom face, outside it is seen
    assert [p['visibility'] for p in pieces] == ['visible', 'hidden', 'visible']


def test_a_solid_behind_another_is_partly_hidden():
    cube = space.cube(size=2)
    pyr = space.pyramid([(0.5, 3, 0), (2.5, 3, 0), (2.5, 5, 0), (0.5, 5, 0)], (1.5, 4, 3.5))
    cam = ortho(-90, 12, target=(1, 2.5, 1))           # the eye looks along +y: the pyramid is behind
    proj = space.Projector(cam)
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube), space.SceneSolid('pyr', pyr)])
    flat = space.flat_scene(scene, cam)
    # the far solid is painted first
    assert flat['fills'][0]['source'] == 'pyr'
    assert flat['fills'][-1]['source'] == 'cube'
    own = dict(zip((f'pyr.edge.{pyr.labels[e.a]}-{pyr.labels[e.b]}' for e in pyr.edges),
                   space.edge_visibility(pyr, proj)))
    by_cube = 0
    for s in flat['strokes']:
        if s['source'] != 'pyr':
            continue
        e = next(e for e in pyr.edges if s['id'] == f'pyr.edge.{pyr.labels[e.a]}-{pyr.labels[e.b]}')
        a, b = pyr.vertices[e.a], pyr.vertices[e.b]
        for piece in s['pieces']:
            mid = vec.lerp(a, b, (piece['t'][0] + piece['t'][1]) / 2)
            hidden = (not own[s['id']]) or _ray_hidden(cube, proj, mid)
            assert (piece['visibility'] == 'hidden') == hidden, (s['id'], piece['t'])
            by_cube += own[s['id']] and piece['visibility'] == 'hidden'
    assert by_cube > 0
    cube_edges = [s for s in flat['strokes'] if s['source'] == 'cube']
    assert all(len(s['pieces']) == 1 for s in cube_edges)    # the pyramid behind hides nothing of the cube


def _document_layers(flat, doc):
    """The z of every fill and piece of ``flat`` in ``doc`` (``native.resolve_paint``):
    ``fills`` in the order of ``flat['fills']``, ``pieces`` as ``(stroke, piece, z)``."""
    paint = native.resolve_paint(doc)
    z = {el_id: entry['z'] for el_id, entry in paint['elements'].items() if entry.get('drawn')}
    fills = [z[f'f{k}'] for k in range(1, len(flat['fills']) + 1)]
    pieces, k = [], 0
    for s in flat['strokes']:
        for piece in s['pieces']:
            k += 1
            pieces.append((s, piece, z[f's{k}']))
    points = [z[el_id] for el_id, e in doc['elements'].items()
              if e['type'] == 'point' and e['displayName']]
    return fills, pieces, points


def test_a_solid_behind_another_lies_under_it_in_the_document():
    cube = space.cube(size=2)
    pyr = space.pyramid([(0.5, 3, 0), (2.5, 3, 0), (2.5, 5, 0), (0.5, 5, 0)], (1.5, 4, 3.5))
    cam = ortho(-90, 12, target=(1, 2.5, 1))           # the eye looks along +y: the pyramid is behind
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube), space.SceneSolid('pyr', pyr)])
    flat = space.flat_scene(scene, cam)
    assert flat['solids'] == ['pyr', 'cube']            # far to near
    assert {f['solid'] for f in flat['fills']} == {'pyr', 'cube'}
    fills, pieces, points = _document_layers(flat, space.to_document(flat))
    layer = {}
    for f, z in zip(flat['fills'], fills):
        layer.setdefault((f['solid'], f.get('facing', f['role'])), []).append(z)
    # every fill of the far solid — its front faces too — lies under the back faces of the near one
    assert max(layer['pyr', 'front']) < min(layer['cube', 'back'])
    assert max(layer['pyr', 'back']) < min(layer['pyr', 'front'])
    assert max(layer['cube', 'back']) < min(layer['cube', 'front'])
    hidden = [(s, p, z) for s, p, z in pieces if p['visibility'] == 'hidden']
    by_cube = [z for s, p, z in hidden if s['source'] == 'pyr' and p['hiddenBy'] == ['cube']]
    own = [z for s, p, z in hidden if p['hiddenBy'][0] == 'pyr']
    assert by_cube and own
    # a piece lies under the front faces of the farthest solid that hides it, over its back faces
    assert all(max(layer['cube', 'back']) < z < min(layer['cube', 'front']) for z in by_cube)
    assert all(max(layer['pyr', 'back']) < z < min(layer['pyr', 'front']) for z in own)
    assert all(p['hiddenBy'] == [] for s, p, z in pieces if p['visibility'] == 'visible')
    visible = [z for s, p, z in pieces if p['visibility'] == 'visible']
    assert min(visible) > max(fills + [z for s, p, z in hidden])
    assert max(visible) < min(points)                   # the points and their labels stay on top


def test_many_solids_keep_lines_under_the_points():
    solids = [space.SceneSolid(f'c{k}', space.prism([(3 * k, 0, 0), (3 * k + 2, 0, 0), (3 * k + 2, 2, 0),
                                                    (3 * k, 2, 0)], (0, 0, 2))) for k in range(8)]
    flat = space.flat_scene(space.SpaceScene(solids=solids), ortho(-20, 25, target=(12, 1, 1)))
    assert len(flat['solids']) == 8
    fills, pieces, points = _document_layers(flat, space.to_document(flat))
    assert max(fills + [z for _, _, z in pieces]) < min(points)
    rank = {sid: k for k, sid in enumerate(flat['solids'])}
    by_solid = sorted((rank[f['solid']], z) for f, z in zip(flat['fills'], fills))
    assert [z for _, z in by_solid] == sorted(fills)    # the solids far to near, one after another


def test_pieces_merge_by_px_of_the_reference_frame():
    """The merge threshold is in px of the reference frame — the source view
    ``native.render`` draws the document in (``SOURCE_WIDTH`` across the
    bounds) — whatever the zoom of a canvas or the size of an export."""
    from animageo.native import rendering
    from animageo.native.space import flat as flat_module
    assert flat_module.SOURCE_WIDTH == rendering.SOURCE_WIDTH
    cube = space.cube(size=2)
    delta = 0.0035                                      # the bit of the segment left of the cube
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                             segments=[space.SceneSegment('s', (-delta, 4, 1), (3, 4, 1))])
    cam = ortho(-90, 0)
    flat = space.flat_scene(scene, cam)
    assert flat['unit'] == pytest.approx(rendering.source_view(space.to_document(flat))['ptUnit'])
    bit_px = delta * flat['unit']
    assert 0.5 < bit_px < 0.9

    def states(min_piece_px):
        stroke = space.flat_scene(scene, cam, min_piece_px=min_piece_px)['strokes']
        return [p['visibility'] for p in next(s for s in stroke if s['id'] == 's')['pieces']]

    assert states(bit_px * 1.01) == ['hidden', 'visible']
    assert states(bit_px * 0.99) == ['visible', 'hidden', 'visible']


def test_hidden_opacity_multiplies_the_opacity_of_the_line(monkeypatch):
    from animageo.native.space import flat as flat_module
    multiplier = flat_module.HIDDEN_LOOKS['dashpale']['stroke_opacity']
    monkeypatch.setitem(flat_module.ROLE_STROKES, 'aux', {'stroke_opacity': 0.5})
    flat = space.flat_scene(cube_scene(), ortho(-60, 25))
    doc = space.to_document(flat)
    k, seen = 0, {}
    for s in flat['strokes']:
        for piece in s['pieces']:
            k += 1
            seen.setdefault((s['role'], piece['visibility']), set()).add(
                round(doc['appearance'][f's{k}']['overrides'].get('stroke_opacity', 1.0), 12))
    assert seen['aux', 'hidden'] == {round(0.5 * multiplier, 12)}
    assert seen['edge', 'hidden'] == {round(multiplier, 12)}
    assert seen['edge', 'visible'] == {1.0}


# ── degenerate views and cuts ───────────────────────────────────────────

def _along_the_view(projector, a, b):
    d = vec.sub(b, a)
    return vec.norm(vec.cross(d, projector.toward_eye(a))) <= 1e-12 * vec.norm(d)


@pytest.mark.parametrize('cam', [ortho(-60, 90), ortho(-90, 0), ortho(0, 0)], ids=['top', 'front', 'side'])
def test_a_line_along_the_view_ray_has_no_pieces(cam):
    cube = space.cube(size=2)
    proj = space.Projector(cam)
    ray = (vec.add((0.5, 0.5, 0.5), vec.mul(proj.toward_eye((0, 0, 0)), -3.0)),
           vec.add((0.5, 0.5, 0.5), vec.mul(proj.toward_eye((0, 0, 0)), 3.0)))
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                             segments=[space.SceneSegment('ray', *ray)])
    flat = space.flat_scene(scene, cam)
    ends = {f'cube.edge.{cube.labels[e.a]}-{cube.labels[e.b]}': (cube.vertices[e.a], cube.vertices[e.b])
            for e in cube.edges}
    end_on = {i for i, (a, b) in ends.items() if _along_the_view(proj, a, b)}
    assert len(end_on) == 4
    for s in flat['strokes']:
        if s['id'] in end_on or s['id'] == 'ray':
            assert s['pieces'] == [], s['id']
        else:
            assert s['pieces'], s['id']
    doc = space.to_document(flat)
    assert all(r['state'] == 'defined' for r in native.evaluate(native.load(doc)).elements.values())
    for el_id, op in ((e, doc['operations'][f'op_{e}']) for e, el in doc['elements'].items()
                      if el['type'] == 'segment'):
        a, b = (doc['inputs'][op['args'][k]['elementId']]['value'] for k in ('a', 'b'))
        assert a != b, el_id


def test_faces_seen_edge_on():
    cube = space.cube(size=2)
    cam = ortho(-90, 0)                                  # the eye on −y: only the faces y = 0 and y = 2 are not side
    proj = space.Projector(cam)
    states = space.face_facing(cube, proj)
    assert sorted(states) == ['back', 'front', 'side', 'side', 'side', 'side']
    flat = space.flat_scene(space.SpaceScene(solids=[space.SceneSolid('cube', cube)]), cam)
    assert sorted(f['facing'] for f in flat['fills']) == ['back', 'front']
    seen = {s['id']: [p['visibility'] for p in s['pieces']] for s in flat['strokes'] if s['pieces']}
    assert len(seen) == 8                                # four edges run along the view
    front = {i for i, v in seen.items() if v == ['visible']}
    assert len(front) == 4 and len([v for v in seen.values() if v == ['hidden']]) == 4
    for i in front:                                      # the edges of the face y = 0
        a, b = (cube.vertex(n) for n in i.split('.')[-1].split('-'))
        assert a[1] == b[1] == 0
    # a line behind the cube at the height of its top face (seen edge-on): the shadow holds its boundary
    occ = space.ConvexOccluder(cube, proj)
    t0, t1 = occ.hidden_interval((-1, 3, 2), (3, 3, 2))
    assert (t0, t1) == (pytest.approx(0.25), pytest.approx(0.75))
    assert occ.hidden_interval((-1, 3, 2 + 1e-6), (3, 3, 2 + 1e-6)) is None


def test_a_plane_through_vertices_of_the_solid():
    cube = space.cube(size=2)
    b, d, a1 = cube.vertex('B'), cube.vertex('D'), cube.vertex('A_1')
    cut = space.section(cube, space.Plane.through(b, d, a1))
    assert cut.state == 'defined' and len(cut.polygon) == 3      # each vertex once, not once per edge
    assert {tuple(p) for p in cut.polygon} == {tuple(b), tuple(d), tuple(a1)}
    assert all(len(faces) == 1 for faces in cut.edge_faces)       # each side on one face of the cube
    cam = ortho(-60, 25)
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                             sections=[space.SceneSection('cut', 'cube', cut.plane)])
    flat = space.flat_scene(scene, cam)
    assert flat['diagnostics'] == []
    assert len([s for s in flat['strokes'] if s['role'] == 'section']) == 3
    assert [f['role'] for f in flat['fills']].count('section') == 1
    facing = space.face_facing(cube, space.Projector(cam))
    for s, faces in zip((s for s in flat['strokes'] if s['role'] == 'section'), cut.edge_faces):
        visible = any(facing[f] == 'front' for f in faces)
        assert [p['visibility'] for p in s['pieces']] == ['visible' if visible else 'hidden']


def test_a_plane_through_an_edge_only_touches_the_solid():
    cube = space.cube(size=2)
    plane = space.Plane((0, 0, 0), (1, 1, 0))            # holds the edge AA_1 and nothing else of the cube
    cut = space.section(cube, plane)
    assert (cut.state, cut.reason) == ('undefined', 'touch')
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                             sections=[space.SceneSection('cut', 'cube', plane)])
    flat = space.flat_scene(scene, ortho(-60, 25))
    assert flat['diagnostics'] == [{'code': 'section_undefined', 'id': 'cut', 'reason': 'touch'}]
    assert [s for s in flat['strokes'] if s['role'] == 'section'] == []
    assert [f for f in flat['fills'] if f['role'] == 'section'] == []


@pytest.mark.parametrize('size', [2e-3, 2e3])
def test_the_shadow_volume_does_not_depend_on_the_unit_of_length(size):
    """A vertical edge seen almost end-on (1e-9 rad from the view) keeps its
    side plane whatever the unit: the threshold of a side normal follows its
    dimension (a length in a parallel projection)."""
    cam = ortho(-60, 90 - math.degrees(1e-9))

    def planes(k):
        cube = space.cube(size=k)
        return len(space.ConvexOccluder(cube, space.Projector(cam)).planes)

    assert planes(size) == planes(2.0)
