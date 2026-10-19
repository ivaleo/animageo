"""G2: axes and grid of the view (``viewDefaults.axes``/``grid``, registry 1.6)."""
import copy
import json

import pytest

from animageo import native
from animageo.native.document import structure_issues
from animageo.native.view import nice_step, number_text, view_layout, view_settings
from tests.native.conftest import NATIVE_DIR, DocBuilder, read_json

SCHEMA_PATH = NATIVE_DIR / 'schema' / 'construction.v1.schema.json'


def doc_with(view=None, bounds=(-10, -10, 10, 10)):
    b = DocBuilder('view', bounds=bounds, registry_version='1.1')
    b.free('A', 1, 2).free('B', 4, 3).segment('s', 'A', 'B')
    if view:
        b.doc['viewDefaults'].update(view)
    return b.doc


VALID = [
    {'axes': {}},
    {'axes': {'show': True, 'numbers': False, 'step': 0.5, 'labels': {'x': 't', 'y': ''}}},
    {'axes': {'show': False, 'step': None}},
    {'grid': {}},
    {'grid': {'kind': 'none'}},
    {'grid': {'kind': 'major_minor', 'step': 2}},
    {'axes': {'step': 1}, 'grid': {'kind': 'major', 'step': None}},
]
INVALID = [
    {'axes': []},
    {'axes': {'show': 1}},
    {'axes': {'numbers': 'yes'}},
    {'axes': {'step': 0}},
    {'axes': {'step': -1}},
    {'axes': {'step': '1'}},
    {'axes': {'labels': {'z': 'z'}}},
    {'axes': {'labels': {'x': 1}}},
    {'axes': {'labels': {'x': 'x' * 33}}},
    {'axes': {'ticks': True}},
    {'grid': 'major'},
    {'grid': {'kind': 'dots'}},
    {'grid': {'step': 0}},
    {'grid': {'kind': 'major', 'color': 'red'}},
]


@pytest.mark.parametrize('view', VALID, ids=lambda v: json.dumps(v)[:40])
def test_structure_accepts(view):
    assert structure_issues(doc_with(view)) == []


@pytest.mark.parametrize('view', INVALID, ids=lambda v: json.dumps(v)[:40])
def test_structure_rejects(view):
    issues = structure_issues(doc_with(view))
    assert issues and {i.code for i in issues} == {'schema'}


def test_json_schema_agrees():
    jsonschema = pytest.importorskip('jsonschema')
    validator = jsonschema.Draft202012Validator(read_json(SCHEMA_PATH))
    for view in VALID:
        assert list(validator.iter_errors(doc_with(view))) == [], view
    for view in INVALID:
        assert list(validator.iter_errors(doc_with(view))), view


def test_nice_step():
    assert [nice_step(v) for v in (2, 1.5, 0.3, 0.07, 12, 49, 51, 1)] == [2, 2, 0.5, 0.1, 20, 50, 100, 1]


def test_settings_defaults():
    assert view_settings(doc_with()) is None
    assert view_settings(doc_with({'axes': {'show': False}, 'grid': {'kind': 'none'}})) is None
    s = view_settings(doc_with({'axes': {}}))
    assert s == {'axes': {'show': True, 'numbers': True, 'step': 2.0, 'labels': {'x': 'x', 'y': 'y'}},
                 'grid': {'kind': 'none', 'step': 2.0}}
    s = view_settings(doc_with({'grid': {}}, bounds=(-3, -1, 3, 1)))
    assert s['axes']['show'] is False and s['grid'] == {'kind': 'major', 'step': 1.0}
    s = view_settings(doc_with({'axes': {'step': 0.25}, 'grid': {'kind': 'major_minor'}}))
    assert s['grid'] == {'kind': 'major_minor', 'step': 0.25}


def test_layout():
    s = view_settings(doc_with({'axes': {'labels': {'y': ''}}, 'grid': {'kind': 'major_minor'}}))
    out = view_layout(s, (-5, -3, 5, 3))
    assert out['axes'] == {'x': True, 'y': True}
    assert out['grid']['major'] == {'x': [-4, -2, 2, 4], 'y': [-2, 2]}
    assert len(out['grid']['minor']['x']) == 25 - 5 and 0.4 in out['grid']['minor']['x']
    assert out['ticks'] == {'x': [-4, -2, 2, 4], 'y': [-2, 2]}
    assert out['numbers']['x'][0] == [-4, '−4']
    assert out['labels'] == {'x': 'x', 'y': None}
    # the origin outside: no axes, the grid keeps its line at 0
    out = view_layout(s, (1, 1, 5, 3))
    assert out['axes'] == {'x': False, 'y': False} and out['ticks'] == {'x': [], 'y': []}
    assert out['grid']['major'] == {'x': [2, 4], 'y': [2]}
    grid_only = view_settings(doc_with({'grid': {}}))
    out = view_layout(grid_only, (-3, -3, 3, 3))
    assert out['grid']['major']['x'] == [-2, 0, 2] and out['numbers'] == {'x': [], 'y': []}


def test_layout_thins_too_many_lines():
    s = view_settings(doc_with({'grid': {'step': 0.001}}))
    out = view_layout(s, (-10, -10, 10, 10))
    assert len(out['grid']['major']['x']) <= 401


def test_number_text():
    assert [number_text(v) for v in (2, -2, 0.5, -1.25, 1e-7)] == ['2', '−2', '0.5', '−1.25', '1e−07']


def test_style_keys_list_the_view_keys():
    keys = native.style_keys()
    view = keys['view']['keys']
    assert {'axes_color', 'axes_width_px', 'axes_opacity', 'axes_font_size_px', 'axes_tick_length_px',
            'grid_color', 'grid_width_px', 'grid_opacity', 'grid_minor_width_px', 'grid_minor_opacity'} == set(view)
    assert view['axes_color']['default'] == '#808080' and view['grid_color']['default'] == '#cccccc'
    assert view['axes_width_px']['unit'] == 'px'


# ── rendering (manim) ───────────────────────────────────────────────────

def _render(doc, tmp_path, name, fmt='svg'):
    pytest.importorskip('manim')
    out = native.render(doc, out=tmp_path / f'{name}.{fmt}', fmt=fmt, report=False)
    return (tmp_path / f'{name}.{fmt}').read_bytes(), out


@pytest.mark.manim
def test_no_axes_is_byte_identical(tmp_path):
    plain, _ = _render(doc_with(), tmp_path, 'plain')
    off, _ = _render(doc_with({'axes': {'show': False}, 'grid': {'kind': 'none'}}), tmp_path, 'off')
    assert plain == off


@pytest.mark.manim
def test_axes_and_grid_are_drawn(tmp_path):
    plain, _ = _render(doc_with(), tmp_path, 'plain')
    axes, _ = _render(doc_with({'axes': {}, 'grid': {'kind': 'major_minor'}}), tmp_path, 'axes')
    assert plain != axes
    assert axes.count(b'<path') > plain.count(b'<path') + 20


@pytest.mark.manim
def test_axes_in_tikz(tmp_path):
    plain, _ = _render(doc_with(), tmp_path, 'plain', fmt='tikz')
    axes, _ = _render(doc_with({'axes': {'labels': {'x': 't'}}, 'grid': {}}), tmp_path, 'axes', fmt='tikz')
    assert b'grid' not in plain
    text = axes.decode('utf-8')
    assert '% grid' in text and '% axes' in text and '$t$' in text and '$-2$' in text
