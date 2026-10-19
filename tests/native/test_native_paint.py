"""``native.resolve_paint``: the paint of the renderer without manim, its
fixtures ``animageo-paint-parity/v1`` and the style contract ``native/style``
(P-8, P-9, 1.11.0rc3)."""
import json
import math

import pytest

from animageo import native
from animageo.native import paint, paint_fixtures
from animageo.native.paint import resolve_paint
from tests.native.test_native_style_keys import zoo


def test_the_fixtures_are_up_to_date():
    assert paint_fixtures.check_fixtures() == []
    files, cases, mismatches = paint_fixtures.verify_fixtures()
    assert mismatches == []
    assert files == len(paint_fixtures.THEMES) and cases >= 40


def test_a_fixture_case_replays():
    fixture = paint_fixtures.build_fixtures()['paint_ticks.json']
    assert fixture['format'] == 'animageo-paint-parity/v1'
    case = fixture['cases'][0]
    assert set(case) == {'name', 'document', 'style', 't', 'timeline', 'expect'}
    case['expect']['elements']['a']['ticks']['lengthPx'] += 1
    n, mismatches = paint_fixtures.verify_fixture(fixture)
    assert n == len(fixture['cases']) and len(mismatches) == 1 and 'lengthPx' in mismatches[0]


def test_the_style_contract_is_up_to_date():
    assert paint.check_style_contract() == []
    from animageo.style.config import BUILTIN_STYLE_PATH
    files = paint.style_contract_files()
    assert files['builtin.json'] == BUILTIN_STYLE_PATH.read_bytes()
    assert json.loads(files['keys.v1.json']) == native.style_keys()


def test_style_export_check(tmp_path):
    assert paint.check_style_contract(tmp_path) == [f'{tmp_path / "builtin.json"}: missing',
                                                    f'{tmp_path / "keys.v1.json"}: missing']
    paint.write_style_contract(tmp_path)
    assert paint.check_style_contract(tmp_path) == []
    (tmp_path / 'keys.v1.json').write_text('{}', encoding='utf-8')
    assert paint.check_style_contract(tmp_path) == [f'{tmp_path / "keys.v1.json"}: out of date']


class TestResolvePaint:
    def test_shape(self):
        out = resolve_paint(zoo().doc)
        assert out['format'] == 'animageo-paint/v1' and out['background'] == '#ffffff' and out['t'] is None
        assert set(out['elements']) == set(zoo().doc['elements'])
        assert {k for k, e in out['elements'].items() if not e['drawn']} == {'mk', 'ma', 'n'}
        assert out['elements']['n'] == {'type': 'number', 'styleType': 'number', 'style': None, 'drawn': False}
        assert out['order'][-1] == 't' and set(out['order']) == {k for k, e in out['elements'].items() if e['drawn']}
        assert out['elements']['q']['style'] == 'circlesector' and out['elements']['w']['style'] == 'locuscurve'

    def test_t_needs_a_timeline(self):
        with pytest.raises(ValueError, match='t and timeline'):
            resolve_paint(zoo().doc, None, 1.0)

    def test_tick_sizes_of_a_mark_reach_its_targets(self):
        b = zoo()
        b.doc['appearance'] = {'mk': {'overrides': {'tick_length_px': 14}}}
        out = resolve_paint(b.doc)['elements']
        for target in ('s', 'u'):
            ticks = out[target]['ticks']
            assert ticks['count'] == 2 and ticks['lengthPx'] == 14
            x1, y1, x2, y2 = ticks['lines'][0]
            assert math.hypot(x2 - x1, y2 - y1) == pytest.approx(14 / 100)
        assert resolve_paint(zoo().doc)['elements']['s']['ticks']['lengthPx'] == 9

    def test_an_angle_of_the_background_has_no_fill(self):
        out = resolve_paint(zoo().doc)['elements']
        assert out['alpha']['fill'] == {'color': None, 'opacity': 0.0, 'isBackground': True,
                                        'z': out['alpha']['z']}
        assert out['T']['fill']['color'] == '#ffffff' and out['T']['fill']['opacity'] == 1.0   # drawn

    def test_the_label_anchor_of_no_style_and_of_the_builtin_one(self):
        doc = zoo().doc
        builtin = json.loads(open(paint._style_dir() / 'builtin.json', encoding='utf-8').read())
        assert resolve_paint(doc)['elements']['A']['label']['anchor'] == 'BL'
        assert resolve_paint(doc, builtin)['elements']['A']['label']['anchor'] == 'BC'

    def test_a_style_track_at_t(self):
        doc = zoo().doc
        timeline = {'version': 2, 'keyframes': [{'t': 0}, {'t': 2, 'styles': {'s': {'stroke_width_px': 5}},
                                                           'easing': 'linear'}]}
        assert resolve_paint(doc, None, 1, timeline=timeline)['elements']['s']['stroke']['widthPx'] == \
            pytest.approx(3.25)


def test_command_line(tmp_path, capsys):
    from animageo.native.cli import main as cli_main
    assert cli_main(['fixtures', 'paint', '--check']) == 0
    assert '0 mismatches' in capsys.readouterr().out
    assert cli_main(['style', 'export', '--check']) == 0
    assert cli_main(['style', 'export', '-o', str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ['builtin.json', 'keys.v1.json']
    (tmp_path / 'extra.json').write_text('{}', encoding='utf-8')
    capsys.readouterr()
    assert cli_main(['style', 'export', '--check', '-o', str(tmp_path)]) == 1
    assert 'not written here' in capsys.readouterr().out
