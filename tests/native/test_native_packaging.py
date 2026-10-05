"""The data files of animageo.native ship with the package."""
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from importlib import resources

import pytest

from tests.native.conftest import NATIVE_DIR, REPO_ROOT

DATA_DIRS = [
    ('schema',),
    ('ops', 'v1'),
    ('parity', 'v1'),
    ('parity', 'v1', 'scenes'),
    ('parity', 'v1', 'expected'),
    ('commands',),
]


def _json_files_on_disk():
    return sorted(str(p.relative_to(REPO_ROOT / 'animageo')) for p in NATIVE_DIR.rglob('*.json'))


def test_resources_are_found_through_importlib():
    root = resources.files('animageo.native')
    for parts in DATA_DIRS:
        entry = root.joinpath(*parts)
        assert entry.is_dir(), parts
        names = [e.name for e in entry.iterdir() if e.name.endswith('.json')]
        assert names, parts
        for name in names:
            json.loads(entry.joinpath(name).read_text(encoding='utf-8'))
    assert root.joinpath('schema', 'construction.v1.schema.json').is_file()
    assert root.joinpath('ops', 'v1', 'INDEX.json').is_file()
    assert root.joinpath('parity', 'v1', 'canonical.json').is_file()


def test_package_data_covers_every_json_file():
    config = tomllib.loads((REPO_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    patterns = config['tool']['setuptools']['package-data']['animageo']
    for rel in _json_files_on_disk():
        assert any(fnmatch.fnmatch(rel, pattern) and rel.count('/') == pattern.count('/')
                   for pattern in patterns), rel


def test_manifest_includes_json_for_the_sdist():
    manifest = (REPO_ROOT / 'MANIFEST.in').read_text(encoding='utf-8')
    assert 'recursive-include animageo *.pyi *.json *.md' in manifest


@pytest.mark.slow
@pytest.mark.skipif(os.environ.get('ANIMAGEO_BUILD_WHEEL') != '1',
                    reason='builds a wheel (network for build isolation); set ANIMAGEO_BUILD_WHEEL=1')
def test_wheel_contains_the_data(tmp_path):
    src = tmp_path / 'src'
    shutil.copytree(REPO_ROOT, src, ignore=shutil.ignore_patterns(
        '.git', 'tests', 'docs', 'examples', 'web', 'build', 'dist', '*.egg-info', '__pycache__'))
    out = tmp_path / 'wheel'
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '-q', '-w', str(out), str(src)],
                   check=True, timeout=600)
    wheel = next(out.glob('animageo-*.whl'))
    names = set(zipfile.ZipFile(wheel).namelist())
    for rel in _json_files_on_disk():
        assert f'animageo/{rel}' in names, rel
