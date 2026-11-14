"""Registry 1.8: the version a document needs and the writers that declare it."""
import json

import pytest

from animageo import native
from animageo.native.registry import registry, registry_problems
from tests.native.conftest import NATIVE_DIR, DocBuilder, ref

OPS_DIR = NATIVE_DIR / 'ops' / 'v1'


def test_version():
    assert native.__registry_version__ == '1.12'
    assert registry().version == '1.12'
    assert json.loads((OPS_DIR / 'INDEX.json').read_text())['registryVersion'] == '1.12'
    assert registry_problems() == []


def _school(version):
    b = DocBuilder('school', registry_version=version).free('A', 0, 0).free('B', 4, 0).free('C', 0, 3)
    b.polygon('T', 'A', 'B', 'C')
    b.op('op_e', 'line.euler', {'polygon': ref('T')}, [('line', 'e', 'line')])
    return b


def test_min_registry_version_is_the_newest_need():
    assert native.min_registry_version(DocBuilder('empty').doc) == '1.0'
    b = DocBuilder('plain').free('A', 0, 0).free('B', 1, 0).segment('s', 'A', 'B')
    assert native.min_registry_version(b.doc) == '1.0'
    b.number('r', 2)
    assert native.min_registry_version(b.doc) == '1.2'
    assert native.min_registry_version(_school('1.0').doc) == '1.7'
    assert native.min_registry_version(native.load(_school('1.0').doc, strict=False)) == '1.7'


def test_validate_refuses_an_operation_newer_than_declared():
    issues = native.validate(_school('1.6').doc)
    assert [(i.code, i.severity, i.path, i.operationId) for i in issues] == [
        ('needs_newer_registry', 'error', '/operations/op_e/op', 'op_e')]
    assert '1.7' in issues[0].message
    assert native.validate(_school('1.7').doc) == []


def test_an_unknown_op_stays_a_warning():
    b = DocBuilder('magic', registry_version='1.6').free('A', 0, 0)
    b.op('op_m', 'point.magic', {'p': ref('A')}, [('point', 'm', 'point')])
    assert [i.code for i in native.validate(b.doc)] == ['unknown_op']


def test_edit_raises_the_declared_version_only_as_needed():
    def scene(version):
        b = DocBuilder('edit', registry_version=version).free('A', 0, 0).free('B', 4, 0).free('C', 1, 3)
        return b.segment('s', 'A', 'B').midpoint('M', 'A', 'C').doc
    foot = {'op': 'point.projection', 'args': {'point': ref('C'), 'base': ref('s')}}
    new, _ = native.redefine(scene('1.1'), 'op_M', foot, slot_map={'point': 'foot'})
    assert new.data['operationRegistryVersion'] == '1.2'
    new, _ = native.redefine(scene('1.7'), 'op_M', foot, slot_map={'point': 'foot'})
    assert new.data['operationRegistryVersion'] == '1.7'
    new, _ = native.redefine(scene('1.1'), 'op_M', {'op': 'point.midpoint', 'args': {'a': ref('B'), 'b': ref('C')}})
    assert new.data['operationRegistryVersion'] == '1.1'


def test_parse_commands_declares_the_minimum():
    from animageo.native.commands import parse_commands
    doc = parse_commands('A = (0, 0)\nB = (4, 0)\ns = Отрезок(A, B)').document
    assert doc.data['operationRegistryVersion'] == '1.0'
    assert native.validate(doc) == []


@pytest.mark.parametrize('version', ['1.1', '1.6', '1.7'])
def test_older_documents_keep_evaluating(version):
    b = DocBuilder('old', registry_version=version).free('A', 0, 0).free('B', 4, 0)
    b.circle('c', 'A', 'B').circle('d', 'B', 'A').circle_circle('P', 'Q', 'c', 'd')
    ev = native.evaluate(b.doc)
    assert ev.elements['P']['state'] == 'defined'
    assert native.validate(b.doc) == []


def test_a_suppressed_parallel_mark_needs_registry_1_8():
    b = DocBuilder('sup').free('A', 0, 0).free('B', 4, 0)
    assert native.min_registry_version(b.doc) == '1.0'
    b.doc['suppressedMarks'] = [{'source': 'c1', 'kind': 'right_angle'}]
    assert native.min_registry_version(b.doc) == '1.0'
    b.doc['suppressedMarks'].append({'source': 'c1', 'kind': 'parallel'})
    assert native.min_registry_version(b.doc) == '1.8'
