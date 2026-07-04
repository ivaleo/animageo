"""End-to-end tests for loadGGB with ImportPolicy.

Validates that the full AnimaGeoScene.loadGGB pipeline correctly threads
an ImportPolicy through applyStyle, and that policy overrides land in the
resolver-visible GGB import layer.
"""
import os
import json

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.style.import_policy import ImportPolicy
from animageo.style.resolver import resolve as resolve_style


FIXTURE = os.path.join(
    os.path.dirname(__file__),
    '..',
    'examples',
    '0_sample_scenes',
    'scene.ggb',
)
GRID_FIXTURE = os.path.join(
    os.path.dirname(__file__),
    '..',
    'examples',
    'test',
    'sector.ggb',
)
STYLE_FILE = os.path.join(
    os.path.dirname(__file__),
    '..',
    'style',
    'default.json',
)


def _require_fixture():
    if not os.path.isfile(FIXTURE):
        pytest.skip(f'Fixture not found: {FIXTURE}')
    if not os.path.isfile(STYLE_FILE):
        pytest.skip(f'Style file not found: {STYLE_FILE}')


def _new_scene():
    return AnimaGeoScene()


class TestLoadggbFaithfulPath:
    """Without an explicit policy, behavior must be byte-for-byte identical
    to pre-ImportPolicy (faithful default)."""

    def test_point_A_size_applies_import_point_size(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(FIXTURE, style=STYLE_FILE, export={"size": [800, 600]})
        # scene.ggb: point A pointSize=5; style/default.json maps raw 5
        # through import.point_size to presets.point_size.main.
        assert resolve_style(s, s.geo.element('A'), 'size_px') == pytest.approx(2.8346456692916)

    def test_import_point_size_custom_style(self, tmp_path):
        _require_fixture()
        style = {
            'presets': {
                'point_size': {'main': 11},
            },
            'import': {
                'point_size': {'5': 'presets.point_size.main'},
            },
        }
        style_path = tmp_path / 'point_size.json'
        style_path.write_text(json.dumps(style))
        s = _new_scene()
        s.loadGGB(FIXTURE, style=str(style_path), export={"size": [800, 600]})
        assert resolve_style(s, s.geo.element('A'), 'size_px') == 11
        assert resolve_style(s, s.geo.element('D'), 'size_px') == 8

    def test_import_disabled_uses_defaults_and_preserves_raw(self, tmp_path):
        _require_fixture()
        style = {
            'defaults': {
                'point': {
                    'size_px': 12,
                    'fill': '#111111',
                    'stroke': '#222222',
                    'label_visible': True,
                },
                'segment': {
                    'stroke_width_px': 4,
                    'stroke': '#333333',
                },
            },
            'overlay': {
                'per_name': {
                    'A': {'size_px': 21},
                },
            },
            'import': {
                'enabled': False,
                'colors': {'#1565c0': '#ff0000'},
                'point_size': {'5': 99},
                'line_width': {'2.5': 99},
                'policy': {
                    'size_px': 77,
                    'stroke_width_px': 88,
                    'fill': '#ff00ff',
                },
            },
        }
        style_path = tmp_path / 'import_disabled.json'
        style_path.write_text(json.dumps(style))

        s = _new_scene()
        s.loadGGB(FIXTURE, style=str(style_path), export={"size": [800, 600]})

        point_a = s.geo.element('A')
        point_d = s.geo.element('D')
        seg_c = s.geo.element('c')

        assert point_a.ggb_raw['point_size'] == 5
        assert point_d.ggb_raw['point_size'] == 4
        assert 'fill' not in point_d.style
        assert 'size_px' not in point_d.style
        assert resolve_style(s, point_a, 'size_px') == 21
        assert resolve_style(s, point_a, 'fill') == '#111111'
        assert resolve_style(s, point_a, 'label_visible') is True

        assert resolve_style(s, point_d, 'size_px') == 12
        assert resolve_style(s, seg_c, 'stroke_width_px') == 4
        assert resolve_style(s, seg_c, 'stroke') == '#333333'
        assert s._build_render_ctx(point_d, z_auto=True).has_label is True
        assert s._active_import_policy is None

    def test_ggb_axes_and_grid_render_background_layer(self):
        if not os.path.isfile(GRID_FIXTURE):
            pytest.skip(f'Fixture not found: {GRID_FIXTURE}')

        s = _new_scene()
        s.loadGGB(GRID_FIXTURE, generate_stubs=False)

        assert s.style.export['showGrid'] is True
        assert s.style.export['showAxes'] is True
        bg = s.mobject('_coordinate_background')
        assert bg is not None
        assert len(bg) > 0

    def test_active_policy_is_faithful(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(FIXTURE, style=STYLE_FILE, export={"size": [800, 600]})
        assert isinstance(s._active_import_policy, ImportPolicy)
        assert s._active_import_policy.base == 'faithful'


class TestLoadggbWithPolicy:
    def test_point_size_override(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(
            FIXTURE, style=STYLE_FILE, export={"size": [800, 600]},
            import_policy=ImportPolicy(size_px=3.0),
        )
        # All points get size=3.0 regardless of GGB pointSize.
        assert resolve_style(s, s.geo.element('A'), 'size_px') == 3.0
        assert resolve_style(s, s.geo.element('D'), 'size_px') == 3.0

    def test_scale_directive_through_python(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(
            FIXTURE, style=STYLE_FILE, export={"size": [800, 600]},
            import_policy=ImportPolicy(
                size_px=lambda raw, d, e: raw * 1.5 if raw is not None else None),
        )
        # A had pointSize=5 → callable gets raw=5 → size_px=7.5
        assert resolve_style(s, s.geo.element('A'), 'size_px') == 7.5
        assert resolve_style(s, s.geo.element('D'), 'size_px') == 6.0   # D: raw=4 → 6

    def test_label_color_unified(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(
            FIXTURE, style=STYLE_FILE, export={"size": [800, 600]},
            import_policy=ImportPolicy(label_color='#222222'),
        )
        for name in ('A', 'B', 'C', 'D'):
            assert resolve_style(s, s.geo.element(name), 'label_color') == '#222222'

    def test_overlay_per_name_override(self, tmp_path):
        _require_fixture()
        style = {
            'overlay': {
                'per_name': {'A': {'size_px': 99}},
            },
        }
        style_path = tmp_path / 'overlay_name.json'
        style_path.write_text(json.dumps(style))
        s = _new_scene()
        s.loadGGB(
            FIXTURE, style=str(style_path), export={"size": [800, 600]},
        )
        assert resolve_style(s, s.geo.element('A'), 'size_px') == 99
        assert resolve_style(s, s.geo.element('B'), 'size_px') != 99

    def test_raw_derived_fields_through_policy(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(
            FIXTURE,
            style=STYLE_FILE,
            export={"size": [800, 600]},
            import_policy=ImportPolicy(
                stroke_opacity='scale:0.001',
                stroke_dash_ratio=lambda raw, d, e: 0.42 if raw == 0 else 0.9,
                visible=False,
                label_text='$FromPolicy$',
                angle_range='reflex',
                tick_count=4,
            ),
        )
        assert resolve_style(s, s.geo.element('c'), 'stroke_opacity') == pytest.approx(0.204)
        assert resolve_style(s, s.geo.element('c'), 'stroke_dash_ratio') == 0.42
        assert resolve_style(s, s.geo.element('A'), 'visible') is False
        assert resolve_style(s, s.geo.element('A'), 'label_text') == '$FromPolicy$'
        assert resolve_style(s, s.geo.element('α'), 'angle_range') == 'reflex'
        assert resolve_style(s, s.geo.element('α'), 'tick_count') == 4

    def test_runtime_show_overrides_import_visible(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(
            FIXTURE,
            style=STYLE_FILE,
            export={"size": [800, 600]},
            import_policy=ImportPolicy(visible=False),
        )
        elem = s.geo.element('A')
        assert resolve_style(s, elem, 'visible') is False
        assert s._element_visible(elem) is False

        s.Show(['A'])

        assert resolve_style(s, elem, 'visible') is True
        assert s._element_visible(elem) is True

    def test_add_all_geometry_show_false_overrides_import_visible(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(FIXTURE, style=STYLE_FILE, export={"size": [800, 600]})
        elem = s.geo.element('A')
        assert resolve_style(s, elem, 'visible') is True

        s.addAllGeometry(show=False)

        assert resolve_style(s, elem, 'visible') is False
        assert s._element_visible(elem) is False


class TestPolicyFromStyleJson:
    """An import_policy section inside style.json should be auto-picked up."""

    def _policy_style(self, name):
        return os.path.join(
            os.path.dirname(__file__), '..', 'examples', 'policies', name,
        )

    def test_flat_black_preset(self):
        _require_fixture()
        if not os.path.isfile(self._policy_style('flat_black.json')):
            pytest.skip('Example policy file missing')
        s = _new_scene()
        s.loadGGB(
            FIXTURE,
            style=self._policy_style('flat_black.json'),
            export={"size": [800, 600]},
        )
        # Every element should have stroke black, label black.
        for name in ('A', 'c', 'α'):
            elem = s.geo.element(name)
            if elem is None:
                continue
            assert resolve_style(s, elem, 'stroke') == '#000000', name
            assert resolve_style(s, elem, 'label_color') == '#000000', name

    def test_no_labels_preset(self):
        _require_fixture()
        if not os.path.isfile(self._policy_style('no_labels.json')):
            pytest.skip('Example policy file missing')
        s = _new_scene()
        s.loadGGB(
            FIXTURE,
            style=self._policy_style('no_labels.json'),
            export={"size": [800, 600]},
        )
        for name in ('A', 'B', 'C', 'D'):
            elem = s.geo.element(name)
            if elem is not None:
                assert resolve_style(s, elem, 'label_visible') is False, name

    def test_import_policy_resolves_preset_refs(self, tmp_path):
        _require_fixture()
        style = {
            'presets': {
                'color': {
                    'main': '#000000',
                    'light': '#eeeeee',
                    'accent': '#123456',
                    'accent_light': '#ddeeff',
                },
                'line_width': {
                    'main': 1,
                    'bold': 3,
                },
                'point_size': {
                    'main': 7,
                    'bold': 12,
                },
            },
            'import': {
                'policy': {
                    'stroke': 'presets.color.accent',
                    'stroke_width_px': 'presets.line_width.bold',
                    'size_px': 'presets.point_size.bold',
                },
            },
        }
        style_path = tmp_path / 'policy_refs.json'
        style_path.write_text(json.dumps(style))

        s = _new_scene()
        s.loadGGB(FIXTURE, style=str(style_path), export={"size": [800, 600]})

        assert resolve_style(s, s.geo.element('c'), 'stroke') == '#123456'
        assert resolve_style(s, s.geo.element('c'), 'stroke_width_px') == 3
        assert resolve_style(s, s.geo.element('A'), 'size_px') == 12


class TestReloadPolicy:
    def test_reload_changes_sizes(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(FIXTURE, style=STYLE_FILE, export={"size": [800, 600]})
        # Baseline
        assert resolve_style(s, s.geo.element('A'), 'size_px') == pytest.approx(2.8346456692916)
        # Reload with new policy
        s.reloadPolicy(ImportPolicy(size_px=5))
        assert resolve_style(s, s.geo.element('A'), 'size_px') == 5
        assert resolve_style(s, s.geo.element('D'), 'size_px') == 5


class TestLoadggbStateReset:
    """A second loadGGB must replace, not append. Web services reuse
    scene instances; previously, the second load stacked both constructions."""

    def test_second_load_replaces_geometry(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(FIXTURE, style=STYLE_FILE, export={"size": [800, 600]})
        first_count = len(s.geo.elements)
        assert first_count > 0
        s.loadGGB(FIXTURE, style=STYLE_FILE, export={"size": [800, 600]})
        second_count = len(s.geo.elements)
        assert second_count == first_count, (
            f"loadGGB appended instead of resetting: {first_count} → {second_count}"
        )

    def test_resetScene_wipes_construction(self):
        _require_fixture()
        s = _new_scene()
        s.loadGGB(FIXTURE, style=STYLE_FILE, export={"size": [800, 600]})
        loaded = len(s.geo.elements)
        s.resetScene()
        # Construction() ships with the two axis Lines pre-populated; after
        # reset we should be back to exactly that baseline, not whatever we
        # accumulated during loadGGB.
        baseline = len(AnimaGeoScene().geo.elements)
        assert len(s.geo.elements) == baseline
        assert len(s.geo.elements) < loaded
        assert s.geo.commands == []
