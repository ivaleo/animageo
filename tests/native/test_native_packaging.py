"""The data files of animageo ship with the package (1.11.0rc1, L6 item 12:
every data file of the package, not only the JSON of ``animageo.native``)."""
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
    ('parity', 'v1', 'commands'),
    ('commands',),
    ('convert',),
    ('labels',),
    ('phrases',),
    ('marks',),
    ('recipes', 'v1'),
    ('parity', 'v1', 'steps'),
    ('parity', 'v1', 'timeline'),
    ('parity', 'v1', 'recipes'),
    ('parity', 'v1', 'general'),
    ('parity', 'v1', 'marks'),
]
PACKAGE_DIR = REPO_ROOT / 'animageo'


def _json_files_on_disk():
    return sorted(str(p.relative_to(REPO_ROOT / 'animageo')) for p in NATIVE_DIR.rglob('*.json'))


def _data_files_on_disk():
    """Every file of the package that is not Python source (``.claude`` is pruned)."""
    out = []
    for path in PACKAGE_DIR.rglob('*'):
        rel = path.relative_to(PACKAGE_DIR)
        if (not path.is_file() or path.suffix in ('.py', '.pyc') or '__pycache__' in rel.parts
                or rel.parts[0] == '.claude'):
            continue
        out.append(rel.as_posix())
    return sorted(out)


def _covered(rel, patterns):
    return any(fnmatch.fnmatch(rel, pattern) and rel.count('/') == pattern.count('/') for pattern in patterns)


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
        assert _covered(rel, patterns), rel


def test_package_data_covers_every_data_file():
    config = tomllib.loads((REPO_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    patterns = config['tool']['setuptools']['package-data']['animageo']
    files = _data_files_on_disk()
    assert {'dsl.pyi', 'py.typed', 'AI_USAGE_PROMPT.md', 'native/convert/dsl_map.json',
            'native/labels/metrics.v1.json', 'native/marks/auto.v1.json', 'style/builtin.json',
            'parsers/dsl/namespace.pyi'} <= set(files)
    assert [rel for rel in files if not _covered(rel, patterns)] == []
    # every pattern still matches something (no stale entry)
    assert [p for p in patterns if not any(_covered(rel, [p]) for rel in files)] == []


def test_the_style_data_is_found_through_importlib():
    root = resources.files('animageo')
    json.loads(root.joinpath('style', 'builtin.json').read_text(encoding='utf-8'))
    presets = [e.name for e in root.joinpath('style', 'presets').iterdir() if e.name.endswith('.json')]
    assert presets
    assert root.joinpath('dsl.pyi').is_file() and root.joinpath('py.typed').is_file()
    json.loads(root.joinpath('exporters', 'jsxgraph', 'board.schema.json').read_text(encoding='utf-8'))


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
    for rel in _data_files_on_disk():
        assert f'animageo/{rel}' in names, rel
    assert not [n for n in names if n.startswith(('tests/', 'docs/', 'animageo/.claude/'))]
