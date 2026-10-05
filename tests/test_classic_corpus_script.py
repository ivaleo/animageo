"""The corpus runner (``scripts/classic_corpus.py``, L6 item 11): finding the
scenes, comparing outputs, the report. Rendering needs a corpus outside the
repository (``ANIMAGEO_CORPUS``); here only the pure parts run."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('classic_corpus', REPO_ROOT / 'scripts' / 'classic_corpus.py')
cc = importlib.util.module_from_spec(_spec)
sys.modules.setdefault('classic_corpus', cc)          # dataclasses look the module up
_spec.loader.exec_module(cc)


def _touch(path: Path, text: str = '') -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@pytest.fixture
def corpus(tmp_path):
    _touch(tmp_path / 'qa' / 'a.ggb')
    _touch(tmp_path / 'qa' / 'manifest.json', '{}')
    _touch(tmp_path / 'qa' / 'expected' / 'a.json', '{}')
    _touch(tmp_path / 'dsl-pairs' / 'p.ggb')
    _touch(tmp_path / 'dsl-pairs' / 'p.dsl', 'A = Point(0, 0)')
    _touch(tmp_path / 'dsl-pairs' / 'lonely.dsl', 'B = Point(1, 1)')       # no drawing: not a scene
    _touch(tmp_path / 'animations' / 'm.ggb')
    _touch(tmp_path / 'animations' / 'm.animation.json', '{}')
    _touch(tmp_path / 'animations' / 'n.animation.json', '{}')              # no drawing
    _touch(tmp_path / 'scenes' / 's.py', 'A = Point(0, 0)')
    _touch(tmp_path / 'scenes' / '_driver.py')
    _touch(tmp_path / '.cache' / 'x.ggb')
    _touch(tmp_path / '_old' / 'y.ggb')
    return tmp_path


class TestScenes:
    def test_kinds(self, corpus):
        scenes = cc.corpus_scenes(corpus)
        assert [(s.id, s.kind) for s in scenes] == [
            ('animations/m.animation.json', 'animation'),
            ('animations/m.ggb', 'ggb'),
            ('dsl-pairs/p.dsl', 'dsl-block'),
            ('dsl-pairs/p.ggb', 'ggb'),
            ('qa/a.ggb', 'ggb'),
            ('scenes/s.py', 'dsl-file'),
        ]
        block = next(s for s in scenes if s.kind == 'dsl-block')
        assert block.ggb == corpus / 'dsl-pairs' / 'p.ggb' and block.code == corpus / 'dsl-pairs' / 'p.dsl'
        animation = scenes[0]
        assert animation.ggb == corpus / 'animations' / 'm.ggb'
        assert cc.counts(scenes) == {'ggb': 3, 'dsl-block': 1, 'dsl-file': 1, 'animation': 1}

    def test_the_corpus_comes_from_the_environment(self, corpus, monkeypatch):
        args = cc.build_parser().parse_args(['verify'])
        monkeypatch.delenv('ANIMAGEO_CORPUS', raising=False)
        assert cc._corpus(args) is None
        monkeypatch.setenv('ANIMAGEO_CORPUS', str(corpus))
        assert cc._corpus(args) == corpus.resolve()
        args = cc.build_parser().parse_args(['compare', str(corpus / 'qa'), '--base', '/old'])
        assert cc._corpus(args) == (corpus / 'qa').resolve()

    def test_selection(self, corpus):
        args = cc.build_parser().parse_args(['compare', str(corpus), '--base', '/old', '--only', 'ggb,dsl-file',
                                             '--limit', '2'])
        assert [s.id for s in cc._selected(args, corpus)] == ['animations/m.ggb', 'dsl-pairs/p.ggb']

    def test_the_worker_is_python(self):
        compile(cc._WORKER, '_worker.py', 'exec')
        # a job file, not a .ggb in argv (1.10.0a3 then skipped its classic API)
        assert 'sys.argv[1]' in cc._WORKER and "generate_stubs=False" in cc._WORKER


SVG = ('<svg><defs><g id="glyph-0-1"><path d="M 1.00001 2.5"/></g><clipPath id="clip3"/></defs>'
       '<use xlink:href="#glyph-0-1" x="10.123449"/><g clip-path="url(#clip3)"/></svg>')


class TestNormalize:
    def test_ids_are_renumbered_with_their_references(self):
        other = SVG.replace('glyph-0-1', 'glyph-2-7').replace('clip3', 'clip9')
        assert cc.normalize_svg(SVG) == cc.normalize_svg(other)
        assert 'href="#id0"' in cc.normalize_svg(SVG) and 'url(#id1)' in cc.normalize_svg(SVG)

    def test_numbers_are_rounded(self):
        assert cc.normalize_svg('<p d="M 1.00001 -0.0001 2.5"/>') == '<p d="M 1.000 0.000 2.500"/>'
        assert cc.normalize_svg(SVG) != cc.normalize_svg(SVG.replace('10.123449', '10.2'))

    def test_integers_and_names_stay(self):
        assert cc.normalize_svg('<svg width="800" class="x1"/>') == '<svg width="800" class="x1"/>'


class TestCompare:
    def test_svg(self, tmp_path):
        a = _touch(tmp_path / 'a.svg', SVG)
        assert cc.compare_outputs(a, _touch(tmp_path / 'b.svg', SVG)) == ('same', '')
        renamed = _touch(tmp_path / 'c.svg', SVG.replace('clip3', 'clip4').replace('1.00001', '1.00002'))
        assert cc.compare_outputs(a, renamed) == ('same-normalized', 'numbers or ids')
        moved = _touch(tmp_path / 'd.svg', SVG.replace('10.123449', '11'))
        verdict, detail = cc.compare_outputs(a, moved)
        assert verdict == 'different' and detail.startswith('line 1:')

    def test_png(self, tmp_path):
        image = pytest.importorskip('PIL.Image')
        first = image.new('RGB', (4, 3), (255, 255, 255))
        first.save(tmp_path / 'a.png', compress_level=1)
        first.save(tmp_path / 'b.png', compress_level=9)      # other bytes, same pixels
        assert (tmp_path / 'a.png').read_bytes() != (tmp_path / 'b.png').read_bytes()
        assert cc.compare_outputs(tmp_path / 'a.png', tmp_path / 'b.png') == ('same-normalized', 'equal pixels')
        first.putpixel((1, 1), (0, 0, 0))
        first.save(tmp_path / 'c.png')
        assert cc.compare_outputs(tmp_path / 'a.png', tmp_path / 'c.png') == ('different', '1 of 12 pixels')

    @pytest.mark.parametrize('old,new,verdict', [
        (True, True, 'same'), (False, False, 'failed-both'), (False, True, 'fixed'), (True, False, 'broken')])
    def test_classify(self, old, new, verdict):
        assert cc.classify({'ok': old}, {'ok': new}, 'same' if old and new else None) == verdict


def test_the_report():
    def row(name, kind, verdict, base_t, head_t, ok=True):
        return {'id': name, 'kind': kind, 'verdict': verdict, 'detail': 'x' if verdict == 'different' else '',
                'base': {'ok': ok, 'times': {'load': base_t}}, 'head': {'ok': True, 'times': {'load': head_t}}}

    rows = [row('a.ggb', 'ggb', 'same', 1.0, 0.5), row('b.ggb', 'ggb', 'different', 3.0, 2.0),
            row('c.ggb', 'ggb', 'fixed', None, 1.0, ok=False)]
    report = cc.summarize(rows, base='1.10.0a3', head='1.11.0rc1')
    assert report['verdicts'] == {'ggb': {'same': 1, 'different': 1, 'fixed': 1}}
    assert report['timings']['ggb']['load'] == {'base': {'n': 2, 'median': 2.0, 'p95': 3.0, 'sum': 4.0},
                                                'head': {'n': 2, 'median': 1.25, 'p95': 2.0, 'sum': 2.5}}
    assert [r['id'] for r in report['notable']] == ['b.ggb', 'c.ggb']
    text = cc.markdown(report)
    assert '| ggb | 1 different, 1 fixed, 1 same |' in text
    assert '| ggb | load | 2.0 / 3.0 | 1.25 / 2.0 |' in text
    assert '- `b.ggb` (ggb): **different** x' in text
    json.dumps(report)


def test_the_runner_itself_imports_no_renderer():
    """Only the worker (a string run in a subprocess) imports the library."""
    import ast
    tree = ast.parse((REPO_ROOT / 'scripts' / 'classic_corpus.py').read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert not imported & {'man' + 'im', 'animageo'}
    assert 'from animageo import AnimaGeoScene' in cc._WORKER


class TestDiffs:
    """``docs/native/classic-diffs.json``: the intended differences (plan L6 item 11)."""

    def test_the_file_of_the_repository_loads(self):
        assert isinstance(cc.load_diffs(cc.DIFFS_PATH), dict)

    def test_verdicts(self):
        diffs = {'qa/a.ggb': {'item': '§15 equality', 'changelog': '1.11.0rc1'}}
        assert cc.apply_diffs('different', 'qa/a.ggb', diffs) == 'expected'
        assert cc.apply_diffs('broken', 'qa/a.ggb', diffs) == 'expected'
        assert cc.apply_diffs('same', 'qa/a.ggb', diffs) == 'unchanged-listed'
        assert cc.apply_diffs('different', 'qa/b.ggb', diffs) == 'different'
        assert cc.apply_diffs('failed-both', 'qa/a.ggb', diffs) == 'failed-both'

    def test_a_reason_is_required(self, tmp_path):
        path = tmp_path / 'd.json'
        path.write_text(json.dumps({'format': cc.DIFFS_FORMAT, 'diffs': {'a.ggb': {'item': 'x'}}}), encoding='utf-8')
        with pytest.raises(ValueError, match='changelog'):
            cc.load_diffs(path)
        path.write_text(json.dumps({'format': 'other', 'diffs': {}}), encoding='utf-8')
        with pytest.raises(ValueError, match='not an'):
            cc.load_diffs(path)
        assert cc.load_diffs(tmp_path / 'missing.json') == {}
