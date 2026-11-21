"""Portable parity cases for the plane primitives of the space painter."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .build import SpaceBuilder
from .fixtures import _cube, _round
from .paint import resolve_paint

FORMAT = 'animageo-space-paint-parity/v1'
DEFAULT_PATH = Path(__file__).resolve().parent.parent / 'parity' / 'v1' / 'space_paint' / 'space_paint_pieces.json'


def decorations_document():
    b = SpaceBuilder('decorations', camera={'azimuthDeg': -64, 'elevationDeg': 33})
    for k, size in enumerate((4, 5, 6), 1):
        a, z = f'A{k}', f'B{k}'
        b.point(a, 0, k * 2, 0)
        b.point(z, size, k * 2, 0)
        b.segment(f's{k}', a, z)
        b.midpoint(f'M{k}', a, z)
    b.point('P', 2, 2, 3)
    b.line('l', 'A1', 'B1')
    b.perpendicular_line('q', 'P', 'l')
    b.projection_line('F', 'P', 'l')
    doc = b.data()
    doc['appearance'] = {
        's1': {'label': {'mode': 'caption', 'text': 'Equal halves'}, 'overrides': {'stroke_linecap': 'round'}},
        'l': {'label': {'mode': 'name'}},
        'q': {'overrides': {'right_angle_size_px': 18}},
    }
    return doc



def _overlapping_document():
    b = SpaceBuilder('overlapping_solids')
    _cube(b)
    b.point('J_A', 1.7, 0.9, 0.3)
    b.point('J_B', 3.7, 0.9, 0.3)
    b.cube('J', 'J_A', 'J_B', vertices=['J_C', 'J_D', 'J_A_1', 'J_B_1', 'J_C_1', 'J_D_1'])
    for name, point in {
        'U': (0, 0, 0.8), 'V': (0, 1.5, 0.8), 'W': (1.5, 1, 0.8),
        'P': (-1.6, 3.4, 1.1), 'Q': (5.6, 3.4, 1.1),
        'C1': (3.8, 0, 0), 'C2': (5, 0, 0), 'C3': (4.6, 0, 1.25),
    }.items():
        b.point(name, *point)
    b.plane('pl', 'U', 'V', 'W')
    b.section('cut', 'pl', 'K')
    b.polygon('triangle', 'C1', 'C2', 'C3')
    b.segment('s', 'P', 'Q')
    b.line('l', 'P', 'Q')
    b.parallel('aux', 'C3', 'l')
    doc = b.data()
    doc['appearance'] = {name: {'visible': False} for name in 'UVWPQ'}
    doc['appearance'].update({
        'l': {'role': 'auxiliary', 'label': {'mode': 'name'}, 'overrides': {'stroke_linecap': 'round'}},
        's': {'overrides': {'stroke': '#843784', 'stroke_width_px': 2.6, 'hidden_look': 'thin'}},
        'aux': {'visibility': 'always', 'overrides': {'stroke_dash_ratio': 0.33, 'stroke_dash_period_px': 19}},
        'triangle': {'label': {'mode': 'caption', 'text': 'Face'}},
        'cut': {'label': {'mode': 'caption', 'text': 'Section'}},
        'pl': {'label': {'mode': 'caption', 'text': 'Plane'}},
    })
    return doc


def partially_hidden_midpoint():
    b = SpaceBuilder('partially_hidden_midpoint', camera={'azimuthDeg': -90, 'elevationDeg': 0})
    _cube(b)
    b.point('P', -4, 3, 1)
    b.point('Q', 2.5, 3, 1)
    b.segment('s', 'P', 'Q')
    b.midpoint('M', 'P', 'Q')
    return b.data()


def build_fixture():
    """The JSON shared by the native tests and other clients."""
    style = {'space': {'hidden': {'stroke_dash_period_px': 13, 'stroke_dash_ratio': 0.4}},
             'roles': {'auxiliary': {'stroke': '#3166a5', 'stroke_width_px': 1.3}}}
    overlap = _overlapping_document()
    marks = decorations_document()
    cases = []
    for name, doc, style_config, camera, layout in (
        ('overlap-ortho', overlap, style,
         {'azimuthDeg': -81, 'elevationDeg': 8, 'target': [1.5, 1.5, 1.0]},
         {'export': {'size': [620, 420]}}),
        ('overlap-perspective-no-hidden', overlap, {**style, 'space': {'hidden': {'look': 'none'}}},
         {'projection': 'perspective', 'azimuthDeg': -82, 'elevationDeg': 13, 'distance': 12,
          'target': [1.5, 1.5, 1.0]}, {'export': {'size': [1050, 680]}}),
        ('marks-oblique', marks, {}, {'projection': 'oblique'}, {'export': {'size': [460, 340]}}),
        ('marks-perspective', marks, {},
         {**marks['viewDefaults']['camera'], 'projection': 'perspective', 'distance': 20},
         {'export': {'size': [1200, 880]}}),
        ('marks-occluded-half', partially_hidden_midpoint(), {}, {'azimuthDeg': -90, 'elevationDeg': 0},
         {'export': {'size': [640, 380]}}),
    ):
        cases.append({'name': name, 'document': doc, 'styleConfig': style_config, 'camera': camera,
                      'exportLayout': layout,
                      'expect': _round(resolve_paint(doc, style_config, camera=camera, export_layout=layout))})
    return {'format': FORMAT, 'cases': cases}


def fixture_text(data=None):
    return json.dumps(build_fixture() if data is None else data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = build_fixture()
    content = fixture_text(data)
    if args.check:
        if not DEFAULT_PATH.is_file() or DEFAULT_PATH.read_text(encoding='utf-8') != content:
            parser.exit(1, f'{DEFAULT_PATH.name}: regenerate the fixture\n')
    else:
        DEFAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_PATH.write_text(content, encoding='utf-8')
    print(f"{DEFAULT_PATH.name}: {len(data['cases'])} cases")


if __name__ == '__main__':
    main()
