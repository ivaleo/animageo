"""Packaged style presets: bare-name resolution and loading."""
import json
from pathlib import Path

import pytest

from animageo.style.config import (
    PRESETS_DIR,
    StyleConfig,
    available_style_presets,
    resolve_style_input,
)

EXPECTED_PRESETS = ['book_blue', 'book_green', 'book_purple', 'book_red', 'default']


class TestAvailablePresets:
    def test_shipped_set(self):
        assert available_style_presets() == EXPECTED_PRESETS

    def test_files_exist_and_are_valid_json(self):
        for name in EXPECTED_PRESETS:
            path = PRESETS_DIR / f'{name}.json'
            assert path.exists()
            data = json.loads(path.read_text())
            assert data['name'] == name


class TestResolveStyleInput:
    def test_bare_name_resolves_to_packaged_path(self):
        resolved = resolve_style_input('default')
        assert resolved == str(PRESETS_DIR / 'default.json')
        assert Path(resolved).exists()

    @pytest.mark.parametrize('name', EXPECTED_PRESETS)
    def test_every_preset_resolves(self, name):
        assert resolve_style_input(name) == str(PRESETS_DIR / f'{name}.json')

    def test_unknown_name_passes_through(self):
        assert resolve_style_input('no_such_preset') == 'no_such_preset'

    def test_json_suffix_passes_through(self):
        assert resolve_style_input('default.json') == 'default.json'

    def test_paths_pass_through(self):
        assert resolve_style_input('style/default.json') == 'style/default.json'
        assert resolve_style_input('a\\b.json') == 'a\\b.json'

    def test_none_dict_and_empty_pass_through(self):
        assert resolve_style_input(None) is None
        assert resolve_style_input('') == ''
        d = {'name': 'inline'}
        assert resolve_style_input(d) is d

    def test_existing_local_file_wins_over_preset(self, tmp_path, monkeypatch):
        local = tmp_path / 'default'
        local.write_text('{}')
        monkeypatch.chdir(tmp_path)
        assert resolve_style_input('default') == 'default'


class TestStyleConfigLoadByName:
    def test_load_default_by_name(self):
        cfg = StyleConfig.load('default')
        assert cfg.presets['color']['main'] == '#4d87c6'

    @pytest.mark.parametrize('name', EXPECTED_PRESETS)
    def test_load_every_preset(self, name):
        cfg = StyleConfig.load(name)
        assert isinstance(cfg.presets.get('color'), dict)

    def test_unknown_name_raises(self):
        with pytest.raises(Exception):
            StyleConfig.load('no_such_preset')


class TestSceneApplyStyleByName:
    def test_apply_style_preset_name(self):
        from animageo import AnimaGeoScene

        scene = AnimaGeoScene()
        scene.applyStyle(style='default',
                         export={'size': {'width': 200, 'height': 200}})
        assert scene.style_config.presets['color']['main'] == '#4d87c6'
        assert scene.style.col == '#4d87c6'
