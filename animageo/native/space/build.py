"""A small builder of space documents (tests, fixtures, examples).

    from animageo.native.space.build import SpaceBuilder

    b = SpaceBuilder('cube-cut', camera={'azimuthDeg': -60, 'elevationDeg': 25})
    b.point('A', 0, 0, 0); b.point('B', 2, 0, 0)
    cube = b.cube('K', 'A', 'B', vertices=['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1'])
    b.on_edge('M', cube.edge(9), 0.5)     # the lateral edge AA_1
    doc = b.data()

An element of an operation output gets the ID the caller gives, else
``<id>_<slot>`` with the dot replaced (``K_edge_3``). The operation ID is
``op-<id>`` of the first output.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..document import DOCUMENT_FORMAT
from .registry import SPACE_REGISTRY_VERSION, space_registry

__all__ = ['SpaceBuilder', 'Made']


def _ref(element_id):
    return {'kind': 'ref', 'elementId': element_id}


def _refs(ids):
    return {'kind': 'list', 'items': [_ref(i) for i in ids]}


@dataclass
class Made:
    """The elements an operation made: ``main`` (its first output) and the
    others by slot."""

    main: str
    slots: dict = field(default_factory=dict)

    def _nth(self, name, k):
        return self.slots[f'{name}.{k}']

    def vertex(self, k):
        return self._nth('vertex', k)

    def edge(self, k):
        return self._nth('edge', k)

    def face(self, k):
        return self._nth('face', k)

    def side(self, k):
        return self._nth('side', k)

    def __str__(self):
        return self.main


class SpaceBuilder:
    def __init__(self, document_id='space', *, camera=None, ground=None):
        self.document_id = document_id
        self.operations: dict = {}
        self.elements: dict = {}
        self.inputs: dict = {}
        self.camera = camera
        self.ground = ground

    def _op(self, element_id, op, args, names=None) -> Made:
        reg = space_registry()
        record = reg.get(op)
        op_id = f'op-{element_id}'
        if op_id in self.operations:
            raise ValueError(f'operation {op_id!r} exists')
        slots = reg.output_slots(record, args, None)
        names = dict(names or {})
        outputs = []
        made = Made(element_id)
        for k, slot in enumerate(slots):
            el_id = element_id if k == 0 else names.get(slot) or f"{element_id}_{slot.replace('.', '_')}"
            if el_id in self.elements:
                raise ValueError(f'element {el_id!r} exists')
            self.elements[el_id] = {'id': el_id, 'type': reg.output_type(record, slot, args), 'displayName': el_id,
                                    'producer': {'operationId': op_id, 'slot': slot}}
            outputs.append({'slot': slot, 'elementId': el_id})
            made.slots[slot] = el_id
        self.operations[op_id] = {'id': op_id, 'op': op, 'args': args, 'outputs': outputs}
        return made

    @staticmethod
    def _names(prefix, ids):
        return {f'{prefix}.{k}': name for k, name in enumerate(ids or (), 1)}

    # ── points ──
    def point(self, element_id, x, y, z) -> str:
        self._op(element_id, 'point3.free', {})
        self.inputs[element_id] = {'kind': 'point3', 'value': [float(x), float(y), float(z)]}
        return element_id

    def on_edge(self, element_id, path, t) -> str:
        self._op(element_id, 'point3.on_path', {'path': _ref(str(path))})
        self.inputs[element_id] = {'kind': 'pathParameter', 'value': float(t)}
        return element_id

    def on_face(self, element_id, face, u, v) -> str:
        self._op(element_id, 'point3.on_surface', {'surface': _ref(str(face))})
        self.inputs[element_id] = {'kind': 'surfaceParameter', 'value': [float(u), float(v)]}
        return element_id

    def midpoint(self, element_id, a, b) -> str:
        return self._op(element_id, 'point3.midpoint', {'a': _ref(a), 'b': _ref(b)}).main

    # ── lines, polygons, planes ──
    def segment(self, element_id, a, b) -> str:
        return self._op(element_id, 'segment3.by_points', {'a': _ref(a), 'b': _ref(b)}).main

    def polygon(self, element_id, *vertices, sides=None) -> Made:
        return self._op(element_id, 'polygon3.by_points', {'vertices': _refs(vertices)},
                        self._names('side', sides))

    def plane(self, element_id, a, b, c) -> str:
        return self._op(element_id, 'plane.by_points', {'a': _ref(a), 'b': _ref(b), 'c': _ref(c)}).main

    # ── solids ──
    def _solid(self, element_id, op, args, vertices, edges, faces) -> Made:
        names = {**self._names('vertex', vertices), **self._names('edge', edges), **self._names('face', faces)}
        return self._op(element_id, op, args, names)

    def cube(self, element_id, a, b, *, vertices=None, edges=None, faces=None) -> Made:
        return self._solid(element_id, 'polyhedron.cube', {'a': _ref(a), 'b': _ref(b)}, vertices, edges, faces)

    def prism(self, element_id, base, top, *, vertices=None, edges=None, faces=None) -> Made:
        return self._solid(element_id, 'polyhedron.prism', {'base': _refs(base), 'top': _ref(top)},
                           vertices, edges, faces)

    def pyramid(self, element_id, base, apex, *, edges=None, faces=None) -> Made:
        return self._solid(element_id, 'polyhedron.pyramid', {'base': _refs(base), 'apex': _ref(apex)},
                           None, edges, faces)

    def tetrahedron(self, element_id, a, b, c, d, *, edges=None, faces=None) -> Made:
        return self._solid(element_id, 'polyhedron.tetrahedron',
                           {'a': _ref(a), 'b': _ref(b), 'c': _ref(c), 'd': _ref(d)}, None, edges, faces)

    def section(self, element_id, plane, solid) -> str:
        return self._op(element_id, 'section.plane_polyhedron',
                        {'plane': _ref(str(plane)), 'solid': _ref(str(solid))}).main

    def data(self) -> dict:
        view = {}
        if self.camera is not None:
            view['camera'] = dict(self.camera)
        if self.ground is not None:
            view['ground'] = dict(self.ground)
        doc = {
            'format': DOCUMENT_FORMAT,
            'documentId': self.document_id,
            'operationRegistryVersion': SPACE_REGISTRY_VERSION,
            'space': 'space',
            'operations': dict(self.operations),
            'elements': dict(self.elements),
            'inputs': dict(self.inputs),
        }
        if view:
            doc['viewDefaults'] = view
        return doc
