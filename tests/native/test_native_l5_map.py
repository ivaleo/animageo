"""The table ``convert/dsl_map.json`` (kernel stage L5, plan §3.2): both directions."""
import json

from animageo.geo.lib_commands import COMMAND_REGISTRY
from animageo.native import registry
from animageo.native.cli import main
from animageo.native.convert import MAP_FORMAT, dsl_map, map_problems
from animageo.native.convert.construction import NOTE_DETAILS
from tests.native.conftest import REPO_ROOT

SEED = json.loads((REPO_ROOT / 'docs/native/seed/translate-2026-10.json').read_text(encoding='utf-8'))
# ops of stages L0–L3 a GGB command builds (the rest have no GGB command: marks, conditions, free inputs, …)
L0_L3_FROM_GGB = {
    'point.midpoint', 'segment.by_points', 'line.by_points', 'ray.by_points', 'circle.center_point',
    'circle.center_radius', 'polygon.by_points', 'polygon.regular', 'line.perpendicular', 'line.parallel',
    'line.perpendicular_bisector', 'line.angle_bisector', 'intersect.line_line', 'intersect.line_circle',
    'intersect.circle_circle', 'measure.distance', 'angle.by_points', 'point.on_path', 'transform.reflect_point',
    'transform.reflect_line', 'transform.rotate', 'transform.translate', 'transform.dilate', 'vector.by_points',
    'circle.three_points', 'arc.three_points', 'arc.center_two_points', 'sector.center_two_points',
    'line.tangents_from_point', 'locus.of_point',
}


def test_the_table_has_no_problems_with_the_seed():
    assert map_problems(seed=SEED) == []


def test_every_classic_key_has_a_row():
    table = dsl_map()
    assert table.data['format'] == MAP_FORMAT and table.version >= 1
    assert set(table.commands) == set(COMMAND_REGISTRY)
    assert table.registry == registry().version


def test_coverage():
    rows = dsl_map().commands
    ops = {r['op'] for r in rows.values() if 'op' in r}
    assert sum(1 for r in rows.values() if 'op' in r) >= 140
    assert len(ops) >= 45
    assert L0_L3_FROM_GGB <= set(registry().ops)
    assert L0_L3_FROM_GGB - ops == set()


def test_unmapped_rows_say_why_in_russian_for_the_report():
    for key, row in dsl_map().commands.items():
        if 'unmapped' in row and row.get('note') is not None:
            assert row['note'] in NOTE_DETAILS, key
    assert all(any('а' <= ch <= 'я' for ch in text) for text in NOTE_DETAILS.values())


def test_conics_and_functions_wait_for_l4():
    rows = dsl_map().commands
    for key in ('ellipse_ppp', 'parabola_pl', 'hyperbola_ppp'):
        if key in rows:
            assert rows[key].get('unmapped') == 'no_registry_op'


def test_problems_are_found_in_both_directions():
    data = json.loads(json.dumps(dsl_map().data))
    first = sorted(k for k, r in data['commands'].items() if 'op' in r)[0]
    data['commands'][first]['op'] = 'no.such.op'
    data['commands']['nope_x'] = {'factory': 'Nope', 'ggb': ['Nope'], 'unmapped': 'no_registry_op'}
    del data['commands'][sorted(data['commands'])[-1]]
    problems = map_problems(data, seed={'commands': {'Unknown': 'Unknown'}})
    text = '\n'.join(problems)
    assert 'no.such.op' in text and 'nope_x: row without a classic key' in text
    assert 'classic key without a row' in text and 'seed Unknown' in text


def test_cli_convert_map(capsys):
    assert main(['convert', 'map', '--check']) == 0
    assert capsys.readouterr().out == ''
    assert main(['convert', 'map']) == 0
    assert 'translated to' in capsys.readouterr().out
