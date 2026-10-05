"""Command line: evaluate, validate, exit codes, python -m."""
import json
import subprocess
import sys

import pytest

from animageo import native
from animageo.native.cli import main
from tests.native.conftest import REPO_ROOT, SCENES_DIR, DocBuilder, point_input, read_json


@pytest.fixture
def doc_path(tmp_path):
    b = DocBuilder('cli').free('A', 0, 0).free('B', 4, 0).free('C', 1, 3)
    b.line('l', 'A', 'B').circle('c', 'A', 'C').midpoint('M', 'A', 'B')
    path = tmp_path / 'doc.json'
    path.write_text(json.dumps(b.doc), encoding='utf-8')
    return path


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


class TestEvaluate:
    def test_pretty(self, capsys, doc_path):
        code, out, _ = run(capsys, 'evaluate', str(doc_path))
        assert code == 0
        data = json.loads(out)
        assert data == native.evaluate(read_json(doc_path)).to_dict()
        assert '\n  "format"' in out

    def test_canonical(self, capsys, doc_path):
        code, out, _ = run(capsys, 'evaluate', str(doc_path), '--canonical')
        assert code == 0
        assert out == native.canonical_json(native.evaluate(read_json(doc_path)).to_dict()) + '\n'

    def test_checks(self, capsys, doc_path):
        code, out, _ = run(capsys, 'evaluate', str(doc_path), '--checks')
        assert code == 0
        assert json.loads(out)['checks'] == {
            'op_M:equidistant': 'passed', 'op_M:collinear': 'passed',
            'op_c:through_on_circle': 'passed',
            'op_l:through_a': 'passed', 'op_l:through_b': 'passed',
        }

    @pytest.mark.parametrize('wrap', [False, True])
    def test_inputs(self, capsys, doc_path, tmp_path, wrap):
        inputs = {'B': point_input(0, 0)}
        path = tmp_path / 'inputs.json'
        path.write_text(json.dumps({'name': 'x', 'inputs': inputs} if wrap else inputs), encoding='utf-8')
        code, out, _ = run(capsys, 'evaluate', str(doc_path), '--inputs', str(path))
        assert code == 0
        assert json.loads(out)['elements']['l']['reason'] == 'coincident_points'

    def test_bad_inputs_exit_2(self, capsys, doc_path, tmp_path):
        path = tmp_path / 'inputs.json'
        path.write_text(json.dumps({'l': point_input(0, 0)}), encoding='utf-8')
        code, _, err = run(capsys, 'evaluate', str(doc_path), '--inputs', str(path))
        assert code == 2 and 'not a free input' in err

    def test_unreadable_exit_2(self, capsys, tmp_path):
        code, _, _ = run(capsys, 'evaluate', str(tmp_path / 'missing.json'))
        assert code == 2
        broken = tmp_path / 'broken.json'
        broken.write_text('{"format": "animageo-construction/v1"}', encoding='utf-8')
        code, _, err = run(capsys, 'evaluate', str(broken))
        assert code == 2 and 'schema' in err

    def test_graph_errors_still_evaluate(self, capsys, tmp_path):
        path = tmp_path / 'graph.json'
        path.write_text(json.dumps(read_json(SCENES_DIR / 'graph_errors.json')['document']), encoding='utf-8')
        code, out, _ = run(capsys, 'evaluate', str(path))
        assert code == 0
        assert json.loads(out)['elements']['P']['reason'] == 'cycle'


class TestValidate:
    def test_clean_exit_0(self, capsys, doc_path):
        code, out, _ = run(capsys, 'validate', str(doc_path))
        assert code == 0 and out.strip() == '0 issues'

    def test_issues_exit_1(self, capsys, tmp_path):
        path = tmp_path / 'graph.json'
        path.write_text(json.dumps(read_json(SCENES_DIR / 'graph_errors.json')['document']), encoding='utf-8')
        code, out, _ = run(capsys, 'validate', str(path))
        assert code == 1
        for code_name in ('dangling_ref', 'cycle', 'unknown_op', 'type_mismatch'):
            assert code_name in out

    def test_json_output(self, capsys, tmp_path):
        path = tmp_path / 'graph.json'
        doc = read_json(SCENES_DIR / 'graph_errors.json')['document']
        path.write_text(json.dumps(doc), encoding='utf-8')
        code, out, _ = run(capsys, 'validate', str(path), '--json')
        assert code == 1
        assert json.loads(out) == [i.to_dict() for i in native.validate(doc)]

    def test_structure_issues_exit_1(self, capsys, tmp_path):
        path = tmp_path / 'broken.json'
        path.write_text('{"format": "animageo-construction/v1"}', encoding='utf-8')
        code, out, _ = run(capsys, 'validate', str(path))
        assert code == 1 and 'schema' in out

    def test_missing_file_exit_2(self, capsys, tmp_path):
        code, _, _ = run(capsys, 'validate', str(tmp_path / 'missing.json'))
        assert code == 2

    def test_invalid_json_is_an_issue(self, capsys, tmp_path):
        bad = tmp_path / 'bad.json'
        bad.write_text('{not json', encoding='utf-8')
        code, out, _ = run(capsys, 'validate', str(bad))
        assert code == 1 and 'not valid JSON' in out


def test_usage_errors_exit_2(capsys):
    for argv in ([], ['fixtures'], ['evaluate'], ['nope']):
        with pytest.raises(SystemExit) as info:
            main(argv)
        assert info.value.code == 2
    capsys.readouterr()


def test_version(capsys):
    import animageo
    with pytest.raises(SystemExit) as info:
        main(['--version'])
    assert info.value.code == 0
    assert capsys.readouterr().out.strip() == f'animageo {animageo.__version__}, registry 1.4'


def test_python_dash_m(doc_path):
    proc = subprocess.run([sys.executable, '-m', 'animageo.native', 'evaluate', str(doc_path), '--canonical'],
                          cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['documentId'] == 'cli'
