"""Lint (plan L5 §7; 1.11.0rc1 over the whole of ``animageo/native/**``): the
code of ``animageo.native`` runs no code it is given and starts no process.

An AST walk over every ``.py`` under ``animageo/native``:

- no call of the builtins ``exec``, ``eval``, ``compile`` (``re.compile``
  is fine), ``__import__``, ``breakpoint`` — by name, through ``builtins``
  or ``__builtins__``, or under another name (``e = eval``);
- no ``importlib.import_module`` (any alias of ``importlib``, or
  ``from importlib import import_module``);
- no ``os.system``, ``os.popen``, ``os.exec*``, ``os.spawn*``,
  ``os.posix_spawn*``, ``os.fork*``;
- no import of ``subprocess``, ``pickle``, ``marshal``, ``ctypes``,
  ``multiprocessing``, ``pty``, ``runpy``, ``code``, ``codeop``,
  ``socket``, ``shelve``;
- ``dsl.run`` only in ``convert/scenario.py`` (stage 2 of L5, after its
  environment guard; the file does not exist yet).

The classic parser the import calls checks the code it builds from a
``.ggb`` itself (``ggb_parser._check_ggb_code``). ``ALLOWED`` lists the
exceptions by file.
"""
import ast

from tests.native.conftest import NATIVE_DIR

BUILTINS = {'exec', 'eval', 'compile', '__import__', 'breakpoint'}
MODULES = {'subprocess', 'pickle', 'marshal', 'ctypes', 'multiprocessing', 'pty', 'runpy', 'code', 'codeop',
           'socket', 'shelve'}
OS_PREFIXES = ('exec', 'spawn', 'posix_spawn', 'fork')
OS_CALLS = {'system', 'popen'}
ALLOWED = {'convert/scenario.py': {'dsl.run()'}}


def _problems(path):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    importlib_names = {'importlib'}
    os_names = {'os'}
    dangerous_names = set(BUILTINS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'importlib':
                    importlib_names.add(alias.asname or alias.name)
                if alias.name == 'os':
                    os_names.add(alias.asname or alias.name)
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            for alias in node.names:
                if node.module == 'importlib' and alias.name == 'import_module':
                    dangerous_names.add(alias.asname or alias.name)
                if node.module == 'os' and (alias.name in OS_CALLS or alias.name.startswith(OS_PREFIXES)):
                    dangerous_names.add(alias.asname or alias.name)
                if node.module == 'builtins' and alias.name in BUILTINS:
                    dangerous_names.add(alias.asname or alias.name)

    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in dangerous_names:
                out.append(f'{node.lineno}: {f.id}()')
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                owner, attr = f.value.id, f.attr
                if owner in importlib_names and attr == 'import_module':
                    out.append(f'{node.lineno}: {owner}.{attr}()')
                elif owner in os_names and (attr in OS_CALLS or attr.startswith(OS_PREFIXES)):
                    out.append(f'{node.lineno}: {owner}.{attr}()')
                elif owner in ('builtins', '__builtins__') and attr in BUILTINS:
                    out.append(f'{node.lineno}: {owner}.{attr}()')
                elif owner == 'dsl' and attr == 'run':
                    out.append(f'{node.lineno}: dsl.run()')
            if (isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name) and f.value.id == '__builtins__'):
                out.append(f'{node.lineno}: __builtins__[...]()')
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in BUILTINS:
            out.append(f'{node.lineno}: alias of {node.value.id}')
        if isinstance(node, ast.Import):
            out += [f'{node.lineno}: import {a.name}' for a in node.names if a.name.split('.')[0] in MODULES]
        if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or '').split('.')[0] in MODULES:
            out.append(f'{node.lineno}: from {node.module} import')
    return out


def test_native_runs_no_code():
    found = {}
    files = sorted(NATIVE_DIR.rglob('*.py'))
    assert len(files) > 50                                 # the whole package, subpackages too
    for path in files:
        rel = path.relative_to(NATIVE_DIR).as_posix()
        problems = [p for p in _problems(path) if p.split(': ', 1)[1] not in ALLOWED.get(rel, ())]
        if problems:
            found[rel] = problems
    assert found == {}


def test_the_lint_sees_a_call(tmp_path):
    bad = tmp_path / 'bad.py'
    bad.write_text('import subprocess\nx = eval("1")\nimport re\ny = re.compile("a")\n', encoding='utf-8')
    assert _problems(bad) == ['1: import subprocess', '2: eval()']


def test_the_lint_sees_aliases(tmp_path):
    bad = tmp_path / 'bad.py'
    bad.write_text(
        'import importlib as il\nfrom importlib import import_module as im\nimport os as o\n'
        'from os import execv\nimport builtins\n'
        'il.import_module("x")\nim("y")\no.spawnl(0, "a")\nexecv("a", [])\nbuiltins.exec("1")\n'
        '__builtins__["eval"]("1")\nrun = eval\nfrom multiprocessing import Process\nimport socket\n'
        'from animageo.parsers import dsl\ndsl.run(None, "A = Point(0, 0)")\n',
        encoding='utf-8')
    assert sorted(_problems(bad), key=lambda p: int(p.split(':')[0])) == [
        '6: il.import_module()', '7: im()', '8: o.spawnl()', '9: execv()', '10: builtins.exec()',
        '11: __builtins__[...]()', '12: alias of eval', '13: from multiprocessing import', '14: import socket',
        '16: dsl.run()',
    ]


def test_dsl_run_is_allowed_only_in_the_scenario_module():
    assert ALLOWED == {'convert/scenario.py': {'dsl.run()'}}
    assert not (NATIVE_DIR / 'convert' / 'scenario.py').exists() or 'dsl.run' in (
        NATIVE_DIR / 'convert' / 'scenario.py').read_text(encoding='utf-8')
