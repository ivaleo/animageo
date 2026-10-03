"""Mandatory checks: three-valued statuses, filtering, the check() wrapper."""
import math

import pytest

from animageo import native
from animageo.native.kernel import checks as kchecks
from animageo.native.kernel import ops as kernel_ops
from animageo.native.kernel.numeric import tolerances
from tests.native.conftest import DocBuilder, point_input


def full_doc():
    b = DocBuilder('checks').free('A', -4, -1).free('B', 4, 3).free('C', -3, 4).free('D', 3, -4)
    b.midpoint('M', 'A', 'B').segment('s', 'A', 'B').line('l', 'A', 'B').line('m', 'C', 'D')
    b.circle('c', 'A', 'B').intersect('X', 'l', 'm').intersect('Y', 's', 'm')
    b.polygon('poly', 'A', 'B', 'C', sides=[(1, 'pAB'), (2, 'pBC'), (3, 'pCA')])
    return b.doc


ALL_KEYS = {
    'op_M:equidistant', 'op_M:collinear', 'op_s:ends', 'op_l:through_a', 'op_l:through_b',
    'op_m:through_a', 'op_m:through_b', 'op_c:through_on_circle', 'op_X:incident_both',
    'op_Y:incident_both', 'op_poly:sides_match',
}


def test_every_registry_check_has_a_function_and_back():
    reg = native.registry()
    declared = {(op, item['id']) for op, rec in reg.ops.items() for item in rec.get('checks', [])}
    assert declared == set(kchecks.CHECKS)


def test_all_checks_pass_on_a_regular_scene():
    report = native.check(full_doc())
    assert set(report.results) == ALL_KEYS
    assert set(report.results.values()) == {'passed'}
    assert report.ok
    assert report.to_dict() == report.results
    assert all(e >= 0 and math.isfinite(e) for e in report.errors.values())


def test_checks_skip_ops_with_an_undefined_output():
    # A = B: the line, the circle and everything after them are not defined.
    report = native.check(full_doc(), inputs={'B': point_input(-4, -1)})
    assert 'op_l:through_a' not in report.results
    assert 'op_c:through_on_circle' not in report.results
    assert 'op_X:incident_both' not in report.results
    # the midpoint of coincident points and the zero segment are defined
    assert report.results['op_M:equidistant'] == 'passed'
    assert report.results['op_M:collinear'] == 'passed'
    assert report.results['op_s:ends'] == 'passed'


def test_checks_skip_ops_whose_element_is_broken():
    b = DocBuilder('broken').free('A', 0, 0).free('B', 1, 0)
    b.segment('s', 'A', 'B')
    b.doc['elements']['s']['type'] = 'line'           # type mismatch of the element
    report = native.check(b.doc)
    assert report.results == {}


def test_filter_by_key_and_by_check_id():
    doc = full_doc()
    assert set(native.check(doc, ['op_l:through_a']).results) == {'op_l:through_a'}
    assert set(native.check(doc, ['through_b']).results) == {'op_l:through_b', 'op_m:through_b'}
    assert native.check(doc, []).results == {}
    assert native.check(doc, ['op_zzz:ends']).results == {}


def test_check_report_from_evaluated():
    ev = native.evaluate(full_doc())
    assert native.run_checks(ev).results == native.check(full_doc()).results


class TestClassify:
    tol = tolerances(10.0)   # passed <= 1e-8, failed >= 1e-5

    @pytest.mark.parametrize('error, status', [
        (0.0, 'passed'),
        (1e-8, 'passed'),
        (1.0000001e-8, 'inconclusive'),
        (5e-6, 'inconclusive'),
        (1e-5, 'failed'),
        (3.0, 'failed'),
        (math.inf, 'inconclusive'),
        (math.nan, 'inconclusive'),
    ])
    def test_thresholds(self, error, status):
        assert kchecks.classify(error, self.tol) == status


def _patched(monkeypatch, op_name, shift):
    original = kernel_ops.IMPLEMENTATIONS[op_name]

    def wrong(args, ctx):
        result = original(args, ctx)
        return shift(result)

    monkeypatch.setitem(kernel_ops.IMPLEMENTATIONS, op_name, wrong)


def test_failed_when_an_implementation_is_wrong(monkeypatch):
    def shift(result):
        p = result['point']
        return {'point': {'x': p['x'] + 0.25, 'y': p['y']}}

    _patched(monkeypatch, 'point.midpoint', shift)
    report = native.check(full_doc())
    assert report.results['op_M:equidistant'] == 'failed'
    assert report.results['op_M:collinear'] == 'failed'
    assert not report.ok
    assert report.results['op_s:ends'] == 'passed'


def test_inconclusive_between_the_thresholds(monkeypatch):
    # S = 20: passed <= 2e-8, failed >= 2e-5; move the line by 1e-6.
    def shift(result):
        line = result['line']
        dx, dy = line['dir']
        px, py = line['p']
        return {'line': {'p': [px - dy * 1e-6, py + dx * 1e-6], 'dir': [dx, dy]}}

    _patched(monkeypatch, 'line.by_points', shift)
    report = native.check(full_doc())
    assert report.results['op_l:through_a'] == 'inconclusive'
    assert report.results['op_l:through_b'] == 'inconclusive'
    assert 1e-7 < report.errors['op_l:through_a'] < 1e-5


@pytest.mark.parametrize('op_name, key, shift', [
    ('segment.by_points', 'op_s:ends',
     lambda r: {'segment': dict(r['segment'], b=[r['segment']['b'][0] + 1, r['segment']['b'][1]])}),
    ('circle.center_point', 'op_c:through_on_circle',
     lambda r: {'circle': dict(r['circle'], r=r['circle']['r'] * 1.5)}),
    ('intersect.line_line', 'op_X:incident_both',
     lambda r: {'point': {'x': r['point']['x'] + 1, 'y': r['point']['y']}}),
    ('polygon.by_points', 'op_poly:sides_match',
     lambda r: dict(r, **{'side.2': dict(r['side.2'], a=[0.0, 0.0])})),
])
def test_each_check_catches_a_wrong_value(monkeypatch, op_name, key, shift):
    _patched(monkeypatch, op_name, shift)
    assert native.check(full_doc()).results[key] == 'failed'


def test_collinear_check_of_coincident_ends():
    b = DocBuilder('same').free('A', 2, 2).free('B', 2, 2).midpoint('M', 'A', 'B')
    assert native.check(b.doc).results == {'op_M:equidistant': 'passed', 'op_M:collinear': 'passed'}
