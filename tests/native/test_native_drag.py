"""Dragging a point: ``appearance.<id>.drag.via``, ``native.drag`` and the
fixtures ``animageo-drag-parity/v1`` (docs/native/kernel.md §8.1)."""
import copy
import importlib
import math

import pytest

from animageo import native
from animageo.native.document import structure_issues
from animageo.native.drag import solve
from tests.native.conftest import DocBuilder, ref, ref_list

REG = '1.5'
drag_module = importlib.import_module('animageo.native.drag')   # ``native.drag`` is the function


def point_of(doc, inputs, el_id):
    rec = native.evaluate(doc, inputs=inputs).elements[el_id]
    assert rec['state'] == 'defined', rec
    return rec['value']['x'], rec['value']['y']


def tol_of(doc, inputs=None):
    return native.evaluate(doc, inputs=inputs).tolerances.decide_length


def via(b, el_id, *ids):
    b.doc.setdefault('appearance', {}).setdefault(el_id, {})['drag'] = {'via': ids[0] if len(ids) == 1 else list(ids)}
    return b


def parallelogram():
    b = DocBuilder('par', registry_version=REG).free('A', 0, 0).free('B', 4, 0).free('C', 5, 3)
    b.op('op_P', 'polygon.parallelogram', {'a': ref('A'), 'b': ref('B'), 'c': ref('C')},
         [('polygon', 'P', 'polygon'), ('vertex', 'D', 'point')])
    return via(b, 'D', 'C')


def reflected():
    b = DocBuilder('refl', registry_version=REG).free('A', 0, 0).free('B', 4, 0).free('C', 1, 3).free('O', 2, -1)
    b.polygon('T', 'A', 'B', 'C')
    b.op('op_T1', 'transform.reflect_point', {'obj': ref('T'), 'point': ref('O')},
         [('image', 'T1', 'polygon'), ('vertex.1', 'A1', 'point'), ('vertex.2', 'B1', 'point'),
          ('vertex.3', 'C1', 'point')])
    via(b, 'A1', 'A')
    via(b, 'B1', 'B')
    return via(b, 'C1', 'C')


def on_segment(t=0.25):
    """``P`` on segment ``AB``; ``Q`` is ``P`` reflected in ``O`` (dragged by the parameter of ``P``)."""
    b = DocBuilder('seg', registry_version=REG).free('A', 0, 0).free('B', 4, 0).free('O', 2, 1)
    b.segment('s', 'A', 'B').on_path('P', 's', t)
    b.op('op_Q', 'transform.reflect_point', {'obj': ref('P'), 'point': ref('O')}, [('image', 'Q', 'point')])
    return via(b, 'Q', 'P')


def on_circle():
    b = DocBuilder('circ', registry_version=REG).free('O', 0, 0).free('R', 3, 0).free('C', 1, 1)
    b.circle('k', 'O', 'R').on_path('P', 'k', 0.5)
    b.midpoint('M', 'P', 'C')
    return via(b, 'M', 'P')


def midpoint_two():
    b = DocBuilder('mid', registry_version=REG).free('A', 0, 0).free('B', 4, 2).midpoint('M', 'A', 'B')
    return via(b, 'M', 'A', 'B')


def incenter():
    b = DocBuilder('inc', registry_version=REG).free('A', 1, 3).free('B', 0, 0).free('C', 4, 0)
    b.op('op_I', 'triangle.incenter', {'a': ref('A'), 'b': ref('B'), 'c': ref('C')}, [('point', 'I', 'point')])
    return via(b, 'I', 'A')


def foot():
    b = DocBuilder('foot', registry_version=REG).free('P', 1, 3).free('B', -2, -1).free('C', 5, 1)
    b.line('l', 'B', 'C').perpendicular('m', 'P', 'l').intersect('F', 'm', 'l')
    return via(b, 'F', 'P')


# ── native.drag: statuses ────────────────────────────────────────────────


class TestDirect:
    def test_free_point_goes_to_the_target(self):
        b = parallelogram()
        inputs = {'B': {'kind': 'point', 'value': [4, 0]}}
        before = copy.deepcopy(inputs)
        out = native.drag(b.doc, inputs, 'A', (0.5, -1.25))
        assert out['status'] == 'ok'
        assert out['inputs'] is not inputs and inputs == before
        assert out['inputs'] == {'B': {'kind': 'point', 'value': [4, 0]}, 'A': {'kind': 'point', 'value': [0.5, -1.25]}}

    def test_point_on_path_is_projected(self):
        b = on_segment()
        out = native.drag(b.doc, {}, 'P', (3, 2))
        assert out == {'status': 'ok', 'inputs': {'P': {'kind': 'pathParameter', 'value': 0.75}}}

    def test_projection_beyond_the_end_is_clamped(self):
        b = on_segment()
        out = native.drag(b.doc, None, 'P', (6, 1))
        assert out == {'status': 'clamped', 'inputs': {'P': {'kind': 'pathParameter', 'value': 1.0}}}

    def test_projection_at_the_end_is_ok(self):
        b = on_segment()
        assert native.drag(b.doc, {}, 'P', (4, 0))['status'] == 'ok'

    def test_projection_keeps_the_branch(self):
        b = on_segment()
        inputs = {'P': {'kind': 'pathParameter', 'value': 0.25, 'branch': -1}}
        out = native.drag(b.doc, inputs, 'P', (1, 5))
        assert out['inputs']['P'] == {'kind': 'pathParameter', 'value': 0.25, 'branch': -1}

    def test_dependent_point_without_via_is_refused(self):
        b = parallelogram()
        del b.doc['appearance']
        with pytest.raises(ValueError):
            native.drag(b.doc, {}, 'D', (1, 1))

    @pytest.mark.parametrize('el_id, target', [('ghost', (0, 0)), ('P', (0, 0)), ('D', (math.nan, 0)),
                                               ('D', (1, 2, 3)), ('D', 'xy')])
    def test_bad_arguments(self, el_id, target):
        with pytest.raises(ValueError):
            native.drag(parallelogram().doc, {}, el_id, target)

    def test_bad_inputs_are_refused(self):
        with pytest.raises(ValueError):
            native.drag(parallelogram().doc, {'D': {'kind': 'point', 'value': [0, 0]}}, 'D', (1, 1))


class TestVia:
    @pytest.mark.parametrize('make, el_id, target, moved', [
        (parallelogram, 'D', (1.5, 4), 'C'),
        (reflected, 'A1', (3.25, -2.5), 'A'),
        (reflected, 'C1', (0, 0), 'C'),
    ])
    def test_affine_dependencies_take_one_step(self, make, el_id, target, moved):
        b = make()
        inputs = {}
        result = solve(b.doc, inputs, el_id, target)
        assert result.status == 'ok' and result.iterations == 1
        assert result.residual <= 1e-12 * native.evaluate(b.doc).tolerances.scale
        assert set(result.inputs) == {moved}
        x, y = point_of(b.doc, result.inputs, el_id)
        assert math.hypot(x - target[0], y - target[1]) <= tol_of(b.doc)
        assert solve(b.doc, inputs, el_id, target, max_iterations=1).status == 'ok'

    def test_parallelogram_moves_c_only(self):
        b = parallelogram()
        out = native.drag(b.doc, {}, 'D', (1.5, 4))
        assert out['status'] == 'ok'
        cx, cy = out['inputs']['C']['value']
        # D = A + C − B → C = D − A + B
        assert abs(cx - 5.5) <= 1e-11 and abs(cy - 4) <= 1e-11

    def test_reflection_moves_a_to_the_mirror_of_the_target(self):
        b = reflected()
        out = native.drag(b.doc, {}, 'A1', (3.25, -2.5))
        ax, ay = out['inputs']['A']['value']
        assert abs(ax - 0.75) <= 1e-11 and abs(ay - 0.5) <= 1e-11

    def test_two_inputs_take_the_least_motion(self):
        b = midpoint_two()
        out = native.drag(b.doc, {}, 'M', (3, 3))
        assert out['status'] == 'ok'
        (ax, ay), (bx, by) = out['inputs']['A']['value'], out['inputs']['B']['value']
        # M moves by (1, 2): the least-norm change moves A and B by the same (1, 2)
        for got, want in ((ax, 1), (ay, 2), (bx, 5), (by, 4)):
            assert abs(got - want) <= 1e-11

    def test_path_parameter_reaches_the_nearest_point(self):
        b = on_circle()
        target = (4, 4)
        out = native.drag(b.doc, {}, 'M', target)
        assert out['status'] == 'ok'
        t = out['inputs']['P']['value']
        assert 0 <= t < 2 * math.pi
        # M = (P + C)/2 runs on the circle of centre (0.5, 0.5) and radius 1.5: the nearest point
        # to (4, 4) lies on the ray from the centre towards it
        assert abs(t - math.pi / 4) <= 1e-9
        x, y = point_of(b.doc, out['inputs'], 'M')
        assert abs(math.hypot(x - 0.5, y - 0.5) - 1.5) <= 1e-12

    @pytest.mark.parametrize('t0', [0.3, 1, 2, 3, 4, 5, 6])
    @pytest.mark.parametrize('target', [(4, 4), (0.4, 0.45), (0.5, -1), (-5, 0.5), (100, -100)])
    def test_curved_path_from_any_start(self, t0, target):
        """One curved parameter far from the target or near the centre: the Newton length
        of the step reaches the nearest point in the iteration budget from any start."""
        b = on_circle()
        out = native.drag(b.doc, {'P': {'kind': 'pathParameter', 'value': t0}}, 'M', target)
        assert out['status'] == 'ok'
        want = math.atan2(target[1] - 0.5, target[0] - 0.5) % (2 * math.pi)
        got = out['inputs']['P']['value']
        assert abs((got - want + math.pi) % (2 * math.pi) - math.pi) <= 1e-8

    def test_farthest_point_is_not_a_solution(self):
        """The target straight across the circle from the point: the step is zero, the
        point is the farthest one, the drag is refused."""
        b = on_circle()
        inputs = {'P': {'kind': 'pathParameter', 'value': 0}}
        out = native.drag(b.doc, inputs, 'M', (-5, 0.5))
        assert out['status'] == 'no_convergence' and out['inputs'] is inputs
        # the centre: every point is the nearest
        out = native.drag(b.doc, inputs, 'M', (0.5, 0.5))
        assert out['status'] == 'ok' and out['inputs'] == inputs

    def test_newton_length(self):
        b = on_circle()
        problem = drag_module._Problem(native.load(b.doc), {}, 'M', ['P'])
        p = problem.point(problem.u0)
        cols, curvature = problem.jacobian(problem.u0, p)
        # M = (0.5, 0.5) + 1.5 (cos t, sin t): |J|² = 2.25, f'' = −(M − centre)
        assert abs(cols[0][0] ** 2 + cols[0][1] ** 2 - 2.25 * problem.vars[0].c ** 2) <= 1e-8
        assert abs(curvature[0] + (p[0] - 0.5)) <= 1e-4 and abs(curvature[1] + (p[1] - 0.5)) <= 1e-4
        # the target beyond the circle: r·f'' = 1.5·(|d| − 1.5) > 0 shortens the step
        far = (0.5 + 4.5 * math.cos(1.5), 0.5 + 4.5 * math.sin(1.5))
        r = (p[0] - far[0], p[1] - far[1])
        delta, moved, _ = drag_module._step(problem, cols, problem.u0, r)
        length = drag_module._length(problem, cols, curvature, r, moved)
        b_term = r[0] * curvature[0] + r[1] * curvature[1]
        assert length == pytest.approx(2.25 / (2.25 + b_term), rel=1e-6) and length < 1
        # a straight path: no curvature, the plain step
        seg = on_segment()
        problem = drag_module._Problem(native.load(seg.doc), {}, 'Q', ['P'])
        p = problem.point(problem.u0)
        cols, curvature = problem.jacobian(problem.u0, p)
        r = (p[0] - 2.5, p[1] - 2)
        assert drag_module._length(problem, cols, curvature, r, 1.0) == 1.0
        # two variables: the plain step
        two = midpoint_two()
        problem = drag_module._Problem(native.load(two.doc), {}, 'M', ['A', 'B'])
        p = problem.point(problem.u0)
        cols, curvature = problem.jacobian(problem.u0, p)
        assert drag_module._length(problem, cols, curvature, (1, 1), 1.0) == 1.0

    def test_interactive_drag_stays_ok(self):
        """A pointer that moves a little at a time, each drag from the inputs of the last one."""
        import random
        for make, el_id, step, inside in (
                (incenter, 'I', 0.15, lambda q: q[1] > 0.02 and math.hypot(q[0] - 2, q[1]) < 1.97),
                (on_circle, 'M', 0.4, lambda q: True)):
            b = make()
            rnd = random.Random(7)
            inputs = {}
            for _ in range(150):
                x, y = point_of(b.doc, inputs, el_id)
                target = (x + rnd.uniform(-step, step), y + rnd.uniform(-step, step))
                if not inside(target):
                    continue
                out = native.drag(b.doc, inputs, el_id, target)
                assert out['status'] == 'ok', (make.__name__, inputs, target)
                inputs = out['inputs']

    def test_path_parameter_inside_the_reach_is_exact(self):
        b = on_segment()
        out = native.drag(b.doc, {}, 'Q', (2.5, 2))
        assert out == {'status': 'ok', 'inputs': {'P': {'kind': 'pathParameter', 'value': pytest.approx(0.375, abs=1e-12)}}}

    def test_path_parameter_stops_at_the_end(self):
        b = on_segment()
        out = native.drag(b.doc, {}, 'Q', (-3, 2))
        assert out['status'] == 'clamped'
        assert out['inputs'] == {'P': {'kind': 'pathParameter', 'value': 1.0}}

    def test_wrapped_parameter_is_normalised(self):
        b = on_circle()
        inputs = {'P': {'kind': 'pathParameter', 'value': 0.5 + 4 * math.pi}}
        out = native.drag(b.doc, inputs, 'M', (0.5, -3))
        assert out['status'] == 'ok'
        assert abs(out['inputs']['P']['value'] - 1.5 * math.pi) <= 1e-9

    def test_success_never_changes_the_input(self):
        b = midpoint_two()
        inputs = {'A': {'kind': 'point', 'value': [0, 0]}, 'X': 'kept'}
        before = copy.deepcopy(inputs)
        with pytest.raises(ValueError):
            native.drag(b.doc, inputs, 'M', (1, 1))      # 'X' is not an element
        del inputs['X']
        before = copy.deepcopy(inputs)
        out = native.drag(b.doc, inputs, 'M', (1, 1))
        assert out['status'] == 'ok' and inputs == before
        assert out['inputs'] is not inputs and out['inputs']['A'] is not inputs['A']


class TestRefusals:
    @pytest.mark.parametrize('make, el_id, target, status', [
        (incenter, 'I', (2, 2.5), 'no_convergence'),
        (foot, 'F', (0, 3), 'singular'),
        (foot, 'F', point_of(foot().doc, {}, 'F'), 'singular'),
    ])
    def test_refusal_returns_the_same_inputs(self, make, el_id, target, status):
        b = make()
        inputs = {'B': copy.deepcopy(b.doc['inputs']['B'])}
        before = copy.deepcopy(inputs)
        out = native.drag(b.doc, inputs, el_id, target)
        assert out['status'] == status
        assert out['inputs'] is inputs
        assert inputs == before

    def test_reachable_incenter_converges(self):
        b = incenter()
        out = native.drag(b.doc, {}, 'I', (1.8, 1.2))
        assert out['status'] == 'ok'
        x, y = point_of(b.doc, out['inputs'], 'I')
        assert math.hypot(x - 1.8, y - 1.2) <= tol_of(b.doc)

    def test_undefined_at_rest_is_no_convergence(self):
        b = incenter()
        inputs = {'A': {'kind': 'point', 'value': [2, 0]}}            # A on BC: no triangle
        out = native.drag(b.doc, inputs, 'I', (1, 1))
        assert out == {'status': 'no_convergence', 'inputs': inputs} and out['inputs'] is inputs


# ── validate ─────────────────────────────────────────────────────────────


def issues_of(doc):
    return [(i.code, i.path, i.severity) for i in native.validate(doc) if i.path.startswith('/appearance')]


class TestValidate:
    @pytest.mark.parametrize('make', [parallelogram, reflected, on_segment, on_circle, midpoint_two, incenter])
    def test_good_hints(self, make):
        assert native.validate(make().doc) == []

    def test_singular_hint_is_a_warning(self):
        assert issues_of(foot().doc) == [('drag_singular', '/appearance/F/drag/via', 'warning')]

    def test_via_not_free(self):
        b = parallelogram()
        b.midpoint('M', 'A', 'B').midpoint('N', 'M', 'C')
        via(b, 'N', 'M')
        assert issues_of(b.doc) == [('drag_via_not_free', '/appearance/N/drag/via', 'error')]

    def test_via_not_upstream(self):
        b = parallelogram()
        b.free('E', 7, 7)
        via(b, 'D', 'C', 'E')
        assert issues_of(b.doc) == [('drag_via_not_upstream', '/appearance/D/drag/via/1', 'error')]

    def test_free_point_has_no_upstream(self):
        b = parallelogram()
        via(b, 'A', 'B')
        assert issues_of(b.doc) == [('drag_via_not_upstream', '/appearance/A/drag/via', 'error')]

    def test_itself_is_not_upstream(self):
        b = on_segment()
        via(b, 'P', 'P')
        assert issues_of(b.doc) == [('drag_via_not_upstream', '/appearance/P/drag/via', 'error')]

    def test_unknown_via_is_a_dangling_ref(self):
        b = parallelogram()
        via(b, 'D', 'C', 'ghost')
        assert issues_of(b.doc) == [('dangling_ref', '/appearance/D/drag/via/1', 'error')]

    def test_unknown_or_non_point_owner(self):
        b = parallelogram()
        via(b, 'ghost', 'C')
        via(b, 'P', 'C')
        assert issues_of(b.doc) == [('type_mismatch', '/appearance/P/drag', 'error'),
                                    ('dangling_ref', '/appearance/ghost/drag', 'error')]

    def test_drag_with_a_bad_hint_is_refused(self):
        b = parallelogram()
        b.free('E', 7, 7)
        via(b, 'D', 'E')
        with pytest.raises(ValueError):
            native.drag(b.doc, {}, 'D', (1, 1))

    @pytest.mark.parametrize('drag', [None, 'C', [], {}, {'via': 3}, {'via': []}, {'via': ['C', 'C']},
                                      {'via': ['C', 4]}, {'via': 'bad id'}, {'via': 'C', 'mode': 'x'}])
    def test_bad_shape_is_schema(self, drag):
        b = parallelogram()
        b.doc['appearance']['D']['drag'] = drag
        assert [i.code for i in structure_issues(b.doc)] == ['schema']
        assert {i.code for i in native.validate(b.doc)} == {'schema'}

    def test_documents_without_drag_never_reach_the_drag_checks(self, monkeypatch):
        from tests.native.conftest import SCENES_DIR, read_json

        def boom(doc):
            raise AssertionError('drag checks ran')
        monkeypatch.setattr(drag_module, 'drag_issues', boom)
        b = parallelogram()
        del b.doc['appearance']
        native.validate(b.doc)
        for path in sorted(SCENES_DIR.glob('*.json')):
            native.validate(read_json(path)['document'])

    def test_evaluate_ignores_the_hint(self):
        b = parallelogram()
        plain = copy.deepcopy(b.doc)
        del plain['appearance']
        assert native.evaluate(b.doc).elements == native.evaluate(plain).elements


# ── features, fixtures ───────────────────────────────────────────────────


def test_has_drag():
    assert native.has('drag') and 'drag' in native.FEATURES and 'drag' in native.__all__
    assert callable(native.drag)

