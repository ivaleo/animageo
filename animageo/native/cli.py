"""Command line of ``animageo.native``::

    python -m animageo.native fixtures generate <scenes…> -o <dir> [--steps <dir>]
    python -m animageo.native fixtures verify <fixtures…>
    python -m animageo.native fixtures conditions [-o <root>] [--check]
    python -m animageo.native registry index [--check]
    python -m animageo.native evaluate <doc.json> [--inputs case.json] [--canonical]
    python -m animageo.native validate <doc.json>
    python -m animageo.native commands fixtures [--lexicon <file>] -o <dir> [--check]
    python -m animageo.native commands parse <text file | -> [--lexicon <file>] [--base <doc.json>]
    python -m animageo.native commands print <doc.json> [--lexicon <file>]

Exit codes: 0 success; 1 verify mismatches, validate issues (invalid JSON
included), an out-of-date registry index or a refused scene, out-of-date
commands fixtures, a commands text with errors; 2 an input that cannot be
used (a missing file; for ``evaluate`` a document that does not load or bad
``--inputs``; an unusable lexicon).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .canonical import canonical_json
from .document import LoadError, load, validate
from .kernel.checks import run_checks
from .kernel.evaluate import evaluate
from .parity import ParityError, generate, verify
from .registry import REGISTRY_VERSION, registry_problems, write_index


def _out(text: str) -> None:
    sys.stdout.write(text + '\n')


def _err(text: str) -> None:
    sys.stderr.write(text + '\n')


def _library_version() -> str:
    from .. import __version__
    return __version__


def _cmd_fixtures_generate(args) -> int:
    try:
        written = generate(args.scenes, args.out, steps_dir=args.steps)
    except ParityError as exc:
        _err(f'refused: {exc}')
        return 1
    for path in written:
        _out(f'wrote {path}')
    return 0


def _cmd_fixtures_verify(args) -> int:
    files, cases, mismatches = verify(args.fixtures)
    for line in mismatches:
        _out(line)
    _out(f'{files} fixtures, {cases} cases, {len(mismatches)} mismatches')
    return 1 if mismatches else 0


def _cmd_fixtures_conditions(args) -> int:
    from .conditions.fixtures import DEFAULT_ROOT, check_fixtures, verify_fixtures, write_fixtures
    root = Path(args.out) if args.out else DEFAULT_ROOT
    if args.check:
        problems = check_fixtures(root)
        files, cases, mismatches = verify_fixtures(root)
        for item in problems + mismatches:
            _out(f'stale: {item}')
        _out(f'{files} fixtures, {cases} cases, {len(problems) + len(mismatches)} mismatches')
        return 1 if problems or mismatches else 0
    for path in write_fixtures(root):
        _out(str(path))
    return 0


def _cmd_registry_index(args) -> int:
    changed = write_index(check=args.check)
    if args.check:
        problems = [p for p in registry_problems() if 'INDEX.json' not in p]
        for name in changed:
            _out(f'out of date: {name}')
        for problem in problems:
            _out(problem)
        if changed or problems:
            _out('run: python -m animageo.native registry index')
            return 1
        _out(f'registry {REGISTRY_VERSION}: index is up to date')
        return 0
    for name in changed:
        _out(f'updated {name}')
    if not changed:
        _out(f'registry {REGISTRY_VERSION}: nothing to update')
    return 0


def _read_inputs(path):
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get('inputs'), dict) and 'kind' not in data:
        return data['inputs']
    return data


def _cmd_evaluate(args) -> int:
    try:
        doc = load(args.document)
        inputs = _read_inputs(args.inputs) if args.inputs else None
        ev = evaluate(doc, inputs=inputs)
    except LoadError as exc:
        for issue in exc.issues:
            _err(f'{issue.code} {issue.path or "/"}: {issue.message}')
        return 2
    except (OSError, ValueError) as exc:
        _err(str(exc))
        return 2
    result = ev.to_dict()
    if args.checks:
        result['checks'] = run_checks(ev).results
    if args.canonical:
        _out(canonical_json(result))
    else:
        _out(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_validate(args) -> int:
    try:
        doc = load(args.document, strict=False)
    except LoadError as exc:
        issues = exc.issues
    except (OSError, ValueError) as exc:
        _err(str(exc))
        return 2
    else:
        issues = validate(doc)
    if args.json:
        _out(json.dumps([i.to_dict() for i in issues], ensure_ascii=False, indent=2))
    else:
        for issue in issues:
            _out(f'{issue.severity} {issue.code} {issue.path or "/"}: {issue.message}')
        _out(f'{len(issues)} issues')
    return 1 if issues else 0


def _read_lexicon(path):
    """The lexicon of ``--lexicon`` (``None``: the shipped one); raises
    ``ValueError`` with the reasons when it is not usable."""
    from .commands.lexicon import Lexicon, LexiconError

    if not path:
        return Lexicon()
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    try:
        return Lexicon(data)
    except LexiconError as exc:
        raise ValueError('lexicon: ' + '; '.join(exc.problems)) from None


def _cmd_commands_fixtures(args) -> int:
    from .commands.fixtures import DEFAULT_DIR, check_fixtures, write_fixtures

    try:
        lexicon = _read_lexicon(args.lexicon)
    except (OSError, ValueError) as exc:
        _err(str(exc))
        return 2
    out = args.out or (None if args.lexicon else str(DEFAULT_DIR))
    if out is None:
        _err('-o/--out is required with --lexicon')
        return 2
    if args.check:
        problems = check_fixtures(out, lexicon)
        for line in problems:
            _out(line)
        if problems:
            _out('run: python -m animageo.native commands fixtures'
                 + (f' --lexicon {args.lexicon}' if args.lexicon else '') + f' -o {out}')
            return 1
        _out(f'commands fixtures in {out} are up to date (lexicon {lexicon.hash})')
        return 0
    for path in write_fixtures(out, lexicon):
        _out(f'wrote {path}')
    return 0


def _cmd_commands_parse(args) -> int:
    from .commands import parse_commands

    try:
        lexicon = _read_lexicon(args.lexicon)
        if args.text == '-':
            text = sys.stdin.read()
        else:
            with open(args.text, encoding='utf-8') as fh:
                text = fh.read()
        base = load(args.base) if args.base else None
        result = parse_commands(text, lexicon=lexicon, base=base, document_id=args.document_id)
    except LoadError as exc:
        for issue in exc.issues:
            _err(f'{issue.code} {issue.path or "/"}: {issue.message}')
        return 2
    except (OSError, ValueError) as exc:
        _err(str(exc))
        return 2
    payload = {
        'document': result.document.data,
        'effects': result.effects,
        'lines': result.lines,
        'issues': [i.to_dict() for i in result.issues],
    }
    if args.canonical:
        _out(canonical_json(payload))
    else:
        _out(json.dumps(payload, ensure_ascii=False, indent=2))
    for issue in result.issues:
        _err(f'{issue.severity} {issue.code} {issue.line}:{issue.column}: {issue.message}'
             + (f' ({issue.hint})' if issue.hint else ''))
    return 1 if any(i.severity == 'error' for i in result.issues) else 0


def _cmd_commands_print(args) -> int:
    from .commands import print_commands

    try:
        lexicon = _read_lexicon(args.lexicon)
        with open(args.document, encoding='utf-8') as fh:
            data = json.load(fh)
        if isinstance(data, dict) and data.get('format') == 'animageo-parity/v1':
            data = data.get('document')          # a parity scene or fixture
        result = print_commands(load(data), lexicon=lexicon)
    except LoadError as exc:
        for issue in exc.issues:
            _err(f'{issue.code} {issue.path or "/"}: {issue.message}')
        return 2
    except (OSError, ValueError) as exc:
        _err(str(exc))
        return 2
    _out(result.text)
    for issue in result.issues:
        _err(f'{issue.severity} {issue.code} {issue.line}:{issue.column}: {issue.message}')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m animageo.native',
        description='animageo.native: construction documents, the reference kernel and parity fixtures.',
    )
    parser.add_argument('--version', action='version',
                        version=f'animageo {_library_version()}, registry {REGISTRY_VERSION}')
    sub = parser.add_subparsers(dest='command', required=True)

    fixtures = sub.add_parser('fixtures', help='parity fixtures animageo-parity/v1')
    fsub = fixtures.add_subparsers(dest='action', required=True)
    gen = fsub.add_parser('generate', help='evaluate scenes and write fixtures with expectations')
    gen.add_argument('scenes', nargs='+', help='scene files or directories of *.json')
    gen.add_argument('-o', '--out', required=True, help='output directory')
    gen.add_argument('--steps', help='also write the animageo-steps/v1 fixtures into this directory')
    gen.set_defaults(func=_cmd_fixtures_generate)
    ver = fsub.add_parser('verify', help='re-evaluate fixtures and compare (exit 1 on mismatch)')
    ver.add_argument('fixtures', nargs='+', help='fixture files or directories of *.json')
    ver.set_defaults(func=_cmd_fixtures_verify)

    fc = fsub.add_parser('conditions', help='write (or --check) the fixtures of recipes, general case and marks')
    fc.add_argument('-o', '--out', help='root directory (default: the shipped parity/v1)')
    fc.add_argument('--check', action='store_true', help='compare with a fresh build and replay every case')
    fc.set_defaults(func=_cmd_fixtures_conditions)

    reg = sub.add_parser('registry', help='operation registry ops/v1')
    rsub = reg.add_subparsers(dest='action', required=True)
    idx = rsub.add_parser('index', help='refresh signatureHash fields and INDEX.json')
    idx.add_argument('--check', action='store_true', help='only check; exit 1 when out of date')
    idx.set_defaults(func=_cmd_registry_index)

    ev = sub.add_parser('evaluate', help='evaluate a document (animageo-evaluated/v1)')
    ev.add_argument('document', help='animageo-construction/v1 JSON file')
    ev.add_argument('--inputs', help='JSON file: {elementId: input} or a case {"inputs": {...}}')
    ev.add_argument('--checks', action='store_true', help='add the check results')
    ev.add_argument('--canonical', action='store_true', help='print canonical JSON')
    ev.set_defaults(func=_cmd_evaluate)

    va = sub.add_parser('validate', help='list the issues of a document (exit 1 if any)')
    va.add_argument('document', help='animageo-construction/v1 JSON file')
    va.add_argument('--json', action='store_true', help='print the issues as JSON')
    va.set_defaults(func=_cmd_validate)

    cm = sub.add_parser('commands', help='«Команды»: the text form of a document')
    csub = cm.add_subparsers(dest='action', required=True)
    cf = csub.add_parser('fixtures', help='write (or --check) the commands fixtures of a lexicon')
    cf.add_argument('--lexicon', help='animageo-lexicon/v1 JSON file (default: the shipped lexicon)')
    cf.add_argument('-o', '--out', help='output directory (default without --lexicon: the shipped fixtures)')
    cf.add_argument('--check', action='store_true', help='only compare; exit 1 when out of date')
    cf.set_defaults(func=_cmd_commands_fixtures)
    cp = csub.add_parser('parse', help='parse commands; print {document, effects, lines, issues}')
    cp.add_argument('text', help='a text file of commands, or - for stdin')
    cp.add_argument('--lexicon', help='animageo-lexicon/v1 JSON file')
    cp.add_argument('--base', help='a document to edit (edit mode)')
    cp.add_argument('--document-id', help='documentId of a new document')
    cp.add_argument('--canonical', action='store_true', help='print canonical JSON')
    cp.set_defaults(func=_cmd_commands_parse)
    cr = csub.add_parser('print', help='print a document as commands')
    cr.add_argument('document', help='animageo-construction/v1 JSON file (or a parity scene)')
    cr.add_argument('--lexicon', help='animageo-lexicon/v1 JSON file')
    cr.set_defaults(func=_cmd_commands_print)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
