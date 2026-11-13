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
