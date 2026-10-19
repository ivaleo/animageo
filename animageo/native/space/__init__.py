"""``animageo.native.space`` — space (3D) drawings. **Experimental.**

The space registry ``1.0`` (a version line of its own), the space
document, the flat scene ``/1`` and the fixtures may change without a
deprecation period; nothing here is a part of the plane contract (the plane
registry ``REGISTRY_VERSION``, ``native.*``, the public API snapshot). Pure Python (no numpy, no manim at import time), so the browser
kernel repeats it formula for formula. Reference: ``docs/native/space.md``.

The path of a drawing::

    space document (space: "space", space registry 1.0)
        ──► evaluate (values by element ID)
        ──► camera (viewDefaults.camera) ──► visibility
        ──► flat scene /1 (pieces seen or hidden, fills far to near, points)
        ──► a plane document ──► native.render (SVG, PNG, PDF, EPS, TikZ)

    from animageo.native import render, space

    b = space.SpaceBuilder('cube', camera={'azimuthDeg': -60, 'elevationDeg': 25, 'target': [1, 1, 1]})
    b.point('A', 0, 0, 0); b.point('B', 2, 0, 0)
    cube = b.cube('K', 'A', 'B', vertices=['C', 'D', 'A_1', 'B_1', 'C_1', 'D_1'])
    doc = b.data()
    space.evaluate(doc)                     # animageo-evaluated/v1, registry 1.0
    flat = space.flat_scene(doc)            # animageo-flat-scene/1
    render(doc, out='cube.svg')             # native.render hands it to space.render (needs manim)

Modules: :mod:`.registry` (space registry 1.0), :mod:`.document` (load, validate),
:mod:`.build` (a builder), :mod:`.ops` and :mod:`.evaluate` (the kernel),
:mod:`.vec`, :mod:`.camera`, :mod:`.solids`, :mod:`.visibility`,
:mod:`.section` (the formulas), :mod:`.scene` (the flat scene ``/1``),
:mod:`.bridge` (the plane document, the style of space, rendering),
:mod:`.fixtures` (``animageo-space-parity/v1``), :mod:`.flicker` (the flicker
metric). :mod:`.flat` is the prototype path of 3D-0 (``SpaceScene`` →
``animageo-flat-scene/0``), kept for its tests: ``flat_scene``,
``to_document`` and ``render`` of the package take either.
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
