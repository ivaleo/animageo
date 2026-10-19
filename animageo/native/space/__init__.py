"""``animageo.native.space`` — a prototype of space (3D) drawings.

**Experimental.** Not a part of the document contract: the operation
registry has no types of space yet, and every name here may change. The
package is pure Python (no numpy, no manim at import time) so that a
browser kernel can repeat it formula for formula.

The path of a drawing::

    solids and planes of space ──► camera (Projector) ──► visibility
        ──► flat scene (pieces of lines seen or hidden, fills far to near,
            points) ──► a native document of the plane ──► native.render

    from animageo.native import space

    cube = space.cube(size=2)
    cut = space.Plane.through((1, 0, 0), (2, 1, 0), (2, 2, 1))
    scene = space.SpaceScene(solids=[space.SceneSolid('cube', cube)],
                             sections=[space.SceneSection('cut', 'cube', cut)])
    camera = space.Camera(azimuth_deg=-60, elevation_deg=25, target=(1, 1, 1))
    flat = space.flat_scene(scene, camera)          # animageo-flat-scene/0
    doc = space.to_document(flat)                   # animageo-construction/v1
    space.render(flat, 'cube.svg')                  # needs manim

Modules: :mod:`.vec` (vectors), :mod:`.camera` (camera, projector),
:mod:`.solids` (planes, convex polyhedra), :mod:`.visibility` (faces,
edges, shadow volumes, pieces), :mod:`.section` (sections, plane sheets),
:mod:`.flat` (the flat scene, its document and rendering).
"""
from __future__ import annotations

from . import vec
from .camera import PROJECTIONS, Camera, Projector
from .flat import (
    FACE_LOOKS,
    FLAT_SCENE_FORMAT,
    HIDDEN_LOOKS,
    ScenePlane,
    ScenePoint,
    SceneSection,
    SceneSegment,
    SceneSolid,
    SpaceScene,
    flat_scene,
    render,
    to_document,
)
from .section import Section, plane_basis, plane_sheet, section, section_visibility
from .solids import Edge, Plane, Polyhedron, cube, polyhedron, prism, pyramid, scale_of, tetrahedron
from .visibility import (
    ConvexOccluder,
    Piece,
    edge_visibility,
    face_facing,
    pieces,
    vertex_visibility,
)

__all__ = [
    'vec',
    'PROJECTIONS', 'Camera', 'Projector',
    'Plane', 'Edge', 'Polyhedron', 'polyhedron', 'cube', 'prism', 'pyramid', 'tetrahedron', 'scale_of',
    'face_facing', 'edge_visibility', 'vertex_visibility', 'ConvexOccluder', 'Piece', 'pieces',
    'Section', 'section', 'section_visibility', 'plane_basis', 'plane_sheet',
    'FLAT_SCENE_FORMAT', 'HIDDEN_LOOKS', 'FACE_LOOKS', 'SceneSolid', 'SceneSection', 'SceneSegment',
    'ScenePoint', 'ScenePlane', 'SpaceScene', 'flat_scene', 'to_document', 'render',
]
