"""Reproduce tangency imports, changed inputs and their parity fixtures.

Run ``python -m tests.native.ggb_tangency_fixtures [--check]``. Synthetic
archives come from the XML below. The saved archives are unchanged GeoGebra
5.4.936.0 files; regeneration only needs the copies shipped in this tree.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import zipfile
from pathlib import Path

from animageo import native
from animageo.native import parity
from animageo.native._fixture_compare import same_fixture
from animageo.native.convert import report_problems
from tests.native.ggb_synth import command, element, expression, ggb_bytes, point
from tests.native.ggb_function_analysis_fixtures import same_archive
from tests.native.test_native_l5_ggb import NS
from tests.native.test_native_tangency_import import conic, function, line, number

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / 'tests/native/import/tangency'
SYNTHETIC = ('graph', 'helpers', 'conic', 'sparse', 'parallel_circle', 'slope', 'refused')
SAVED = ('abscissa', 'parameter', 'domain', 'corner', 'hole', 'external', 'multiplicity',
         'inside', 'vertical', 'parallel', 'hyperbola', 'parabola', 'slope', 'circle')
NAMES = tuple('ggb_tangency_' + n for n in SYNTHETIC) + tuple('ggb_tangency_saved_' + n for n in SAVED)


def synthetic_source(name):
    if name == 'graph':
        body = number('a', 1) + number('u', 1) + point('A', 1., 7.) + function('a*x^2')
        body += expression('Q', '(x(A),f(x(A)))', 'point') + point('Q', 1., 1.)
        for arg, label in [('u', 't'), ('A', 's')]:
            body += command('Tangent', [arg, 'f'], [label]) + line(label, (-2, 1, 1))
        body += command('OrthogonalLine', ['Q', 's'], ['n']) + line('n', (1, 2, -3))
        body += command('Slope', ['n'], ['m']) + number('m', -.5)
        changes = [('ordinate', {'A': [1, -20]}), ('abscissa', {'u': 2, 'A': [2, 7]}),
                   ('coefficient', {'a': 3}), ('horizontal', {'a': 0}), ('restored', {'a': 1})]
    elif name == 'helpers':
        body = point('A', -2., 7.) + number('a', 2)
        body += command('Tangent', ['A', 'a*x^2'], ['t']) + line('t', (8, 1, 8))
        body += command('Tangent', ['x(A)+a', 'x^2'], ['s']) + line('s', (0, 1, 0))
        changes = [('zero', {'A': [0, 99]}), ('positive', {'A': [3, -7]}), ('coefficient', {'a': -1})]
    elif name == 'conic':
        body = point('P', 4., 0.) + conic() + command('Tangent', ['P', 'K'], ['lower', 'upper'])
        body += line('lower', (math.sqrt(3), -6, -4*math.sqrt(3)))
        body += line('upper', (-math.sqrt(3), -6, 4*math.sqrt(3)))
        changes = [('on_curve', {'P': [2, 0]}), ('inside', {'P': [0, 0]}),
                   ('opposite', {'P': [-4, 0]}), ('restored', {'P': [4, 0]})]
    elif name == 'sparse':
        body = point('P', 0., 0.) + conic() + command('Tangent', ['P', 'K'], ['', 't'])
        body += line('t', ('NaN',)*3)
        changes = [('outside', {'P': [4, 0]}), ('on_curve', {'P': [2, 0]}), ('restored', {'P': [0, 0]})]
    elif name == 'parallel_circle':
        body = conic('x^2+y^2=4', (1, 1, -4, 0, 0, 0)) + point('A', 0., 0.) + point('B', 1., 0.)
        body += command('Line', ['A', 'B'], ['l']) + line('l', (0, 1, 0))
        body += command('Tangent', ['l', 'K'], ['t', 's']) + line('t', (0, 1, -2)) + line('s', (0, 1, 2))
        changes = [('vertical', {'B': [0, 1]}), ('reversed', {'B': [-1, 0]}), ('restored', {'B': [1, 0]})]
    elif name == 'slope':
        body = point('A', 0., 0.) + point('B', 0., 1.) + command('Line', ['A', 'B'], ['l']) + line('l', (1, 0, 0))
        body += command('Slope', ['l'], ['s']) + number('s', 'NaN')
        body += number('u', 0) + function('sqrt(x)') + command('Tangent', ['u', 'f'], ['t'])
        body += line('t', ('-Infinity', 1, 'NaN'))
        changes = [('finite', {'B': [1, 2], 'u': 1}), ('outside', {'u': -1}), ('recovered', {'u': 4})]
    elif name == 'refused':
        body = point('P', 2., 0.) + conic() + command('Tangent', ['P', 'K'], ['t', 's'])
        body += line('t', (1, 0, -2)) + line('s', (-3, 0, 6))
        body += command('OrthogonalLine', ['P', 't'], ['n']) + line('n', (0, 1, 0))
        changes = []
    else:
        raise KeyError(name)
    return ggb_bytes(body), changes


def source(name):
    suffix = name.removeprefix('ggb_tangency_')
    if not suffix.startswith('saved_'):
        return synthetic_source(suffix)
    changes = {
        'abscissa': [('abscissa', {'u': 2, 'A': [2, -4]}), ('zero', {'u': 0, 'A': [0, 7]})],
        'parameter': [('coefficient', {'a': 3}), ('flat', {'a': 0})],
        'domain': [('interior', {'u': 1}), ('outside', {'u': -1}), ('recovery', {'u': 0})],
        'corner': [('left', {'u': -1}), ('right', {'u': 1}), ('join', {'u': 0})],
        'hole': [('regular', {'u': 0, 'a': .5}), ('hole', {'u': 1}), ('pole', {'a': 0})],
        'external': [('on_curve', {'P': [2, 0]}), ('inside', {'P': [0, 0]}), ('opposite', {'P': [-4, 0]})],
        'inside': [('external', {'P': [4, 0]}), ('recovered', {'P': [0, 0]})],
        'vertical': [('off_curve', {'A': [4, 0]}), ('other_touch', {'A': [0, 1]})],
        'hyperbola': [('center', {'P': [0, 0]}), ('vertex', {'P': [1, 0]}), ('recovery', {'P': [1, 1]})],
    }.get(suffix.removeprefix('saved_'), [])
    return (SOURCE_DIR / f'{name}.ggb').read_bytes(), changes


def build(name):
    raw, changes = source(name)
    doc, report = native.from_ggb(raw, id_namespace=NS)
    assert doc is not None and report_problems(report, doc) == []
    items = {e['ggb_name']: e for e in report['elements']}
    doc['documentId'] = name
    scene = {'format': 'animageo-parity/v1', 'id': name, 'document': doc, 'cases': [{'name': 'saved'}] + [
        {'name': title, 'inputs': {items[n]['native_ids'][0]: {'kind': 'point' if isinstance(v, list) else 'number',
                                                          'value': v} for n, v in change.items()}}
        for title, change in changes]}
    fixture = parity.generate_scene(scene)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        xml = archive.read('geogebra.xml').decode('utf-8')
    fixture['import'] = {'xml': xml, 'elements': [
        {k: e[k] for k in ('ggb_name', 'ggb_type', 'category', 'reason', 'detail', 'value_check', 'native_ids') if k in e}
        for e in report['elements']]}
    return raw, scene, fixture


def outputs():
    for name in NAMES:
        raw, scene, fixture = build(name)
        yield SOURCE_DIR / f'{name}.ggb', raw
        yield ROOT / 'tests/native/import/scenes' / f'{name}.json', scene
        yield ROOT / 'animageo/native/parity/v1/ggb' / f'{name}.json', fixture


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    mismatches = []
    for path, value in outputs():
        if args.check:
            same = path.exists() and (same_archive(path.read_bytes(), value) if isinstance(value, bytes)
                                      else same_fixture(json.loads(path.read_text()), value))
            if not same:
                mismatches.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode())
    print(f'{len(NAMES)} source files and parity fixtures; {len(mismatches)} mismatches')
    for name in mismatches:
        print(name)
    return bool(mismatches)


if __name__ == '__main__':
    raise SystemExit(main())
