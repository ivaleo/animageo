"""A sampled locus as a path (registry 1.10)."""
import math

import pytest

from animageo import native
from animageo.native.kernel import paths
from animageo.native.registry import registry
from tests.native.conftest import DocBuilder, path_input, ref
from tests.native.test_native_l3a1_ops import segment_locus


def locus_doc(t=0.25):
    b = segment_locus(DocBuilder('locus-path', registry_version='1.10'))
    b.op('op_Q', 'point.on_path', {'path': ref('g')}, [('point', 'Q', 'point')])
    b.doc['inputs']['Q'] = path_input(t)
    return b.doc


def test_locus_path_requires_registry_1_10_without_changing_old_signatures():
    reg = registry()
    assert reg.member_since('path', 'locus') == '1.10'
    assert reg.get('point.on_path')['since'] == '1.1'
    doc = locus_doc()
    assert native.min_registry_version(doc) == '1.10'
    assert native.validate(doc) == []
    doc['operationRegistryVersion'] = '1.9'
    assert [(i.code, i.elementId) for i in native.validate(doc)] == [('needs_newer_registry', 'g')]


@pytest.mark.parametrize('t,xy', [(-2, (.5, 0)), (0, (.5, 0)), (.25, (1.25, .375)), (1, (3.5, 1.5)),
                                 (2, (3.5, 1.5))])
def test_point_on_locus_has_a_normalized_continuous_parameter(t, xy):
    doc = locus_doc(t)
    state = native.evaluate(doc).elements['Q']
    assert state['state'] == 'defined', state
    assert (state['value']['x'], state['value']['y']) == pytest.approx(xy)
    assert set(native.check(doc).results.values()) == {'passed'}


def frame(points, closed=False, scale=100):
    return paths.frame('locus', {'points': points, 'range': [0, 1], 'closed': closed}, scale=scale)


def test_locus_parameter_is_the_fraction_of_the_sample_index_not_length():
    f = frame([[0, 0], [1, 0], [1, 3]])
    assert paths.point_at(f, .25) == {'x': .5, 'y': 0}
    assert paths.point_at(f, .75) == {'x': 1, 'y': 1.5}


def test_closed_locus_has_a_closing_link_and_clamps():
    f = frame([[0, 0], [1, 0], [1, 1]], closed=True)
    assert paths.point_at(f, 5 / 6) == pytest.approx({'x': .5, 'y': .5})
    assert paths.point_at(f, 1) == paths.point_at(f, 2) == {'x': 0, 'y': 0}


def test_null_and_far_samples_do_not_interpolate_across_breaks():
    f = frame([[0, 0], [.1, 0], None, [1, 0], [1.1, 0], [4, 0], [4.1, 0]], scale=1)
    assert paths.point_at(f, 1 / 12) == pytest.approx({'x': .05, 'y': 0})
    assert paths.point_at(f, .25) is None
    assert paths.point_at(f, .75) is None
    assert paths.point_at(f, .5) == {'x': 1, 'y': 0}


@pytest.mark.parametrize('points,reason', [([], 'empty_locus'), ([None] * 3, 'empty_locus'),
                                         ([[1, 2]], 'degenerate_locus'),
                                         ([[1, 2]] * 3, 'degenerate_locus')])
def test_empty_or_stationary_locus_has_an_explicit_reason(points, reason):
    assert paths.locus_reason(frame(points)) == reason


def test_stationary_locus_point_is_undefined_in_the_kernel():
    doc = locus_doc()
    # The midpoint of P and its reflection is constant but still depends on P.
    b = DocBuilder('constant', registry_version='1.10')
    b.doc = doc
    b.op('op_R', 'transform.reflect_point', {'obj': ref('P'), 'point': ref('A')}, [('image', 'R', 'point')])
    doc['operations']['op_M']['args'] = {'a': ref('P'), 'b': ref('R')}
    state = native.evaluate(doc).elements['Q']
    assert state['state'] == 'undefined' and state['reason'] == 'degenerate_locus', state


def test_projection_and_drag_use_the_same_locus_parameter():
    doc = locus_doc()
    for xy in [(1.625, .5625), (2, 1), (-2, -1), (5, 3)]:
        t = native.project(doc, 'g', xy)
        result = native.drag(doc, {}, 'Q', xy)
        assert t is not None and result['inputs']['Q']['value'] == pytest.approx(t)
        state = native.evaluate(doc, inputs=result['inputs']).elements['Q']
        assert state['state'] == 'defined'
    assert native.project(doc, 'Q', (1.625, .5625)) == pytest.approx(.375)
    assert native.drag(doc, {}, 'Q', (-2, -1))['status'] == 'clamped'


def test_projection_uses_scene_scale_for_large_sample_links():
    doc = locus_doc()
    # Each link is about 1.3 units: visible at scene scale 850, hidden at scale 1.
    doc['inputs']['C'] = {'kind': 'point', 'value': [600, 300]}
    assert native.project(doc, 'g', (150, 75)) is not None
    result = native.drag(doc, {}, 'Q', (150, 75))
    assert result['status'] == 'ok'


def test_incidence_and_condition_projection_use_the_locus_scene_scale():
    doc = locus_doc()
    doc['inputs']['C'] = {'kind': 'point', 'value': [600, 300]}
    b = DocBuilder()
    b.doc = doc
    b.free('Z', 150, 75)
    rel = {'id': 'on', 'predicate': 'incident', 'args': ['Q', 'g']}
    assert native.check(doc, relations=[rel]).results['relation:on'] == 'passed'
    out = native.apply_condition(doc, {'statement': {'kind': 'on', 'point': {'ref': 'Z'},
                                  'object': {'ref': 'g'}}, 'mode': 'construct', 'source': 'panel'},
                                 receiver='Z', marks=False)
    assert out.refusal is None, out.refusal


def test_incidence_on_an_undefined_locus_point_is_inconclusive():
    doc = locus_doc()
    doc['inputs']['C'] = doc['inputs']['B']
    rel = {'id': 'on', 'predicate': 'incident', 'args': ['Q', 'g']}
    assert native.check(doc, relations=[rel]).results['relation:on'] == 'inconclusive'


def test_projection_on_broken_locus_selects_nearest_run_and_smallest_parameter():
    f = frame([[0, 0], [1, 0], None, [0, 2], [1, 2]])
    assert paths.project(f, .5, 1, 1e-9) == pytest.approx(.125)
    assert paths.project(f, .5, 1.9, 1e-9) == pytest.approx(.875)
    assert paths.project(frame([None, None]), 0, 0, 1e-9) is None
    assert paths.project(frame([[1, 2]] * 3), 1, 2, 1e-9) is None


def test_drag_and_project_input_on_a_stationary_locus_have_no_projection():
    doc = locus_doc()
    doc['inputs']['C'] = doc['inputs']['B']
    assert native.project_input(doc, 'g', (2, 3)) is None
    out = native.drag(doc, {}, 'Q', (2, 3))
    assert out['status'] == 'no_convergence' and out['inputs'] == {}


def test_closest_point_on_a_locus_and_dragging_a_dependent_point():
    doc = locus_doc()
    b = DocBuilder('closest', registry_version='1.10')
    b.doc = doc
    b.free('Z', 2, 1)
    b.op('op_F', 'point.closest', {'path': ref('g'), 'point': ref('Z')}, [('foot', 'F', 'point')])
    b.midpoint('D', 'Q', 'Z')
    state = native.evaluate(doc).elements['F']
    assert state['state'] == 'defined', state
    assert native.project(doc, 'g', (2, 1)) == pytest.approx(8 / 15)
    doc.setdefault('appearance', {})['D'] = {'drag': {'via': ['Q']}}
    result = native.drag(doc, {}, 'D', (2.1875, .96875))
    assert result['status'] == 'ok', result
    assert result['inputs']['Q']['value'] == pytest.approx(.625, abs=1e-6)


def test_classic_bridge_keeps_locus_sample_indices_in_the_inverse():
    from animageo.native.kernel.bridge import build_construction
    doc = locus_doc()
    doc['inputs']['C'] = {'kind': 'point', 'value': [600, 300]}
    construction, names = build_construction(doc)
    construction.rebuild(full=True)
    q = names.by_id['Q']
    target = (150, 75)
    t = native.project(doc, 'g', target)
    assert construction.tparam_from_coords(q, target) == pytest.approx(t)
    construction.update_tparam(q, t)
    construction.rebuild(full=True)
    value = native.evaluate(doc, inputs={'Q': path_input(t)}).elements['Q']['value']
    assert construction.element(q).data.coords == pytest.approx([value['x'], value['y']])


def test_classic_bridge_inverse_does_not_compress_null_samples():
    from animageo.native.curves_fixtures import _locus_scenes
    from animageo.native.kernel.bridge import build_construction
    doc = _locus_scenes()[1][0].doc
    construction, names = build_construction(doc)
    construction.rebuild(full=True)
    value = native.evaluate(doc).elements['Q']['value']
    target = value['x'], value['y']
    assert construction.tparam_from_coords(names.by_id['Q'], target) == pytest.approx(.75, abs=1e-9)


def test_classic_bridge_locus_uses_the_current_scale_after_a_free_point_moves():
    from animageo.geo.lib_elements import Point
    from animageo.native.kernel.bridge import build_construction
    doc = locus_doc()
    construction, names = build_construction(doc)
    construction.rebuild(full=True)
    construction.update(names.by_id['C'], Point([60000, 30000]))
    construction.rebuild(full=True)
    value = native.evaluate(doc, inputs={'C': {'kind': 'point', 'value': [60000, 30000]}}).elements['Q']['value']
    q = construction.element(names.by_id['Q']).data
    assert q is not None
    assert q.coords == pytest.approx([value['x'], value['y']])
    assert construction.tparam_from_coords(names.by_id['Q'], q.coords) == pytest.approx(.25)


def test_closed_locus_kernel_point_and_projection_match_the_closing_link():
    doc = locus_doc()
    b = DocBuilder('closed', registry_version='1.10')
    b.doc = doc
    b.circle('c', 'A', 'C')
    doc['operations']['op_P']['args']['path'] = ref('c')
    doc['inputs']['Q'] = path_input(1 - .5 / 256)
    ev = native.evaluate(doc)
    pts = ev.elements['g']['value']['points']
    target = [(pts[-1][k] + pts[0][k]) / 2 for k in (0, 1)]
    assert ev.elements['Q']['value'] == pytest.approx(dict(zip(('x', 'y'), target)))
    assert native.project(doc, 'Q', target) == pytest.approx(1 - .5 / 256, abs=1e-9)
