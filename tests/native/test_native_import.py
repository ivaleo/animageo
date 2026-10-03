"""``animageo.native`` imports without manim and the classic modules."""
import subprocess
import sys

import animageo
from tests.native.conftest import REPO_ROOT

# Built from parts: the root conftest skips any test whose source mentions
# the classic module path or a manim import statement.
CLASSIC = 'animageo.' + 'animageo'
GEO = 'animageo.' + 'geo'
BLOCKED = 'man' + 'im'

_BLOCKER = f"""
import importlib.abc, sys

class _Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == {BLOCKED!r} or name.startswith({BLOCKED!r} + '.'):
            raise ModuleNotFoundError('blocked: ' + name, name=name)
        return None

sys.meta_path.insert(0, _Block())
"""


def _run(code, *args, extra=()):
    return subprocess.run(
        [sys.executable, *extra, '-c', code, *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )


def test_import_native_with_manim_blocked():
    code = _BLOCKER + f"""
import json
import animageo.native as native
from animageo.native import cli, parity
from animageo.native.kernel import checks, evaluate
with open('animageo/native/parity/v1/scenes/basic_points.json', encoding='utf-8') as fh:
    native.evaluate(json.load(fh)['document'])
loaded = sorted(m for m in sys.modules
                if m == {BLOCKED!r} or m.startswith({BLOCKED!r} + '.')
                or m == {GEO!r} or m.startswith({GEO!r} + '.') or m == {CLASSIC!r})
print('LOADED', loaded)
"""
    proc = _run(code)
    assert proc.returncode == 0, proc.stderr
    assert 'LOADED []' in proc.stdout


def test_geo_modules_import_on_their_own_without_manim():
    """``import animageo`` no longer loads the geo package when manim is
    missing; ``animageo.geo`` must still import in any module order."""
    for module in ('lib_elements', 'lib_vars', 'lib_commands', 'lib_conic', 'construction'):
        proc = _run(_BLOCKER + f"import {GEO}.{module}\nprint('OK')")
        assert proc.returncode == 0 and 'OK' in proc.stdout, (module, proc.stderr[-2000:])


def _resolved_imports(path):
    import ast
    parts = list(path.relative_to(REPO_ROOT).with_suffix('').parts)
    package = parts[:-1]  # the package of a module, or of an __init__.py itself
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - node.level + 1]
                yield '.'.join(base + ([node.module] if node.module else []))
            else:
                yield node.module


def test_native_modules_do_not_import_classic_code():
    """Every import under animageo/native stays in animageo.native (or the
    package root for ``__version__``) or the standard library."""
    offenders = []
    for path in sorted((REPO_ROOT / 'animageo' / 'native').rglob('*.py')):
        for name in _resolved_imports(path):
            top = name.split('.')[0]
            outside_native = top == 'animageo' and name != 'animageo' and not (
                name == 'animageo.native' or name.startswith('animageo.native.'))
            if top == BLOCKED or outside_native or top in ('numpy', 'sympy', 'scipy'):
                offenders.append(f'{path.relative_to(REPO_ROOT)}: {name}')
    assert offenders == []


def test_cli_does_not_import_classic_modules():
    proc = subprocess.run(
        [sys.executable, '-X', 'importtime', '-m', 'animageo.native', 'registry', 'index', '--check'],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    imported = [line.rsplit('|', 1)[-1].strip() for line in proc.stderr.splitlines() if '|' in line]
    assert 'animageo.native' in imported
    assert not [m for m in imported if m.split('.')[0] == BLOCKED or m == CLASSIC or m.startswith(GEO)]


class TestRunningPackageMain:
    def _set(self, monkeypatch, argv, orig_argv):
        monkeypatch.setattr(sys, 'argv', argv)
        monkeypatch.setattr(sys, 'orig_argv', orig_argv, raising=False)

    def test_native_dash_m_while_locating(self, monkeypatch):
        self._set(monkeypatch, ['-m', 'registry', 'index'],
                  ['python3', '-m', 'animageo.native', 'registry', 'index'])
        assert animageo._running_package_main()

    def test_native_dash_m_with_interpreter_options(self, monkeypatch):
        self._set(monkeypatch, ['-m'], ['python3', '-X', 'importtime', '-B', '-m', 'animageo.native.cli'])
        assert animageo._running_package_main()

    def test_native_main_path(self, monkeypatch):
        self._set(monkeypatch, ['/x/site-packages/animageo/native/__main__.py', 'validate', 'd.json'],
                  ['python3', '-m', 'animageo.native', 'validate', 'd.json'])
        assert animageo._running_package_main()

    def test_other_module_is_not_native(self, monkeypatch):
        self._set(monkeypatch, ['-m', '-q'], ['python3', '-m', 'pytest', '-q'])
        assert not animageo._running_package_main()

    def test_script_arguments_are_not_interpreter_options(self, monkeypatch):
        self._set(monkeypatch, ['script.py', '-m', 'animageo.native'],
                  ['python3', 'script.py', '-m', 'animageo.native'])
        assert not animageo._running_package_main()
        self._set(monkeypatch, ['-c', '-m', 'animageo.native'],
                  ['python3', '-c', 'pass', '-m', 'animageo.native'])
        assert not animageo._running_package_main()

    def test_classic_cli_unchanged(self, monkeypatch):
        self._set(monkeypatch, ['/usr/bin/animageo', 'scene.ggb'], ['python3', '/usr/bin/animageo', 'scene.ggb'])
        assert animageo._running_package_main()
