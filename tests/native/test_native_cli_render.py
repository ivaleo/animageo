"""``python -m animageo doc.json -o out.svg``: documents render in process."""
import json
import subprocess
import sys

import pytest

from tests.native.conftest import REPO_ROOT, DocBuilder

BLOCKED = 'man' + 'im'


def document(tmp_path, **extra):
    b = DocBuilder('cli_doc', registry_version='1.1', bounds=(-6, -4, 6, 4))
    b.free('A', -4, -2).free('B', 4, -2).free('C', 1, 3).segment('s', 'A', 'B').circle('c', 'A', 'C')
    b.doc.update(extra)
    path = tmp_path / 'doc.json'
    path.write_text(json.dumps(b.doc), encoding='utf-8')
    return path


def run(*args, blocked=False):
    prefix = []
    if blocked:
        code = (f"import importlib.abc, runpy, sys\n"
                f"class B(importlib.abc.MetaPathFinder):\n"
                f"    def find_spec(self, name, path=None, target=None):\n"
                f"        if name == {BLOCKED!r} or name.startswith({BLOCKED!r} + '.'):\n"
                f"            raise ModuleNotFoundError('blocked', name=name)\n"
                f"sys.meta_path.insert(0, B())\n"
                f"sys.argv = ['animageo'] + sys.argv[1:]\n"
                f"runpy.run_module('animageo', run_name='__main__')\n")
        prefix = ['-c', code]
    else:
        prefix = ['-m', 'animageo']
    return subprocess.run([sys.executable, *prefix, *map(str, args)], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=300)


def test_without_the_renderer_exit_code_2(tmp_path):
    proc = run(document(tmp_path), '-o', tmp_path / 'out.svg', blocked=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert 'needs ' + BLOCKED in proc.stdout + proc.stderr


@pytest.mark.parametrize('args, message', [
    (('-o', 'out.mp4'), 'renders to svg/png/pdf'),
    (('--style-from-document',), 'no styleBinding.configSnapshot'),
])
def test_refused_arguments(tmp_path, args, message):
    proc = run(document(tmp_path), *args, blocked=True)
    assert proc.returncode == 2
    assert message in proc.stdout + proc.stderr


def test_a_broken_document(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps({'format': 'animageo-construction/v1', 'documentId': 'x'}), encoding='utf-8')
    proc = run(path, '-o', tmp_path / 'out.svg', blocked=True)
    assert proc.returncode == 2
    assert 'invalid animageo-construction/v1 document' in proc.stdout + proc.stderr


def test_other_json_is_not_a_document(tmp_path):
    from animageo import __main__ as cli
    path = tmp_path / 'x.json'
    path.write_text('{"format": "something-else"}', encoding='utf-8')
    assert cli._read_document(path) is None
    assert cli._read_document(document(tmp_path))['documentId'] == 'cli_doc'
    (tmp_path / 'z.ggb').write_bytes(b'PK\x03\x04')
    assert cli._read_document(tmp_path / 'z.ggb') is None


@pytest.mark.manim
@pytest.mark.parametrize('fmt, magic', [('svg', b'<?xml'), ('png', b'\x89PNG'), ('pdf', b'%PDF')])
def test_render(tmp_path, fmt, magic):
    pytest.importorskip(BLOCKED)
    out = tmp_path / f'out.{fmt}'
    proc = run(document(tmp_path), '-o', out, '--export-size', '400', '300')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.read_bytes().startswith(magic)
    if fmt == 'svg':
        assert 'width="400" height="300"' in out.read_text(encoding='utf-8')


@pytest.mark.manim
def test_style_from_document(tmp_path):
    pytest.importorskip(BLOCKED)
    snapshot = {'presets': {'color': {'strong': '#123456'}}}
    path = document(tmp_path, styleBinding={'styleId': None, 'version': '1', 'configSnapshot': snapshot})
    proc = run(path, '--style-from-document')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'configSnapshot as is' in proc.stdout + proc.stderr
    assert 'rgb(7.058824%, 20.392157%, 33.72549%)' in (tmp_path / 'doc.svg').read_text(encoding='utf-8')
