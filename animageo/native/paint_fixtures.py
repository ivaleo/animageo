"""Fixtures of the paint of the renderer (1.11.0rc3): ``animageo-paint-parity/v1``
in ``animageo/native/parity/v1/paint``.

One file per theme: ``{format, id, registry, generatedBy, cases: [{name,
document, style, t, timeline, expect}]}`` — ``expect`` is
:func:`~animageo.native.paint.resolve_paint` of the document under
``style`` (a style JSON, ``null`` — no style) at ``t`` of ``timeline``
(both ``null`` — the document as it is). Numbers compare with ``1e-9``
(absolute); everything else exactly. The documents are built here;
expectations are what this library gives. The scenes: ticks 1/2/3 and the
wave, the automatic radius of an angle, point shapes and arrows, caps and
dashes with their fit, label anchors by type, the format of values, the
layers, ``text.free``, the base without a style and under the built-in one,
roles, hatching, a style track of a timeline.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from .registry import REGISTRY_VERSION

__all__ = ['PAINT_PARITY_FORMAT', 'DEFAULT_DIR', 'build_fixtures', 'write_fixtures', 'check_fixtures',
           'verify_fixture', 'verify_fixtures']

PAINT_PARITY_FORMAT = 'animageo-paint-parity/v1'
DEFAULT_DIR = Path(__file__).resolve().parent / 'parity' / 'v1' / 'paint'
TOLERANCE = 1e-9


def _ref(el_id):
    return {'kind': 'ref', 'elementId': el_id}


def _refs(*el_ids):
    return {'kind': 'list', 'items': [_ref(e) for e in el_ids]}


def _num(v):
    return {'kind': 'number', 'value': v}


class _Doc:
    def __init__(self, doc_id, bounds=(-1, -1, 7, 5)):
        self.doc = {'format': 'animageo-construction/v1', 'documentId': doc_id,
                    'operationRegistryVersion': REGISTRY_VERSION, 'operations': {}, 'elements': {},
                    'inputs': {}, 'viewDefaults': {'bounds': list(bounds)}, 'appearance': {}}

    def op(self, name, args, outputs, op_id=None):
        op_id = op_id or 'op_' + outputs[0][1]
        self.doc['operations'][op_id] = {'id': op_id, 'op': name, 'args': args,
                                         'outputs': [{'slot': s, 'elementId': e} for s, e, _t in outputs]}
        for slot, el_id, type_ in outputs:
            self.doc['elements'][el_id] = {'id': el_id, 'type': type_, 'displayName': el_id,
                                           'producer': {'operationId': op_id, 'slot': slot}}
        return self

    def free(self, el_id, x, y):
        self.op('point.free', {}, [('point', el_id, 'point')])
        self.doc['inputs'][el_id] = {'kind': 'point', 'value': [x, y]}
        return self

    def two(self, name, el_id, a, b, type_, slots=('a', 'b')):
        return self.op(name, {slots[0]: _ref(a), slots[1]: _ref(b)}, [(type_, el_id, type_)])

    def segment(self, el_id, a, b):
        return self.two('segment.by_points', el_id, a, b, 'segment')

    def line(self, el_id, a, b):
        return self.two('line.by_points', el_id, a, b, 'line')

    def ray(self, el_id, a, b):
        return self.two('ray.by_points', el_id, a, b, 'ray', slots=('origin', 'through'))

    def vector(self, el_id, a, b):
        return self.two('vector.by_points', el_id, a, b, 'vector')

    def circle(self, el_id, center, through):
        return self.two('circle.center_point', el_id, center, through, 'circle', slots=('center', 'through'))

    def polygon(self, el_id, *vertices):
        return self.op('polygon.by_points', {'vertices': _refs(*vertices)}, [('polygon', el_id, 'polygon')])

    def arc(self, el_id, center, a, b):
        return self.op('arc.center_two_points', {'center': _ref(center), 'a': _ref(a), 'b': _ref(b)},
                       [('arc', el_id, 'arc')])

    def sector(self, el_id, center, a, b):
        return self.op('sector.center_two_points', {'center': _ref(center), 'a': _ref(a), 'b': _ref(b)},
                       [('sector', el_id, 'sector')])

    def polyline(self, el_id, *points):
        return self.op('polyline.by_points', {'points': _refs(*points)}, [('polyline', el_id, 'polyline')])

    def angle(self, el_id, a, vertex, b):
        return self.op('angle.by_points', {'a': _ref(a), 'vertex': _ref(vertex), 'b': _ref(b)},
                       [('angle', el_id, 'angle')])

    def right_mark(self, el_id, a, vertex, b):
        return self.op('mark.right_angle', {'a': _ref(a), 'vertex': _ref(vertex), 'b': _ref(b)},
                       [('mark', el_id, 'mark')])

    def equal_segments(self, el_id, *segments, count=1):
        return self.op('mark.equal_segments', {'segments': _refs(*segments), 'count': _num(count)},
                       [('mark', el_id, 'mark')])

    def equal_angles(self, el_id, *angles, count=1):
        return self.op('mark.equal_angles', {'angles': _refs(*angles), 'count': _num(count)},
                       [('mark', el_id, 'mark')])

    def text(self, el_id, template, anchor, *refs):
        return self.op('text.free', {'text': {'kind': 'template', 'value': template}, 'anchor': _ref(anchor),
                                     'refs': _refs(*refs)}, [('text', el_id, 'text')])

    def look(self, el_id, **entry):
        self.doc['appearance'].setdefault(el_id, {}).update(entry)
        return self

    def overrides(self, el_id, **keys):
        self.doc['appearance'].setdefault(el_id, {}).setdefault('overrides', {}).update(keys)
        return self

    def label(self, el_id, mode='name'):
        return self.look(el_id, label={'mode': mode})


def _triangle(doc_id, c=(1.5, 3.5)):
    return _Doc(doc_id).free('A', 0, 0).free('B', 5, 0).free('C', *c)


def _zoo(doc_id):
    """One element of each drawn type and the three marks."""
    d = _Doc(doc_id).free('A', 0, 0).free('B', 4, 0).free('C', 1, 3).free('D', 5, 3)
    d.segment('s', 'A', 'B').segment('u', 'B', 'C').line('l', 'C', 'D').ray('r', 'A', 'D').vector('v', 'C', 'A')
    d.circle('c', 'D', 'B').polygon('T', 'A', 'B', 'C').arc('k', 'D', 'B', 'C').sector('q', 'A', 'B', 'C')
    d.polyline('w', 'A', 'C', 'D').angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    d.right_mark('ra', 'D', 'B', 'A').equal_segments('mk', 's', 'u', count=2)
    d.equal_angles('ma', 'alpha', 'beta', count=2)
    d.op('number.free', {}, [('number', 'n', 'number')])
    d.doc['inputs']['n'] = {'kind': 'number', 'value': 2.5}
    d.text('t', 'Zoo', 'D')
    return d


def _builtin_style():
    from ..style.config import BUILTIN_STYLE_PATH
    return json.loads(Path(BUILTIN_STYLE_PATH).read_text(encoding='utf-8'))


# ── scenes: (name, document, style, timeline, t) ─────────────────────────

def _ticks():
    out = []
    for count in (1, 2, 3):
        d = _triangle(f'ticks_{count}').segment('a', 'B', 'C').segment('b', 'C', 'A')
        d.equal_segments('m', 'a', 'b', count=count)
        out.append((f'ticks_{count}', d, None))
    d = _triangle('ticks_wave').segment('a', 'B', 'C').segment('b', 'C', 'A')
    d.equal_segments('m', 'a', 'b', count=3).overrides('m', tick_style='wave')
    out.append(('ticks_wave', d, None))
    d = _triangle('ticks_wave_radius').segment('a', 'B', 'C').segment('b', 'C', 'A')
    d.equal_segments('m', 'a', 'b', count=2).overrides('m', tick_style='wave', tick_radius_px=1.5)
    out.append(('ticks_wave_radius', d, None))
    d = _triangle('ticks_mark_sizes').segment('a', 'B', 'C').segment('b', 'C', 'A')
    d.equal_segments('m', 'a', 'b', count=2).overrides('m', tick_length_px=14, tick_width_px=2.5, tick_shift_px=4)
    d.overrides('b', tick_length_px=6)
    out.append(('ticks_mark_sizes', d, None))
    d = _triangle('ticks_override').segment('a', 'B', 'C').vector('v', 'A', 'B')
    d.overrides('a', tick_count=2).overrides('v', tick_count=1)
    out.append(('ticks_override', d, None))
    return out


def _angles():
    out = []
    for count in (2, 3):
        d = _triangle(f'arcs_{count}').angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
        d.equal_angles('m', 'alpha', 'beta', count=count)
        out.append((f'arcs_{count}', d, None))
    auto = {'overlay': {'angle_radius': {'enabled': True}}}
    d = _triangle('auto_radius').angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    out.append(('auto_radius', d, auto))
    d = _triangle('auto_radius_narrow', c=(5.5, 0.6)).angle('alpha', 'B', 'A', 'C').angle('gamma', 'A', 'C', 'B')
    d.overrides('gamma', auto_radius=False)
    out.append(('auto_radius_narrow', d, auto))
    d = _triangle('right_angle', c=(0, 3)).right_mark('ra', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    out.append(('right_angle', d, None))
    d = _triangle('right_angle_auto', c=(0, 3)).right_mark('ra', 'B', 'A', 'C')
    out.append(('right_angle_auto', d, {'overlay': {'angle_radius': {'enabled': True, 'apply_to_right': True}}}))
    d = _triangle('right_angle_by_size', c=(0, 3)).angle('alpha', 'B', 'A', 'C')
    d.overrides('alpha', right_angle_joint='miter', right_angle_size_px=12)
    out.append(('right_angle_by_size', d, None))
    d = _triangle('right_angle_arcs', c=(0, 3)).right_mark('ra', 'B', 'A', 'C')
    d.overrides('ra', right_angle_marker=False, tick_count=2, arc_shift_px=3)
    out.append(('right_angle_arcs', d, None))
    d = _triangle('reflex').angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    d.overrides('alpha', angle_range='reflex', arc_size_px=10)
    out.append(('reflex', d, None))
    d = _triangle('wedge').polygon('T', 'A', 'B', 'C').angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    d.overrides('T', fill='#4a90d9', fill_opacity=0.35).overrides('beta', fill='#d05456', fill_opacity=0.5)
    out.append(('wedge', d, None))
    return out


def _points():
    from ..style.enums import POINT_SHAPES
    d = _Doc('point_shapes')
    for i, shape in enumerate(POINT_SHAPES):
        d.free(f'P{i}', i % 3 * 2, i // 3 * 1.5).overrides(f'P{i}', point_shape=shape, size_px=8 + i)
    d.overrides('P1', stroke='#d05456', stroke_width_px=2, fill_opacity=0)
    out = [('point_shapes', d, None)]
    d = _triangle('points_only_labels')
    out.append(('points_only_labels', d, {'rendering': {'points_display': 'only_labels'}}))
    d = _triangle('arrows').vector('v', 'A', 'B').vector('w', 'C', 'A')
    d.overrides('w', arrow_length_px=16, arrow_width_px=10, stroke_width_px=2.5)
    out.append(('arrows', d, None))
    return out


def _dashes():
    out = []
    d = _triangle('caps').segment('a', 'A', 'B').segment('b', 'B', 'C').segment('c', 'C', 'A')
    d.overrides('a', stroke_linecap='round', stroke_width_px=4).overrides('b', stroke_linecap='square',
                                                                           stroke_width_px=4)
    out.append(('caps', d, None))
    d = _triangle('caps_rendering').segment('a', 'A', 'B').ray('r', 'A', 'C')
    out.append(('caps_rendering', d, {'rendering': {'line_cap': 'round'}}))
    d = _triangle('dash_fit').segment('a', 'A', 'B').circle('c', 'A', 'C').arc('k', 'A', 'B', 'C')
    d.line('l', 'B', 'C').ray('r', 'C', 'A').vector('v', 'B', 'C')
    for el_id in ('a', 'c', 'k', 'l', 'r', 'v'):
        d.overrides(el_id, stroke_dash_ratio=0.6)
    d.overrides('k', stroke_dash_period_px=7)
    out.append(('dash_fit', d, None))
    d = _triangle('dash_round_caps').segment('a', 'A', 'B').line('l', 'B', 'C')
    d.overrides('a', stroke_dash_ratio=0.5, stroke_linecap='round', stroke_width_px=3)
    d.overrides('l', stroke_dash_ratio=0.5, stroke_linecap='square', stroke_width_px=2)
    out.append(('dash_round_caps', d, None))
    d = _triangle('dash_period_rendering').segment('a', 'A', 'B').polyline('w', 'A', 'C', 'B', 'A')
    d.overrides('a', stroke_dash_ratio=0.5).overrides('w', stroke_dash_ratio=0.3)
    out.append(('dash_period_rendering', d, {'rendering': {'dash_period_px': 16}}))
    return out


def _labels():
    out = []
    d = _zoo('label_anchors')
    for el_id in ('s', 'l', 'r', 'v', 'c', 'T', 'k', 'q', 'alpha', 'ra'):
        d.label(el_id)
    out.append(('label_anchors', d, None))
    out.append(('label_anchors_bc', copy.deepcopy(d).look('A'), {'rendering': {'label_anchor': 'BC'}}))
    d = _triangle('label_anchor_overrides').segment('a', 'A', 'B').angle('alpha', 'B', 'A', 'C')
    d.label('a').label('alpha').overrides('a', label_anchor='TR', label_color='#d05456', font_size_px=18)
    d.overrides('alpha', label_anchor='MC', label_radial_offset_px=6).overrides('C', label_anchor='ML')
    out.append(('label_anchor_overrides', d, None))
    d = _triangle('label_offsets').look('A', label={'mode': 'name', 'offsetWorld': [0.3, -0.2]})
    out.append(('label_offsets', d, None))
    # the underscore: one character, a group, nothing to index
    d = _triangle('label_names').segment('a', 'A', 'B').segment('b', 'B', 'C').angle('alpha', 'B', 'A', 'C')
    for el_id, name in (('A', 'A_1'), ('B', 'B_{12}'), ('C', 'angle_C'), ('a', 'a_'), ('b', 'b__2'),
                        ('alpha', '\\alpha_1')):
        d.doc['elements'][el_id]['displayName'] = name
    d.label('a').label('b', 'name_value').label('alpha', 'name_value')
    out.append(('label_names', d, None))
    # the halo: of the style, of an element, on a dark background
    d = _triangle('label_halo').segment('a', 'A', 'B').angle('alpha', 'B', 'A', 'C').text('t', 'x', 'C')
    d.label('a').label('alpha', 'value')
    d.overrides('a', label_halo_px=4, label_halo_color='#ffee00', label_halo_opacity=0.5)
    out.append(('label_halo', d, {'rendering': {'label_halo_px': 3}}))
    out.append(('label_halo_dark', copy.deepcopy(d),
                {'presets': {'color': {'background': '#1e1e1e', 'strong': '#f0f0f0'}},
                 'rendering': {'label_halo_px': 2, 'label_halo_opacity': 0.8}}))
    return out


def _values():
    out = []
    d = _triangle('value_format').segment('a', 'A', 'B').segment('b', 'B', 'C').angle('alpha', 'B', 'A', 'C')
    d.label('a', 'value').label('b', 'name_value').label('alpha', 'value')
    d.overrides('b', label_value_precision=3, label_value_strip_zeros=False, label_value_separator=': ')
    d.overrides('alpha', label_value_precision=0)
    out.append(('value_format', d, None))
    d = _triangle('value_radian').angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    d.label('alpha', 'value').label('beta', 'name_value').overrides('alpha', label_angle_unit='radian',
                                                                    label_value_precision=2)
    out.append(('value_radian', d, None))
    d = _triangle('value_measures').polygon('T', 'A', 'B', 'C').circle('c', 'A', 'B')
    d.label('T', 'name_value').label('c', 'value')
    out.append(('value_measures', d, {'rendering': {'label_value_precision': 2}}))
    return out


def _layers():
    out = [('z_order', _zoo('z_order'), None)]
    d = _triangle('z_overrides').polygon('T', 'A', 'B', 'C').segment('a', 'A', 'B').circle('c', 'C', 'A')
    d.overrides('T', z_index=6, fill='#4a90d9', fill_opacity=0.5).overrides('c', z_index_fill=7)
    out.append(('z_overrides', d, None))
    return out


def _texts():
    d = _triangle('text_free').text('t', 'Треугольник ABC', 'C').text('u', 'x', 'A')
    d.overrides('u', label_color='#d05456', font_size_px=20)
    return [('text_free', d, None)]


def _base():
    out = [('zoo_no_style', _zoo('zoo_no_style'), None),
           ('zoo_builtin', _zoo('zoo_builtin'), _builtin_style())]
    d = _zoo('zoo_book').label('s').label('alpha', 'value')
    out.append(('zoo_book', d, json.loads((Path(__file__).resolve().parents[1] / 'style' / 'presets'
                                           / 'book_blue.json').read_text(encoding='utf-8'))))
    d = _triangle('roles').segment('a', 'A', 'B').segment('b', 'B', 'C').circle('c', 'A', 'B')
    d.look('a', role='given').look('b', role='aux').look('c', role='sought').look('C', role='aux')
    out.append(('roles', d, None))
    d = _triangle('hatch').polygon('T', 'A', 'B', 'C').circle('c', 'C', 'A').sector('q', 'A', 'B', 'C')
    d.overrides('T', fill_pattern='hatch', hatch_angle_deg=30).overrides('c', fill_pattern='crosshatch',
                                                                         hatch_color='#d05456')
    d.overrides('q', fill_pattern='dots', hatch_spacing_px=4, fill='#eeeeee')
    out.append(('hatch', d, None))
    d = _triangle('dark').polygon('T', 'A', 'B', 'C').angle('alpha', 'B', 'A', 'C')
    out.append(('dark', d, {'presets': {'color': {'background': '#1e1e1e', 'strong': '#f0f0f0'}}}))
    return out


def _timeline():
    d = _triangle('style_track').segment('a', 'A', 'B').circle('c', 'A', 'B')
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'styles': {'a': {'stroke': '#000000', 'stroke_width_px': 1}}},
        {'t': 1, 'styles': {'a': {'stroke': '#ff0000', 'stroke_width_px': 3}}, 'easing': 'linear'},
        {'t': 2, 'values': {'C': [2, 4]}, 'easing': 'linear'},
    ]}
    out = [(f'style_track_{t}', d, None, timeline, t) for t in (0, 0.5, 1, 1.5)]
    # effects: T enters in [0.2, 0.8] (its fill a track), a leaves in [1, 1.4] (its cap a discrete track)
    d = _triangle('effects').segment('a', 'A', 'B').polygon('T', 'A', 'B', 'C')
    d.overrides('a', stroke_width_px=4).overrides('T', fill='#4a90d9', fill_opacity=0.35)
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'visible': {'T': False}, 'styles': {'a': {'stroke_linecap': 'butt'}}},
        {'t': 1, 'visible': {'T': True}, 'enter': {'T': {'effect': 'fade', 'duration': 0.6, 'at': 0.2}},
         'styles': {'T': {'fill': '#d05456'}, 'a': {'stroke_linecap': 'round'}}},
        {'t': 2, 'visible': {'a': False}, 'exit': {'a': 'fade'}},
    ]}
    out += [(f'effects_{t}', d, None, timeline, t) for t in (0.1, 0.5, 1.2, 2)]
    return out


THEMES = (('paint_ticks', _ticks), ('paint_angles', _angles), ('paint_points', _points),
          ('paint_dashes', _dashes), ('paint_labels', _labels), ('paint_values', _values),
          ('paint_layers', _layers), ('paint_text', _texts), ('paint_base', _base),
          ('paint_timeline', _timeline))


def _expect(document, style, timeline, t) -> dict:
    from .paint import resolve_paint
    return resolve_paint(document, style, t, timeline=timeline)


def _rows(scenes) -> list:
    rows = []
    for scene in scenes:
        name, d, style = scene[:3]
        timeline, t = (scene[3], scene[4]) if len(scene) > 3 else (None, None)
        document = d.doc if isinstance(d, _Doc) else d
        rows.append({'name': name, 'document': document, 'style': style, 't': t, 'timeline': timeline,
                     'expect': json.loads(json.dumps(_expect(document, style, timeline, t)))})
    return rows


def build_fixtures() -> dict:
    """``{file name: fixture}``."""
    from .. import __version__
    return {name + '.json': {'format': PAINT_PARITY_FORMAT, 'id': name, 'registry': REGISTRY_VERSION,
                             'generatedBy': f'animageo {__version__}', 'cases': _rows(scenes())}
            for name, scenes in THEMES}


def _dump(fixture) -> str:
    return json.dumps(fixture, ensure_ascii=False, indent=1) + '\n'


def write_fixtures(directory=DEFAULT_DIR) -> list:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fixture in sorted(build_fixtures().items()):
        path = directory / name
        path.write_text(_dump(fixture), encoding='utf-8')
        written.append(path)
    return written


def check_fixtures(directory=DEFAULT_DIR) -> list:
    """Files that differ from a fresh build (the version label aside)."""
    directory = Path(directory)
    problems = []
    built = build_fixtures()
    for name, fixture in sorted(built.items()):
        path = directory / name
        if not path.exists():
            problems.append(f'{path}: missing')
            continue
        old = json.loads(path.read_text(encoding='utf-8'))
        old.pop('generatedBy', None)
        new = dict(fixture)
        new.pop('generatedBy', None)
        if old != json.loads(json.dumps(new)):
            problems.append(f'{path}: out of date')
    for path in sorted(directory.glob('*.json')):
        if path.name not in built:
            problems.append(f'{path}: not built here')
    return problems


def _compare(expected, actual, where) -> list:
    if isinstance(expected, bool) or isinstance(actual, bool) or expected is None or actual is None:
        return [] if expected == actual else [f'{where}: expected {expected!r}, got {actual!r}']
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        ok = math.isfinite(expected) and abs(expected - actual) <= TOLERANCE
        return [] if ok else [f'{where}: expected {expected!r}, got {actual!r}']
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f'{where}: expected {len(expected)} items, got {len(actual)}']
        out = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            out += _compare(e, a, f'{where}[{i}]')
        return out
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            return [f'{where}: keys {sorted(expected)} != {sorted(actual)}']
        out = []
        for key in sorted(expected):
            out += _compare(expected[key], actual[key], f'{where}.{key}')
        return out
    return [] if expected == actual else [f'{where}: expected {expected!r}, got {actual!r}']


def verify_fixture(fixture: dict, label: str = '') -> tuple:
    """``(cases, mismatches)`` of one ``animageo-paint-parity/v1`` fixture."""
    label = label or str(fixture.get('id', '?'))
    out = []
    for case in fixture.get('cases') or []:
        where = f"{label} [{case.get('name')}]"
        try:
            actual = json.loads(json.dumps(_expect(case['document'], case.get('style'), case.get('timeline'),
                                                   case.get('t'))))
        except (KeyError, ValueError) as exc:
            out.append(f'{where}: {exc}')
            continue
        out += _compare(case.get('expect'), actual, where)
    return len(fixture.get('cases') or []), out


def verify_fixtures(directory=DEFAULT_DIR) -> tuple:
    """``(files, cases, mismatches)`` over the fixtures in ``directory``."""
    files = cases = 0
    mismatches = []
    for path in sorted(Path(directory).glob('*.json')):
        fixture = json.loads(path.read_text(encoding='utf-8'))
        n, out = verify_fixture(fixture, path.stem)
        files += 1
        cases += n
        mismatches += out
    return files, cases, mismatches
