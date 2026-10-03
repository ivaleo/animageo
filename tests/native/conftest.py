import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_DIR = REPO_ROOT / 'animageo' / 'native'
SCENES_DIR = NATIVE_DIR / 'parity' / 'v1' / 'scenes'
EXPECTED_DIR = NATIVE_DIR / 'parity' / 'v1' / 'expected'


def ref(element_id):
    return {'kind': 'ref', 'elementId': element_id}


def ref_list(*element_ids):
    return {'kind': 'list', 'items': [ref(e) for e in element_ids]}


def point_input(x, y):
    return {'kind': 'point', 'value': [x, y]}


class DocBuilder:
    """Small builder of animageo-construction/v1 documents for tests."""

    def __init__(self, document_id='doc', bounds=(-10, -10, 10, 10)):
        self.doc = {
            'format': 'animageo-construction/v1',
            'documentId': document_id,
            'operationRegistryVersion': '1.0',
            'operations': {},
            'elements': {},
            'inputs': {},
        }
        if bounds is not None:
            self.doc['viewDefaults'] = {'bounds': list(bounds)}

    def op(self, op_id, name, args, outputs):
        """``outputs``: ``[(slot, elementId, type), …]``."""
        self.doc['operations'][op_id] = {
            'id': op_id, 'op': name, 'args': args,
            'outputs': [{'slot': s, 'elementId': e} for s, e, _ in outputs],
        }
        for slot, el_id, type_ in outputs:
            self.doc['elements'][el_id] = {
                'id': el_id, 'type': type_, 'displayName': el_id,
                'producer': {'operationId': op_id, 'slot': slot},
            }
        return self

    def free(self, el_id, x=None, y=None):
        self.op('op_' + el_id, 'point.free', {}, [('point', el_id, 'point')])
        if x is not None:
            self.doc['inputs'][el_id] = point_input(x, y)
        return self

    def two(self, op_name, el_id, a, b, type_, slots=('a', 'b'), out_slot=None):
        out_slot = out_slot or type_
        return self.op('op_' + el_id, op_name, {slots[0]: ref(a), slots[1]: ref(b)},
                       [(out_slot, el_id, type_)])

    def midpoint(self, el_id, a, b):
        return self.two('point.midpoint', el_id, a, b, 'point')

    def segment(self, el_id, a, b):
        return self.two('segment.by_points', el_id, a, b, 'segment')

    def line(self, el_id, a, b):
        return self.two('line.by_points', el_id, a, b, 'line')

    def circle(self, el_id, center, through):
        return self.two('circle.center_point', el_id, center, through, 'circle',
                        slots=('center', 'through'))

    def intersect(self, el_id, first, second):
        return self.two('intersect.line_line', el_id, first, second, 'point',
                        slots=('first', 'second'))

    def polygon(self, el_id, *vertices, sides=()):
        outputs = [('polygon', el_id, 'polygon')]
        outputs += [(f'side.{i}', side_id, 'segment') for i, side_id in sides]
        return self.op('op_' + el_id, 'polygon.by_points', {'vertices': ref_list(*vertices)}, outputs)


@pytest.fixture
def builder():
    return DocBuilder


def read_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)
