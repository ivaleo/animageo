"""Reproduce function-analysis GGB imports and their editable parity cases.

Run ``python -m tests.native.ggb_function_analysis_fixtures [--check]``.
Synthetic archives are rebuilt from XML below. The ``saved_*`` archives are
unaltered GeoGebra 5.4.936.0 inputs kept beside the generated source files;
generation never needs a separate installation or external source directory.
Saved coordinates are import evidence, not the analytical test expectations.
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
from tests.native.test_native_l5_ggb import NS

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / 'tests/native/import/functions'
SYNTHETIC = ('roots', 'extrema', 'intervals', 'axes', 'value', 'helpers', 'refused')
SAVED = ('multiplicity', 'rank', 'quartic', 'ordinate', 'point_value',
         'touching_difference', 'constant_difference', 'near_difference')
NAMES = tuple('ggb_function_' + name for name in SYNTHETIC) + tuple(
    'ggb_function_saved_' + name for name in SAVED)


def number(label, value):
    return element('numeric', label, extra=f'<value val="{value}"/>')


def function(label, text):
    return expression(label, text, 'function') + element('function', label)


def result(name, inputs, outputs):
    """A command with explicit source ordinals, including empty outputs."""
    return command(name, inputs, [label for label, _ in outputs]) + ''.join(
        point(label, *xy) if xy is not None else element(
            'point', label, extra='<coords x="NaN" y="NaN" z="NaN"/>')
        for label, xy in outputs if label)


def synthetic_source(name):
    if name == 'roots':
        body = number('k', 1) + function('f', 'x^2-k')
        body += result('Root', ['f'], [('Right', (1, 0)), ('', None),
                                      ('Left', (-1, 0)), ('Spare', None)])
        changes = [('merged', {'k': 0}), ('absent', {'k': -1}), ('restored', {'k': 4})]
    elif name == 'extrema':
        body = number('k', 1) + function('f', 'x^3-3*k*x')
        body += result('Extremum', ['f'], [('Maximum', (-1, 2)), ('Minimum', (1, -2))])
        changes = [('wider', {'k': 4}), ('stationary', {'k': 0}), ('monotone', {'k': -1})]
    elif name == 'intervals':
        body = number('a', -4) + number('b', 4) + number('s', 1) + function('f', 'sin(x)')
        body += result('Roots', ['f', 'a', 'b'], [('L', (-math.pi, 0)), ('M', (0, 0)), ('R', (math.pi, 0))])
        body += result('Root', ['f', 's'], [('Near', (0, 0))])
        body += result('Root', ['f', 'a', 'b'], [('Single', (0, 0))])
        body += result('Extremum', ['f', 'a', 'b'], [('Low', (-math.pi/2, -1)), ('High', (math.pi/2, 1))])
        changes = [('positive', {'a': .25, 'b': 4, 's': 3}),
                   ('negative', {'a': -4, 'b': -.25, 's': -3}),
                   ('reversed', {'a': 4, 'b': -4}), ('recovered', {'a': -4, 'b': 4, 's': 6})]
    elif name == 'axes':
        body = number('k', 1) + function('f', 'x^2-k')
        body += result('Intersect', ['f', 'xAxis', '2'], [('Indexed', (1, 0))])
        body += result('Intersect', ['xAxis', 'f'], [('Left', (-1, 0)), ('Right', (1, 0))])
        body += command('Intersect', ['yAxis', 'f', '1'], ['Ordinate'])
        body += element('point', 'Ordinate', extra='<coords x="0" y="-2" z="2"/>')
        changes = [('wider', {'k': 4}), ('merged', {'k': 0}), ('absent', {'k': -1})]
    elif name == 'value':
        body = number('c', 2) + number('a', 3) + function('f', 'c*x^2-1')
        body += expression('P', '(a,f(a))', 'point') + point('P', 3, 17)
        body += expression('v', 'f(a)') + number('v', 17)
        changes = [('abscissa', {'a': -2}), ('coefficient', {'c': -1}),
                   ('both', {'c': 0, 'a': 100})]
    elif name == 'helpers':
        body = number('k', 1) + number('a', 2)
        body += result('Root', ['x^2-k'], [('L', (-1, 0)), ('R', (1, 0))])
        body += result('Root', ['x^2-k', '-a-1', 'a+1'], [('Single', (-1, 0))])
        changes = [('wider', {'k': 4, 'a': 3}), ('empty', {'a': -1}), ('recovered', {'a': 2})]
    elif name == 'refused':
        body = number('k', 2) + function('f', 'sin(x)') + function('p', 'x^2-1')
        for label, cmd, args in [
            ('Unbounded', 'Intersect', ['f', 'xAxis']),
            ('DynamicIndex', 'Intersect', ['p', 'xAxis', 'k']),
            ('MissingOrdinate', 'Intersect', ['f', 'yAxis', '2']),
            ('NonPolynomial', 'Root', ['f']),
            ('UnknownFormula', 'Root', ['gamma(x)']),
        ]:
            body += result(cmd, args, [(label, (0, 0))])
        changes = []
    else:
        raise KeyError(name)
    return ggb_bytes(body), changes


def source(name):
    suffix = name.removeprefix('ggb_function_')
    if not suffix.startswith('saved_'):
        return synthetic_source(suffix)
    changes = {
        'rank': [('merged', {'a': 0}), ('absent_pair', {'a': -1}), ('restored', {'a': 4})],
        'ordinate': [('coefficient', {'a': 5}), ('zero', {'a': 0})],
        'point_value': [('negative', {'a': -2}), ('zero', {'a': 0}), ('larger', {'a': 3})],
        'near_difference': [('middle', {'a': 1.01}), ('right', {'a': 1.03})],
    }.get(suffix.removeprefix('saved_'), [])
    return (SOURCE_DIR / f'{name}.ggb').read_bytes(), changes


def build(name):
    raw, changes = source(name)
    doc, report = native.from_ggb(raw, id_namespace=NS)
    assert doc is not None and report_problems(report, doc) == []
    items = {e['ggb_name']: e for e in report['elements']}
    doc['documentId'] = name
    scene = {'format': 'animageo-parity/v1', 'id': name, 'document': doc,
             'cases': [{'name': 'saved'}] + [
                 {'name': title, 'inputs': {items[n]['native_ids'][0]: {'kind': 'number', 'value': v}
                                            for n, v in change.items()}}
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


def same_archive(saved, generated):
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
