"""The ``animageo-construction/v1`` document: load, validate, dump.

``load`` checks the structure (the rules of ``schema/construction.v1.schema.json``
plus ``xmin < xmax``, ``ymin < ymax`` of ``viewDefaults.bounds``) without a
``jsonschema`` dependency. ``validate`` adds the graph rules against the
registry; see ``docs/native/kernel.md`` for the issue codes.

``load → dump`` keeps the document as given: no defaults are added and keys
the library does not know are preserved, so the canonical dump of a canonical
input is byte-for-byte the input.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .canonical import canonical_json, sha256_of
from .expr import MAX_TEMPLATE_LENGTH, template_problems
from .expr import problems as expr_problems
from .registry import FREE_INPUT_DEFAULTS, REGISTRY_VERSION, free_slot, registry

__all__ = [
    'DOCUMENT_FORMAT',
    'NativeDocument',
    'LoadError',
    'Issue',
    'load',
    'validate',
    'dump',
    'dumps',
    'content_hash',
    'iter_refs',
]

DOCUMENT_FORMAT = 'animageo-construction/v1'

ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
SLOT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
OUTPUT_SLOT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[1-9][0-9]*)?$')
OP_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')
TYPE_RE = re.compile(r'^[a-z][a-z0-9_]*$')
VERSION_RE = re.compile(r'^[0-9]+\.[0-9]+$')

_REQUIRED = ('format', 'documentId', 'operationRegistryVersion', 'operations', 'elements')


@dataclass(frozen=True)
class Issue:
    """One problem of a document. ``severity`` is ``"error"`` or ``"warning"``."""

    code: str
    path: str
    message: str
    elementId: str | None = None
    operationId: str | None = None
    severity: str = 'error'

    def to_dict(self) -> dict:
        out = {'code': self.code, 'path': self.path, 'message': self.message, 'severity': self.severity}
        if self.elementId is not None:
            out['elementId'] = self.elementId
        if self.operationId is not None:
            out['operationId'] = self.operationId
        return out


class LoadError(ValueError):
    """The document cannot be read; ``issues`` lists the reasons."""

    def __init__(self, issues):
        self.issues = list(issues)
        head = '; '.join(f'{i.path or "/"}: {i.message}' for i in self.issues[:5])
        more = f' (+{len(self.issues) - 5} more)' if len(self.issues) > 5 else ''
        super().__init__(f'invalid {DOCUMENT_FORMAT} document: {head}{more}')


class NativeDocument:
    """A loaded document. ``data`` is the JSON object; treat it as read-only."""

    __slots__ = ('_data', 'schema_issues')

    def __init__(self, data: dict, schema_issues=()):
        self._data = data
        self.schema_issues = tuple(schema_issues)

    @property
    def data(self) -> dict:
        return self._data

    @property
    def document_id(self):
        return self._data.get('documentId')

    @property
    def registry_version(self):
        return self._data.get('operationRegistryVersion')

    @property
    def operations(self) -> dict:
        return self._data.get('operations') or {}

    @property
    def elements(self) -> dict:
        return self._data.get('elements') or {}

    @property
    def inputs(self) -> dict:
        return self._data.get('inputs') or {}

    @property
    def bounds(self):
        """``viewDefaults.bounds`` or ``None``."""
        view = self._data.get('viewDefaults')
        return view.get('bounds') if isinstance(view, dict) else None

    def __repr__(self):
        return (f'NativeDocument({self.document_id!r}, operations={len(self.operations)}, '
                f'elements={len(self.elements)})')


# ── JSON reading ─────────────────────────────────────────────────────────


def _pointer(*parts) -> str:
    return ''.join('/' + str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def _reject_constant(name):
    raise ValueError(f'{name} is not valid JSON')


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'duplicate key {key!r}')
        out[key] = value
    return out


def _parse_json(text: str):
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_no_duplicates)
    except ValueError as exc:
        raise LoadError([Issue('schema', '', f'not valid JSON: {exc}')]) from None


def _read_source(source):
    if isinstance(source, NativeDocument):
        return source.data
    if isinstance(source, dict):
        return source
    if isinstance(source, (bytes, bytearray)):
        return _parse_json(bytes(source).decode('utf-8'))
    if isinstance(source, os.PathLike):
        return _parse_json(Path(source).read_text(encoding='utf-8'))
    if isinstance(source, str):
        if source.lstrip()[:1] in ('{', '['):
            return _parse_json(source)
        return _parse_json(Path(source).read_text(encoding='utf-8'))
    raise TypeError(f'cannot load a document from {type(source).__name__}')


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_number(value) -> bool:
    return _is_number(value) and math.isfinite(value)


def _json_issues(value, path, out):
    """Values a JSON document cannot hold (NaN, ∞, non-string keys, objects)."""
    if value is None or isinstance(value, (bool, str)):
        return
    if _is_number(value):
        if not math.isfinite(value):
            out.append(Issue('schema', path, 'numbers must be finite'))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                out.append(Issue('schema', path, f'object key {key!r} is not a string'))
                continue
            _json_issues(item, path + _pointer(key), out)
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _json_issues(item, path + _pointer(i), out)
        return
    out.append(Issue('schema', path, f'{type(value).__name__} is not a JSON value'))


# ── structure (mirror of construction.v1.schema.json) ───────────────────


_WORK_INTENT_KEYS = ('condition', 'forbid', 'assumptions', 'briefRevision')
_CONDITION_SOURCES = ('typed', 'photo', 'voice')
_FORBID = ('solution', 'move_given', 'extra_points')
_CONDITION_TEXT_MAX = 4000
_ASSUMPTIONS_MAX = 10
_ASSUMPTION_MAX = 200


class _Structure:
    def __init__(self):
        self.issues = []

    def add(self, path, message, **ids):
        self.issues.append(Issue('schema', path, message, **ids))

    def object(self, value, path, what) -> bool:
        if not isinstance(value, dict):
            self.add(path, f'{what} must be an object')
            return False
        return True

    def string(self, value, path, what, pattern=None) -> bool:
        if not isinstance(value, str):
            self.add(path, f'{what} must be a string')
            return False
        if pattern is not None and not pattern.match(value):
            self.add(path, f'{what} {value!r} does not match {pattern.pattern}')
            return False
        return True

    def keys(self, value, path, what, required, allowed=None, **ids):
        for key in required:
            if key not in value:
                self.add(path, f'{what} misses required key {key!r}', **ids)
        if allowed is not None:
            for key in value:
                if key not in allowed:
                    self.add(path + _pointer(key), f'{what} does not allow key {key!r}', **ids)

    def numbers(self, value, path, what, count) -> bool:
        if not isinstance(value, list) or len(value) != count or not all(_is_number(v) for v in value):
            self.add(path, f'{what} must be an array of {count} numbers')
            return False
        return True

    def argument(self, arg, path, op_id):
        if not self.object(arg, path, 'an argument'):
            return
        kind = arg.get('kind')
        if 'kind' not in arg:
            self.add(path, "an argument misses required key 'kind'", operationId=op_id)
            return
        if kind == 'ref':
            self.keys(arg, path, 'a ref argument', ('kind', 'elementId'), ('kind', 'elementId'), operationId=op_id)
            if 'elementId' in arg:
                self.string(arg['elementId'], path + '/elementId', 'elementId', ID_RE)
        elif kind == 'list':
            self.keys(arg, path, 'a list argument', ('kind', 'items'), ('kind', 'items'), operationId=op_id)
            items = arg.get('items')
            if 'items' in arg:
                if not isinstance(items, list):
                    self.add(path + '/items', 'items must be an array', operationId=op_id)
                else:
                    for i, item in enumerate(items):
                        self.argument(item, f'{path}/items/{i}', op_id)
        elif kind == 'number':
            self.keys(arg, path, 'a number argument', ('kind', 'value'), ('kind', 'value'), operationId=op_id)
            if 'value' in arg and not _is_number(arg['value']):
                self.add(path + '/value', 'value must be a number', operationId=op_id)
        elif kind == 'expr':           # registry 1.4 (a5): the tree itself is checked by validate (formula)
            self.keys(arg, path, 'an expr argument', ('kind', 'ast'), ('kind', 'ast'), operationId=op_id)
            if 'ast' in arg:
                self.object(arg['ast'], path + '/ast', 'ast')
        elif kind == 'template':       # registry 1.4 (a5): inserts are checked by validate (formula)
            self.keys(arg, path, 'a template argument', ('kind', 'value'), ('kind', 'value'), operationId=op_id)
            value = arg.get('value')
            if 'value' in arg and (not isinstance(value, str) or len(value) > MAX_TEMPLATE_LENGTH):
                self.add(path + '/value', f'value must be a string of at most {MAX_TEMPLATE_LENGTH} characters',
                         operationId=op_id)
        else:
            self.add(path + '/kind', f'unknown argument kind {kind!r} (ref, list, number, expr, template)',
                     operationId=op_id)

    def operation(self, key, op, path):
        if not self.object(op, path, 'an operation'):
            return
        self.keys(op, path, 'an operation', ('id', 'op', 'args', 'outputs'),
                  ('id', 'op', 'args', 'outputs', 'branch'), operationId=key)
        if 'id' in op:
            self.string(op['id'], path + '/id', 'id', ID_RE)
        if 'op' in op:
            self.string(op['op'], path + '/op', 'op', OP_RE)
        args = op.get('args')
        if 'args' in op and self.object(args, path + '/args', 'args'):
            for slot, arg in args.items():
                self.string(slot, path + '/args' + _pointer(slot), 'an argument slot', SLOT_RE)
                self.argument(arg, path + '/args' + _pointer(slot), key)
        outputs = op.get('outputs')
        if 'outputs' in op:
            if not isinstance(outputs, list):
                self.add(path + '/outputs', 'outputs must be an array', operationId=key)
            else:
                for i, out in enumerate(outputs):
                    opath = f'{path}/outputs/{i}'
                    if not self.object(out, opath, 'an output'):
                        continue
                    self.keys(out, opath, 'an output', ('slot', 'elementId'), ('slot', 'elementId'), operationId=key)
                    if 'slot' in out:
                        self.string(out['slot'], opath + '/slot', 'slot', OUTPUT_SLOT_RE)
                    if 'elementId' in out:
                        self.string(out['elementId'], opath + '/elementId', 'elementId', ID_RE)
        if 'branch' in op and op['branch'] is not None:
            branch = op['branch']
            bpath = path + '/branch'
            if self.object(branch, bpath, 'branch'):
                self.keys(branch, bpath, 'branch', ('policy', 'selector'), ('policy', 'selector'), operationId=key)
                for name in ('policy', 'selector'):
                    if name in branch:
                        self.string(branch[name], f'{bpath}/{name}', name)

    def element(self, key, el, path):
        if not self.object(el, path, 'an element'):
            return
        self.keys(el, path, 'an element', ('id', 'type', 'producer', 'displayName'),
                  ('id', 'type', 'producer', 'displayName', 'origin'), elementId=key)
        if 'id' in el:
            self.string(el['id'], path + '/id', 'id', ID_RE)
        if 'type' in el:
            self.string(el['type'], path + '/type', 'type', TYPE_RE)
        if 'displayName' in el:
            self.string(el['displayName'], path + '/displayName', 'displayName')
        if 'origin' in el:
            self.object(el['origin'], path + '/origin', 'origin')
        prod = el.get('producer')
        if 'producer' in el and self.object(prod, path + '/producer', 'producer'):
            ppath = path + '/producer'
            self.keys(prod, ppath, 'producer', ('operationId', 'slot'), ('operationId', 'slot'), elementId=key)
            if 'operationId' in prod:
                self.string(prod['operationId'], ppath + '/operationId', 'operationId', ID_RE)
            if 'slot' in prod:
                self.string(prod['slot'], ppath + '/slot', 'slot', OUTPUT_SLOT_RE)

    def input_value(self, key, value, path):
        if not self.object(value, path, 'an input'):
            return
        kind = value.get('kind')
        if kind == 'pathParameter':
            self.keys(value, path, 'a path parameter input', ('kind', 'value'), ('kind', 'value', 'branch'),
                      elementId=key)
            if 'value' in value and not _is_number(value['value']):
                self.add(path + '/value', 'a path parameter must be a number', elementId=key)
            if 'branch' in value and (not _is_number(value['branch']) or value['branch'] not in (-1, 1)):
                self.add(path + '/branch', 'a path branch must be -1 or 1', elementId=key)
            return
        if kind in ('number', 'angle'):
            self.keys(value, path, f'a{"n" if kind == "angle" else ""} {kind} input', ('kind', 'value'),
                      ('kind', 'value'), elementId=key)
            if 'value' in value and not _is_number(value['value']):
                self.add(path + '/value', f'a{"n" if kind == "angle" else ""} {kind} input must be a number',
                         elementId=key)
            return
        self.keys(value, path, 'an input', ('kind', 'value'), ('kind', 'value'), elementId=key)
        if 'kind' in value and kind != 'point':
            self.add(path + '/kind', f'unknown input kind {kind!r} (point, pathParameter, number, angle)',
                     elementId=key)
        if 'value' in value:
            self.numbers(value['value'], path + '/value', 'a point value', 2)

    def work_intent(self, intent, path):
        if not self.object(intent, path, 'workIntent'):
            return
        self.keys(intent, path, 'workIntent', (), _WORK_INTENT_KEYS)
        condition = intent.get('condition')
        cpath = path + '/condition'
        if 'condition' in intent and self.object(condition, cpath, 'condition'):
            self.keys(condition, cpath, 'condition', ('text',), ('text', 'source', 'quote', 'mediaRef'))
            for name in ('text', 'quote', 'mediaRef'):
                if name in condition:
                    self.string(condition[name], f'{cpath}/{name}', name)
            text = condition.get('text')
            if isinstance(text, str) and len(text) > _CONDITION_TEXT_MAX:
                self.add(cpath + '/text', f'the condition text is longer than {_CONDITION_TEXT_MAX} characters')
            if 'source' in condition and condition['source'] not in _CONDITION_SOURCES:
                self.add(cpath + '/source', f"source must be one of {', '.join(_CONDITION_SOURCES)}")
        forbid = intent.get('forbid')
        if 'forbid' in intent:
            if not isinstance(forbid, list):
                self.add(path + '/forbid', 'forbid must be an array')
            else:
                for i, item in enumerate(forbid):
                    if not isinstance(item, str) or item not in _FORBID:
                        self.add(f'{path}/forbid/{i}', f"forbid items must be one of {', '.join(_FORBID)}")
                if len(set(map(repr, forbid))) != len(forbid):
                    self.add(path + '/forbid', 'forbid items must be unique')
        assumptions = intent.get('assumptions')
        if 'assumptions' in intent:
            if not isinstance(assumptions, list):
                self.add(path + '/assumptions', 'assumptions must be an array')
            else:
                if len(assumptions) > _ASSUMPTIONS_MAX:
                    self.add(path + '/assumptions', f'at most {_ASSUMPTIONS_MAX} assumptions')
                for i, item in enumerate(assumptions):
                    ipath = f'{path}/assumptions/{i}'
                    if self.string(item, ipath, 'an assumption') and len(item) > _ASSUMPTION_MAX:
                        self.add(ipath, f'an assumption is longer than {_ASSUMPTION_MAX} characters')
        if 'briefRevision' in intent:
            value = intent['briefRevision']
            if not (_is_number(value) and math.isfinite(value) and value == int(value) and value >= 0):
                self.add(path + '/briefRevision', 'briefRevision must be a non-negative integer')

    def document(self, doc):
        self.keys(doc, '', 'the document', _REQUIRED)
        if 'format' in doc and doc['format'] != DOCUMENT_FORMAT:
            self.add('/format', f'format must be {DOCUMENT_FORMAT!r}')
        if 'documentId' in doc:
            self.string(doc['documentId'], '/documentId', 'documentId', ID_RE)
        if 'operationRegistryVersion' in doc:
            self.string(doc['operationRegistryVersion'], '/operationRegistryVersion',
                        'operationRegistryVersion', VERSION_RE)
        for section, check in (('operations', self.operation), ('elements', self.element),
                               ('inputs', self.input_value)):
            if section not in doc:
                continue
            records = doc[section]
            if not self.object(records, '/' + section, section):
                continue
            for key, record in records.items():
                path = '/' + section + _pointer(key)
                self.string(key, path, f'a key of {section}', ID_RE)
                check(key, record, path)
        for section in ('appearance', 'styleBinding', 'exportDefaults', 'bindings'):
            if section in doc:
                self.object(doc[section], '/' + section, section)
        if isinstance(doc.get('appearance'), dict):
            for key, entry in doc['appearance'].items():
                if isinstance(entry, dict) and 'locked' in entry and not isinstance(entry['locked'], bool):
                    self.add('/appearance' + _pointer(key) + '/locked', 'locked must be a boolean')
        if 'workIntent' in doc and doc['workIntent'] is not None:
            self.work_intent(doc['workIntent'], '/workIntent')
        if 'timeline' in doc and doc['timeline'] is not None:
            self.object(doc['timeline'], '/timeline', 'timeline')
        view = doc.get('viewDefaults')
        if 'viewDefaults' in doc and self.object(view, '/viewDefaults', 'viewDefaults') and 'bounds' in view:
            bounds = view['bounds']
            if self.numbers(bounds, '/viewDefaults/bounds', 'bounds', 4):
                xmin, ymin, xmax, ymax = bounds
                if all(math.isfinite(v) for v in bounds) and not (xmin < xmax and ymin < ymax):
                    self.add('/viewDefaults/bounds', 'bounds must satisfy xmin < xmax and ymin < ymax')


def structure_issues(data) -> list:
    """Structural issues (code ``schema``) of a parsed document."""
    if not isinstance(data, dict):
        return [Issue('schema', '', 'the document must be a JSON object')]
    issues: list = []
    _json_issues(data, '', issues)
    checker = _Structure()
    checker.document(data)
    return issues + checker.issues


# ── public API ───────────────────────────────────────────────────────────


def load(source, *, strict: bool = True) -> NativeDocument:
    """Read a document from a dict, a JSON string, bytes or a path.

    The structure is checked; with ``strict`` any structural issue raises
    :class:`LoadError`, otherwise the issues are kept in
    ``doc.schema_issues`` and reported by :func:`validate`. The document is
    copied, so later changes to ``source`` do not reach it.
    """
    data = _read_source(source)
    if not isinstance(data, dict):
        raise LoadError([Issue('schema', '', 'the document must be a JSON object')])
    issues = structure_issues(data)
    if strict and issues:
        raise LoadError(issues)
    return NativeDocument(copy.deepcopy(data), issues)


def as_document(source) -> NativeDocument:
    """``source`` as a structurally valid document (loads it when needed)."""
    if isinstance(source, NativeDocument):
        if source.schema_issues:
            raise LoadError(source.schema_issues)
        return source
    return load(source, strict=True)


def dump(doc) -> dict:
    """The document as a new JSON object (no defaults added, unknown keys kept)."""
    doc = doc if isinstance(doc, NativeDocument) else load(doc, strict=False)
    return copy.deepcopy(doc.data)


def dumps(doc) -> str:
    """Canonical JSON text of the document (``canonical.py``)."""
    doc = doc if isinstance(doc, NativeDocument) else load(doc, strict=False)
    return canonical_json(doc.data)


def content_hash(doc) -> str:
    """``"sha256:" + hex(sha256(utf8(dumps(doc))))``; a plain dict is hashed as is."""
    if isinstance(doc, NativeDocument):
        return sha256_of(doc.data)
    if isinstance(doc, dict):
        return sha256_of(doc)
    return sha256_of(load(doc, strict=False).data)


def iter_refs(arg):
    """Element IDs referenced by an argument, in order (list items in order)."""
    if not isinstance(arg, dict):
        return
    kind = arg.get('kind')
    if kind == 'ref':
        yield arg.get('elementId')
    elif kind == 'list':
        for item in arg.get('items') or ():
            yield from iter_refs(item)


def _op_refs(op) -> list:
    refs = []
    for arg in (op.get('args') or {}).values():
        refs.extend(iter_refs(arg))
    return refs


def bound_producer(doc: NativeDocument, element_id: str):
    """The producing operation ID of a consistently bound element, else ``None``.

    Consistent means: ``producer.operationId`` exists and lists
    ``{slot: producer.slot, elementId: element_id}`` in its ``outputs``.
    """
    el = doc.elements.get(element_id)
    if not isinstance(el, dict):
        return None
    prod = el.get('producer') or {}
    op = doc.operations.get(prod.get('operationId'))
    if not isinstance(op, dict):
        return None
    for out in op.get('outputs') or ():
        if out.get('elementId') == element_id and out.get('slot') == prod.get('slot'):
            return prod.get('operationId')
    return None


def op_dependencies(doc: NativeDocument) -> dict:
    """``{operationId: set of operationIds it depends on}`` through bound elements."""
    deps = {}
    for op_id, op in doc.operations.items():
        found = set()
        for ref in _op_refs(op):
            producer = bound_producer(doc, ref)
            if producer is not None:
                found.add(producer)
        deps[op_id] = found
    return deps


def cyclic_operations(deps: dict) -> set:
    """Operations that lie on a dependency cycle (strongly connected components
    of two or more operations, or an operation that depends on itself)."""
    index = {}
    low = {}
    on_stack = set()
    stack = []
    result = set()
    counter = 0
    for root in sorted(deps):
        if root in index:
            continue
        work = [(root, iter(sorted(deps[root])))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in deps:
                    continue
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(deps[child]))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1 or node in deps[node]:
                    result.update(component)
    return result


def _version_tuple(text):
    try:
        major, minor = text.split('.')
        return int(major), int(minor)
    except (AttributeError, ValueError):
        return None


def is_newer_registry(version) -> bool:
    """True when a document's ``operationRegistryVersion`` is newer than ours."""
    theirs = _version_tuple(version)
    ours = _version_tuple(REGISTRY_VERSION)
    return theirs is not None and theirs > ours


def validate(doc) -> list:
    """All issues of a document: structure first, then the graph rules.

    Graph rules run only on a structurally valid document. Codes:
    ``schema``, ``id_mismatch``, ``duplicate_output``, ``producer_mismatch``,
    ``unknown_slot``, ``missing_slot``, ``dangling_ref``, ``type_mismatch``,
    ``cycle``, ``input_not_free``, ``missing_input`` (errors) and
    ``unknown_op``, ``newer_registry`` (warnings).
    """
    if not isinstance(doc, NativeDocument):
        doc = load(doc, strict=False)
    if doc.schema_issues:
        return list(doc.schema_issues)
    reg = registry()
    issues: list = []
    ops = doc.operations
    elements = doc.elements
    inputs = doc.inputs

    if is_newer_registry(doc.registry_version):
        issues.append(Issue('newer_registry', '/operationRegistryVersion',
                            f'the document needs registry {doc.registry_version}, '
                            f'this library has {REGISTRY_VERSION}', severity='warning'))

    for section, records, id_key in (('operations', ops, 'operationId'), ('elements', elements, 'elementId')):
        for key in sorted(records):
            if records[key]['id'] != key:
                issues.append(Issue('id_mismatch', f'/{section}{_pointer(key)}/id',
                                    f'key {key!r} differs from id {records[key]["id"]!r}', **{id_key: key}))

    bound_by: dict = {}
    for op_id in sorted(ops):
        op = ops[op_id]
        path = '/operations' + _pointer(op_id)
        record = reg.get(op['op'])
        if record is None:
            code = 'newer_registry' if is_newer_registry(doc.registry_version) else 'unknown_op'
            issues.append(Issue(code, path + '/op', f"operation {op['op']!r} is not in registry {REGISTRY_VERSION}",
                                operationId=op_id, severity='warning'))
        args = op['args']
        if record is not None:
            declared = {item['slot'] for item in record['inputs']} | {item['slot'] for item in record['params']}
            for slot in sorted(args):
                if slot not in declared:
                    issues.append(Issue('unknown_slot', path + '/args' + _pointer(slot),
                                        f"{op['op']} has no argument slot {slot!r}", operationId=op_id))
            for item in record['inputs']:
                slot = item['slot']
                spath = path + '/args' + _pointer(slot)
                arg = args.get(slot)
                if arg is None:
                    issues.append(Issue('missing_slot', spath, f"{op['op']} needs argument {slot!r}",
                                        operationId=op_id))
                    continue
                if item['type'] in ('expr', 'template'):
                    if arg['kind'] != item['type']:
                        issues.append(Issue('type_mismatch', spath, f"argument {slot!r} must be "
                                            f"{'an expression' if item['type'] == 'expr' else 'a template'}",
                                            operationId=op_id))
                        continue
                    refs_arg = args.get('refs')
                    count = len(refs_arg['items']) if isinstance(refs_arg, dict) and refs_arg['kind'] == 'list' \
                        else None
                    if item['type'] == 'expr':
                        for pointer, message in expr_problems(arg['ast'], count):
                            issues.append(Issue('formula', spath + '/ast' + pointer, message, operationId=op_id))
                    else:
                        for message in template_problems(arg['value'], count):
                            issues.append(Issue('formula', spath + '/value', message, operationId=op_id))
                    continue
                if item.get('list'):
                    if arg['kind'] != 'list':
                        issues.append(Issue('type_mismatch', spath, f'argument {slot!r} must be a list',
                                            operationId=op_id))
                        continue
                    refs = arg['items']
                    if len(refs) < (item.get('min') or 0):
                        issues.append(Issue('type_mismatch', spath,
                                            f"argument {slot!r} needs at least {item['min']} items",
                                            operationId=op_id))
                    pairs = [(f'{spath}/items/{i}', r) for i, r in enumerate(refs)]
                else:
                    if item['type'] == 'number' and arg['kind'] == 'number':
                        continue                       # a number literal
                    pairs = [(spath, arg)]
                for rpath, ref in pairs:
                    if ref['kind'] != 'ref':
                        issues.append(Issue('type_mismatch', rpath,
                                            f'argument {slot!r} must reference an element', operationId=op_id))
                        continue
                    target = elements.get(ref['elementId'])
                    if target is None:
                        issues.append(Issue('dangling_ref', rpath + '/elementId',
                                            f"element {ref['elementId']!r} does not exist", operationId=op_id))
                    elif not reg.accepts(item['type'], target['type']):
                        issues.append(Issue('type_mismatch', rpath + '/elementId',
                                            f"{target['type']} {ref['elementId']!r} does not fit slot "
                                            f"{slot!r} ({item['type']})", operationId=op_id,
                                            elementId=ref['elementId']))
            for item in record['params']:
                slot = item['slot']
                spath = path + '/args' + _pointer(slot)
                arg = args.get(slot)
                if arg is None:
                    if not item.get('optional', False):
                        issues.append(Issue('missing_slot', spath, f"{op['op']} needs parameter {slot!r}",
                                            operationId=op_id))
                elif arg['kind'] != 'number':
                    issues.append(Issue('type_mismatch', spath, f'parameter {slot!r} must be a number',
                                        operationId=op_id))
        else:
            for slot in sorted(args):
                for ref in iter_refs(args[slot]):
                    if ref not in elements:
                        issues.append(Issue('dangling_ref', path + '/args' + _pointer(slot),
                                            f'element {ref!r} does not exist', operationId=op_id))
        seen_slots = set()
        for i, out in enumerate(op['outputs']):
            opath = f'{path}/outputs/{i}'
            slot, el_id = out['slot'], out['elementId']
            if slot in seen_slots:
                issues.append(Issue('duplicate_output', opath + '/slot', f'slot {slot!r} is bound twice',
                                    operationId=op_id))
            seen_slots.add(slot)
            if el_id in bound_by:
                issues.append(Issue('duplicate_output', opath + '/elementId',
                                    f'element {el_id!r} is bound twice', operationId=op_id, elementId=el_id))
            bound_by.setdefault(el_id, op_id)
            if record is not None and reg.output_type(record, slot, args, doc) is None:
                issues.append(Issue('unknown_slot', opath + '/slot', f"{op['op']} has no output slot {slot!r}",
                                    operationId=op_id))
            el = elements.get(el_id)
            if el is None:
                issues.append(Issue('producer_mismatch', opath + '/elementId',
                                    f'output element {el_id!r} does not exist', operationId=op_id))
            elif el['producer'] != {'operationId': op_id, 'slot': slot}:
                issues.append(Issue('producer_mismatch', opath,
                                    f'element {el_id!r} names another producer', operationId=op_id,
                                    elementId=el_id))

    for el_id in sorted(elements):
        el = elements[el_id]
        path = '/elements' + _pointer(el_id)
        prod = el['producer']
        op = ops.get(prod['operationId'])
        if op is None:
            issues.append(Issue('producer_mismatch', path + '/producer/operationId',
                                f"operation {prod['operationId']!r} does not exist", elementId=el_id))
            continue
        if bound_producer(doc, el_id) is None:
            issues.append(Issue('producer_mismatch', path + '/producer',
                                f"operation {prod['operationId']!r} does not bind {el_id!r} to slot "
                                f"{prod['slot']!r}", elementId=el_id, operationId=prod['operationId']))
            continue
        record = reg.get(op['op'])
        if record is None:
            continue
        out_type = reg.output_type(record, prod['slot'], op['args'], doc)
        if out_type is not None and out_type != el['type']:
            issues.append(Issue('type_mismatch', path + '/type',
                                f"slot {prod['slot']!r} of {op['op']} produces {out_type}, not {el['type']}",
                                elementId=el_id, operationId=prod['operationId']))
        if record.get('free') is not None and el_id not in inputs and prod['slot'] == free_slot(record) \
                and record['free']['kind'] not in FREE_INPUT_DEFAULTS:
            issues.append(Issue('missing_input', '/inputs' + _pointer(el_id),
                                f'free element {el_id!r} has no input value', elementId=el_id))

    for el_id in sorted(inputs):
        path = '/inputs' + _pointer(el_id)
        if el_id not in elements:
            issues.append(Issue('dangling_ref', path, f'element {el_id!r} does not exist', elementId=el_id))
            continue
        producer = bound_producer(doc, el_id)
        record = reg.get(ops[producer]['op']) if producer is not None else None
        free = record.get('free') if record is not None else None
        if free is not None and elements[el_id]['producer']['slot'] != free_slot(record):
            free = None             # only the element of the first output slot holds the input
        if free is None:
            issues.append(Issue('input_not_free', path, f'element {el_id!r} is not a free input',
                                elementId=el_id))
        elif inputs[el_id]['kind'] != free['kind']:
            issues.append(Issue('type_mismatch', path + '/kind',
                                f"element {el_id!r} takes a {free['kind']} input", elementId=el_id))

    for op_id in sorted(cyclic_operations(op_dependencies(doc))):
        issues.append(Issue('cycle', '/operations' + _pointer(op_id),
                            f'operation {op_id!r} depends on itself', operationId=op_id))
    return issues
