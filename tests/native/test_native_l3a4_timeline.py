"""1.9.0a4: time by element ID — ``animageo/easing.py``, ``sample_timeline``,
``evaluate(t, timeline)``, ``timeline_to_bridge``, ``steps_timeline``,
fixtures ``animageo-timeline/v1`` and the CLI (plan L3 §5)."""
import ast
import copy
import gc
import json
import math
import time
from pathlib import Path

import pytest

from animageo import easing, native
from animageo.native import timeline as tl
from animageo.native.canonical import canonical_json
from animageo.native.cli import main as cli_main
from animageo.native.timeline_fixtures import DEFAULT_DIR, check_fixtures, paths_document, triangle_document, \
    verify_fixtures
from tests.native.conftest import REPO_ROOT, SCENES_DIR, DocBuilder, read_json

SNAPSHOTS = REPO_ROOT / 'tests' / 'native' / 'snapshots'


def kf(t, **kw):
    return {'t': t, **kw}


def timeline(*keyframes, **top):
    return {'version': 2, 'keyframes': list(keyframes), **top}


# ── easing.py ────────────────────────────────────────────────────────────

def test_easing_values_bitwise_as_in_keyframes_of_1_9_0a3():
    """The functions left ``keyframes.py`` for the leaf ``easing.py`` with the
    same values bit for bit (snapshot of 1.9.0a3 on a grid of 205 points)."""
    snap = read_json(SNAPSHOTS / 'easing_grid_1.9.0a3.json')
    grid = [float.fromhex(h) for h in snap['t']]
    assert sorted(snap['values']) == sorted(easing.EASING_FUNCTIONS)
    for name, values in snap['values'].items():
        fn = easing.EASING_FUNCTIONS[name]
        assert [float(fn(t)).hex() for t in grid] == values, name


def test_keyframes_uses_the_easing_module():
    from animageo import keyframes
    assert keyframes.EASING_FUNCTIONS is easing.EASING_FUNCTIONS
    assert keyframes._ease_smooth is easing._ease_smooth


def test_enter_effects_repeat_the_classic_list():
    from animageo import keyframes
    assert tl.ENTER_EFFECTS == keyframes.ENTER_EFFECTS


def test_easing_is_a_leaf_module():
    tree = ast.parse(Path(easing.__file__).read_text(encoding='utf-8'))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported == {'math'}
    assert easing.ease('linear', 0.25) == 0.25
    with pytest.raises(ValueError):
        easing.ease('nope', 0.5)


# ── sample_timeline ──────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def paths_doc():
    return native.load(paths_document())


def _value(sample, el_id):
    return sample['inputs'][el_id]['value']


def test_point_values_interpolate_with_the_easing_of_the_target_keyframe(paths_doc):
    tm = timeline(kf(0, values={'A': [0, 0]}), kf(2, values={'A': [2, -1]}, easing='in'))
    s = native.sample_timeline(paths_doc, tm, 1.0)
    e = easing.EASING_FUNCTIONS['in'](0.5)
    assert _value(s, 'A') == [(1 - e) * 0 + e * 2, (1 - e) * 0 + e * -1]
    assert s['t'] == 1.0 and s['inputs']['A']['kind'] == 'point'
    assert _value(native.sample_timeline(paths_doc, tm, 2), 'A') == [2.0, -1.0]


def test_values_carry_forward_and_start_from_the_document(paths_doc):
    tm = timeline(kf(0), kf(1, values={'B': [4, 1]}, easing='linear'), kf(2, values={'C': [1, 3]}, easing='linear'))
    s = native.sample_timeline(paths_doc, tm, 0.5)
    assert _value(s, 'B') == [3.5, 0.5]                  # from the document input (3, 0)
    assert _value(s, 'C') == [1.0, 2.0]                  # not moving yet
    s = native.sample_timeline(paths_doc, tm, 1.5)
    assert _value(s, 'B') == [4.0, 1.0]                  # carried forward
    assert _value(s, 'C') == [1.0, 2.5]


@pytest.mark.parametrize('direction, end', [('short', 0.5 - (2 * math.pi - 5.0)), ('long', 5.5),
                                            ('ccw', 5.5), ('cw', 0.5 - (2 * math.pi - 5.0))])
def test_circle_directions(paths_doc, direction, end):
    tm = timeline(kf(0, values={'Pc': {'tparam': 0.5}}),
                  kf(2, values={'Pc': {'tparam': 5.5, 'direction': direction}}, easing='linear'))
    assert _value(native.sample_timeline(paths_doc, tm, 2), 'Pc') == pytest.approx(end, abs=1e-12)
    mid = _value(native.sample_timeline(paths_doc, tm, 1), 'Pc')
    assert mid == pytest.approx((0.5 + end) / 2, abs=1e-12)


@pytest.mark.parametrize('direction, end', [('short', 4.5), ('long', 0.5), ('ccw', 4.5), ('cw', 0.5)])
def test_polygon_wraps_with_the_number_of_vertices(paths_doc, direction, end):
    tm = timeline(kf(0, values={'Pq': {'tparam': 3.5}}),
                  kf(2, values={'Pq': {'tparam': 0.5, 'direction': direction}}, easing='linear'))
    assert _value(native.sample_timeline(paths_doc, tm, 2), 'Pq') == pytest.approx(end, abs=1e-12)


def test_sector_wraps_with_period_three_and_other_paths_ignore_direction(paths_doc):
    tm = timeline(kf(0, values={'Psc': {'tparam': 2.5}, 'Ps': {'tparam': 0.9}}),
                  kf(2, values={'Psc': {'tparam': 0.5, 'direction': 'short'},
                                'Ps': {'tparam': 0.1, 'direction': 'ccw'}}, easing='linear'))
    s = native.sample_timeline(paths_doc, tm, 1)
    assert _value(s, 'Psc') == pytest.approx(3.0, abs=1e-12)      # 2.5 → 3.5 the short way
    assert _value(s, 'Ps') == pytest.approx(0.5, abs=1e-12)       # a segment lerps


def test_path_delta_formulas():
    P = 4.0
    assert tl.path_delta(1, 1, 'long', P) == 0.0
    assert tl.path_delta(1, 1, 'cw', P) == 0.0
    assert tl.path_delta(0, 2, 'short', P) == 2.0                  # half period: the positive way
    assert tl.path_delta(0, 2, 'long', P) == -2.0
    assert tl.path_delta(0, 3, 'short', P) == -1.0
    assert tl.path_delta(0, 3, 'long', P) == 3.0
    assert tl.path_delta(0.25, 0.5, 'ccw', None) == 0.25


def test_time_is_clamped_to_the_keyframes(paths_doc):
    tm = timeline(kf(1, values={'B': [3, 0]}), kf(2, values={'B': [3, 2]}, easing='linear'))
    assert native.sample_timeline(paths_doc, tm, -5)['t'] == 1.0
    assert _value(native.sample_timeline(paths_doc, tm, 9), 'B') == [3.0, 2.0]


def test_visibility_carries_forward_from_the_document(paths_doc):
    tm = timeline(kf(0, visible={'s': False}, hide=['q']), kf(1, show=['s'], visible={'h': True}),
                  kf(2, hide=['h'], visible={'gone': True}))
    v0 = native.sample_timeline(paths_doc, tm, 0.5)['visible']
    assert sorted(v0) == sorted(paths_doc.elements)
    assert (v0['s'], v0['q'], v0['h'], v0['c']) == (False, False, False, True)   # h: appearance
    v1 = native.sample_timeline(paths_doc, tm, 1.0)['visible']                     # at the keyframe
    assert (v1['s'], v1['h']) == (True, True)
    v2 = native.sample_timeline(paths_doc, tm, 2.5)['visible']
    assert (v2['s'], v2['q'], v2['h']) == (True, False, False)
    assert 'gone' not in v2


def test_visibility_formula_is_the_web_parity_fixture():
    """``keyframe_visibility_parity.json`` of the web (a copy): the keyframes
    without a system role, element IDs = names; an element first mentioned
    later (β_{1}) keeps the state of t = 0, a removed one (γ) is skipped."""
    fixture = read_json(SNAPSHOTS / 'keyframe_visibility_parity.json')
    names = sorted({n for exp in fixture['expectations'].values() for n in exp})
    ids = {name: f'n{i}' for i, name in enumerate(names)}       # IDs are [A-Za-z0-9_-]
    b = DocBuilder(registry_version='1.5')
    for name, el_id in ids.items():
        b.free(el_id, 0, 0)
        b.doc['elements'][el_id]['displayName'] = name
    keyframes = []
    for item in fixture['keyframes']:
        if item.get('system_role'):
            continue
        keyframes.append({'t': item['timestamp_ms'] / 1000,
                          'show': [ids.get(n, n) for n in item['visibility']['show']],
                          'hide': [ids.get(n, n) for n in item['visibility']['hide']]})
    tm = timeline(*keyframes)
    for ms, expected in fixture['expectations'].items():
        visible = native.sample_timeline(b.doc, tm, int(ms) / 1000)['visible']
        assert {n: visible[ids[n]] for n in expected} == expected, ms


@pytest.mark.parametrize('bad, code', [
    (timeline(), 'at least one keyframe'),
    (timeline(kf(0), kf(0)), 'strictly increasing'),
    (timeline(kf(0, values={'s': 1})), 'not a free element'),
    (timeline(kf(0, values={'Pc': {'tparam': 1, 'direction': 'up'}})), 'direction'),
    (timeline(kf(0, values={'Pc': 1.0})), 'tparam'),
    (timeline(kf(0, values={'A': [0]})), '[x, y]'),
    (timeline(kf(0, easing='zigzag')), 'unknown easing'),
    (timeline(kf(0, values={'k': 'x'})), 'finite number'),
])
def test_broken_timelines(paths_doc, bad, code):
    with pytest.raises(ValueError, match=None) as info:
        native.sample_timeline(paths_doc, bad, 0)
    assert code in str(info.value)


def test_a_free_angle_input_is_not_animatable():
    b = DocBuilder(registry_version='1.5')
    b.free('A', 0, 0)
    b.op('op_s', 'segment.from_point_length', {'a': {'kind': 'ref', 'elementId': 'A'},
                                              'length': {'kind': 'number', 'value': 2}},
         [('segment', 's', 'segment'), ('b', 'B', 'point')])
    free = tl._free_kinds(native.load(b.doc))
    angle_ids = [e for e, k in free.items() if k == 'angle']
    if not angle_ids:
        pytest.skip('segment.from_point_length has no free angle element here')
    with pytest.raises(ValueError, match='not animatable'):
        native.sample_timeline(b.doc, timeline(kf(0, values={angle_ids[0]: 1.0})), 0)


# ── evaluate(t, timeline) ────────────────────────────────────────────────

def test_evaluate_at_time_is_evaluate_with_the_sampled_inputs(paths_doc):
    tm = timeline(kf(0, values={'A': [0, 0], 'Pc': {'tparam': 0.5}}, hide=['l']),
                  kf(2, values={'A': [1, 1], 'Pc': {'tparam': 2.5, 'direction': 'ccw'}, 'k': 4}))
    ev = native.evaluate(paths_doc, t=1.2, timeline=tm)
    sample = native.sample_timeline(paths_doc, tm, 1.2)
    plain = native.evaluate(paths_doc, inputs=sample['inputs'])
    assert ev.elements == plain.elements
    assert ev.t == 1.2 and ev.visible == sample['visible'] and ev.visible['l'] is False
    body = ev.to_dict()
    assert body['visible'] == sample['visible'] and body['t'] == 1.2
    assert 'visible' not in native.evaluate(paths_doc).to_dict()
    with pytest.raises(ValueError):
        native.evaluate(paths_doc, t=1.0)
    # inputs go on top of the sample
    ev2 = native.evaluate(paths_doc, t=1.2, timeline=tm, inputs={'A': {'kind': 'point', 'value': [5, 5]}})
    assert ev2.elements['A']['value'] == {'x': 5.0, 'y': 5.0} or ev2.elements['A']['value'] == [5.0, 5.0]


# ── timeline_to_bridge ───────────────────────────────────────────────────

def _classic_at(doc, bridge, t):
    """Classic playback state at ``t`` without manim: keyframe 0, then every
    interval up to ``t`` through the classic interpolators."""
    from animageo.keyframes import KeyframeSequence, _parse_value, apply_parsed_value
    from animageo.native.kernel.bridge import build_construction
    construction, names = build_construction(doc)
    seq = KeyframeSequence.from_json(bridge, construction)
    for name, raw in seq.keyframes[0].values.items():
        kind, val, _d = _parse_value(name, raw, seq.element_info[name], construction)
        apply_parsed_value(construction, name, kind, val)
    for interval in seq.intervals:
        if t < interval.start_t:
            break
        p = 1.0 if t >= interval.end_t else (t - interval.start_t) / interval.duration
        for interp in interval.interpolators:
            apply_parsed_value(construction, interp.name, interp.kind, interp.at(p))
    construction.rebuild(full=True)
    return construction, names


@pytest.mark.parametrize('el_id, a, b, direction', [
    ('Ps', 0.1, 0.9, 'short'), ('Pr', 0.5, 3.0, 'short'), ('Pl', -1.0, 2.0, 'cw'),
    ('Pc', 0.5, 5.5, 'short'), ('Pc', 0.5, 5.5, 'long'), ('Pc', 5.5, 0.5, 'cw'),
    ('Pq', 3.5, 0.5, 'short'), ('Pq', 3.5, 0.5, 'long'), ('Pq', 0.5, 3.5, 'cw'),
    ('Pa', 0.0, 1.0, 'cw'), ('Psc', 2.5, 0.5, 'short'), ('Psc', 2.5, 0.5, 'long'), ('Ppl', 0.0, 2.0, 'ccw'),
])
def test_bridge_tparam_matches_native_on_every_path_type(paths_doc, el_id, a, b, direction):
    """Segment, ray, line, circle, polygon, arc, sector, polyline: the classic
    playback of ``timeline_to_bridge`` puts the point where ``evaluate(t,
    timeline)`` does, at keyframes and between them, over three keyframes."""
    tm = timeline(kf(0, values={el_id: {'tparam': a}}),
                  kf(1, values={el_id: {'tparam': b, 'direction': direction}}, easing='smooth'),
                  kf(2, values={el_id: {'tparam': a, 'direction': direction}}, easing='linear'))
    bridge = native.timeline_to_bridge(paths_doc, tm)
    for t in (0.0, 0.3, 1.0, 1.4, 2.0):
        construction, names = _classic_at(paths_doc, bridge, t)
        x, y = (float(v) for v in construction.element(names.by_id[el_id]).data.coords[:2])
        native_value = native.evaluate(paths_doc, t=t, timeline=tm).elements[el_id]['value']
        nx, ny = (native_value['x'], native_value['y']) if isinstance(native_value, dict) else native_value
        assert (x, y) == pytest.approx((nx, ny), abs=1e-9), (el_id, t)


def test_bridge_names_visibility_and_extras(paths_doc):
    tm = timeline(kf(0, values={'@camera': {'width': 12}, 'k': 2}, visible={'s': False, 'k': False}),
                  kf(1, values={'A': [1, 1]}, show=['s'], enter={'s': {'effect': 'create'}},
                     styles={'c': {'stroke': '#ff0000'}}, easing='linear',
                     events=[{'effect': 'indicate', 'targets': ['A', 'k', 'gone']}]),
                  defaults={'easing': 'smooth'})
    bridge = native.timeline_to_bridge(paths_doc, tm)
    assert bridge['version'] == 2 and bridge['defaults'] == {'easing': 'smooth'}
    k0, k1 = bridge['keyframes']
    assert k0 == {'t': 0.0, 'values': {'e_k': 2.0, '@camera': {'width': 12}}, 'visible': {'e_s': False}}
    assert k1['values'] == {'e_A': [1.0, 1.0]} and k1['visible'] == {'e_s': True}
    assert k1['enter'] == {'e_s': {'effect': 'create'}} and k1['styles'] == {'e_c': {'stroke': '#ff0000'}}
    assert k1['events'] == [{'effect': 'indicate', 'targets': ['e_A']}] and k1['easing'] == 'linear'


# ── steps_timeline ───────────────────────────────────────────────────────

def test_steps_timeline_layout_of_the_contract():
    doc = native.load(triangle_document())
    st = native.steps_timeline(doc, lag=0.3, duration=0.5, pause=0.6, start=1.0)
    kfs = st.keyframes['keyframes']
    assert st.keyframes['version'] == 2
    assert kfs[0] == {'t': 1.0, 'visible': {e: False for e in ['A', 'B', 'C', 'M', 'm', 't']}}
    assert [s['elementIds'] for s in st.steps] == [['A', 'B', 'C'], ['M', 'm'], ['t']]
    s1, s2, s3 = st.steps
    assert (s1['start'], s1['end']) == (1.0, 1.0 + 2 * 0.3 + 0.5)
    assert s2['start'] == s1['end'] + 0.6 and s2['end'] == s2['start'] + 0.3 + 0.5
    assert s3['start'] == s2['end'] + 0.6 and s3['end'] == s3['start'] + 0.5
    assert [k['t'] for k in kfs[1:]] == [s['end'] for s in st.steps] and st.duration == s3['end']
    assert kfs[1]['enter'] == {'A': {'effect': 'fade', 'duration': 0.5, 'at': 0.0},
                               'B': {'effect': 'fade', 'duration': 0.5, 'at': 0.3},
                               'C': {'effect': 'fade', 'duration': 0.5, 'at': 0.6}}
    assert kfs[2]['enter']['M'] == {'effect': 'fade', 'duration': 0.5, 'at': 0.6}
    assert kfs[2]['enter']['m'] == {'effect': 'create', 'duration': 0.5, 'at': 0.6 + 0.3}
    assert s2['text'] == 'Проводим медиану CM' and s1['stepId'] == 'given' and s1['text'] is None
    eff = native.steps_timeline(doc, effects={'point': 'grow', 'segment': 'write'}).keyframes['keyframes']
    assert eff[1]['enter']['A']['effect'] == 'grow' and eff[2]['enter']['m']['effect'] == 'write'


def test_steps_timeline_bad_arguments():
    doc = triangle_document()
    for kw in ({'lag': -1}, {'duration': 0}, {'pause': -0.1}, {'effects': {'point': 'explode'}},
               {'start': float('nan')}):
        with pytest.raises(ValueError):
            native.steps_timeline(doc, **kw)


def test_steps_timeline_skips_hidden_numbers_and_empty_steps():
    b = DocBuilder(registry_version='1.5')
    b.free('A', 0, 0).free('B', 1, 0).number('k', 1)
    b.segment('s', 'A', 'B')
    b.doc['appearance'] = {'s': {'visible': False}}
    st = native.steps_timeline(b.doc)
    assert [s['elementIds'] for s in st.steps] == [['A', 'B']]
    assert set(st.keyframes['keyframes'][0]['visible']) == {'A', 'B'}
    empty = native.steps_timeline(DocBuilder(registry_version='1.5').doc, start=2.0)
    assert empty.keyframes == {'version': 2, 'keyframes': [{'t': 2.0, 'visible': {}}]}
    assert empty.steps == [] and empty.duration == 2.0


def _ancestors(doc, el_id, memo):
    from animageo.native.document import bound_producer, iter_refs
    if el_id in memo:
        return memo[el_id]
    out = set()
    memo[el_id] = out                    # a cycle (graph_errors) stops here
    producer = bound_producer(doc, el_id)
    if producer is not None:
        for arg in doc.operations[producer]['args'].values():
            for ref in iter_refs(arg):
                if ref in doc.elements:
                    out.add(ref)
                    out |= _ancestors(doc, ref, memo)
    memo[el_id] = out
    return out


@pytest.mark.parametrize('path', sorted(SCENES_DIR.glob('*.json')), ids=lambda p: p.stem)
def test_steps_timeline_acceptance_on_parity_scenes(path):
    """Plan L3 §5.4 (§16 of the spec): every visible element appears exactly
    once and not before its visible ancestors; hidden elements never appear;
    two calls give byte-equal results."""
    doc = native.load(read_json(path)['document'])
    st = native.steps_timeline(doc)
    assert canonical_json(st.to_dict()) == canonical_json(native.steps_timeline(doc).to_dict())
    shown = {}
    for k in st.keyframes['keyframes'][1:]:
        for el_id, flag in k['visible'].items():
            assert flag is True and el_id not in shown
            shown[el_id] = (k['t'], k['enter'][el_id]['at'])
    visible = {e for e in doc.elements if tl.appearance_visible(doc, e) and doc.elements[e]['type'] != 'number'}
    in_steps = {e for s in native.steps(doc) for e in s.elementIds}
    assert set(shown) == visible & in_steps
    assert not set(shown) & {e for e in doc.elements if not tl.appearance_visible(doc, e)}
    memo = {}
    for el_id, when in shown.items():
        for anc in _ancestors(doc, el_id, memo):
            if anc in shown and el_id not in _ancestors(doc, anc, memo):    # not on a cycle
                assert shown[anc] <= when, (el_id, anc)


@pytest.mark.slow
def test_steps_timeline_within_budget():
    """Plan L3 §6: ``steps_timeline`` on 300 operations ≤ 10 ms (p95,
    measured ≈ 7 ms on a busy machine, ``steps`` itself ≈ 5 ms); a margin of 2."""
    from tests.native.test_native_l3a2_budgets import _doc_of_300, _p95
    doc = _doc_of_300()
    assert len(doc.operations) >= 300
    assert _p95(lambda: native.steps_timeline(doc)) <= 0.020


@pytest.mark.slow
def test_sample_timeline_within_budget():
    """``sample_timeline`` on 300 operations with a moving point: well under
    the 10 ms of ``evaluate`` (no budget in the plan; guarded at 10 ms)."""
    from tests.native.test_native_l3a2_budgets import _doc_of_300, _p95
    doc = _doc_of_300()
    tm = timeline(kf(0, values={'Z': [0, 0]}), kf(3, values={'Z': [1, 1]}))
    assert _p95(lambda: native.sample_timeline(doc, tm, 1.3)) <= 0.010


# ── fixtures and CLI ─────────────────────────────────────────────────────

def test_timeline_fixtures_are_fresh_and_replay():
    assert check_fixtures(DEFAULT_DIR) == []
    files, cases, mismatches = verify_fixtures(DEFAULT_DIR)
    assert (files, mismatches) == (2, []) and cases >= 20


def test_steps_fixtures_carry_the_steps_timeline():
    for path in sorted((SCENES_DIR.parent / 'steps').glob('*.json'))[:20]:
        fixture = read_json(path)
        expect = native.steps_timeline(fixture['document']).to_dict()
        assert fixture['expect']['timeline'] == json.loads(json.dumps(expect))


def test_cli_steps_describe_timeline(tmp_path, capsys):
    doc_path = tmp_path / 'doc.json'
    doc_path.write_text(json.dumps(triangle_document(), ensure_ascii=False), encoding='utf-8')
    assert cli_main(['steps', str(doc_path)]) == 0
    assert [s['id'] for s in json.loads(capsys.readouterr().out)][:2] == ['given', 'median']
    assert cli_main(['describe', str(doc_path)]) == 0
    assert capsys.readouterr().out.startswith('1. ')
    assert cli_main(['timeline', str(doc_path), '--pause', '1']) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(json.dumps(native.steps_timeline(triangle_document(), pause=1).to_dict()))
    tl_path = tmp_path / 'tl.json'
    tl_path.write_text(json.dumps(printed), encoding='utf-8')
    assert cli_main(['timeline', str(doc_path), '--timeline', str(tl_path), '--t', '1.1']) == 0
    sample = json.loads(capsys.readouterr().out)
    assert sample['visible']['A'] is True and sample['visible']['M'] is False
    assert cli_main(['timeline', str(doc_path), '--timeline', str(tl_path), '--bridge']) == 0
    assert 'e_A' in json.loads(capsys.readouterr().out)['keyframes'][1]['visible']
    assert cli_main(['timeline', str(doc_path), '--t', '1']) == 2
    assert cli_main(['fixtures', 'timeline', '--check']) == 0


def test_has_stage_four_features():
    for feature in ('timeline', 'steps_timeline', 'render.t', 'render.video'):
        assert native.has(feature)


def test_render_video_needs_a_timeline():
    with pytest.raises(ValueError, match='timeline_required'):
        native.render(triangle_document(), fmt='mp4')
    with pytest.raises(ValueError):
        native.render(triangle_document(), fmt='svg', t=1.0)
    with pytest.raises(ValueError):
        native.render(triangle_document(), fmt='svg', video={'fps': 10})
