"""The deliberate ``.ggb`` files, the corpus expectations and the coverage of the
table (plan L5 §8, stage 3; 1.10.0a2)."""
import json
import zipfile

import pytest

from animageo.native.cli import main
from animageo.native.convert import from_ggb
from animageo.native.convert.corpus import corpus_files, coverage, expectation, record, verify
from tests.native.conftest import REPO_ROOT
from tests.native.ggb_synth import SYNTHETIC, SYNTHETIC_DIR, ggb_bytes, point, triangle, zip_bytes
from tests.native.test_native_l5_ggb import NS, _check

EXPECTED_DIR = REPO_ROOT / 'tests/native/import/expected'

# what each deliberate file is for: {ggb_name: (category, reason)}, the dropped kinds, or the refusal
PURPOSE = {
    'triangle_editable': {'all': 'editable'},
    'value_mismatch': {'M': ('differs', 'value_mismatch')},
    'intersections': {'all': 'editable'},
    'breakpoints': {'all': 'editable', 'steps': 3},
    'scripts_and_button': {'t1': ('picture', 'script'), 'b1': ('unsupported', 'script'), 'dropped': {'script'}},
    'list': {'L': ('unsupported', 'list'), 'L2': ('unsupported', 'list')},
    'macro': {'D': ('editable', None), 'warnings': {'macros_expanded'}},
    'three_d': {'P': ('unsupported', '3d'), 'p': ('unsupported', '3d'), 'dropped': {'3d'}},
    'cas': {'dropped': {'cas'}},
    'spreadsheet': {'A1': ('editable', None), 'B1': ('unsupported', 'parse_error'),
                    'P': ('closure', 'depends_on_unsupported')},
    'dtd': {'refused': 'ggb_invalid'},
    'not_a_ggb': {'refused': 'import_not_ggb'},
    'pictures_only': {'t1': ('picture', 'fixed_text'), 't2': ('picture', 'latex_macros'),
                      'pic1': ('unsupported', 'image'), 'document': False},
    'texts': {'t1': ('editable', None), 'title': ('picture', 'fixed_text'), 't2': ('picture', 'fixed_text'),
              't3': ('picture', 'fixed_text')},
    'function_closure': {'f': ('unsupported', 'formula_unsupported'), 'P': ('closure', 'depends_on_unsupported'),
                         'M': ('closure', 'depends_on_unsupported')},
    'formula_argument': {"I'": ('picture', 'formula_unsupported'), 'M': ('picture', 'depends_on_unsupported')},
    'dropped_effects': {'all': 'editable',
                        'dropped': {'conditional_visibility', 'dynamic_color', 'animation', 'layers'}},
    'random_point': {'R': ('picture', 'random_point')},
    'style_labels': {'all': 'editable'},
    'ui_objects': {'tf': ('unsupported', 'ui_object'), 'cb': ('unsupported', 'ui_object'), 'n': ('editable', None)},
    'regular_polygon': {'poly1': ('editable', None), 'poly2': ('unsupported', 'unsupported_signature')},
    'latex_texts': {'n': ('editable', None), 't2': ('picture', 'latex_macros'), 't3': ('picture', 'fixed_text')},
    'command_synonym': {'all': 'editable'},
}


def test_the_files_are_the_output_of_the_generator():
    """``tests/native/import/synthetic/`` is ``python -m tests.native.ggb_synth``:
    the same entries in the same order, with the same bytes, dates and method
    (the deflated bytes themselves depend on the zlib of the machine)."""
    on_disk = sorted(p.stem for p in SYNTHETIC_DIR.glob('*.ggb'))
    assert on_disk == sorted(SYNTHETIC)
    assert len(SYNTHETIC) >= 15
    for name, (purpose, build) in SYNTHETIC.items():
        assert purpose, name
        with zipfile.ZipFile(SYNTHETIC_DIR / f'{name}.ggb') as disk, zipfile.ZipFile(_bytes_io(build())) as fresh:
            assert [_entry(disk, i) for i in disk.infolist()] == [_entry(fresh, i) for i in fresh.infolist()], name


def _bytes_io(data):
    import io
    return io.BytesIO(data)


def _entry(zf, info):
    return info.filename, info.date_time, info.compress_type, info.external_attr, zf.read(info)


def test_the_generator_is_reproducible():
    for _, build in SYNTHETIC.values():
        assert build() == build()
    assert ggb_bytes(triangle()) == ggb_bytes(triangle())


@pytest.mark.parametrize('name', sorted(PURPOSE))
def test_each_file_shows_what_it_is_for(name):
    data = (SYNTHETIC_DIR / f'{name}.ggb').read_bytes()
    want = PURPOSE[name]
    if 'refused' in want:
        from animageo.native.convert import ImportRefused
        with pytest.raises(ImportRefused) as exc:
            from_ggb(data, id_namespace=NS)
        assert exc.value.code == want['refused']
        return
    doc, rep = from_ggb(data, id_namespace=NS, name=f'{name}.ggb')
    _check(doc, rep)
    by_name = {e['ggb_name']: e for e in rep['elements']}
    if want.get('all'):
        assert {e['category'] for e in rep['elements']} == {want['all']}
    for label, (category, reason) in ((k, v) for k, v in want.items() if isinstance(v, tuple)):
        assert (by_name[label]['category'], by_name[label].get('reason')) == (category, reason), label
    if 'dropped' in want:
        assert {d['kind'] for d in rep['dropped']} == want['dropped']
    if 'warnings' in want:
        assert want['warnings'] <= {w['code'] for w in rep['warnings']}
    if 'document' in want:
        assert (doc is not None) == want['document']
    if 'steps' in want:
        assert len(doc['steps']) == want['steps']


def test_every_deliberate_file_has_a_purpose():
    assert set(PURPOSE) == set(SYNTHETIC)


def test_the_synthetic_corpus_meets_its_expectations():
    problems, checked = verify(SYNTHETIC_DIR, EXPECTED_DIR)
    assert problems == [] and checked == len(SYNTHETIC)


def test_record_and_verify(tmp_path):
    corpus = tmp_path / 'corpus'
    (corpus / 'a' / 'b').mkdir(parents=True)
    (corpus / 'small.ggb').write_bytes(ggb_bytes(point('A', 0.0, 0.0)))
    (corpus / 'a' / 'b' / 'tri.ggb').write_bytes(ggb_bytes(triangle()))
    (corpus / 'broken.ggb').write_bytes(b'PK not a zip')
    (corpus / 'notes.txt').write_text('not a ggb')
    assert [p.relative_to(corpus).as_posix() for p in corpus_files(corpus)] == ['a/b/tri.ggb', 'broken.ggb',
                                                                                'small.ggb']
    expected = tmp_path / 'expected'
    written = record(corpus, expected)
    assert len(written) == 3 and all(p.parent == expected for p in written)
    assert verify(corpus, expected) == ([], 3)
    exp = json.loads((expected / written[0].name).read_text(encoding='utf-8'))
    assert exp['file'] == 'a/b/tri.ggb' and exp['outcome'] == 'report' and len(exp['elements']) == 7
    assert exp == expectation(corpus / 'a' / 'b' / 'tri.ggb', name='a/b/tri.ggb')
    # a changed category is a difference, by object
    exp['elements'][3] = ['t1', 'differs', 'value_mismatch']
    exp['summary']['editable'] -= 1
    exp['summary']['differs'] += 1
    (expected / written[0].name).write_text(json.dumps(exp), encoding='utf-8')
    problems, _ = verify(corpus, expected)
    assert problems == ['a/b/tri.ggb: editable 6 → 7', 'a/b/tri.ggb: differs 1 → 0',
                        'a/b/tri.ggb: t1: differs value_mismatch → editable']
    # a file without an expectation, a changed refusal
    (corpus / 'new.ggb').write_bytes(zip_bytes({'readme.txt': 'x'}))
    broken = expectation(corpus / 'broken.ggb')
    (expected / f'{broken["sha256"]}.json').write_text(json.dumps({**broken, 'code': 'import_too_large'}))
    problems, checked = verify(corpus, expected)
    assert checked == 4
    assert 'broken.ggb: outcome import_too_large → import_not_ggb' in problems
    assert any(p.startswith('new.ggb: no expectation') for p in problems)


def test_cli_corpus_and_coverage(tmp_path, capsys):
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    (corpus / 'tri.ggb').write_bytes(ggb_bytes(triangle()))
    expected = tmp_path / 'expected'
    assert main(['convert', 'corpus', 'record', str(corpus), '--expected', str(expected)]) == 0
    assert main(['convert', 'corpus', 'verify', str(corpus), '--expected', str(expected)]) == 0
    assert '1 files, 0 differences' in capsys.readouterr().out
    (corpus / 'other.ggb').write_bytes(ggb_bytes(point('A', 1.0, 1.0)))
    assert main(['convert', 'corpus', 'verify', str(corpus), '--expected', str(expected)]) == 1
    assert main(['convert', 'corpus', 'verify', str(tmp_path / 'missing')]) == 2
    capsys.readouterr()
    assert main(['convert', 'map', '--coverage', str(corpus)]) == 0
    text = capsys.readouterr().out
    assert text.startswith('2 files, 8 objects') and 'polygon' in text
    assert main(['convert', 'map', '--coverage', str(corpus), '--json']) == 0
    cov = json.loads(capsys.readouterr().out)
    assert cov['categories']['editable'] == 8 and cov['keys']['polygon']['editable'] == 4
    assert cov['keys']['type:point']['editable'] == 4 and cov['editable_share'] == 1.0
    assert main(['convert', 'map', '--coverage', str(tmp_path / 'missing')]) == 2


def test_coverage_of_the_synthetic_corpus():
    cov = coverage(SYNTHETIC_DIR)
    assert cov['files'] == len(SYNTHETIC)
    assert cov['refused'] == {'ggb_invalid': 1, 'import_not_ggb': 1}
    assert cov['objects'] == sum(cov['categories'].values()) == sum(sum(v.values()) for v in cov['keys'].values())
    assert cov['keys']['intersect_lc']['editable'] == 2
