"""Registry 1.8: the automatic ``mark.parallel`` of a ∥ condition
(docs/native/conditions.md §6)."""
import pytest

from animageo import native
from animageo.native.conditions.apply import apply_condition, release_condition, shape_conditions
from animageo.native.conditions.marks import add_auto_marks, auto_sources
from animageo.native.edit import delete
from tests.native.conftest import DocBuilder


def pair(p, q):
    return {'pair': [p, q]}


def base(segments=True):
    b = DocBuilder('par-auto', registry_version='1.7', bounds=(-6, -4, 6, 4))
    b.free('A', -3, -2).free('B', 3, -1.5).free('C', -2, 1).free('D', 2, 2.5)
    if segments:
        b.segment('s', 'A', 'B').segment('t', 'C', 'D')
    return b


def parallel(doc, a=('A', 'B'), b=('C', 'D'), receiver='D', **kw):
    r = apply_condition(doc, {'statement': {'kind': 'parallel', 'a': pair(*a), 'b': pair(*b)},
                              'mode': 'construct', 'source': 'panel'}, receiver=receiver, **kw)
    assert r.refusal is None
    return r


def marks_of(doc, op='mark.parallel'):
    data = doc.data if hasattr(doc, 'data') else doc
    return [op_ for op_ in data['operations'].values() if op_['op'] == op]


def items(op):
    return [x['elementId'] for x in op['args']['lines']['items']]


def test_a_parallel_condition_marks_its_two_segments():
    r = parallel(base().doc)
    (mark,) = marks_of(r.document)
    assert items(mark) == ['s', 't'] and mark['args']['count'] == {'kind': 'number', 'value': 1}
    el = r.document.elements[mark['outputs'][0]['elementId']]
    assert el['origin'] == {'kind': 'auto', 'source': r.condition['id']}
    assert r.document.data['operationRegistryVersion'] == '1.8'
    assert native.check(r.document).results[mark['id'] + ':parallel'] == 'passed'
    assert r.condition['id'] in auto_sources(r.document)


def test_without_segments_the_mark_takes_hidden_helpers():
    r = parallel(base(segments=False).doc)
    (mark,) = marks_of(r.document)
    helpers = items(mark)
    assert len(helpers) == 2
    for h in helpers:
        assert r.document.data['appearance'][h] == {'visible': False, 'role': 'aux'}
        assert r.document.elements[h]['origin']['kind'] == 'auto'


def test_segment_of_chooses_the_lines():
    def segment_of(data, p, q):
        return {frozenset('AB'): 't', frozenset('CD'): 's'}.get(frozenset((p, q)))
    r = parallel(base().doc, segment_of=segment_of)
    assert items(marks_of(r.document)[0]) == ['t', 's']


def test_marks_off_without_marks():
    assert marks_of(parallel(base().doc, marks=False).document) == []


def test_suppressed_parallel_gives_nothing_and_a_second_call_adds_none():
    r = parallel(base().doc)
    cid = r.condition['id']
    again = add_auto_marks(r.document, [cid])
    assert again.operations == []
    data = r.document.data
    for op_ in marks_of(data):
        data = delete(native.load(data), [op_['outputs'][0]['elementId']]).document.data
    data['suppressedMarks'] = [{'source': cid, 'kind': 'parallel'}]
    assert add_auto_marks(data, [cid]).operations == []
    data['suppressedMarks'] = [{'source': cid, 'kind': 'equal_segments'}]
    assert len(add_auto_marks(data, [cid]).operations) == 1


def test_classes_one_count_per_direction():
    b = base()
    b.free('E', -4, -3).free('F', -1, 3).free('G', 1, -3).free('H', 3, 3)
    doc = parallel(b.doc).document
    doc = parallel(doc, ('A', 'B'), ('E', 'F'), receiver='F').document     # the same direction as AB
    doc = parallel(doc, ('A', 'C'), ('G', 'H'), receiver='H').document     # another direction
    counts = [m['args']['count']['value'] for m in sorted(marks_of(doc), key=lambda m: m['seq'])]
    assert counts == [1, 1, 2]


def test_classes_wrap_at_a_half_turn():
    """Directions θ and θ + π are one class."""
    b = DocBuilder('wrap', registry_version='1.8', bounds=(-6, -4, 6, 4))
    b.free('A', 0, 0).free('B', 4, -1e-9).free('C', 0, 1).free('D', -4, 1 - 1e-9)
    b.free('E', 0, 2).free('F', 4, 2 + 1e-9)
    doc = parallel(b.doc, receiver='D').document
    doc = parallel(doc, ('C', 'D'), ('E', 'F'), receiver='F').document
    assert sorted(m['args']['count']['value'] for m in marks_of(doc)) == [1, 1]


def test_release_takes_the_mark_and_its_helpers():
    r = parallel(base(segments=False).doc)
    before = set(r.document.elements)
    out = release_condition(r.document, r.condition['id'])
    auto = {e for e in before if (r.document.elements[e].get('origin') or {}).get('kind') == 'auto'}
    assert len(auto) == 3
    assert not (auto & set(out.document.elements))
    assert marks_of(out.document) == []


def test_parallelogram_shape_gets_two_classes():
    b = DocBuilder('pg', registry_version='1.7', bounds=(-6, -4, 6, 4))
    for name, x, y in (('A', -3, -2), ('B', 3, -1.5), ('C', 2.5, 2.2), ('D', -2.2, 1.8)):
        b.free(name, x, y)
    b.op('op_T', 'polygon.by_points', {'vertices': {'kind': 'list', 'items': [
        {'kind': 'ref', 'elementId': p} for p in 'ABCD']}}, [('polygon', 'T', 'polygon')])
    cur = b.doc
    for item in shape_conditions(cur, 'T', 'parallelogram'):
        cur = apply_condition(cur, {'statement': item['statement'], 'mode': 'construct', 'source': 'shape',
                                    'shapeId': 'T'}, receiver=item['receiver']).document
    assert sorted(m['args']['count']['value'] for m in marks_of(cur)) == [1, 2]


@pytest.mark.parametrize('kind', ['perpendicular', 'tangent'])
def test_other_statements_make_no_parallel_mark(kind):
    from animageo.native.conditions.marks import _condition_requests
    st = {'kind': kind, 'a': pair('A', 'B'), 'b': pair('C', 'D')}
    assert _condition_requests({'statement': st}, 'parallel') == []
