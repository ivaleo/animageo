"""Tests for the new StyleConfig + resolver subsystem (Phase 1).

These exercise the scaffolding only — not yet wired into AnimaGeoScene.
Verifies deep-merge semantics, builtin.json shape, and resolver priority
chain independently of the rest of the library.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from animageo.style.config import (
    BUILTIN_STYLE_PATH,
    DefaultsProfile,
    StyleConfig,
    StyleOverlay,
    deep_merge,
)
from animageo.style.resolver import (
    etype_of,
    resolve,
    resolved_style,
    trace,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

def _elem(name='A', type_name='Point', style=None):
    """Stand-in element — resolver only needs .name, .style, .data."""
    data_cls = type(type_name, (), {})
    return SimpleNamespace(name=name, style=dict(style or {}), data=data_cls())


def _scene(cfg):
    return SimpleNamespace(style_config=cfg)


# ── deep_merge ───────────────────────────────────────────────────────────

class TestDeepMerge:
    def test_adds_new_keys(self):
        assert deep_merge({'a': 1}, {'b': 2}) == {'a': 1, 'b': 2}

    def test_overrides_scalar(self):
        assert deep_merge({'a': 1}, {'a': 2}) == {'a': 2}

    def test_recursive_dict(self):
        base = {'defaults': {'point': {'size_px': 6, 'fill': '#000'}}}
        user = {'defaults': {'point': {'size_px': 10}}}
        out = deep_merge(base, user)
        assert out == {'defaults': {'point': {'size_px': 10, 'fill': '#000'}}}

    def test_list_replaces_not_concatenates(self):
        assert deep_merge({'a': [1, 2]}, {'a': [3]}) == {'a': [3]}

    def test_dict_replaced_by_scalar(self):
        assert deep_merge({'a': {'b': 1}}, {'a': 5}) == {'a': 5}

    def test_inputs_not_mutated(self):
        base = {'x': {'y': 1}}
        user = {'x': {'y': 2}}
        deep_merge(base, user)
        assert base == {'x': {'y': 1}}
        assert user == {'x': {'y': 2}}

    def test_nested_lists_in_values_deep_copied(self):
        base = {'a': {'list': [1, 2]}}
        user = {'a': {'other': 3}}
        out = deep_merge(base, user)
        out['a']['list'].append(99)
        assert base['a']['list'] == [1, 2]


# ── builtin.json sanity ──────────────────────────────────────────────────

class TestBuiltinJSON:
    def test_builtin_file_exists(self):
        assert BUILTIN_STYLE_PATH.exists(), f"missing {BUILTIN_STYLE_PATH}"

    def test_builtin_parses_as_json(self):
        with open(BUILTIN_STYLE_PATH) as f:
            data = json.load(f)
        assert 'defaults' in data
        assert 'presets' in data
        assert 'color' in data['presets']

    def test_builtin_has_core_types(self):
        with open(BUILTIN_STYLE_PATH) as f:
            data = json.load(f)
        expected = {'point', 'segment', 'line', 'ray', 'angle', 'polygon',
                    'circle', 'arc', 'vector', 'conic', 'function',
                    'implicitcurve'}
        assert expected.issubset(set(data['defaults'].keys()))

    def test_builtin_values_pixel_sized(self):
        """Sanity: key size values are in the single/double-digit pixel range."""
        cfg = StyleConfig.load()
        assert 3 < cfg.defaults.get('point', 'size_px') < 50
        assert 0.1 < cfg.defaults.get('segment', 'stroke_width_px') < 20
        assert 5 < cfg.defaults.get('angle', 'arc_size_px') < 100

    def test_builtin_defaults_are_semantic_refs(self):
        with open(BUILTIN_STYLE_PATH) as f:
            data = json.load(f)
        assert data['defaults']['point']['size_px'] == 'presets.point_size.main'
        assert data['defaults']['segment']['stroke_width_px'] == 'presets.line_width.main'
        assert data['defaults']['vector']['$include'] == ['presets.tick.main', 'presets.arrow.main']


# ── StyleConfig.load ─────────────────────────────────────────────────────

class TestStyleConfigLoad:
    def test_load_builtin_only(self):
        cfg = StyleConfig.load()
        assert isinstance(cfg, StyleConfig)
        assert 'point' in cfg.defaults.by_type
        assert cfg.presets['color']['main']

    def test_load_with_user_file_merges(self, tmp_path):
        user = {
            'defaults': {'point': {'size_px': 99}},
            'presets': {'color': {'main': '#ff0000'}},
            'reference': {'size': {'width': 500, 'height': 500}, 'source': 'manual'},
        }
        p = tmp_path / 'user.json'
        p.write_text(json.dumps(user))

        cfg = StyleConfig.load(str(p))

        assert cfg.defaults.get('point', 'size_px') == 99  # user wins
        assert cfg.presets['color']['main'] == '#ff0000'   # user wins
        # Other point defaults survive from builtin:
        assert 'fill' in cfg.defaults.by_type['point']
        # Other types survive from builtin:
        assert 'segment' in cfg.defaults.by_type
        assert cfg.reference['size']['width'] == 500

    def test_load_accepts_dict_style(self):
        cfg = StyleConfig.load({
            'reference': {'size': {'width': 320, 'height': 240}, 'source': 'manual'},
            'defaults': {'point': {'size_px': 11}},
        })
        assert cfg.reference['size']['height'] == 240
        assert cfg.defaults.get('point', 'size_px') == 11

    def test_load_user_adds_new_type(self, tmp_path):
        user = {'defaults': {'mytype': {'foo': 42}}}
        p = tmp_path / 'user.json'
        p.write_text(json.dumps(user))
        cfg = StyleConfig.load(str(p))
        assert cfg.defaults.get('mytype', 'foo') == 42
        # Builtin types still present:
        assert 'point' in cfg.defaults.by_type

    def test_semantic_defaults_choose_presets(self, tmp_path):
        user = {
            'presets': {
                'angle_radius': {'main': 21, 'shift': 2, 'right': 19},
                'tick': {'main': {'tick_width_px': 1.2, 'tick_length_px': 8, 'tick_shift_px': 3}},
                'arrow': {'main': {'arrow_width_px': 6, 'arrow_length_px': 10}},
                'font_size': {'main': 15},
            },
            'defaults': {
                'angle': {
                    'stroke_width_px': 0.9,
                    'arc_size_px': 'presets.angle_radius.main',
                    'arc_shift_px': 'presets.angle_radius.shift',
                    'right_angle_size_px': 'presets.angle_radius.right',
                    'font_size_px': 'presets.font_size.main',
                },
                'segment': {
                    '$include': 'presets.tick.main',
                },
                'vector': {
                    '$include': 'presets.arrow.main',
                },
            },
        }
        p = tmp_path / 'semantic.json'
        p.write_text(json.dumps(user))

        cfg = StyleConfig.load(str(p))

        assert cfg.presets['angle_radius']['main'] == 21
        assert cfg.defaults.get('angle', 'arc_size_px') == 21
        assert cfg.defaults.get('angle', 'arc_shift_px') == 2
        assert cfg.defaults.get('angle', 'stroke_width_px') == 0.9
        assert cfg.defaults.get('angle', 'font_size_px') == 15
        assert cfg.defaults.get('segment', 'tick_length_px') == 8
        assert cfg.defaults.get('segment', 'tick_width_px') == 1.2
        assert cfg.defaults.get('vector', 'arrow_width_px') == 6
        assert cfg.defaults.get('vector', 'arrow_length_px') == 10


class TestExampleStyles:
    def test_examples_do_not_use_legacy_presets_prefix(self):
        examples_dir = Path(__file__).resolve().parents[1] / 'examples'
        files = sorted(examples_dir.rglob('*.json'))
        assert files, f"missing example JSON files under {examples_dir}"

        for path in files:
            assert 'presets.' not in path.read_text(encoding='utf-8'), str(path)

    def test_examples_load_with_style_config(self):
        examples_dir = Path(__file__).resolve().parents[1] / 'examples'
        for path in sorted(examples_dir.rglob('*.json')):
            cfg = StyleConfig.load(str(path))
            assert isinstance(cfg, StyleConfig), str(path)


# ── semantic presets ─────────────────────────────────────────────────────

class TestSemanticPresets:
    def test_presets_color_is_canonical(self):
        cfg = StyleConfig.from_dict({'presets': {'color': {'main': '#111111'}}})
        assert cfg.presets['color']['main'] == '#111111'

    def test_presets_color_merges_with_builtin(self, tmp_path):
        user = {
            'presets': {
                'color': {'main': '#222222'},
            },
        }
        p = tmp_path / 'user.json'
        p.write_text(json.dumps(user))
        cfg = StyleConfig.load(str(p))
        assert cfg.presets['color']['main'] == '#222222'
        assert 'strong' in cfg.presets['color']

    def test_arbitrary_preset_names_resolve_in_defaults(self):
        cfg = StyleConfig.from_dict({
            'presets': {
                'color': {'answer': '#123456'},
                'line_width': {'construction': 0.5},
            },
            'defaults': {
                'segment': {
                    'stroke': 'presets.color.answer',
                    'stroke_width_px': 'presets.line_width.construction',
                },
            },
        })
        assert cfg.defaults.get('segment', 'stroke') == '#123456'
        assert cfg.defaults.get('segment', 'stroke_width_px') == 0.5

    def test_short_preset_names_resolve_without_presets_prefix(self):
        cfg = StyleConfig.from_dict({
            'presets': {
                'color': {'answer': '#123456'},
                'line_width': {'construction': 0.5},
            },
            'defaults': {
                'segment': {
                    'stroke': 'color.answer',
                    'stroke_width_px': 'line_width.construction',
                },
            },
        })
        assert cfg.defaults.get('segment', 'stroke') == '#123456'
        assert cfg.defaults.get('segment', 'stroke_width_px') == 0.5

    def test_literal_strings_that_are_not_token_paths_stay_unchanged(self):
        cfg = StyleConfig.from_dict({
            'presets': {'color': {'main': '#123456'}},
            'defaults': {
                'point': {
                    'point_shape': 'circle',
                    'label_text': 'A',
                    'stroke': 'color.missing',
                },
            },
        })
        assert cfg.defaults.get('point', 'point_shape') == 'circle'
        assert cfg.defaults.get('point', 'label_text') == 'A'
        assert cfg.defaults.get('point', 'stroke') == 'color.missing'

    def test_structural_include_merges_preset_dict(self):
        cfg = StyleConfig.from_dict({
            'presets': {
                'arrow': {
                    'main': {
                        'arrow_length_px': 11,
                        'arrow_width_px': 7.5,
                    },
                },
            },
            'defaults': {
                'vector': {
                    '$include': 'presets.arrow.main',
                    'arrow_width_px': 9,
                },
            },
        })
        assert cfg.defaults.get('vector', 'arrow_length_px') == 11
        assert cfg.defaults.get('vector', 'arrow_width_px') == 9

    def test_short_structural_include_merges_preset_dict(self):
        cfg = StyleConfig.from_dict({
            'presets': {
                'tick': {
                    'main': {
                        'tick_length_px': 8,
                        'tick_width_px': 1.2,
                    },
                },
            },
            'defaults': {
                'segment': {
                    '$include': 'tick.main',
                    'tick_width_px': 2,
                },
            },
        })
        assert cfg.defaults.get('segment', 'tick_length_px') == 8
        assert cfg.defaults.get('segment', 'tick_width_px') == 2


# ── DefaultsProfile ──────────────────────────────────────────────────────

class TestDefaultsProfile:
    def test_get_hit(self):
        prof = DefaultsProfile(by_type={'point': {'size_px': 6}})
        assert prof.get('point', 'size_px') == 6

    def test_get_miss_returns_fallback(self):
        prof = DefaultsProfile()
        assert prof.get('point', 'size_px', 99) == 99

    def test_for_type_empty_for_unknown(self):
        prof = DefaultsProfile()
        assert prof.for_type('unknown') == {}


# ── StyleOverlay ─────────────────────────────────────────────────────────

class TestStyleOverlay:
    def test_default_empty(self):
        ov = StyleOverlay()
        assert ov.per_type == {}
        assert ov.per_name == {}
        assert ov.angle_radius == {}
        assert ov.label_placement == {}


# ── etype_of ─────────────────────────────────────────────────────────────

class TestEtypeOf:
    def test_lowercases_class_name(self):
        e = _elem(type_name='Point')
        assert etype_of(e) == 'point'

    def test_compound_name(self):
        e = _elem(type_name='CircleSector')
        assert etype_of(e) == 'circlesector'

    def test_no_data_returns_unknown(self):
        e = SimpleNamespace(name='x', style={}, data=None)
        assert etype_of(e) == 'unknown'


# ── resolve priority chain ───────────────────────────────────────────────

class TestResolvePriority:
    def test_elem_style_wins(self):
        cfg = StyleConfig(
            defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}),
            overlay=StyleOverlay(per_type={'point': {'size_px': 10}},
                                 per_name={'A': {'size_px': 20}}),
        )
        e = _elem(type_name='Point', style={'size_px': 99})
        assert resolve(_scene(cfg), e, 'size_px') == 99

    def test_per_name_beats_per_type(self):
        cfg = StyleConfig(
            defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}),
            overlay=StyleOverlay(per_type={'point': {'size_px': 10}},
                                 per_name={'A': {'size_px': 20}}),
        )
        e = _elem(name='A', type_name='Point')
        assert resolve(_scene(cfg), e, 'size_px') == 20

    def test_per_type_beats_defaults(self):
        cfg = StyleConfig(
            defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}),
            overlay=StyleOverlay(per_type={'point': {'size_px': 10}}),
        )
        e = _elem(name='B', type_name='Point')
        assert resolve(_scene(cfg), e, 'size_px') == 10

    def test_defaults_as_last_resort(self):
        cfg = StyleConfig(defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}))
        e = _elem(type_name='Point')
        assert resolve(_scene(cfg), e, 'size_px') == 6

    def test_missing_returns_user_default(self):
        cfg = StyleConfig()
        e = _elem(type_name='Point')
        assert resolve(_scene(cfg), e, 'size_px', default=42) == 42
        assert resolve(_scene(cfg), e, 'nonexistent') is None

    def test_no_style_config_returns_default(self):
        e = _elem(type_name='Point', style={})
        scene_without_cfg = SimpleNamespace()
        assert resolve(scene_without_cfg, e, 'size_px', default=7) == 7

    def test_elem_style_wins_over_bare_config(self):
        """Resolver should accept a bare StyleConfig as scene-like (for tests)."""
        cfg = StyleConfig(defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}))
        e = _elem(type_name='Point', style={'size_px': 42})
        assert resolve(cfg, e, 'size_px') == 42

    def test_per_name_only_if_named(self):
        cfg = StyleConfig(
            overlay=StyleOverlay(per_name={'X': {'size_px': 99}}),
            defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}),
        )
        e = _elem(name=None, type_name='Point')
        assert resolve(_scene(cfg), e, 'size_px') == 6


# ── Preset expansion ─────────────────────────────────────────────────────

class TestPresetExpansion:
    def test_preset_ref_resolved(self):
        cfg = StyleConfig(
            presets={'color': {'main': '#123456'}},
            defaults=DefaultsProfile(by_type={'point': {'fill': 'presets.color.main'}}),
        )
        e = _elem(type_name='Point')
        assert resolve(_scene(cfg), e, 'fill') == '#123456'

    def test_preset_ref_in_elem_style(self):
        cfg = StyleConfig(presets={'color': {'accent': '#d05456'}})
        e = _elem(type_name='Point', style={'fill': 'presets.color.accent'})
        assert resolve(_scene(cfg), e, 'fill') == '#d05456'

    def test_short_preset_ref_in_elem_style(self):
        cfg = StyleConfig(presets={'color': {'accent': '#d05456'}})
        e = _elem(type_name='Point', style={'fill': 'color.accent'})
        assert resolve(_scene(cfg), e, 'fill') == '#d05456'

    def test_literal_hex_unchanged(self):
        cfg = StyleConfig(presets={'color': {'main': '#000000'}})
        e = _elem(type_name='Point', style={'fill': '#abcdef'})
        assert resolve(_scene(cfg), e, 'fill') == '#abcdef'

    def test_unresolved_preset_ref_passes_through(self):
        """If presets.X is missing, the string is returned verbatim."""
        cfg = StyleConfig(presets={})
        e = _elem(type_name='Point', style={'fill': 'presets.color.doesnotexist'})
        assert resolve(_scene(cfg), e, 'fill') == 'presets.color.doesnotexist'


# ── resolved_style (full materialisation) ────────────────────────────────

class TestResolvedStyle:
    def test_merges_all_layers(self):
        cfg = StyleConfig(
            presets={'color': {'main': '#123'}},
            defaults=DefaultsProfile(by_type={'point': {'size_px': 6, 'fill': 'presets.color.main'}}),
            overlay=StyleOverlay(per_type={'point': {'stroke': '#000'}},
                                 per_name={'A': {'size_px': 10}}),
        )
        e = _elem(name='A', type_name='Point', style={'label_text': 'A'})
        out = resolved_style(_scene(cfg), e)
        assert out == {
            'size_px': 10,                    # per_name wins
            'fill': '#123',                   # from defaults, preset-expanded
            'stroke': '#000',                 # from per_type
            'label_text': 'A',                # from elem.style
        }

    def test_empty_scene_config(self):
        cfg = StyleConfig()
        e = _elem(type_name='Point', style={'size_px': 99})
        out = resolved_style(_scene(cfg), e)
        assert out == {'size_px': 99}


# ── trace helper (debugging) ─────────────────────────────────────────────

class TestTrace:
    def test_elem_style_source(self):
        cfg = StyleConfig(defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}))
        e = _elem(type_name='Point', style={'size_px': 42})
        source, val = trace(_scene(cfg), e, 'size_px')
        assert source == 'elem.style'
        assert val == 42

    def test_defaults_source(self):
        cfg = StyleConfig(defaults=DefaultsProfile(by_type={'point': {'size_px': 6}}))
        e = _elem(type_name='Point')
        source, val = trace(_scene(cfg), e, 'size_px')
        assert source == 'defaults'
        assert val == 6

    def test_missing_source(self):
        cfg = StyleConfig()
        e = _elem(type_name='Point')
        source, val = trace(_scene(cfg), e, 'nonexistent')
        assert source == 'missing'
        assert val is None

    def test_per_type_source(self):
        cfg = StyleConfig(overlay=StyleOverlay(per_type={'point': {'fill': '#abc'}}))
        e = _elem(type_name='Point')
        source, val = trace(_scene(cfg), e, 'fill')
        assert source == 'overlay.per_type'
        assert val == '#abc'

    def test_per_name_source(self):
        cfg = StyleConfig(
            overlay=StyleOverlay(per_type={'point': {'fill': '#abc'}},
                                 per_name={'A': {'fill': '#def'}}),
        )
        e = _elem(name='A', type_name='Point')
        source, val = trace(_scene(cfg), e, 'fill')
        assert source == 'overlay.per_name'
        assert val == '#def'
