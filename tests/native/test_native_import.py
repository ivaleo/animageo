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


def test_layout_labels_without_manim():
    code = _BLOCKER + f"""
import json
import animageo.native as native
with open('animageo/native/parity/v1/scenes/a3_chain.json', encoding='utf-8') as fh:
    doc = json.load(fh)['document']
out = native.layout_labels(doc, place=True, export_layout={{'content': {{'source': 'rendered_bounds'}}}})
loaded = sorted(m for m in sys.modules if m == {BLOCKED!r} or m.startswith({BLOCKED!r} + '.') or m == {CLASSIC!r})
print('LABELS', len(out), 'LOADED', loaded)
"""
    proc = _run(code)
    assert proc.returncode == 0, proc.stderr
    assert 'LOADED []' in proc.stdout and 'LABELS 0' not in proc.stdout


def test_bridge_loads_geo_only_when_used():
    code = _BLOCKER + f"""
import json
from animageo.native.kernel import bridge
before = sorted(m for m in sys.modules if m.startswith({GEO!r}))
with open('animageo/native/parity/v1/scenes/on_path_chain.json', encoding='utf-8') as fh:
    construction, names = bridge.build_construction(json.load(fh)['document'])
construction.rebuild(full=True)
after = sorted(m for m in sys.modules if m == {BLOCKED!r} or m.startswith({BLOCKED!r} + '.') or m == {CLASSIC!r})
print('BEFORE', before)
print('AFTER', after, construction.element(names.by_id['M']).data is not None)
"""
    proc = _run(code)
    assert proc.returncode == 0, proc.stderr
    assert 'BEFORE []' in proc.stdout
    assert 'AFTER [] True' in proc.stdout


def test_geo_modules_import_on_their_own_without_manim():
    """``import animageo`` no longer loads the geo package when manim is
    missing; ``animageo.geo`` must still import in any module order."""
    for module in ('lib_elements', 'lib_vars', 'lib_commands', 'lib_conic', 'construction'):
        proc = _run(_BLOCKER + f"import {GEO}.{module}\nprint('OK')")
        assert proc.returncode == 0 and 'OK' in proc.stdout, (module, proc.stderr[-2000:])


def _resolved_imports(path):
    """``(module, lazy)`` of every import; ``lazy``: inside a function."""
    import ast
    parts = list(path.relative_to(REPO_ROOT).with_suffix('').parts)
    package = parts[:-1]  # the package of a module, or of an __init__.py itself
    tree = ast.parse(path.read_text(encoding='utf-8'))
    lazy_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lazy_nodes.update(id(inner) for inner in ast.walk(node))
    for node in ast.walk(tree):
        lazy = id(node) in lazy_nodes
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, lazy
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - node.level + 1]
                yield '.'.join(base + ([node.module] if node.module else [])), lazy
            else:
                yield node.module, lazy


# Modules that reach the classic code on purpose, inside functions only
# (``import animageo.native`` never loads it).
LAZY_ALLOWED = {
    'animageo/native/kernel/bridge.py': (GEO, 'numpy'),
    # 1.9.0a4: video — manim (tempconfig) and render_config inside _render_video;
    # 1.9.0a5: styles and @camera at t — the classic KeyframeSequence inside _apply_extras
    'animageo/native/rendering.py': (CLASSIC, GEO, 'animageo.labels', 'cairosvg', BLOCKED, 'animageo.render_config',
                                     'animageo.keyframes'),
    # backend='tex' loads animageo.ui (manim) on purpose, inside a function
    'animageo/native/labels/layout.py': (GEO, 'animageo.labels', 'animageo.label_placement', 'animageo.style',
                                         'animageo.export_layout', 'animageo.ui', 'numpy'),
    # 1.10.0a1 (L5): the translator reads the classic graph and runs the classic .ggb parser inside its functions
    'animageo/native/convert/__init__.py': (GEO, 'animageo.parsers'),
    'animageo/native/convert/construction.py': (GEO,),
    'animageo/native/convert/mapping.py': (GEO,),
    'animageo/native/convert/style.py': ('animageo.style',),
}


# Leaf modules of pure math outside animageo.native any native module may
# import at module level (1.9.0a4: the easing functions, plan L3 §5.2).
LEAF_ALLOWED = ('animageo.easing',)


def test_native_modules_do_not_import_classic_code():
    """Every import under animageo/native stays in animageo.native (or the
    package root for ``__version__``, or a leaf of :data:`LEAF_ALLOWED`) or
    the standard library."""
    offenders = []
    for path in sorted((REPO_ROOT / 'animageo' / 'native').rglob('*.py')):
        allowed = LAZY_ALLOWED.get(path.relative_to(REPO_ROOT).as_posix(), ())
        for name, lazy in _resolved_imports(path):
            if lazy and any(name == a or name.startswith(a + '.') for a in allowed):
                continue
            if name in LEAF_ALLOWED:
                continue
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

    def test_package_dash_m_with_a_document(self, monkeypatch):
        self._set(monkeypatch, ['-m', 'doc.json', '-o', 'out.svg'],
                  ['python3', '-m', 'animageo', 'doc.json', '-o', 'out.svg'])
        assert animageo._running_package_main()
        self._set(monkeypatch, ['-m'], ['python3', '-X', 'utf8', '-manimageo.__main__'])
        assert animageo._running_package_main()

    def test_a_json_argument_of_another_module_is_not_the_cli(self, monkeypatch):
        # the web sandbox: python -m app.sandbox.dsl_entry --job job.json
        self._set(monkeypatch, ['-m', '--job', 'job.json'],
                  ['python3', '-m', 'app.sandbox.dsl_entry', '--job', 'job.json'])
        assert not animageo._running_package_main()
        self._set(monkeypatch, ['/srv/app/run.py', 'doc.json'], ['python3', '/srv/app/run.py', 'doc.json'])
        assert not animageo._running_package_main()
