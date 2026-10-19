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
from . import flat as _flat
from .bridge import FACE_LOOKS, HIDDEN_LOOKS, SPACE_STYLE_DEFAULTS, space_style
from .bridge import render as _render_document
from .bridge import to_document as _document_of_flat
from .build import SpaceBuilder
from .camera import PROJECTIONS, Camera, Projector
from .document import camera_of, is_space, load, validate
from .evaluate import evaluate
from .flat import ScenePlane, ScenePoint, SceneSection, SceneSegment, SceneSolid, SpaceScene
from .registry import SPACE_REGISTRY_VERSION, space_registry
from .scene import FLAT_SCENE_FORMAT
from .scene import flat_scene as _flat_scene_of_document
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


def flat_scene(source, camera=None, **kwargs) -> dict:
    """The flat scene of a space document (``animageo-flat-scene/1``,
    :func:`.scene.flat_scene`); of a prototype :class:`SpaceScene`, the
    prototype ``animageo-flat-scene/0`` (:func:`.flat.flat_scene`)."""
    if isinstance(source, SpaceScene):
        return _flat.flat_scene(source, camera, **kwargs)
    return _flat_scene_of_document(source, camera, **kwargs)


def to_document(flat, doc=None, **kwargs) -> dict:
    """The plane document that draws a flat scene: of ``/1`` with its space
    document ``doc`` (:func:`.bridge.to_document`), of the prototype ``/0``
    alone (:func:`.flat.to_document`)."""
    if flat.get('format') == _flat.FLAT_SCENE_FORMAT:
        return _flat.to_document(flat, **kwargs)
    return _document_of_flat(flat, doc, **kwargs)


def render(source, out=None, **kwargs):
    """Draw a space document (:func:`.bridge.render`) or a prototype flat
    scene ``/0`` (:func:`.flat.render`) with ``native.render``."""
    if isinstance(source, dict) and source.get('format') == _flat.FLAT_SCENE_FORMAT:
        return _flat.render(source, out, **kwargs)
    return _render_document(source, out, **kwargs)


__all__ = [
    'vec',
    'SPACE_REGISTRY_VERSION', 'space_registry', 'is_space', 'load', 'validate', 'camera_of', 'evaluate',
    'SpaceBuilder', 'FLAT_SCENE_FORMAT', 'flat_scene', 'to_document', 'render',
    'HIDDEN_LOOKS', 'FACE_LOOKS', 'SPACE_STYLE_DEFAULTS', 'space_style',
    'PROJECTIONS', 'Camera', 'Projector',
    'Plane', 'Edge', 'Polyhedron', 'polyhedron', 'cube', 'prism', 'pyramid', 'tetrahedron', 'scale_of',
    'face_facing', 'edge_visibility', 'vertex_visibility', 'ConvexOccluder', 'Piece', 'pieces',
    'Section', 'section', 'section_visibility', 'plane_basis', 'plane_sheet',
    'SceneSolid', 'SceneSection', 'SceneSegment', 'ScenePoint', 'ScenePlane', 'SpaceScene',
]
