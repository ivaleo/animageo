"""Lint (plan L5 §3.1): the code of ``animageo.native`` runs no code it is given.

An AST walk over ``animageo/native/**``: no call of the builtins ``exec``,
``eval``, ``compile`` (``re.compile`` is fine), ``__import__``; no
``importlib.import_module``, ``os.system``, ``os.popen``; no import of
``subprocess``, ``pickle``, ``marshal``, ``ctypes``. The classic parser the
import calls checks the code it builds from a ``.ggb`` itself
(``ggb_parser._check_ggb_code``). ``ALLOWED`` lists the exceptions by file
(none yet; ``convert/scenario.py`` of stage 2 will call ``dsl.run`` after its
environment guard).
"""
import ast

from tests.native.conftest import NATIVE_DIR

BUILTINS = {'exec', 'eval', 'compile', '__import__'}
MODULES = {'subprocess', 'pickle', 'marshal', 'ctypes'}
ATTRS = {('importlib', 'import_module'), ('os', 'system'), ('os', 'popen')}
ALLOWED: dict = {}


def _problems(path):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in BUILTINS:
                out.append(f'{node.lineno}: {f.id}()')
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (f.value.id, f.attr) in ATTRS:
                out.append(f'{node.lineno}: {f.value.id}.{f.attr}()')
        if isinstance(node, ast.Import):
            out += [f'{node.lineno}: import {a.name}' for a in node.names if a.name.split('.')[0] in MODULES]
        if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or '').split('.')[0] in MODULES:
            out.append(f'{node.lineno}: from {node.module} import')
    return out


def test_native_runs_no_code():
    found = {}
    for path in sorted(NATIVE_DIR.rglob('*.py')):
        rel = str(path.relative_to(NATIVE_DIR))
        problems = [p for p in _problems(path) if p.split(': ', 1)[1] not in ALLOWED.get(rel, ())]
        if problems:
            found[rel] = problems
    assert found == {}


def test_the_lint_sees_a_call(tmp_path):
    bad = tmp_path / 'bad.py'
    bad.write_text('import subprocess\nx = eval("1")\nimport re\ny = re.compile("a")\n', encoding='utf-8')
    assert _problems(bad) == ['1: import subprocess', '2: eval()']
