"""The space document: ``animageo-construction/v1`` with ``space: "space"``.

A space document is the plane document (``animageo.native.document``) with
three more places (spec §2.1):

- ``space``: ``"space"`` — written at creation, never changed; a plane
  document has no such key (so ``load → dump`` of an old one stays byte for
  byte);
- ``viewDefaults.camera`` — the view of the export, thumbnails and the exact
  frame (:class:`~animageo.native.space.camera.Camera`, ``Camera.to_dict``):
  ``projection`` (``orthographic`` | ``oblique`` | ``perspective``),
  ``azimuthDeg``, ``elevationDeg`` (z up), ``target`` ``[x, y, z]``,
  ``distance`` (perspective), ``oblique`` ``{angleDeg, ratio}``; no scale and
  no frame — the export layout frames the flat scene;
- ``viewDefaults.ground`` — ``{look: none | sheet | grid, size}``, display
  only.

``viewDefaults.bounds`` is not written in a space document (``schema``).
Inputs: ``{"kind": "point3", "value": [x, y, z]}`` (``point3.free``),
``{"kind": "pathParameter", "value": t}`` (``point3.on_path``) and
``{"kind": "surfaceParameter", "value": [u, v]}`` (``point3.on_surface``);
the plane ``point`` input is refused. The operations are those of the
space registry 1.0 (:mod:`.registry`, a version line of its own:
``operationRegistryVersion`` ``"1.0"``); an operation of the plane is
``space_unsupported``.

:func:`load` checks the structure with the rules of the plane plus the ones
above; :func:`validate` adds the graph rules against the space registry.
"""
from __future__ import annotations

import math

from ..document import (
    Issue,
    LoadError,
    NativeDocument,
    _json_issues,
    _pointer,
    _read_source,
    _Structure,
    _version_tuple,
    bound_producer,
    cyclic_operations,
    op_dependencies,
)
from ..registry import registry as plane_registry
from .camera import Camera
from .registry import SPACE_REGISTRY_VERSION, space_registry

__all__ = ['SPACE', 'GROUND_LOOKS', 'is_space', 'load', 'as_space_document', 'validate', 'camera_of',
           'is_newer_space_registry', 'structure_issues']

SPACE = 'space'
GROUND_LOOKS = ('none', 'sheet', 'grid')
_CAMERA_KEYS = ('projection', 'azimuthDeg', 'elevationDeg', 'target', 'distance', 'oblique')


def is_space(doc) -> bool:
    """Whether ``doc`` (a dict or a :class:`NativeDocument`) is a space document."""
    data = doc.data if isinstance(doc, NativeDocument) else doc
    return isinstance(data, dict) and data.get('space') == SPACE


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class _SpaceStructure(_Structure):
    def input_value(self, key, value, path):
        if not isinstance(value, dict):
            super().input_value(key, value, path)
            return
        kind = value.get('kind')
        if kind == 'point3':
            self.keys(value, path, 'a point3 input', ('kind', 'value'), ('kind', 'value'), elementId=key)
            if 'value' in value:
                self.numbers(value['value'], path + '/value', 'a point3 value', 3)
            return
        if kind == 'surfaceParameter':
            self.keys(value, path, 'a surface parameter input', ('kind', 'value'), ('kind', 'value'),
                      elementId=key)
            if 'value' in value:
                self.numbers(value['value'], path + '/value', 'a surface parameter', 2)
            return
        if kind == 'point':
            self.add(path + '/kind', "a space document takes point3 inputs, not 'point'", elementId=key)
            return
        super().input_value(key, value, path)

    def camera(self, camera, path):
        if not self.object(camera, path, 'camera'):
            return
        self.keys(camera, path, 'camera', (), _CAMERA_KEYS)
        if 'target' in camera and not self.numbers(camera['target'], path + '/target', 'target', 3):
            return
        oblique = camera.get('oblique')
        if 'oblique' in camera and self.object(oblique, path + '/oblique', 'oblique'):
            self.keys(oblique, path + '/oblique', 'oblique', (), ('angleDeg', 'ratio'))
        try:
            Camera.from_dict(camera)
        except (TypeError, ValueError) as exc:
            self.add(path, f'camera: {exc}')

    def ground(self, ground, path):
        if not self.object(ground, path, 'ground'):
            return
        self.keys(ground, path, 'ground', (), ('look', 'size'))
        if 'look' in ground and ground['look'] not in GROUND_LOOKS:
            self.add(path + '/look', f'look must be one of {", ".join(GROUND_LOOKS)}')
        size = ground.get('size')
        if 'size' in ground and not (_is_number(size) and math.isfinite(size) and size > 0):
            self.add(path + '/size', 'size must be a positive number')

    def document(self, doc):
        super().document(doc)
        if doc.get('space') != SPACE:
            self.add('/space', f'a space document has space: {SPACE!r}')
        view = doc.get('viewDefaults')
        if isinstance(view, dict):
            if 'bounds' in view:
                self.add('/viewDefaults/bounds', 'a space document has no bounds: the export frames its flat scene')
            if 'camera' in view:
                self.camera(view['camera'], '/viewDefaults/camera')
            if 'ground' in view:
                self.ground(view['ground'], '/viewDefaults/ground')


def structure_issues(data) -> list:
    """Structural issues (code ``schema``) of a parsed space document."""
    if not isinstance(data, dict):
        return [Issue('schema', '', 'the document must be a JSON object')]
    issues: list = []
    _json_issues(data, '', issues)
    checker = _SpaceStructure()
    checker.document(data)
    return issues + checker.issues


def load(source, *, strict: bool = True) -> NativeDocument:
    """Read a space document (a dict, JSON text, bytes or a path); with
    ``strict`` a structural issue raises :class:`LoadError`."""
    import copy
    data = _read_source(source)
    if not isinstance(data, dict):
        raise LoadError([Issue('schema', '', 'the document must be a JSON object')])
    issues = structure_issues(data)
    if strict and issues:
        raise LoadError(issues)
    return NativeDocument(copy.deepcopy(data), issues)


def as_space_document(source) -> NativeDocument:
    """``source`` as a structurally valid space document."""
    if isinstance(source, NativeDocument):
        if source.schema_issues or structure_issues(source.data):
            raise LoadError(list(source.schema_issues) or structure_issues(source.data))
        return source
    return load(source, strict=True)


def is_newer_space_registry(version) -> bool:
    theirs = _version_tuple(version)
    return theirs is not None and theirs > _version_tuple(SPACE_REGISTRY_VERSION)


def camera_of(doc) -> Camera:
    """The camera of the export: ``viewDefaults.camera`` or :class:`Camera` ()."""
    data = doc.data if isinstance(doc, NativeDocument) else doc
    camera = ((data or {}).get('viewDefaults') or {}).get('camera')
    return Camera.from_dict(camera) if camera is not None else Camera()


def validate(doc) -> list:
    """All issues of a space document: structure first, then the graph rules
    against the space registry 1.0. Codes: ``schema``, ``id_mismatch``,
    ``space_unsupported`` (a plane operation), ``unknown_slot``,
    ``missing_slot``, ``dangling_ref``, ``type_mismatch``,
    ``producer_mismatch``, ``cycle``, ``input_not_free``, ``missing_input``
    (errors); ``unknown_op``, ``newer_registry`` (warnings)."""
    if not isinstance(doc, NativeDocument):
        doc = load(doc, strict=False)
    if doc.schema_issues:
        return list(doc.schema_issues)
    reg = space_registry()
    plane = plane_registry()
    newer = is_newer_space_registry(doc.registry_version)
    issues: list = []
    ops, elements, inputs = doc.operations, doc.elements, doc.inputs
    if newer:
        issues.append(Issue('newer_registry', '/operationRegistryVersion',
                            f'the document needs registry {doc.registry_version}, '
                            f'this library has {SPACE_REGISTRY_VERSION}', severity='warning'))
    for section, records, id_key in (('operations', ops, 'operationId'), ('elements', elements, 'elementId')):
        for key in sorted(records):
            if records[key]['id'] != key:
                issues.append(Issue('id_mismatch', f'/{section}{_pointer(key)}/id',
                                    f'key {key!r} differs from id {records[key]["id"]!r}', **{id_key: key}))
    free_targets = {}
    for op_id in sorted(ops):
        op = ops[op_id]
        path = '/operations' + _pointer(op_id)
        record = reg.get(op['op'])
        if record is None:
            if plane.get(op['op']) is not None:
                issues.append(Issue('space_unsupported', path + '/op',
                                    f"{op['op']} is an operation of the plane", operationId=op_id))
            else:
                issues.append(Issue('newer_registry' if newer else 'unknown_op', path + '/op',
                                    f"operation {op['op']!r} is not in registry {SPACE_REGISTRY_VERSION}",
                                    operationId=op_id, severity='warning'))
            continue
        declared = {item['slot'] for item in record['inputs']} | {item['slot'] for item in record['params']}
        for slot in sorted(op['args']):
            if slot not in declared:
                issues.append(Issue('unknown_slot', path + '/args' + _pointer(slot),
                                    f"{op['op']} has no argument slot {slot!r}", operationId=op_id))
        for item in record['inputs']:
            spath = path + '/args' + _pointer(item['slot'])
            arg = op['args'].get(item['slot'])
            if arg is None:
                issues.append(Issue('missing_slot', spath, f"{op['op']} needs argument {item['slot']!r}",
                                    operationId=op_id))
                continue
            if item.get('list'):
                if arg['kind'] != 'list' or len(arg.get('items') or []) < (item.get('min') or 0):
                    issues.append(Issue('type_mismatch', spath, f"argument {item['slot']!r} must be a list of at "
                                        f"least {item.get('min') or 0} references", operationId=op_id))
                    continue
                refs = arg['items']
            else:
                refs = [arg]
            for k, ref in enumerate(refs):
                rpath = spath + (f'/items/{k}' if item.get('list') else '')
                if ref.get('kind') != 'ref':
                    issues.append(Issue('type_mismatch', rpath, 'a reference expected', operationId=op_id))
                    continue
                target = elements.get(ref['elementId'])
                if target is None:
                    issues.append(Issue('dangling_ref', rpath + '/elementId',
                                        f"no element {ref['elementId']!r}", operationId=op_id))
                elif not reg.accepts(item['type'], target['type']):
                    issues.append(Issue('type_mismatch', rpath, f"{target['type']} does not fit a "
                                        f"{item['type']} slot", operationId=op_id, elementId=ref['elementId']))
        for k, out in enumerate(op['outputs']):
            opath = f'{path}/outputs/{k}'
            out_type = reg.output_type(record, out['slot'], op['args'], doc)
            if out_type is None:
                issues.append(Issue('unknown_slot', opath + '/slot', f"{op['op']} has no output {out['slot']!r}",
                                    operationId=op_id))
                continue
            el = elements.get(out['elementId'])
            if el is None or bound_producer(doc, out['elementId']) != op_id:
                issues.append(Issue('producer_mismatch', opath, f"element {out['elementId']!r} is not bound to "
                                    f"this output", operationId=op_id, elementId=out['elementId']))
            elif el['type'] != out_type:
                issues.append(Issue('type_mismatch', opath, f"output {out['slot']!r} is a {out_type}",
                                    operationId=op_id, elementId=out['elementId']))
            elif record.get('free') is not None and out['slot'] == record['outputs'][0]['slot']:
                free_targets[out['elementId']] = record['free']['kind']
    for el_id in sorted(elements):
        if bound_producer(doc, el_id) is None:
            issues.append(Issue('producer_mismatch', '/elements' + _pointer(el_id) + '/producer',
                                f'element {el_id!r} has no consistent producer', elementId=el_id))
    cyclic = cyclic_operations(op_dependencies(doc))
    for op_id in sorted(cyclic):
        issues.append(Issue('cycle', '/operations' + _pointer(op_id), 'the operation lies on a dependency cycle',
                            operationId=op_id))
    for el_id in sorted(inputs):
        path = '/inputs' + _pointer(el_id)
        kind = free_targets.get(el_id)
        if kind is None:
            issues.append(Issue('input_not_free', path, f'element {el_id!r} takes no input', elementId=el_id))
        elif inputs[el_id]['kind'] != kind:
            issues.append(Issue('type_mismatch', path + '/kind', f'element {el_id!r} takes a {kind} input',
                                elementId=el_id))
    for el_id in sorted(free_targets):
        if el_id not in inputs:
            issues.append(Issue('missing_input', '/inputs' + _pointer(el_id), f'element {el_id!r} needs an input',
                                elementId=el_id))
    return issues
