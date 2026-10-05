"""1.9.0a1: style roles of a native document (``appearance.<id>.role``,
plan L3 §2.7) — without manim."""
import json

from animageo.native.rendering import RENDER_FORMATS, appearance_plan, role_style
from animageo.style.config import StyleConfig
from animageo.style.schema import ROLE_DEFAULTS, validate_style_json
from tests.native.conftest import NATIVE_DIR, DocBuilder

BUILTIN = NATIVE_DIR.parent / 'style' / 'builtin.json'


def doc_with_roles():
    b = DocBuilder(registry_version='1.5')
    b.free('A', 0, 0).free('B', 3, 0).segment('s', 'A', 'B')
    b.doc['appearance'] = {'A': {'role': 'sought'}, 's': {'role': 'aux', 'overrides': {'stroke': '#123456'}},
                           'B': {'role': 'main'}}
    return b.doc


def test_role_defaults_are_mirrored_in_builtin_json():
    roles = json.loads(BUILTIN.read_text(encoding='utf-8'))['roles']
    roles.pop('_comment')
    assert roles == ROLE_DEFAULTS
    assert set(ROLE_DEFAULTS) == {'given', 'aux', 'sought'}
    assert StyleConfig.load(None).source['roles']['sought']['stroke'] == 'presets.color.accent'
    assert not any('roles' in w for w in validate_style_json({'roles': {}}))


def test_role_tokens_exist_in_the_builtin_presets():
    presets = StyleConfig.load(None).presets
    for role in ROLE_DEFAULTS.values():
        for value in list(role.values()) + list(role.get('point', {}).values()):
            if isinstance(value, str) and value.startswith('presets.'):
                group, name = value.split('.')[1:]
                assert name in presets[group], value


def test_role_keys_go_under_the_overrides():
    plan, diagnostics = appearance_plan(doc_with_roles(), 40.0, roles=ROLE_DEFAULTS)
    assert plan['A']['style']['fill'] == 'presets.color.accent'
    assert plan['A']['style']['size_px'] == 'presets.point_size.bold'
    assert 'stroke_width_px' not in plan['A']['style']                  # a point takes the point keys only
    assert plan['s']['style']['stroke'] == '#123456'                     # the override wins
    assert plan['s']['style']['stroke_width_px'] == 'presets.line_width.aux'
    assert plan['s']['style']['stroke_dash_ratio'] == 0.5
    assert 'fill' not in plan['B']['style'] and diagnostics == []        # an unknown role is ignored


def test_no_roles_section_ignores_the_role():
    plan, _ = appearance_plan(doc_with_roles(), 40.0, roles=None)
    assert 'size_px' not in plan['A']['style']
    plain = doc_with_roles()
    for entry in plain['appearance'].values():
        entry.pop('role')
    assert appearance_plan(plain, 40.0, roles=ROLE_DEFAULTS)[0] == appearance_plan(plain, 40.0)[0]


def test_role_style_split_and_formats():
    assert role_style(ROLE_DEFAULTS, 'aux', 'point') == {'size_px': 'presets.point_size.aux'}
    assert role_style({'aux': {'_comment': 'x', 'stroke': 'red'}}, 'aux', 'circle') == {'stroke': 'red'}
    assert role_style(None, 'aux', 'circle') == {}
    assert RENDER_FORMATS[:6] == ('svg', 'png', 'pdf', 'eps', 'tikz', 'tex')
    assert RENDER_FORMATS[6:] == ('mp4', 'gif', 'webm', 'mov')        # 1.9.0a4
