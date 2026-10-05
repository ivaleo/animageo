"""Parity fixtures: the library set, generate/verify, the refusal rule."""
import copy
import json
from collections import Counter

import pytest

from animageo import native
from animageo.native import parity
from animageo.native.cli import main
from tests.native.conftest import EXPECTED_DIR, SCENES_DIR, DocBuilder, point_input, read_json

SCENES = sorted(p.name for p in SCENES_DIR.glob('*.json'))
REQUIRED_SCENES = {
    'basic_points', 'segment_line', 'circle', 'intersect_lines', 'intersect_segments',
    'polygon_triangle', 'polygon_quad', 'upstream_chain', 'graph_errors',
    # registry 1.1
    'ray_points', 'ray_segment_cross', 'line_circle_order', 'line_circle_tangent', 'line_circle_miss',
    'segment_circle_part', 'segment_circle_zero', 'ray_circle', 'circle_circle_sides',
    'circle_circle_tangent_out', 'circle_circle_tangent_in', 'circle_circle_apart',
    'circle_circle_concentric', 'other_than_line_circle', 'other_than_tangent', 'other_than_circles',
    'other_than_absent', 'on_path_segment', 'on_path_line_ray', 'on_path_circle', 'on_path_polygon',
    'on_path_chain',
    # registry 1.2
    'projection', 'parallel_perpendicular', 'perpendicular_bisector', 'angle_bisector', 'vector_points',
    'circle_center_radius', 'circle_three_points', 'number_free', 'on_path_l2_lines', 'l2a1_chain',
    # registry 1.3
    'angle_points', 'angle_zero_wrap', 'marks_equal_segments', 'marks_equal_angles', 'marks_right_angle',
    'incircle', 'incircle_touch_chain', 'a3_chain',
    # registry 1.4
    'l2a4_divide', 'l2a4_center', 'l2a4_closest', 'l2a4_at_distance', 'l2a4_vertex', 'l2a4_bisectors_lines',
    'l2a4_external_bisector', 'l2a4_ray_at_angle', 'l2a4_ray_by_vector', 'l2a4_tangents', 'l2a4_tangent_at',
    'l2a4_segment_length', 'l2a4_midline', 'l2a4_polyline', 'l2a4_circles', 'l2a4_arcs', 'l2a4_sectors',
    'l2a4_on_path_arcs', 'l2a4_regular', 'l2a4_parallelogram', 'l2a4_line_sector', 'l2a4_arc_filter',
    # registry 1.4, 1.8.1a5
    'l2a5_angle_lines', 'l2a5_angle_vectors', 'l2a5_angle_by_size', 'l2a5_number_angle', 'l2a5_measures',
    'l2a5_distance', 'l2a5_polygon_angles', 'l2a5_translate', 'l2a5_rotate', 'l2a5_reflect_line',
    'l2a5_reflect_point', 'l2a5_dilate', 'l2a5_number_expression', 'l2a5_text',
}


def scene(doc, *cases):
    return {'format': 'animageo-parity/v1', 'id': doc['documentId'], 'document': doc,
            'cases': [dict(c) for c in cases]}


def test_the_library_set():
    assert {name[:-5] for name in SCENES} == REQUIRED_SCENES
    assert sorted(p.name for p in EXPECTED_DIR.glob('*.json')) == SCENES
    for name in SCENES:
        data = read_json(SCENES_DIR / name)
        assert data['format'] == 'animageo-parity/v1'
        assert data['id'] == name[:-5]
        assert set(data) <= {'format', 'id', 'document', 'cases'}
        assert native.validate(data['document']) == [] or data['id'] == 'graph_errors'


def test_every_expected_fixture_verifies():
    files, cases, mismatches = parity.verify([EXPECTED_DIR])
    assert mismatches == []
    assert files == len(SCENES)
    assert cases >= 3 * len(SCENES)


def test_generate_reproduces_the_committed_fixtures(tmp_path):
    written = parity.generate([SCENES_DIR], tmp_path)
    assert sorted(p.name for p in written) == SCENES
    for name in SCENES:
        assert (tmp_path / name).read_bytes() == (EXPECTED_DIR / name).read_bytes(), name


def test_fixture_shape():
    for name in SCENES:
        fixture = read_json(EXPECTED_DIR / name)
        assert list(fixture) == ['format', 'id', 'registry', 'generatedBy', 'document', 'cases']
        assert fixture['registry'] == native.__registry_version__
        assert fixture['generatedBy'] == 'animageo ' + native_version()
        assert fixture['document'] == read_json(SCENES_DIR / name)['document']
        elements = set(fixture['document']['elements'])
        for case in fixture['cases']:
            assert set(case) <= {'name', 'inputs', 'scale', 'expect', 'checks'}
            assert set(case['expect']) == elements
            assert isinstance(case['scale'], float)


def native_version():
    import animageo
    return animageo.__version__


def _defined_cases_by_op():
    counts = Counter()
    for name in SCENES:
        fixture = read_json(EXPECTED_DIR / name)
        ops = fixture['document']['operations']
        elements = fixture['document']['elements']
        for case in fixture['cases']:
            seen = {ops[elements[e]['producer']['operationId']]['op']
                    for e, rec in case['expect'].items() if rec['state'] == 'defined'}
            counts.update(seen)
    return counts


def test_at_least_three_defined_cases_per_op():
    counts = _defined_cases_by_op()
    for op in native.registry().ops:
        assert counts[op] >= 3, op


def test_every_reason_is_covered():
    seen = set()
    for name in SCENES:
        for case in read_json(EXPECTED_DIR / name)['cases']:
            seen.update(rec['reason'] for rec in case['expect'].values() if rec['state'] != 'defined')
    for op, record in native.registry().ops.items():
        assert set(record['undefined']) <= seen, op
    assert {'dangling_ref', 'cycle', 'unknown_op', 'type_mismatch', 'schema'} <= seen


def test_every_case_has_its_own_scale():
    for name in ('basic_points.json', 'circle.json'):
        fixture = read_json(EXPECTED_DIR / name)
        scales = [case['scale'] for case in fixture['cases']]
        assert len(set(scales)) > 1, name          # far inputs widen the scale
        assert min(scales) == 20.0                 # default bounds [-10, -10, 10, 10]
    fixture = read_json(EXPECTED_DIR / 'intersect_lines.json')   # bounds [-8, -6, 8, 6]
    assert {case['scale'] for case in fixture['cases']} == {16.0}


class TestRefusal:
    """Inputs closer than decisionMargin * tol.decide to a threshold are refused."""

    def _two_lines(self, d):
        b = DocBuilder('near_parallel', bounds=(-10, -10, 10, 10))
        b.free('A', 0, 0).free('B', 4, 0).free('C', 0, 1).free('D', *d)
        b.line('l', 'A', 'B').line('m', 'C', 'D').intersect('X', 'l', 'm')
        return b.doc

    def test_coincident_points(self):
        b = DocBuilder('near_same').free('A', 0, 0).free('B', 1e-12, 0).line('l', 'A', 'B')
        with pytest.raises(parity.ParityError, match='coincident_points'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def test_coincident_points_beyond_the_tolerance_but_inside_the_margin(self):
        # L = 1e-7 is not degenerate (tol = 2e-9) but is within 1e3 * tol = 2e-6.
        b = DocBuilder('near_same').free('A', 0, 0).free('B', 1e-7, 0).line('l', 'A', 'B')
        assert native.evaluate(b.doc).elements['l']['state'] == 'defined'
        with pytest.raises(parity.ParityError, match='coincident_points'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def test_parallel(self):
        doc = self._two_lines((4, 1 + 1e-9))
        with pytest.raises(parity.ParityError, match='parallel'):
            parity.generate_scene(scene(doc, {'name': 'near'}))

    def test_outside_part(self):
        b = DocBuilder('near_end').free('A', 0, 0).free('B', 4, 0)
        b.free('C', 4 + 1e-9, -1).free('D', 4 + 1e-9, 1)
        b.segment('s', 'A', 'B').line('m', 'C', 'D').intersect('X', 's', 'm')
        with pytest.raises(parity.ParityError, match='outside_part'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def test_nonpositive_radius_and_zero_length(self):
        b = DocBuilder('near_zero').free('A', 0, 0).free('B', 0, 3e-10).circle('c', 'A', 'B')
        with pytest.raises(parity.ParityError, match='nonpositive_radius'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))
        b = DocBuilder('near_zero').free('A', 0, 0).free('B', 0, 3e-10).free('C', -1, 1).free('D', 1, 1)
        b.segment('s', 'A', 'B').line('m', 'C', 'D').intersect('X', 's', 'm')
        with pytest.raises(parity.ParityError, match='zero_length'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def _circle_and_line(self, y, registry_version='1.1'):
        b = DocBuilder('near_tangent', registry_version=registry_version)
        b.free('O', 0, 0).free('R', 0, 2).free('A', -3, y).free('B', 3, y)
        return b.circle('c', 'O', 'R').line('l', 'A', 'B').line_circle('P', 'Q', 'l', 'c')

    def test_tangent_line_circle(self):
        with pytest.raises(parity.ParityError, match='tangent'):
            parity.generate_scene(scene(self._circle_and_line(2 + 1e-8).doc, {'name': 'near'}))

    def test_tangent_circle_circle(self):
        b = DocBuilder('near_touch', registry_version='1.1')
        b.free('O1', 0, 0).free('R1', 2, 0).free('O2', 3 + 1e-8, 0).free('R2', 4 + 1e-8, 0)
        b.circle('c1', 'O1', 'R1').circle('c2', 'O2', 'R2').circle_circle('P', 'Q', 'c1', 'c2')
        with pytest.raises(parity.ParityError, match='tangent'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def test_concentric(self):
        b = DocBuilder('near_concentric', registry_version='1.1')
        b.free('O1', 0, 0).free('R1', 2, 0).free('O2', 1e-8, 0).free('R2', 3, 0)
        b.circle('c1', 'O1', 'R1').circle('c2', 'O2', 'R2').circle_circle('P', 'Q', 'c1', 'c2')
        with pytest.raises(parity.ParityError, match='concentric'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def test_known(self):
        # The known point K is 1e-8 off the intersection (3, 4): a near decision.
        b = DocBuilder('near_known', registry_version='1.1')
        b.free('O', 0, 0).free('R', 5, 0).free('A', -6, 4).free('B', 6, 4).free('K', 3 + 1e-8, 4)
        b.circle('c', 'O', 'R').line('l', 'A', 'B').other_than('X', 'l', 'c', 'K')
        with pytest.raises(parity.ParityError, match='known'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def test_ray_outside_part(self):
        b = DocBuilder('near_origin', registry_version='1.1')
        b.free('O', 1e-8, 0).free('P', 4, 0).free('A', 0, -3).free('B', 0, 3)
        b.ray('r', 'O', 'P').line('m', 'A', 'B').intersect('X', 'r', 'm')
        with pytest.raises(parity.ParityError, match='outside_part'):
            parity.generate_scene(scene(b.doc, {'name': 'near'}))

    def test_rounding_noise_of_an_exact_tangency_is_accepted(self):
        # Tangent at (3, 4) to the circle of radius 5: h - r is rounding noise.
        b = DocBuilder('noise', registry_version='1.1')
        b.free('O', 0, 0).free('R', 3, 4).free('A', 7, 1).free('B', -1, 7)
        b.circle('c', 'O', 'R').line('l', 'A', 'B').line_circle('P', 'Q', 'l', 'c')
        fixture = parity.generate_scene(scene(b.doc, {'name': 'oblique'}))
        assert fixture['cases'][0]['expect']['P']['detail'] == {'multiplicity': 2}

    def _angle(self, a, b):
        bld = DocBuilder('near_angle', registry_version='1.3').free('V', 0, 0).free('A', *a).free('C', *b)
        return bld.angle('g', 'A', 'V', 'C').doc

    def test_angle_wrap(self):
        # the side to A is 2.5e-9 rad above +x: a0 would jump to 2 pi just below it
        with pytest.raises(parity.ParityError, match='angle_wrap'):
            parity.generate_scene(scene(self._angle((4, 1e-8), (0, 3)), {'name': 'near'}))

    def test_zero_angle(self):
        with pytest.raises(parity.ParityError, match='zero_angle'):
            parity.generate_scene(scene(self._angle((-4, 1), (-4, 1 + 1e-8)), {'name': 'near'}))

    def test_exact_zero_angle_and_wrap_are_accepted(self):
        fixture = parity.generate_scene(scene(self._angle((4, 0), (7, 0)), {'name': 'exact'}))
        assert fixture['cases'][0]['expect']['g']['value'] == {'vertex': [0.0, 0.0], 'a0': 0.0, 'a1': 0.0,
                                                               'size': 0.0}

    def test_collinear_incircle(self):
        b = DocBuilder('near_line', registry_version='1.3').free('A', 0, 0).free('B', 4, 0).free('C', 2, 1e-7)
        with pytest.raises(parity.ParityError, match='collinear_points'):
            parity.generate_scene(scene(b.incircle('k', 'A', 'B', 'C').doc, {'name': 'near'}))

    def test_a_refused_case_is_named(self):
        b = DocBuilder('two').free('A', 0, 0).free('B', 1, 0).line('l', 'A', 'B')
        sc = scene(b.doc, {'name': 'fine'}, {'name': 'bad', 'inputs': {'B': point_input(1e-12, 0)}})
        with pytest.raises(parity.ParityError, match=r'two / bad'):
            parity.generate_scene(sc)

    def test_exact_degenerate_inputs_are_accepted(self):
        b = DocBuilder('exact').free('A', 0.5, 0.25).free('B', 0.5, 0.25).free('C', 0, 1).free('D', 4, 1)
        b.line('l', 'A', 'B').circle('c', 'A', 'B')
        b.free('E', 0, 0).free('F', 4, 0).line('m', 'E', 'F').line('n', 'C', 'D').intersect('X', 'm', 'n')
        b.free('G', 0, 0).free('H', 4, 0).segment('s', 'G', 'H').intersect('Y', 's', 'n')
        fixture = parity.generate_scene(scene(
            b.doc, {'name': 'exact'},
            {'name': 'end', 'inputs': {'C': point_input(4, -1), 'D': point_input(4, 1)}}))
        expect = fixture['cases'][0]['expect']
        assert expect['l']['reason'] == 'coincident_points'
        assert expect['c']['reason'] == 'nonpositive_radius'
        assert expect['X']['reason'] == 'parallel'
        end = fixture['cases'][1]['expect']
        assert end['Y'] == {'state': 'defined', 'type': 'point', 'value': {'x': 4.0, 'y': 0.0}}

    def test_far_inputs_are_accepted(self):
        fixture = parity.generate_scene(scene(self._two_lines((4, 1.001)), {'name': 'far'}))
        assert fixture['cases'][0]['expect']['X']['state'] == 'defined'

    def test_verify_does_not_refuse(self):
        doc = self._two_lines((4, 1.001))
        fixture = parity.generate_scene(scene(doc, {'name': 'far'}))
        fixture['cases'][0]['inputs'] = {'D': point_input(4, 1 + 1e-9)}
        mismatches = parity.verify_fixture(fixture)
        assert mismatches and not any('within' in line for line in mismatches)


class TestVerifyDetects:
    def fixture(self):
        return read_json(EXPECTED_DIR / 'segment_line.json')

    def test_a_value_beyond_tol_parity(self):
        fixture = self.fixture()
        rec = fixture['cases'][0]['expect']['A']
        rec['value']['x'] += 1e-6
        mismatches = parity.verify_fixture(fixture)
        assert len(mismatches) == 1 and 'A.value.x' in mismatches[0]

    def test_a_value_within_tol_parity(self):
        fixture = self.fixture()
        fixture['cases'][0]['expect']['A']['value']['x'] += 1e-12
        assert parity.verify_fixture(fixture) == []

    def test_state_reason_cause(self):
        fixture = self.fixture()
        case = next(c for c in fixture['cases'] if any(r['state'] != 'defined' for r in c['expect'].values()))
        el_id, rec = next((e, r) for e, r in case['expect'].items() if r['state'] != 'defined')
        for key, value in (('reason', 'parallel'), ('state', 'error'), ('cause', 'Z')):
            changed = copy.deepcopy(fixture)
            target = next(c for c in changed['cases'] if c['name'] == case['name'])
            target['expect'][el_id][key] = value
            mismatches = parity.verify_fixture(changed)
            assert any(f'{el_id}.{key}' in line for line in mismatches), (key, mismatches)

    def test_a_check_status(self):
        fixture = self.fixture()
        key = next(iter(fixture['cases'][0]['checks']))
        fixture['cases'][0]['checks'][key] = 'failed'
        assert any(key in line for line in parity.verify_fixture(fixture))

    def test_missing_and_extra_elements(self):
        fixture = self.fixture()
        expect = fixture['cases'][0]['expect']
        expect['ghost'] = expect.pop('A')
        mismatches = parity.verify_fixture(fixture)
        assert any('ghost: expected but not evaluated' in line for line in mismatches)
        assert any('A: evaluated but not expected' in line for line in mismatches)

    def test_a_scene_without_expectations(self):
        mismatches = parity.verify_fixture(read_json(SCENES_DIR / 'segment_line.json'))
        assert mismatches and all('run fixtures generate' in line for line in mismatches)

    def test_a_broken_document(self):
        fixture = self.fixture()
        del fixture['document']['operations']
        assert parity.verify_fixture(fixture)


def test_scene_shape_errors():
    b = DocBuilder('s').free('A', 0, 0)
    good = scene(b.doc, {'name': 'x'})
    for broken in (
        dict(good, format='other'),
        dict(good, id=''),
        dict(good, cases=[]),
        dict(good, cases=[{'name': 'x'}, {'name': 'x'}]),
        dict(good, cases=[{'name': 'x', 'inputs': []}]),
        dict(good, document='nope'),
    ):
        with pytest.raises(parity.ParityError):
            parity.generate_scene(broken)
    with pytest.raises(parity.ParityError, match='unknown element'):
        parity.generate_scene(dict(good, cases=[{'name': 'x', 'inputs': {'Q': point_input(1, 1)}}]))


class TestCli:
    def test_verify_green(self, capsys):
        assert main(['fixtures', 'verify', str(EXPECTED_DIR)]) == 0
        assert f'{len(SCENES)} fixtures' in capsys.readouterr().out

    def test_verify_mismatch_exit_1(self, tmp_path, capsys):
        fixture = read_json(EXPECTED_DIR / 'circle.json')
        fixture['cases'][0]['scale'] = 99.0
        path = tmp_path / 'circle.json'
        path.write_text(json.dumps(fixture), encoding='utf-8')
        assert main(['fixtures', 'verify', str(path)]) == 1
        assert 'scale' in capsys.readouterr().out

    def test_generate_and_verify(self, tmp_path, capsys):
        out = tmp_path / 'out'
        assert main(['fixtures', 'generate', str(SCENES_DIR / 'circle.json'),
                     str(SCENES_DIR / 'basic_points.json'), '-o', str(out)]) == 0
        assert sorted(p.name for p in out.iterdir()) == ['basic_points.json', 'circle.json']
        assert main(['fixtures', 'verify', str(out)]) == 0

    def test_generate_refused_exit_1(self, tmp_path, capsys):
        b = DocBuilder('near').free('A', 0, 0).free('B', 1e-12, 0).line('l', 'A', 'B')
        path = tmp_path / 'near.json'
        path.write_text(json.dumps(scene(b.doc, {'name': 'near'})), encoding='utf-8')
        out = tmp_path / 'out'
        assert main(['fixtures', 'generate', str(path), '-o', str(out)]) == 1
        assert 'refused' in capsys.readouterr().err
        assert not list(out.glob('*.json'))
