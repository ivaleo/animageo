"""``import-audit``: how much of a corpus of ``.ggb`` files the import carries over."""
import hashlib
import json
import uuid

import pytest

from animageo.native.cli import main
from animageo.native.convert import from_ggb
from animageo.native.convert.audit import _counts, audit, audit_line, web_categories
from tests.native.ggb_synth import command, ggb_bytes, point, triangle
from tests.native.test_native_ggb_conic_meet import body as conic_meet_body


def meet_body():
    """Four points of an ellipse and a circle (``intersect.conic_conic``, registry 1.8) and a
    midpoint built on one of them."""
    return conic_meet_body(['q', 'k'], ['P', 'Q', 'R', 'S']) + command('Midpoint', ['P', 'O'], ['M']) + point(
        'M', 0.5 * 4.05 ** 0.5, 0.5 * 2.2 ** 0.5)


def lost_body():
    """A conic by a command the import does not know and its centre: unsupported and closure."""
    return (point('A', 0., 0.) + command('Foo', ['A'], ['c']) + '<element type="conic" label="c"/>'
            + command('Center', ['c'], ['C']) + point('C', 0., 0.))


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / 'corpus'
    (root / 'deep').mkdir(parents=True)
    files = {'full.ggb': ggb_bytes(triangle()), 'deep/meet.ggb': ggb_bytes(meet_body()),
             'deep/lost.ggb': ggb_bytes(lost_body()), 'broken.ggb': b'not a zip'}
    for rel, data in files.items():
        (root / rel).write_bytes(data)
    (root / 'notes.txt').write_text('not a ggb')
    return root, {rel: hashlib.sha256(data).hexdigest() for rel, data in files.items()}


def report_of(path):
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    return from_ggb(data, id_namespace=uuid.UUID(sha[:32]), name=path.name)


def test_totals_are_the_weighted_categories_of_the_reports(corpus):
    root, sha = corpus
    weights = {sha['deep/meet.ggb']: 3, sha['broken.ggb']: 2}
    result = audit([root], weights=weights)
    assert [r['path'] for r in result['files']] == [str(root / p) for p in
                                                   ('broken.ggb', 'deep/lost.ggb', 'deep/meet.ggb', 'full.ggb')]
    expected = {'editable': 0, 'picture': 0, 'differs': 0, 'unsupported': 0, 'closure': 0}
    for rel in ('full.ggb', 'deep/meet.ggb', 'deep/lost.ggb'):
        _doc, rep = report_of(root / rel)
        for cat in expected:
            expected[cat] += weights.get(sha[rel], 1) * rep['summary'][cat]
    t = result['totals']['library']
    assert t['files'] == 1 + 2 + 3 + 1
    assert t['refused'] == 2 and t['errors'] == 0
    assert {c: t[c] for c in expected} == expected
    assert t['lost'] == expected['unsupported'] + expected['closure'] > 0
    assert t['objects'] == sum(expected.values())
    assert t['full'] == 1 + 3                    # the triangle and the conics; not the lost file, not the refused one
    rows = {r['path']: r for r in result['files']}
    assert rows[str(root / 'broken.ggb')]['outcome'] == 'refused'
    assert rows[str(root / 'deep/lost.ggb')]['full'] is False
    assert 'web' not in result['totals']


def test_full_needs_a_document_and_no_lost_picture_differs_or_dropped():
    editable = [{'category': 'editable'}]
    assert _counts(editable, {}, [])['full'] is True
    assert _counts(editable, None, [])['full'] is False
    assert _counts(editable, {}, ['animation'])['full'] is False
    for cat in ('picture', 'differs', 'unsupported', 'closure'):
        assert _counts(editable + [{'category': cat}], {}, [])['full'] is False
    counted = _counts([{'category': 'differs', 'reason': 'value_unchecked'},
                       {'category': 'differs', 'reason': 'value_mismatch'}], {}, [])
    assert (counted['differs'], counted['value_unchecked']) == (2, 1)


def test_operations_newer_than_the_web_registry_are_pictures_and_their_dependents_closure(tmp_path):
    path = tmp_path / 'meet.ggb'
    path.write_bytes(ggb_bytes(meet_body()))
    doc, rep = report_of(path)
    assert all(e['category'] == 'editable' for e in rep['elements'])
    web = {n: (c, r) for n, c, r in web_categories(rep, doc, '1.7')}
    for name in 'PQRS':
        assert web[name] == ('picture', 'web_capability_missing')
    assert web['M'] == ('closure', 'depends_on_unsupported')
    assert web['q'] == web['k'] == ('editable', None)
    assert all(c == 'editable' for _n, c, _r in web_categories(rep, doc, '1.8'))
    t = audit([path], web_registry='1.7')['totals']
    assert (t['library']['full'], t['library']['picture'], t['library']['lost']) == (1, 0, 0)
    assert (t['web']['full'], t['web']['picture'], t['web']['lost']) == (0, 4, 1)
    assert t['web']['editable'] == t['library']['editable'] - 5
    assert t['web']['objects'] == t['library']['objects']


def test_a_hidden_helper_of_a_newer_operation_takes_its_dependents(tmp_path):
    path = tmp_path / 'meet.ggb'
    path.write_bytes(ggb_bytes(meet_body()))
    doc, rep = report_of(path)
    # the same graph with the conic intersection as an anonymous helper of M: M itself is built on it
    entry = {e['ggb_name']: e for e in rep['elements']}
    for name in 'PQRS':
        entry[name]['native_ids'] = []
    web = {n: (c, r) for n, c, r in web_categories(rep, doc, '1.7')}
    assert web['M'] == ('picture', 'web_capability_missing')


def test_cli_prints_the_library_and_web_lines_and_writes_json(corpus, tmp_path, capsys):
    root, sha = corpus
    weights = tmp_path / 'weights.json'
    weights.write_text(json.dumps({sha['full.ggb']: 2}))
    out = tmp_path / 'audit.json'
    assert main(['import-audit', str(root / 'full.ggb'), str(root / 'deep'), '--weights', str(weights),
                 '--json', str(out), '--web-registry', '1.7']) == 0
    lines = capsys.readouterr().out.splitlines()
    data = json.loads(out.read_text())
    assert data['format'] == 'animageo.import_audit' and data['webRegistry'] == '1.7'
    assert lines == [audit_line('library', data['totals']['library']),
                     audit_line('web at registry 1.7', data['totals']['web'])]
    assert lines[0].startswith('library files 4 full 3 objects ')
    assert lines[1].startswith('web at registry 1.7 files 4 full 2 objects ')
    assert [len(r['elements']) for r in data['files']] == [len(report_of(root / p)[1]['elements'])
                                                           for p in ('full.ggb', 'deep/lost.ggb', 'deep/meet.ggb')]


@pytest.mark.parametrize('args', [['missing-dir'], ['{root}', '--web-registry', 'next'],
                                  ['{root}', '--weights', '{bad}']])
def test_cli_refuses_unusable_input(corpus, tmp_path, capsys, args):
    root, _sha = corpus
    bad = tmp_path / 'bad.json'
    bad.write_text('[1, 2]')
    argv = ['import-audit'] + [a.format(root=root, bad=bad) for a in args]
    assert main(argv) == 2
    assert capsys.readouterr().out == ''
