"""Parity fixtures ``animageo-parity/v1``: generate expectations and verify them.

A scene (``parity/v1/scenes/*.json``) is ``{format, id, document, cases:
[{name, inputs?}]}``. ``generate`` evaluates every case and writes the
fixture with ``registry``, ``generatedBy`` and, per case, ``scale``,
``expect`` (every element of the document) and ``checks``
(``"<operationId>:<checkId>" → status``). ``verify`` evaluates again and
compares: state, type, reason, cause and detail exactly; values within
``tol.parity`` of the case scale (``parity.length·S`` for coordinates and
lengths, ``parity.area·S²`` for areas, ``parity.scalar`` for unit
directions); check statuses exactly.

Near-degenerate inputs are refused: every degeneracy decision of an op
reports its decision value ``m`` measured from the exact boundary (a length,
a cross product, a segment parameter minus an end) with the decide
tolerance ``tol`` it is compared to; the generator refuses the case when
``0 < |m| < decisionMargin · tol`` (``decisionMargin = 1e3``,
``_numeric.json``). ``m == 0`` exactly — a degenerate case built from
binary-exact inputs — is accepted.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .document import load
from .kernel.checks import run_checks
from .kernel.evaluate import evaluate
from .kernel.numeric import decision_margin, tolerances
from .kernel.values import compare_values
from .registry import REGISTRY_VERSION, registry

__all__ = [
    'PARITY_FORMAT',
    'ParityError',
    'check_scene',
    'generate_scene',
    'generate',
    'verify_fixture',
    'verify',
    'expand_paths',
    'margin_problems',
]

PARITY_FORMAT = 'animageo-parity/v1'


class ParityError(ValueError):
    """A scene or fixture cannot be used."""


def _library_version() -> str:
    from .. import __version__
    return __version__


def _read(path) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def expand_paths(paths) -> list:
    """Files as given, directories as their ``*.json`` files (sorted)."""
    out = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            out.extend(sorted(p for p in path.glob('*.json') if p.is_file()))
        else:
            out.append(path)
    return out


def check_scene(scene) -> None:
    """Raise :class:`ParityError` unless ``scene`` has the scene shape."""
    if not isinstance(scene, dict) or scene.get('format') != PARITY_FORMAT:
        raise ParityError(f'not an {PARITY_FORMAT} scene')
    if not isinstance(scene.get('id'), str) or not scene['id']:
        raise ParityError('a scene needs a string id')
    if not isinstance(scene.get('document'), dict):
        raise ParityError(f"scene {scene['id']}: document must be an object")
    cases = scene.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ParityError(f"scene {scene['id']}: cases must be a non-empty array")
    names = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('name'), str) or not case['name']:
            raise ParityError(f"scene {scene['id']}: every case needs a name")
        if case['name'] in names:
            raise ParityError(f"scene {scene['id']}: case name {case['name']!r} is repeated")
        names.add(case['name'])
        if 'inputs' in case and not isinstance(case['inputs'], dict):
            raise ParityError(f"scene {scene['id']} / {case['name']}: inputs must be an object")


def margin_problems(decisions, operations) -> list:
    """Decisions too close to their threshold: ``0 < |m| < decisionMargin · tol``."""
    factor = decision_margin()
    problems = []
    for op_id, name, value, tol in decisions:
        if not math.isfinite(value):
            continue
        limit = factor * tol
        if 0 < abs(value) < limit:
            op_name = operations.get(op_id, {}).get('op', '?')
            problems.append(
                f'{op_id} ({op_name}): {name} decision value {value!r} is within '
                f'{factor:g}·tol.decide = {limit!r} of its threshold; use binary-exact '
                f'degenerate inputs or move the inputs farther from the threshold')
    return problems


def _evaluate_case(doc, case, *, refuse: bool):
    decisions = [] if refuse else None
    try:
        ev = evaluate(doc, inputs=case.get('inputs'), _decisions=decisions)
    except ValueError as exc:
        raise ParityError(str(exc)) from None
    if refuse:
        problems = margin_problems(decisions, doc.operations)
        if problems:
            raise ParityError('; '.join(problems))
    return ev, run_checks(ev)


def generate_scene(scene: dict) -> dict:
    """The fixture of one scene (raises :class:`ParityError`)."""
    check_scene(scene)
    try:
        doc = load(scene['document'], strict=True)
    except ValueError as exc:
        raise ParityError(f"scene {scene['id']}: {exc}") from None
    cases = []
    for case in scene['cases']:
        try:
            ev, report = _evaluate_case(doc, case, refuse=True)
        except ParityError as exc:
            raise ParityError(f"scene {scene['id']} / {case['name']}: {exc}") from None
        out = {'name': case['name']}
        if 'inputs' in case:
            out['inputs'] = case['inputs']
        out['scale'] = ev.scale
        out['expect'] = ev.elements
        out['checks'] = report.results
        cases.append(out)
    return {
        'format': PARITY_FORMAT,
        'id': scene['id'],
        'registry': REGISTRY_VERSION,
        'generatedBy': f'animageo {_library_version()}',
        'document': scene['document'],
        'cases': cases,
    }


def generate(paths, out_dir) -> list:
    """Generate fixtures for scene files/directories into ``out_dir``; returns written paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for path in expand_paths(paths):
        try:
            scene = _read(path)
        except (OSError, ValueError) as exc:
            raise ParityError(f'{path}: {exc}') from None
        fixtures.append((path, generate_scene(scene)))
    written = []
    for path, fixture in fixtures:
        target = out_dir / path.name
        _write(target, fixture)
        written.append(target)
    return written


def _compare_record(el_id, expected, actual, type_info, tol, label) -> list:
    out = []
    if not isinstance(expected, dict):
        return [f'{label} {el_id}: expectation is not an object']
    for key in ('state', 'type', 'reason', 'cause', 'detail'):
        if expected.get(key) != actual.get(key):
            out.append(f'{label} {el_id}.{key}: expected {expected.get(key)!r}, got {actual.get(key)!r}')
    if out:
        return out
    if expected.get('state') == 'defined':
        if 'value' not in expected:
            return [f'{label} {el_id}: defined without a value']
        for line in compare_values(type_info or {}, expected['value'], actual.get('value'), tol.parity):
            out.append(f'{label} {el_id}.{line}')
    elif 'value' in expected or 'value' in actual:
        out.append(f'{label} {el_id}: a value on a {expected.get("state")} element')
    return out


def verify_fixture(fixture: dict, label: str = '') -> list:
    """Mismatches between a fixture and this library, as readable lines."""
    label = label or str(fixture.get('id', '?'))
    try:
        check_scene(fixture)
        doc = load(fixture['document'], strict=True)
    except ValueError as exc:
        return [f'{label}: {exc}']
    reg = registry()
    mismatches = []
    for case in fixture['cases']:
        where = f"{label} [{case['name']}]"
        for key in ('scale', 'expect', 'checks'):
            if key not in case:
                mismatches.append(f'{where}: no {key!r}; run fixtures generate')
        if any(key not in case for key in ('scale', 'expect', 'checks')):
            continue
        try:
            ev, report = _evaluate_case(doc, case, refuse=False)
        except ParityError as exc:
            mismatches.append(f'{where}: {exc}')
            continue
        tol = tolerances(case['scale'])
        if not abs(ev.scale - case['scale']) <= tol.parity_length:
            mismatches.append(f"{where} scale: expected {case['scale']!r}, got {ev.scale!r}")
        expect = case['expect']
        for el_id in sorted(set(expect) | set(ev.elements)):
            if el_id not in ev.elements:
                mismatches.append(f'{where} {el_id}: expected but not evaluated')
                continue
            if el_id not in expect:
                mismatches.append(f'{where} {el_id}: evaluated but not expected')
                continue
            actual = ev.elements[el_id]
            type_info = reg.types.get(actual.get('type'))
            mismatches.extend(_compare_record(el_id, expect[el_id], actual, type_info, tol, where))
        checks = case['checks']
        for key in sorted(set(checks) | set(report.results)):
            if checks.get(key) != report.results.get(key):
                mismatches.append(f'{where} check {key}: expected {checks.get(key)!r}, '
                                  f'got {report.results.get(key)!r}')
    return mismatches


def verify(paths):
    """Verify fixture files/directories: ``(fixtures, cases, mismatches)``."""
    files = expand_paths(paths)
    cases = 0
    mismatches = []
    for path in files:
        try:
            fixture = _read(path)
        except (OSError, ValueError) as exc:
            mismatches.append(f'{path}: {exc}')
            continue
        if isinstance(fixture, dict) and isinstance(fixture.get('cases'), list):
            cases += len(fixture['cases'])
        mismatches.extend(verify_fixture(fixture, label=path.name))
    return len(files), cases, mismatches
