"""Registry 1.8: the chevrons a ``mark.parallel`` puts on its targets — the
transfer, the direction, the second decoration channel (plan, paint,
renderer, report, TikZ, JSXGraph)."""
import re

import pytest

from animageo import native
from animageo.native import rendering
from animageo.native.paint_fixtures import _Doc

GREEN = '#2e7d32'
PURPLE = '#9933cc'


def trapezoid(doc_id='trap'):
    d = _Doc(doc_id).free('A', 0, 0).free('B', 4, 0).free('C', 3, 2.5).free('D', 1, 2.5)
    return d.segment('s', 'A', 'B').segment('t', 'D', 'C').segment('u', 'C', 'D')


def plan_of(d, inputs=None):
    plan, diagnostics = rendering.appearance_plan(d.doc, 50.0, inputs=inputs)
    return plan, diagnostics


def test_targets_get_count_and_the_direction_of_the_first():
    d = trapezoid().parallel('p', 's', 'u', 't', count=2)
    plan, diagnostics = plan_of(d)
    assert diagnostics == []
    assert {k: plan[k]['style'].get('parallel_direction') for k in 'sut'} == \
        {'s': 'forward', 'u': 'backward', 't': 'forward'}
    assert all(plan[k]['style']['parallel_count'] == 2 for k in 'sut')
    assert plan['s']['parallelDecoration'] == {'owner': 'p', 'stroke': None}
    assert 'decoration' not in plan['s'] and 'tick_count' not in plan['s']['style']


def test_mark_overrides_turn_and_size_and_the_target_wins():
    d = trapezoid().parallel('p', 's', 'u')
    d.overrides('p', stroke=GREEN, parallel_direction='backward', parallel_count=3, parallel_size_px=11,
                parallel_shift_px=5).overrides('u', parallel_count=1, parallel_direction='backward')
    plan, diagnostics = plan_of(d)
    assert diagnostics == []
    s, u = plan['s']['style'], plan['u']['style']
    assert (s['parallel_count'], s['parallel_direction'], s['parallel_size_px'], s['parallel_shift_px']) == \
        (3, 'backward', 11, 5)
    assert (u['parallel_count'], u['parallel_direction'], u['parallel_size_px']) == (1, 'backward', 11)
    assert plan['u']['parallelDecoration'] == {'owner': 'p', 'stroke': GREEN}
    assert 'stroke' not in s


def test_other_keys_of_the_mark_are_transfers_only():
    d = trapezoid().parallel('p', 's', 'u').overrides('p', tick_count=2)
    _plan, diagnostics = plan_of(d)
    assert diagnostics == [{'code': 'style_key_ineffective', 'elementId': 'p', 'key': 'tick_count',
                            'type': 'mark.parallel', 'reason': 'mark_transfers_only'}]


def test_hidden_or_undefined_mark_puts_nothing():
    d = trapezoid().parallel('p', 's', 'u').look('p', visible=False)
    plan, _ = plan_of(d)
    assert 'parallel_count' not in plan['s']['style'] and 'parallelDecoration' not in plan['s']
    d = trapezoid().parallel('p', 's', 'u', count=4)
    plan, _ = plan_of(d)
    assert 'parallel_count' not in plan['s']['style']


def test_a_carrier_of_no_length_gives_way_to_the_next():
    d = trapezoid().parallel('p', 's', 'u', 't')
    plan, _ = plan_of(d, inputs={'B': {'kind': 'point', 'value': [0, 0]}})
    assert [plan[k]['style']['parallel_direction'] for k in 'sut'] == ['forward', 'forward', 'backward']


def test_paint_has_both_channels():
    d = trapezoid().equal_segments('m', 's', 'u', count=2).parallel('p', 's', 'u')
    d.overrides('m', stroke=PURPLE).overrides('p', stroke=GREEN, parallel_count=2)
    paint = native.resolve_paint(d.doc)
    for target, direction in (('s', 'forward'), ('u', 'backward')):
        entry = paint['elements'][target]
        assert entry['decoration']['owner'] == 'm' and entry['decoration']['color'] == PURPLE
        assert entry['decoration']['count'] == 2
        assert entry['parallelDecoration'] == {'owner': 'p', 'color': GREEN, 'count': 2, 'sizePx': 8.0,
                                               'shiftPx': 3.5, 'direction': direction}
        assert entry['parallel']['count'] == 2 and len(entry['parallel']['chevrons']) == 2
        assert entry['stroke']['color'] == '#000000'
    # the chevrons of u point the way of those of s on the sheet
    tip = lambda ch: ch[2] - ch[0]                                  # noqa: E731
    assert tip(paint['elements']['s']['parallel']['chevrons'][0]) > 0
    assert tip(paint['elements']['u']['parallel']['chevrons'][0]) > 0


def test_paint_at_t_follows_the_mark_and_the_direction():
    d = trapezoid().parallel('p', 's', 'u')
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'p': False}},
        {'t': 1, 'visible': {'p': True}},
        {'t': 2, 'values': {'C': [-1, 2.5]}, 'easing': 'linear'},
    ]}
    at = lambda t: native.resolve_paint(d.doc, t=t, timeline=timeline)['elements']['u']      # noqa: E731
    assert 'parallel' not in at(0) and 'parallelDecoration' not in at(0)
    assert at(1)['parallel']['direction'] == 'backward'
    assert at(2)['parallel']['direction'] == 'forward'


def test_style_contract_lists_the_parallel_mark():
    types = native.style_keys()['types']
    assert set(types['mark.parallel']['keys']) == {'stroke', 'parallel_count', 'parallel_direction'}
    assert types['mark.parallel']['transfers'] == ['parallel_count', 'parallel_direction', 'parallel_shift_px',
                                                   'parallel_size_px', 'stroke']
    assert types['mark.parallel']['keys']['parallel_count']['values'] == [0, 1, 2, 3]


@pytest.mark.manim
def test_renderer_tags_and_colours_each_channel():
    pytest.importorskip('manim')
    from animageo import AnimaGeoScene
    d = trapezoid().equal_segments('m', 's', 'u', count=2).parallel('p', 's', 'u')
    d.overrides('m', stroke=PURPLE).overrides('p', stroke=GREEN, parallel_count=2)
    scene = AnimaGeoScene()
    scene.loadDocument(d.doc)
    by_id = scene.native_names.by_id
    for target in ('s', 'u'):
        parts = scene.mobject(by_id[target]).submobjects
        tagged = {}
        for m in parts:
            mark = getattr(m, '_animageo_mark', None)
            if mark is not None:
                tagged.setdefault(mark, set()).add(m.get_stroke_color().to_hex().lower())
        assert tagged == {by_id['m']: {PURPLE}, by_id['p']: {GREEN}}
    assert [len(g.submobjects) for g in scene._mark_decoration_groups(by_id['p'])] == [2, 2]
    assert [len(g.submobjects) for g in scene._mark_decoration_groups(by_id['m'])] == [2, 2]
    report = rendering.build_report(scene, d.doc, fmt='svg')
    assert report['elements']['u']['parallelDecoration']['owner'] == 'p'
    assert report['elements']['u']['parallelDecoration']['direction'] == 'backward'
    assert report['elements']['u']['decoration']['owner'] == 'm'
    assert report['elements']['p']['box'] is not None


@pytest.mark.manim
def test_seek_takes_the_chevrons_off_and_back():
    pytest.importorskip('manim')
    from animageo import AnimaGeoScene
    d = trapezoid().parallel('p', 's', 'u').overrides('p', stroke=GREEN)
    scene = AnimaGeoScene()
    scene.loadDocument(d.doc)
    timeline = {'version': 2, 'keyframes': [{'t': 0, 'visible': {'p': False}}, {'t': 1, 'visible': {'p': True}}]}
    bridged = native.timeline_to_bridge(d.doc, timeline)
    name = scene.native_names.by_id['u']
    for t, count in ((1, 1), (0, 0), (1, 1)):
        scene.seek_keyframes(bridged, t)
        elem = scene.geo.element(name)
        ctx = scene._build_render_ctx(elem, True)
        assert (ctx.parallel_mark is not None) == bool(count)
        drawn = [m for m in scene.mobject(name).submobjects
                 if getattr(m, '_animageo_mark', None) is not None and m.get_stroke_opacity() > 0]
        assert len(drawn) == count


@pytest.mark.manim
def test_tikz_and_jsxgraph_colour_the_chevrons(tmp_path):
    pytest.importorskip('manim')
    from animageo import AnimaGeoScene
    d = trapezoid().parallel('p', 's', 'u').overrides('p', stroke=GREEN, parallel_count=2)
    path = tmp_path / 'p.tex'
    native.render(d.doc, fmt='tikz', out=path)
    text = path.read_text()
    color = re.search(r'\\definecolor\{([^}]+)\}\{HTML\}\{2E7D32\}', text).group(1)
    assert len(re.findall(r'\\draw\[draw=' + re.escape(color) + r'[^\]]*line join=miter\]', text)) == 4
    scene = AnimaGeoScene()
    scene.loadDocument(d.doc)
    js = scene.exportJSXGraph(output='js')
    chevrons = [line for line in js.splitlines() if '__parallel_' in line and 'strokeColor' in line]
    assert chevrons and all('#2E7D32' in line.upper() for line in chevrons)
