"""Generate reproducible GGB source files, scenes and typed-import parity.

Run ``python -m tests.native.ggb_expression_fixtures [--check]``.
The optional ``import`` section records source XML and report expectations,
including refused objects, alongside the ordinary kernel parity cases.
"""
from __future__ import annotations

import argparse
import json
import io
import math
import zipfile
from pathlib import Path

from animageo import native
from animageo.native import parity
from animageo.native.convert import report_problems
from animageo.native._fixture_compare import same_fixture
from tests.native.ggb_synth import command, element, expression, ggb_bytes, point
from tests.native.test_native_l5_ggb import NS

ROOT = Path(__file__).resolve().parents[2]
NAMES = ('ggb_point_expression', 'ggb_vector_expression', 'ggb_vector_rotate', 'ggb_expression_refused')


def operands():
    return (point('A', 1., 2.) + point('B', 3., -1.) + point('O', 0., 0.)
            + element('numeric', 'a', extra='<value val="2"/>')
            + element('angle', 'α', extra=f'<value val="{math.pi / 3}"/>')
            + command('Vector', ['O', 'B'], ['v'])
            + element('vector', 'v', extra='<coords x="3" y="-1" z="0"/>')
            + expression('f', 'a*x^2', 'function') + element('function', 'f'))


def formula(label, text, kind, xy):
    z = 1 if kind == 'point' else 0
    return expression(label, text, kind) + element(kind, label, extra=
        f'<coords x="{xy[0]}" y="{xy[1]}" z="{z}"/>')


def source(name):
    body = operands()
    if name in ('ggb_point_expression', 'ggb_vector_expression'):
        kind = 'point' if name == 'ggb_point_expression' else 'vector'
        for label, text, xy in [
            ('P_sum', 'A + v', (4., 1.)), ('P_points', 'A + B', (4., 1.)),
            ('P_pair', '(a, 4)', (2., 4.)), ('P_linear', '2A − B', (-1., 5.)),
            ('P_coords', '(x(A), y(v))', (1., -1.)),
            ('P_trig', '(cos(α), sin(α))', (.5, math.sqrt(3) / 2)),
            ('P_fn', '(1, f(2))', (1., 8.)), ('P_div', '(0, 1/(4a))', (0., .125)),
        ]:
            body += formula(label, text, kind, xy)
        changes = [{'A': ('point', [4., 5.]), 'a': ('number', 5.)}, {'a': ('number', 0.)},
                   {'a': ('number', -2.), 'B': ('point', [-1., 3.])}]
    elif name == 'ggb_vector_rotate':
        body += (command('Rotate', ['Vector[(a, 0)]', '90°', 'O'], ['u'])
                 + element('vector', 'u', extra='<coords x="0" y="2" z="0"/>')
                 + command('Rotate', ['Vector[(a, f(a))]', '-α', 'O'], ['w'])
                 + element('vector', 'w', extra=f'<coords x="{1 + 4 * math.sqrt(3)}" '
                                                f'y="{4 - math.sqrt(3)}" z="0"/>')
                 + command('Translate', ['A', 'Vector[(a, f(a))]'], ['T']) + point('T', 3., 10.))
        changes = [{'a': ('number', 0.)}, {'a': ('number', -3.)}, {'O': ('point', [2., 1.])}]
    else:
        for label, text, kind in [('Bad_div', 'A/B', 'point'), ('Bad_pair', '(a, 0, 1)', 'point'),
                                  ('Bad_scalar', 'x(A)', 'point'), ('Bad_list', '{A, B}', 'vector')]:
            body += formula(label, text, kind, (1., 2.))
        changes = [{'A': ('point', [2., -3.])}]
    return body, changes


def build(name):
    body, changes = source(name)
    raw = ggb_bytes(body)
    doc, report = native.from_ggb(raw, id_namespace=NS)
    assert doc is not None and report_problems(report, doc) == []
    items = {e['ggb_name']: e for e in report['elements']}
    assert all(e['category'] == ('unsupported' if e['ggb_type'] == 'vector' else 'picture')
               and e['reason'] == 'formula_unsupported' if n.startswith('Bad_') else e['category'] == 'editable'
               for n, e in items.items()), items
    doc['documentId'] = name
    scene = {'format': 'animageo-parity/v1', 'id': name, 'document': doc,
             'cases': [{'name': 'saved'}] + [
                 {'name': f'changed-{i}', 'inputs': {items[n]['native_ids'][0]: {'kind': k, 'value': v}
                                                   for n, (k, v) in change.items()}}
                 for i, change in enumerate(changes, 1)]}
    fixture = parity.generate_scene(scene)
    fixture['import'] = {'xml': body, 'elements': [
        {k: e[k] for k in ('ggb_name', 'ggb_type', 'category', 'reason', 'detail', 'value_check', 'native_ids') if k in e}
        for e in report['elements']]}
    return raw, scene, fixture


def outputs():
    for name in NAMES:
        raw, scene, fixture = build(name)
        yield ROOT / 'tests/native/import/expressions' / f'{name}.ggb', raw
        yield ROOT / 'tests/native/import/scenes' / f'{name}.json', scene
        yield ROOT / 'animageo/native/parity/v1/ggb' / f'{name}.json', fixture


def same_archive(saved, generated):
    """Compare entries independently of the host zlib's deflate bytes."""
    with zipfile.ZipFile(io.BytesIO(saved)) as a, zipfile.ZipFile(io.BytesIO(generated)) as b:
        return a.namelist() == b.namelist() and all(a.read(n) == b.read(n) for n in a.namelist())


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    mismatches = []
    for path, value in outputs():
        if args.check:
            matches = path.exists() and (same_archive(path.read_bytes(), value) if isinstance(value, bytes)
                                         else same_fixture(json.loads(path.read_text()), value))
            if not matches:
                mismatches.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
    print(f'{len(NAMES)} source files and parity fixtures; {len(mismatches)} differences')
    for line in mismatches:
        print(line)
    return bool(mismatches)


if __name__ == '__main__':
    raise SystemExit(main())
