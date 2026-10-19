"""Views of one space drawing with the ``animageo.native.space`` prototype.

A cube ``ABCDA_1B_1C_1D_1`` cut by the plane through the midpoints M, N, K of
the edges AB, BC, CC_1, drawn through the native renderer:

- three projections — parallel (orthographic), the cabinet projection of
  school textbooks, perspective;
- three looks of hidden lines — pale dashes, dashes, thin;
- three ways to show the cutting plane — a sheet, its corners, its trace on
  the ground;
- the axes with z up and with y up.

    python scripts/native/space_views.py OUT_DIR

Needs manim and LaTeX, as any ``native.render``.
"""
from __future__ import annotations

import os
import sys

from animageo.native import space
from animageo.native.space import vec

VIEW = {'azimuth_deg': -60, 'elevation_deg': 22, 'target': (1, 1, 1)}


def cube_with_section(plane_look=None):
    cube = space.cube(size=2)
    m = vec.lerp(cube.vertex('A'), cube.vertex('B'), 0.5)
    n = vec.lerp(cube.vertex('B'), cube.vertex('C'), 0.5)
    k = vec.lerp(cube.vertex('C'), cube.vertex('C_1'), 0.5)
    plane = space.Plane.through(m, n, k)
    points = [space.ScenePoint('M', 'M', m), space.ScenePoint('N', 'N', n), space.ScenePoint('K', 'K', k)]
    planes = []
    if plane_look:
        cut = space.section(cube, plane)
        planes.append(space.ScenePlane('alpha', plane, cut.polygon, look=plane_look, margin=0.12))
    return space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                            sections=[space.SceneSection('cut', 'cube', plane)],
                            points=points, planes=planes)


def cube_with_axes(up):
    """The cube with A at the origin and the axes; the point P = (2, 1, 2) of
    the world named by the coordinates a reader would see: with z up as is,
    with y up (the ground Oxz) as ``(x, z, −y)``."""
    cube = space.cube(size=2)
    if up == 'z':
        axes = {'x': (3.6, 0, 0), 'y': (0, 3.6, 0), 'z': (0, 0, 3.4)}
        name = 'P(2;\\,1;\\,2)'
    else:
        axes = {'x': (3.6, 0, 0), 'y': (0, 0, 3.4), 'z': (0, -3.0, 0)}
        name = 'P(2;\\,2;\\,{-1})'
    segments = [space.SceneSegment(f'axis_{a}', (0, 0, 0), end, role='axis') for a, end in axes.items()]
    points = [space.ScenePoint(f'axis_{a}_end', a, end) for a, end in axes.items()]
    points.append(space.ScenePoint('P', name, (2, 1, 2)))
    return space.SpaceScene(solids=[space.SceneSolid('cube', cube)], segments=segments, points=points)


def views():
    """``{file name: (scene, camera, look)}``."""
    scene = cube_with_section()
    ortho = space.Camera(projection='orthographic', **VIEW)
    return {
        'projection-orthographic.svg': (scene, ortho, None),
        'projection-oblique.svg': (scene, space.Camera(projection='oblique', target=(1, 1, 1)), None),
        'projection-perspective.svg': (scene, space.Camera(projection='perspective', distance=7.5, **VIEW), None),
        'hidden-dashpale.svg': (scene, ortho, {'hidden': 'dashpale', 'faces': 'none'}),
        'hidden-dash.svg': (scene, ortho, {'hidden': 'dash', 'faces': 'none'}),
        'hidden-thin.svg': (scene, ortho, {'hidden': 'thin', 'faces': 'none'}),
        'plane-sheet.svg': (cube_with_section('sheet'), ortho, {'faces': 'none'}),
        'plane-corners.svg': (cube_with_section('corners'), ortho, {'faces': 'none'}),
        'plane-trace.svg': (cube_with_section('trace'), ortho, {'faces': 'none'}),
        'axes-z-up.svg': (cube_with_axes('z'), space.Camera(azimuth_deg=20, elevation_deg=18, target=(1, 1, 1)),
                          {'faces': 'none'}),
        'axes-y-up.svg': (cube_with_axes('y'), space.Camera(azimuth_deg=-70, elevation_deg=18, target=(1, 1, 1)),
                          {'faces': 'none'}),
    }


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, (scene, camera, look) in views().items():
        flat = space.flat_scene(scene, camera)
        space.render(flat, os.path.join(out_dir, name), look=look)
        print(name)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'space-views')
