"""Relation predicates and general_position (``native.check(relations=…, trials=…)``)."""
import hashlib
import math

import pytest

from animageo import native
from animageo.native.kernel import relations as rel
from tests.native.conftest import DocBuilder, num, point_input, ref


def B(name='rel'):
    return DocBuilder(name, registry_version='1.4')


def scene():
    """A triangle with its midpoint, circumcircle, tangent, angles and parallels."""
    b = B('relations').free('A', -4, -2).free('Q', 4, -2).free('C', 1, 4).free('P', 7, 5)
    b.midpoint('M', 'A', 'Q').segment('ab', 'A', 'Q').segment('ac', 'A', 'C').segment('bc', 'Q', 'C')
    b.line('l', 'A', 'Q').parallel('p', 'C', 'l').perpendicular('h', 'C', 'l')
    b.vector('v', 'A', 'Q')
    b.circle3('k', 'A', 'Q', 'C', center='O')
    b.perp_bisector('m1', 'A', 'Q').perp_bisector('m2', 'Q', 'C').perp_bisector('m3', 'C', 'A')
    b.on_path('T', 'k', 0.5)
    b.op('op_t', 'line.tangent_at', {'point': ref('T'), 'circle': ref('k')}, [('line', 't', 'line')])
    b.segment('ma', 'M', 'A').segment('mb', 'M', 'Q')
    b.angle('g1', 'C', 'A', 'Q').angle('g2', 'Q', 'C', 'A')
    b.circle('c2', 'C', 'Q')
    b.op('op_arc', 'arc.center_two_points', {'center': ref('O'), 'a': ref('A'), 'b': ref('Q')}, [('arc', 'w', 'arc')])
    return b.doc


def results(doc, relations, **kw):
    return native.check(doc, relations=relations, **kw)


def status(doc, predicate, *args, **kw):
    report = results(doc, [{'id': 'r', 'predicate': predicate, 'args': list(args)}], **kw)
    return report.results['relation:r']


# ── predicates ───────────────────────────────────────────────────────────

class TestPredicates:
    @pytest.mark.parametrize('predicate, args', [
        ('incident', ('A', 'k')), ('incident', ('k', 'C')), ('incident', ('M', 'ab')), ('incident', ('M', 'l')),
        ('incident', ('T', 'k')), ('incident', ('A', 'w')), ('incident', ('O', 'm1')),
        ('parallel', ('l', 'p')), ('parallel', ('ab', 'v')), ('parallel', ('h', 'm1')),
        ('perpendicular', ('l', 'h')), ('perpendicular', ('v', 'm1')),
        ('equal_length', ('ma', 'mb')),
        ('collinear', ('A', 'M', 'Q')),
        ('concyclic', ('A', 'Q', 'C', 'T')),
        ('concurrent', ('m1', 'm2', 'm3')),
        ('tangent', ('t', 'k')), ('tangent', ('k', 't')),
    ])
    def test_passed(self, predicate, args):
        assert status(scene(), predicate, *args) == 'passed'

    @pytest.mark.parametrize('predicate, args', [
        ('incident', ('P', 'k')), ('incident', ('C', 'ab')), ('incident', ('C', 'w')),
        ('parallel', ('l', 'h')), ('perpendicular', ('l', 'p')),
        ('equal_length', ('ab', 'ac')), ('equal_angle', ('g1', 'g2')),
        ('collinear', ('A', 'Q', 'C')), ('concyclic', ('A', 'Q', 'C', 'P')),
        ('concurrent', ('l', 'h', 'm3')), ('tangent', ('l', 'k')), ('tangent', ('k', 'c2')),
    ])
    def test_failed(self, predicate, args):
        report = results(scene(), [{'id': 'r', 'predicate': predicate, 'args': list(args)}])
        assert report.results['relation:r'] == 'failed'
        assert report.errors['relation:r'] > 0
        assert not report.ok

    def test_equal_angle_and_tangent_circles(self):
        b = B('iso').free('A', -3, 0).free('Q', 3, 0).free('C', 0, 5).free('O', 0, 0).free('R', 2, 0).free('S', 5, 0)
        b.angle('g1', 'Q', 'A', 'C').angle('g2', 'C', 'Q', 'A')
        b.circle('c1', 'O', 'R').circle('c2', 'S', 'R')        # radii 2 and 3, centres 5 apart
        assert status(b.doc, 'equal_angle', 'g1', 'g2') == 'passed'
        assert status(b.doc, 'tangent', 'c1', 'c2') == 'passed'

    def test_collinear_of_coincident_points(self):
        b = B('same').free('A', 1, 1).free('Q', 1, 1).free('C', 1, 1)
        assert status(b.doc, 'collinear', 'A', 'Q', 'C') == 'passed'

    def test_inconclusive_degenerate_cases(self):
        doc = scene()
        report = results(doc, [{'id': 'c', 'predicate': 'concyclic', 'args': ['A', 'M', 'Q', 'C']},
                               {'id': 'p', 'predicate': 'concurrent', 'args': ['l', 'p', 'ab']}])
        assert report.results['relation:c'] == 'failed'          # A, M, Q collinear but C is not
        b = B('flat').free('A', 0, 0).free('Q', 1, 0).free('C', 2, 0).free('D', 3, 0)
        report = results(b.doc, [{'id': 'c', 'predicate': 'concyclic', 'args': ['A', 'Q', 'C', 'D']}])
        assert report.results['relation:c'] == 'inconclusive'
        assert report.details['relation:c'] == {'reason': 'degenerate'}
        report = results(scene(), [{'id': 'p', 'predicate': 'concurrent', 'args': ['l', 'p', 'ab']}])
        assert report.results['relation:p'] == 'inconclusive'
        assert report.details['relation:p'] == {'reason': 'parallel'}

    def test_zero_length_direction(self):
        b = B('zero').free('A', 1, 1).free('Q', 1, 1).free('C', 3, 1).free('D', 4, 2)
        b.segment('s', 'A', 'Q').segment('t', 'C', 'D')
        report = results(b.doc, [{'id': 'z', 'predicate': 'parallel', 'args': ['s', 't']}])
        assert report.results['relation:z'] == 'inconclusive'
        assert report.details['relation:z'] == {'reason': 'zero_length'}

    def test_undefined_argument(self):
        doc = scene()
        report = results(doc, [{'id': 'u', 'predicate': 'incident', 'args': ['M', 'k']}],
                         inputs={'C': point_input(0, -2)})           # collinear: no circumcircle
        assert report.results['relation:u'] == 'inconclusive'
        assert report.details['relation:u'] == {'reason': 'undefined', 'elementIds': ['k']}

    @pytest.mark.parametrize('predicate, args, why', [
        ('orthocentric', ('A', 'Q'), 'unknown_predicate'),
        ('parallel', ('A', 'l'), 'type'),
        ('incident', ('A', 'Q'), 'type'),
        ('incident', ('A', 'k', 'l'), 'arity'),
        ('collinear', ('A', 'Q'), 'arity'),
        ('concyclic', ('A', 'Q', 'C'), 'arity'),
        ('equal_length', ('ab', 'l'), 'type'),
        ('tangent', ('l', 'p'), 'type'),
        ('incident', ('A', 'nowhere'), 'dangling_ref'),
    ])
    def test_unsupported(self, predicate, args, why):
        report = results(scene(), [{'id': 'r', 'predicate': predicate, 'args': list(args)}])
        assert report.results['relation:r'] == 'unsupported'
        assert report.details['relation:r']['reason'] == why
        assert 'relation:r' not in report.errors

    def test_types_decide_unsupported_before_undefined(self):
        report = results(scene(), [{'id': 'r', 'predicate': 'parallel', 'args': ['A', 'k']}],
                         inputs={'C': point_input(0, -2)})
        assert report.results['relation:r'] == 'unsupported'

    @pytest.mark.parametrize('bad', [
        {'id': 'r'}, 'no', [{'predicate': 'parallel', 'args': []}], [{'id': '', 'predicate': 'x', 'args': []}],
        [{'id': 'r', 'predicate': 'x', 'args': 'A'}], [{'id': 'r', 'predicate': 3, 'args': []}],
        [{'id': 'r', 'predicate': 'x', 'args': [1]}],
        [{'id': 'r', 'predicate': 'x', 'args': []}, {'id': 'r', 'predicate': 'x', 'args': []}], ['r'],
    ])
    def test_malformed_relations(self, bad):
        with pytest.raises(ValueError):
            native.check(scene(), relations=bad)

    def test_negative_trials(self):
        with pytest.raises(ValueError):
            native.check(scene(), trials=-1)

    def test_op_checks_stay_in_the_report(self):
        report = results(scene(), [{'id': 'r', 'predicate': 'collinear', 'args': ['A', 'M', 'Q']}])
        assert 'op_M:equidistant' in report.results and report.results['relation:r'] == 'passed'
        assert report.ok


# ── the generator and general_position ───────────────────────────────────

class TestGenerator:
    def test_splitmix64_reference(self):
        g = rel.SplitMix64(0)
        assert [g.next_u64() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]
        g = rel.SplitMix64(1234567)
        assert [g.next_u64() for _ in range(2)] == [6457827717110365317, 3203168211198807973]
        assert rel.SplitMix64(0).random() == (0xE220A8397B1DCDAF >> 11) / 2 ** 53

    def test_trial_seed(self):
        digest = hashlib.sha256('doc\0r1'.encode()).digest()
        assert rel.trial_seed('doc', 'r1') == int.from_bytes(digest[:8], 'big')
        assert rel.trial_seed('doc', '') != rel.trial_seed('doc', 'r1')

    def test_perturbed_inputs(self):
        specs = [('A', 'point', {}), ('t', 'pathParameter', {'lo': 0.0, 'hi': 1.0}),
                 ('n', 'number', {'min': 1.0, 'max': 3.0}), ('s', 'angle', {})]
        values = {'A': point_input(1, 1), 't': {'kind': 'pathParameter', 'value': 0.5, 'branch': -1},
                  'n': {'kind': 'number', 'value': 2.0}}
        out = rel.perturbed_inputs(specs, values, rel.SplitMix64(7), 0.5)
        assert math.hypot(out['A']['value'][0] - 1, out['A']['value'][1] - 1) <= 0.5
        assert 0 <= out['t']['value'] <= 1 and out['t']['branch'] == -1
        assert 1 <= out['n']['value'] <= 3
        assert 0 <= out['s']['value'] < 2 * math.pi
        assert out == rel.perturbed_inputs(specs, values, rel.SplitMix64(7), 0.5)

    @pytest.mark.parametrize('base, trials, expected', [
        (('passed', 0.0), [('passed', 0.0, {})] * 3, 'passed'),
        (('passed', 0.0), [('passed', 0.0, {}), ('failed', 1.0, {'A': 1})], 'failed'),
        (('failed', 1.0), [('passed', 0.0, {})], 'failed'),
        (('passed', 0.0), [('passed', 0.0, {}), ('undefined', None, None)], 'inconclusive'),
        (('passed', 0.0), [('inconclusive', 1e-7, {})], 'inconclusive'),
        (('inconclusive', 1e-7), [('passed', 0.0, {})], 'inconclusive'),
    ])
    def test_aggregate(self, base, trials, expected):
        got, detail = rel.aggregate(base, trials)
        assert got == expected and detail['trials'] == len(trials)
        if expected == 'failed':
            assert 'counterexample' in detail

    def test_aggregate_counterexample(self):
        _s, detail = rel.aggregate(('passed', 0.0), [('passed', 0.0, {}), ('failed', 2.0, {'A': 'x'}),
                                                     ('failed', 3.0, {})])
        assert detail == {'trials': 3, 'passed': 1, 'failed': 2, 'inconclusive': 0, 'undefined': 0,
                          'counterexample': {'trial': 2, 'error': 2.0, 'inputs': {'A': 'x'}}}


class TestGeneralPosition:
    def test_a_theorem_passes_every_trial(self):
        rels = [{'id': 'mid', 'predicate': 'collinear', 'args': ['A', 'M', 'Q']},
                {'id': 'cc', 'predicate': 'concurrent', 'args': ['m1', 'm2', 'm3']},
                {'id': 'on', 'predicate': 'concyclic', 'args': ['A', 'Q', 'C', 'T']}]
        report = results(scene(), rels, trials=8)
        for rid in ('mid', 'cc', 'on'):
            assert report.results['relation:' + rid] == 'passed'
            detail = report.details['relation:' + rid]
            assert detail['trials'] == 8 and detail['passed'] == 8 and 'counterexample' not in detail

    def test_an_accident_fails_with_a_counterexample(self):
        b = B('accident').free('A', 0, 0).free('Q', 2, 0).free('C', 4, 0)
        rels = [{'id': 'line', 'predicate': 'collinear', 'args': ['A', 'Q', 'C']}]
        assert results(b.doc, rels).results['relation:line'] == 'passed'
        report = results(b.doc, rels, trials=5)
        assert report.results['relation:line'] == 'failed'
        example = report.details['relation:line']['counterexample']
        assert example['trial'] == 1 and example['error'] > 0 and set(example['inputs']) == {'A', 'Q', 'C'}

    def test_trials_are_deterministic_and_seeded(self):
        b = B('accident').free('A', 0, 0).free('Q', 2, 0).free('C', 4, 0)
        rels = [{'id': 'line', 'predicate': 'collinear', 'args': ['A', 'Q', 'C']}]
        one = results(b.doc, rels, trials=3).details
        assert one == results(b.doc, rels, trials=3).details
        assert one == results(b.doc, rels, trials=3, seed='accident').details     # the default material
        other = results(b.doc, rels, trials=3, seed=42).details
        assert other['relation:line']['counterexample'] != one['relation:line']['counterexample']

    def test_op_checks_run_on_every_trial(self):
        report = native.check(scene(), trials=4)
        assert report.results and set(report.results.values()) == {'passed'}
        assert all(d['trials'] == 4 and d['passed'] == 4 for d in report.details.values())

    def test_unsupported_skips_the_trials(self):
        report = results(scene(), [{'id': 'r', 'predicate': 'parallel', 'args': ['A', 'l']}], trials=3)
        assert report.results['relation:r'] == 'unsupported'
        assert report.details['relation:r'] == {'reason': 'type'}

    def test_a_base_inconclusive_keeps_its_reason(self):
        b = B('flat').free('A', 0, 0).free('Q', 1, 0).free('C', 2, 0).free('D', 3, 0)
        report = results(b.doc, [{'id': 'c', 'predicate': 'concyclic', 'args': ['A', 'Q', 'C', 'D']}], trials=3)
        assert report.results['relation:c'] in ('inconclusive', 'failed')
        assert report.details['relation:c']['base'] == {'reason': 'degenerate'}

    def test_inputs_override_the_base_of_the_trials(self):
        b = B('moved').free('A', 0, 0).free('Q', 2, 0).free('C', 4, 1)
        rels = [{'id': 'line', 'predicate': 'collinear', 'args': ['A', 'Q', 'C']}]
        report = results(b.doc, rels, inputs={'C': point_input(4, 0)}, trials=2)
        assert report.details['relation:line']['counterexample']['trial'] == 1

    def test_angle_and_path_inputs_are_perturbed(self):
        b = B('inputs').free('A', 0, 0)
        b.op('op_s', 'segment.from_point_length', {'start': ref('A'), 'length': num(2)},
             [('segment', 's', 'segment'), ('end', 'E', 'point')])
        b.on_path('P', 's', 0.5)
        b.doc['inputs']['s'] = {'kind': 'angle', 'value': 0.0}
        rels = [{'id': 'on', 'predicate': 'incident', 'args': ['P', 's']},
                {'id': 'flat', 'predicate': 'collinear', 'args': ['A', 'E', 'P']}]
        report = results(b.doc, rels, trials=4)
        assert report.results['relation:on'] == 'passed' and report.results['relation:flat'] == 'passed'
        assert report.results['op_s:length'] == 'passed'
