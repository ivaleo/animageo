"""Reproduce conic-element source imports and editable parity scenes.

Synthetic archives come from the XML below; saved archives are unaltered
GeoGebra 5.4.936.0 files shipped beside them. No external source is needed.
Run ``python -m tests.native.ggb_conic_elements_fixtures [--check]``.
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
from tests.native.ggb_function_analysis_fixtures import same_archive
from tests.native.ggb_synth import command, element, ggb_bytes, point
from tests.native.test_native_l5_ggb import NS
from tests.native.test_native_tangency_import import conic, function, line, number
from tests.native.test_native_conic_elements_import import circle, ellipse, undefined

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / 'tests/native/import/conic_elements'
SYNTHETIC = ('parts', 'circle', 'collapsed_center', 'asymptotes', 'polar', 'diameter', 'sparse', 'inline', 'refused')
SAVED = ('pairing', 'pairing_rotated', 'parts', 'circle', 'parabola', 'hyperbola', 'axes', 'asymptotes',
         'polar', 'polar_near_center', 'diameter_line', 'diameter_vector', 'diameter_zero', 'diameter_far', 'degenerate', 'center')
NAMES = tuple('ggb_conic_elements_'+n for n in SYNTHETIC) + tuple('ggb_conic_elements_saved_'+n for n in SAVED)


def result(name, args, outputs, kind='line'):
    return command(name, args, [n for n, _ in outputs]) + ''.join(
        undefined(n, kind) if value is None else point(n, *value) if kind == 'point' else line(n, value)
        for n, value in outputs if n)


def synthetic_source(name):
    if name == 'parts':
        body = ellipse()
        body += result('Focus', ['K'], [('R', (math.sqrt(5), 0)), ('L', (-math.sqrt(5), 0))], 'point')
        body += result('Vertex', ['K'], [('V', (3, 0)), ('U', (-3, 0)), ('T', (0, 2)), ('B', (0, -2))], 'point')
        body += result('Axes', ['K'], [('h', (0, 1, 0)), ('v', (1, 0, 0))])
        body += result('Directrix', ['K'], [('left', (1, 0, 9/math.sqrt(5))), ('right', (1, 0, -9/math.sqrt(5)))])
        body += result('MajorAxis', ['K'], [('major', (0, 1, 0))])
        body += result('SecondAxis', ['K'], [('minor', (1, 0, 0))])
        changes = [('wider', {'a': 1}), ('circle', {'a': 9}), ('hyperbola', {'a': -4}), ('restored', {'a': 4})]
    elif name == 'circle':
        body = circle()
        body += result('Center', ['c'], [('Q', (1, -2))], 'point')
        body += result('Focus', ['c'], [('F', (1, -2)), ('G', (1, -2))], 'point')
        body += result('Vertex', ['c'], [('A', (-2, -2)), ('B', (4, -2)), ('C', (1, -5)), ('D', (1, 1))], 'point')
        body += result('Axes', ['c'], [('h', (0, 1, 2)), ('v', (1, 0, -1))])
        body += result('MinorAxis', ['c'], [('minor', (1, 0, -1))])
        body += result('Directrix', ['c'], [('d', None), ('e', None)])
        body += result('Asymptote', ['c'], [('s', None), ('t', None)])
        changes = [('center', {'O': [-2, 3]}), ('radius', {'r': 2}), ('collapsed', {'r': 0}), ('restored', {'r': 3})]
    elif name == 'collapsed_center':
        body = point('M', 1., -2.) + point('N', 1., -2.) + point('O', 1., -2.)
        body += command('Circle', ['M', 'N', 'O'], ['c'])
        body += element('conic', 'c', extra='<matrix A0="1" A1="1" A2="5" A3="0" A4="-1" A5="2"/>')
        body += result('Center', ['c'], [('Q', (1, -2))], 'point')
        changes = [('separated', {'N': [2, -2], 'O': [1, -1]}),
                   ('translated', {'M': [2, 0], 'N': [3, 0], 'O': [2, 1]})]
    elif name == 'asymptotes':
        body = number('a', -4) + conic('9*x^2+a*y^2=36', (9, -4, -36, 0, 0, 0))
        body += result('Asymptote', ['K'], [('s', (-3, 2, 0)), ('t', (-3, -2, 0))])
        changes = [('ellipse', {'a': 4}), ('circle', {'a': 9}), ('degenerate', {'a': 0}), ('recovery', {'a': -4})]
    elif name == 'polar':
        body = ellipse() + circle() + point('P', 2., 0.)
        body += result('Polar', ['P', 'K'], [('s', (8, 0, -36))])
        body += result('Polar', ['P', 'c'], [('t', (1, 2, -6))])
        changes = [('ellipse_center', {'P': [0, 0]}), ('circle_center', {'P': [1, -2]}),
                   ('near_center', {'P': [1e-12, 0]}), ('outside', {'P': [6, 2]})]
    elif name == 'diameter':
        body = ellipse() + circle() + point('A', 0., 0.) + point('B', 1., 1.)
        body += result('Line', ['A', 'B'], [('d', (-1, 1, 0))])
        body += command('Vector', ['A', 'B'], ['v']) + element('vector', 'v', extra='<coords x="1" y="1" z="0"/>')
        for direction, name, curve, saved in [('d', 'l', 'K', (4, 9, 0)), ('v', 'm', 'K', (4, 9, 0)), ('d', 'n', 'c', (1, 1, 1))]:
            body += result('ConjugateDiameter' if direction == 'v' else 'Diameter', [direction, curve], [(name, saved)])
        changes = [('vertical', {'B': [0, 1]}), ('zero', {'B': [0, 0]}),
                   ('translated', {'A': [5, 3], 'B': [6, 4]}), ('reversed', {'B': [-1, -1]})]
    elif name == 'sparse':
        body = number('a', 0) + conic('a*x^2+y^2=4*x', (0, 1, 0, 0, -2, 0))
        body += result('Focus', ['K'], [('F', (1, 0)), ('', None)], 'point')
        body += result('Focus', ['K'], [('', None), ('G', None)], 'point')
        body += result('Vertex', ['K'], [('P', (0, 0)), ('', None), ('R', None), ('S', None)], 'point')
        body += result('Axes', ['K'], [('h', (0, 1, 0)), ('v', (1, 0, 0))])
        body += result('Directrix', ['K'], [('d', (1, 0, 1)), ('', None)])
        body += result('Asymptote', ['K'], [('', None), ('s', None)])
        changes = [('circle', {'a': 1}), ('hyperbola', {'a': -1}), ('recovery', {'a': 0})]
    elif name == 'inline':
        body = number('a', 4) + point('A', 1., 0.)
        body += result('Polar', ['A+(1,0)', 'a*x^2+9*y^2=36'], [('p', (8, 0, -36))])
        body += result('Diameter', ['Vector[(1,1)]', 'a*x^2+9*y^2=36'], [('d', (4, 9, 0))])
        body += result('Asymptote', ['9*x^2-4*y^2=36'], [('s', (-3, 2, 0)), ('t', (-3, -2, 0))])
        changes = [('coefficient', {'a': 1}), ('abscissa', {'A': [3, 0]}), ('ordinate', {'A': [1, 7]})]
    elif name == 'refused':
        body = circle() + ellipse() + function()
        body += result('Axes', ['c'], [('h', (0, 1, 2)), ('v', (0, 2, 4))])
        body += result('OrthogonalLine', ['O', 'h'], [('n', (1, 0, -1))])
        body += result('Asymptote', ['f'], [('bad', (1, 0, 0))])
        body += result('Polar', ['h', 'K'], [('pole', (0, 0))], 'point')
        body += command('Eccentricity', ['K'], ['e']) + number('e', math.sqrt(5)/3)
        changes = []
    else:
        raise KeyError(name)
    return ggb_bytes(body), changes


def source(name):
    suffix = name.removeprefix('ggb_conic_elements_')
    if not suffix.startswith('saved_'):
        return synthetic_source(suffix)
    changes = {
        'polar': [('center', {'P': [0, 0]}), ('near', {'P': [1e-12, 0]}), ('recovery', {'P': [1, 0]})],
    }.get(suffix.removeprefix('saved_'), [])
    return (SOURCE_DIR/(name+'.ggb')).read_bytes(), changes


def build(name):
    raw, changes = source(name)
    doc, report = native.from_ggb(raw, id_namespace=NS)
    assert doc is not None and report_problems(report, doc) == []
    items = {e['ggb_name']: e for e in report['elements']}
    doc['documentId'] = name
    scene = {'format': 'animageo-parity/v1', 'id': name, 'document': doc, 'cases': [{'name': 'saved'}] + [
        {'name': title, 'inputs': {items[n]['native_ids'][0]: {'kind': 'point' if isinstance(v, list) else 'number', 'value': v}
                                 for n, v in change.items()}} for title, change in changes]}
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
        yield SOURCE_DIR/(name+'.ggb'), raw
        yield ROOT/'tests/native/import/scenes'/(name+'.json'), scene
        yield ROOT/'animageo/native/parity/v1/ggb'/(name+'.json'), fixture


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
