"""Command line of ``animageo.native``::

    python -m animageo.native fixtures generate <scenes…> -o <dir> [--steps <dir>]
    python -m animageo.native fixtures verify <fixtures…>
    python -m animageo.native fixtures conditions [-o <root>] [--check]
    python -m animageo.native fixtures timeline [-o <dir>] [--check]
    python -m animageo.native registry index [--check]
    python -m animageo.native evaluate <doc.json> [--inputs case.json] [--canonical]
    python -m animageo.native validate <doc.json>
    python -m animageo.native commands fixtures [--lexicon <file>] -o <dir> [--check]
    python -m animageo.native commands parse <text file | -> [--lexicon <file>] [--base <doc.json>]
    python -m animageo.native commands print <doc.json> [--lexicon <file>]
    python -m animageo.native steps <doc.json>
    python -m animageo.native describe <doc.json> [--values] [--precision N]
    python -m animageo.native timeline <doc.json> [--lag L --duration D --pause P --start S]
    python -m animageo.native timeline <doc.json> --timeline <keyframes.json> --t T [--bridge]
    python -m animageo.native from-ggb <file.ggb> [-o doc.json] [--report rep.json] [--namespace UUID] [--mode partial|strict]
    python -m animageo.native convert map [--check]

Exit codes: 0 success; 1 verify mismatches, validate issues (invalid JSON
included), an out-of-date registry index or a refused scene, out-of-date
commands fixtures, a commands text with errors, out-of-date timeline
fixtures, ``from-ggb --mode strict`` with objects that do not translate, a
problem of the GGB command table (``convert map --check``); 2 an input that
cannot be used (a missing file; for ``evaluate`` a document that does not load
or bad ``--inputs``; an unusable lexicon; a ``.ggb`` refused by ``from-ggb``).
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


def _cmd_fixtures_timeline(args) -> int:
    from .timeline_fixtures import DEFAULT_DIR, check_fixtures, verify_fixtures, write_fixtures
    root = Path(args.out) if args.out else DEFAULT_DIR
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


def _read_document(path):
    """A document file, or the document of a parity scene or fixture."""
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if isinstance(data, dict) and data.get('format') != 'animageo-construction/v1' and \
            isinstance(data.get('document'), dict):
        data = data['document']
    return load(data)


def _document_command(args, run) -> int:
    try:
        result = run(_read_document(args.document))
    except LoadError as exc:
        for issue in exc.issues:
            _err(f'{issue.code} {issue.path or "/"}: {issue.message}')
        return 2
    except (OSError, ValueError) as exc:
        _err(str(exc))
        return 2
    if isinstance(result, str):
        _out(result)
    else:
        _out(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_steps(args) -> int:
    from .steps import steps
    return _document_command(args, lambda doc: [s.to_dict() for s in steps(doc)])


def _cmd_describe(args) -> int:
    from .describe import describe
    return _document_command(args, lambda doc: '\n'.join(
        describe(doc, values=args.values, precision=args.precision)))


def _cmd_timeline(args) -> int:
    from .timeline import sample_timeline, steps_timeline, timeline_to_bridge

    def run(doc):
        if args.timeline is None:
            if args.t is not None or args.bridge:
                raise ValueError('--t and --bridge need --timeline')
            return steps_timeline(doc, lag=args.lag, duration=args.duration, pause=args.pause,
                                  start=args.start).to_dict()
        with open(args.timeline, encoding='utf-8') as fh:
            timeline = json.load(fh)
        if isinstance(timeline, dict) and isinstance(timeline.get('keyframes'), dict):
            timeline = timeline['keyframes']          # a steps timeline printed by this command
        if args.bridge:
            return timeline_to_bridge(doc, timeline)
        if args.t is None:
            raise ValueError('--timeline needs --t or --bridge')
        return sample_timeline(doc, timeline, args.t)
    return _document_command(args, run)


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
        'conditionRequests': result.conditionRequests,
        'queries': result.queries,
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


def _cmd_from_ggb(args) -> int:
    import hashlib
    import uuid
    from .convert import ConvertError, ImportRefused, from_ggb
    try:
        data = Path(args.file).read_bytes()
    except OSError as exc:
        _err(str(exc))
        return 2
    try:
        ns = uuid.UUID(args.namespace) if args.namespace else uuid.UUID(hashlib.sha256(data).hexdigest()[:32])
    except ValueError:
        _err(f'--namespace: not a UUID: {args.namespace}')
        return 2
    try:
        doc, report = from_ggb(data, id_namespace=ns, mode=args.mode, name=Path(args.file).name)
    except ImportRefused as exc:
        _err(f'{exc.code}: {exc.detail}')
        return 2
    except ConvertError as exc:
        for item in exc.items:
            _err(f'{item.get("name")}: {item.get("command") or ""} {item.get("reason") or ""}')
        return 1
    if args.out and doc is not None:
        Path(args.out).write_text(canonical_json(doc) + '\n', encoding='utf-8')
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not args.out and not args.report:
        _out(json.dumps({'document': doc, 'report': report}, ensure_ascii=False, indent=2))
    else:
        _out(' '.join(f'{k} {v}' for k, v in report['summary'].items()))
    return 0


def _cmd_convert_map(args) -> int:
    from .convert import dsl_map, map_problems
    problems = map_problems()
    for p in problems:
        _out(p)
    table = dsl_map()
    rows = table.commands
    mapped = sum(1 for r in rows.values() if 'op' in r or 'free' in r)
    ops = {r['op'] for r in rows.values() if 'op' in r}
    if not args.check or problems:
        _out(f'{len(rows)} classic signatures, {mapped} translated to {len(ops)} operations, '
             f'map version {table.version}')
    return 1 if problems else 0


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

    ft = fsub.add_parser('timeline', help='write (or --check) the animageo-timeline/v1 fixtures')
    ft.add_argument('-o', '--out', help='directory (default: the shipped parity/v1/timeline)')
    ft.add_argument('--check', action='store_true', help='compare with a fresh build and replay every case')
    ft.set_defaults(func=_cmd_fixtures_timeline)

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
    cp = csub.add_parser('parse', help='parse commands; print {document, effects, lines, issues, conditionRequests, queries}')
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

    st = sub.add_parser('steps', help='the steps of a document (native.steps) as JSON')
    st.add_argument('document', help='animageo-construction/v1 JSON file (or a scene or fixture)')
    st.set_defaults(func=_cmd_steps)
    de = sub.add_parser('describe', help='the text of a construction (native.describe)')
    de.add_argument('document', help='animageo-construction/v1 JSON file (or a scene or fixture)')
    de.add_argument('--values', action='store_true', help='add the values now')
    de.add_argument('--precision', type=int, default=2, help='digits after the comma (default 2)')
    de.set_defaults(func=_cmd_describe)
    tl = sub.add_parser('timeline', help='steps_timeline of a document, or a timeline sampled at --t')
    tl.add_argument('document', help='animageo-construction/v1 JSON file (or a scene or fixture)')
    tl.add_argument('--lag', type=float, default=0.3)
    tl.add_argument('--duration', type=float, default=0.5)
    tl.add_argument('--pause', type=float, default=0.6)
    tl.add_argument('--start', type=float, default=0.0)
    tl.add_argument('--timeline', help='keyframes by element ID (JSON); with --t: sample_timeline')
    tl.add_argument('--t', type=float, help='the time to sample --timeline at')
    tl.add_argument('--bridge', action='store_true', help='print timeline_to_bridge of --timeline')
    tl.set_defaults(func=_cmd_timeline)

    fg = sub.add_parser('from-ggb', help='import a .ggb: the document and the import_report.v1')
    fg.add_argument('file', help='a .ggb file')
    fg.add_argument('-o', '--out', help='write the document (canonical JSON) here')
    fg.add_argument('--report', help='write the import report here')
    fg.add_argument('--namespace', help='UUID namespace of the IDs (default: from the sha256 of the file)')
    fg.add_argument('--mode', choices=('partial', 'strict'), default='partial',
                    help='strict: exit 1 unless every object is editable')
    fg.set_defaults(func=_cmd_from_ggb)
    cv = sub.add_parser('convert', help='the GGB command → operation table')
    cvsub = cv.add_subparsers(dest='action', required=True)
    cvm = cvsub.add_parser('map', help='check convert/dsl_map.json against the classic commands and the registry')
    cvm.add_argument('--check', action='store_true', help='print only the problems; exit 1 when any')
    cvm.set_defaults(func=_cmd_convert_map)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
