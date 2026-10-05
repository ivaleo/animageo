"""Keys and IDs of the translator (kernel stage L5, plan §3.3): ``uuid5(id_namespace, key)``,
phantoms by structure, repeats, stability against an inserted line."""
import uuid

import pytest

from animageo import native
from animageo.native.convert.keys import KeyMaker, element_id, make_id, namespace_of, operation_id
from tests.native.test_native_l5_convert import NS, SCENE, _constr


def test_keys():
    assert make_id(NS, 'x') == str(uuid.uuid5(NS, 'x'))
    assert element_id(NS, 'dsl:A') == make_id(NS, 'el:dsl:A')
    assert operation_id(NS, 'dsl:A') == make_id(NS, 'op:dsl:A')
    assert namespace_of(str(NS)) == NS
    with pytest.raises(TypeError):
        namespace_of(5)
    km = KeyMaker('ggb', {'P_1': 'P₁'})
    assert km.named('P_1') == 'ggb:P₁' and km.named('Q') == 'ggb:Q'
    assert KeyMaker.is_phantom('_12') and not KeyMaker.is_phantom('_a') and not KeyMaker.is_phantom('A')
    k1 = km.phantom('_1', 'midpoint_pp', ['ggb:A', 'ggb:B'], 0)
    k2 = km.phantom('_2', 'midpoint_pp', ['ggb:A', 'ggb:B'], 0)
    assert k1 == 'anon:midpoint_pp(ggb:A,ggb:B)#0' and k2 == k1 + '~2'
    assert km.phantom('_1', 'other', [], 0) == k1 and km.key_of('_2') == k2


def test_ids_are_stable_and_namespaced():
    d1, _ = native.from_construction(_constr(SCENE), id_namespace=NS)
    d2, _ = native.from_construction(_constr(SCENE), id_namespace=str(NS))
    assert native.dumps(d1) == native.dumps(d2)
    d3, _ = native.from_construction(_constr(SCENE), id_namespace=uuid.uuid4())
    assert set(d1['elements']).isdisjoint(d3['elements'])
    # a line added above keeps every other ID
    d4, _ = native.from_construction(_constr('Z = Point(9, 9)\n' + SCENE), id_namespace=NS)
    assert set(d1['elements']) <= set(d4['elements'])
    assert set(d1['operations']) <= set(d4['operations'])


def test_phantom_keys_follow_the_structure():
    # Midpoint(Point(0, 0), …) makes phantoms: their keys come from the command and its inputs
    code = 'A = Point(0, 0)\nM = Midpoint(A, Point(4, 0))\nN = Midpoint(A, Point(4, 0))\n'
    d1, r1 = native.from_construction(_constr(code), id_namespace=NS)
    d2, r2 = native.from_construction(_constr('Z = Point(5, 5)\n' + code), id_namespace=NS)
    keys1 = {e['key'] for e in r1['elements']}
    assert any(k.startswith('anon:point_ii(') and k.endswith('~2') for k in keys1)
    assert keys1 <= {e['key'] for e in r2['elements']}
    assert set(d1['elements']) <= set(d2['elements'])
