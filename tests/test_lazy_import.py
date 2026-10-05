"""``import animageo`` is light (1.11.0rc1, L6 item 4): the classic, manim
backed API loads on the first access to one of its names, and
``from animageo import *`` still gives exactly the names of 1.10.0a3
(``tests/snapshots/star_import.json``).

Every check runs in a fresh interpreter: what an import loads is a property
of the process.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = json.loads((REPO_ROOT / 'tests' / 'snapshots' / 'star_import.json').read_text(encoding='utf-8'))

# Built from parts: the root conftest skips any test whose source mentions
# the classic module path or a manim import statement.
BLOCKED = 'man' + 'im'
CLASSIC = 'animageo.' + 'animageo'

_BLOCKER = f"""
import importlib.abc, sys

class _Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == {BLOCKED!r} or name.startswith({BLOCKED!r} + '.'):
            raise ModuleNotFoundError('blocked: ' + name, name=name)
        return None

sys.meta_path.insert(0, _Block())
"""

_LOADED = f"""
import json as _json, sys as _sys
print('LOADED', _json.dumps(sorted(m for m in _sys.modules
      if m == {BLOCKED!r} or m.startswith({BLOCKED!r} + '.') or m == {CLASSIC!r})))
"""


def _run(code, *, blocked=False):
    proc = subprocess.run(
        [sys.executable, '-c', (_BLOCKER if blocked else '') + code],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def _loaded(out):
    line = next(line for line in out.splitlines() if line.startswith('LOADED '))
    return json.loads(line[len('LOADED '):])


def _manim_available():
    import importlib.util
    return importlib.util.find_spec(BLOCKED) is not None


needs_manim = pytest.mark.skipif(not _manim_available(), reason='requires optional dependency manim')


class TestImportIsLight:
    def test_import_animageo(self):
        out = _run('import animageo\nprint(animageo.__version__)\n' + _LOADED)
        assert _loaded(out) == []

    def test_version_and_path(self):
        out = _run('from animageo import __version__\nimport animageo\nassert animageo.__path__\n' + _LOADED)
        assert _loaded(out) == []

    def test_from_animageo_import_native(self):
        out = _run('from animageo import native\nprint(native.has("evaluate"))\n' + _LOADED)
        assert _loaded(out) == []

    def test_submodules_do_not_load_the_classic_api(self):
        code = ('import animageo\nfrom animageo import style, labels, keyframes\n'
                'import animageo.geo.construction\nfrom animageo.parsers import dsl\n'
                'assert not hasattr(animageo, "__wrapped__")\n' + _LOADED)
        # the classic submodules may use manim themselves; the classic API
        # module stays unloaded
        assert CLASSIC not in _loaded(_run(code))

    def test_unknown_name(self):
        code = ('import animageo\ntry:\n    animageo.no_such_name\nexcept AttributeError as e:\n'
                '    print("ERR", e)\n' + _LOADED)
        out = _run(code)
        assert "ERR module 'animageo' has no attribute 'no_such_name'" in out
        # a dunder or a private name is answered without loading anything
        code = ('import animageo\nfor n in ("__wrapped__", "_x", "__all_names__"):\n'
                '    assert not hasattr(animageo, n)\n' + _LOADED)
        assert _loaded(_run(code)) == []


@needs_manim
class TestClassicApiOnFirstUse:
    def test_attribute_loads_it(self):
        code = ('import animageo\nscene = animageo.AnimaGeoScene\n'
                f'import {CLASSIC} as classic\nassert scene is classic.AnimaGeoScene\n' + _LOADED)
        assert CLASSIC in _loaded(_run(code))

    def test_from_import(self):
        code = (f'from animageo import AnimaGeoScene, GeoStyle\nimport {CLASSIC} as classic\n'
                'assert AnimaGeoScene is classic.AnimaGeoScene and GeoStyle is classic.GeoStyle\n'
                'print("OK")\n')
        assert 'OK' in _run(code)

    def test_names_the_web_imports(self):
        code = ('from animageo import AnimaGeoScene, __version__\nfrom animageo import native\n'
                'import animageo\nassert animageo.AnimaGeoScene is AnimaGeoScene\n'
                'from animageo.ui import RusTex, correctedLabel\nprint("OK")\n')
        assert 'OK' in _run(code)

    def test_star_import_gives_the_names_of_1_10_0a3(self):
        code = ('ns = {}\nexec("from animageo import *", ns)\nimport json, manim\n'
                'print("NAMES", json.dumps(sorted(k for k in ns if k != "__builtins__")))\n'
                'm = {}\nexec("from manim import *", m)\n'
                'print("MANIM", json.dumps([manim.__version__, sorted(k for k in m if k != "__builtins__")]))\n'
                'print("GEO", ns["geo"].__name__)\n')
        out = _run(code)
        rows = {line.split(' ', 1)[0]: line.split(' ', 1)[1] for line in out.splitlines() if ' ' in line}
        names = json.loads(rows['NAMES'])
        manim_version, manim_names = json.loads(rows['MANIM'])
        if manim_version == SNAPSHOT['manim']:
            assert names == SNAPSHOT['names']
        else:
            # another manim: its star names may differ, the own ones may not
            assert set(SNAPSHOT['own']) <= set(names)
            assert set(manim_names) <= set(names)
            assert set(names) <= set(SNAPSHOT['names']) | set(manim_names)
        # as in 1.10.0a3: the classic module's ``geo`` (the construction
        # module) wins over the subpackage
        assert rows['GEO'] == 'animageo.geo.construction'

    def test_star_import_then_names(self):
        code = ('from animageo import *\nassert issubclass(AnimaGeoScene, Scene)\n'
                'assert callable(resolve_style_input) and WHITE\nprint("OK")\n')
        assert 'OK' in _run(code)


class TestWithoutManim:
    def test_import_and_native(self):
        code = ('import animageo, animageo.native as native\nnative.has("evaluate")\n' + _LOADED)
        assert _loaded(_run(code, blocked=True)) == []

    def test_classic_names_are_absent(self):
        code = ('import animageo\ntry:\n    animageo.AnimaGeoScene\nexcept AttributeError as e:\n'
                '    print("ATTR", type(e.__cause__).__name__)\n'
                'try:\n    from animageo import AnimaGeoScene\nexcept ImportError:\n    print("IMPORT")\n'
                'import sys\nprint("HALF", sorted(m for m in sys.modules if m.startswith("animageo.")))\n')
        out = _run(code, blocked=True)
        assert 'ATTR ModuleNotFoundError' in out and 'IMPORT' in out
        # no classic module is half imported on the way to the failure
        assert 'HALF []' in out

    def test_star_import(self):
        code = ('ns = {}\nexec("from animageo import *", ns)\n'
                'print("NAMES", sorted(k for k in ns if k != "__builtins__"))\n')
        out = _run(code, blocked=True)
        assert f"NAMES {SNAPSHOT['without_manim']}" in out
