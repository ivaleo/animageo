"""Label layout of a document without manim: :func:`layout_labels` (spec §9.3).

The same pipeline as ``native.render`` up to the drawing: the bridge builds
the classic construction, the appearance plan is applied, the style and the
export layout give the output canvas, and the classic placement solver
(``label_placement.compute_label_layout``) runs on a
``label_placement.LayoutInput`` instead of a manim scene. Labels are
measured by the ``metrics`` backend (``labels/tex.py``: the TeX of the
label set with the metrics of the template's fonts) or by ``tex`` (manim's
``Tex``, as the renderer).

Nothing is written into the document: a suggested position becomes a
user's when it is pinned (``appearance.label.offsetWorld`` and
``overrides.label_anchor`` of the entry), and ``native.render`` then draws
the label there.
"""
from __future__ import annotations

import functools
import json
import math
from types import SimpleNamespace

from ..document import as_document
from ..rendering import (
    _check_layout,
    appearance_plan,
    apply_appearance,
    label_overlaps,
    label_point_overlaps,
    source_view,
)
from . import tex

__all__ = ['BACKENDS', 'FRAME_RATIO', 'frame_bounds', 'layout_labels', 'measure_metrics']

BACKENDS = ('metrics', 'tex')
# The camera frame of the renderer keeps the aspect of the manim output
# (``config.pixel_width / pixel_height``, 1920×1080 by default).
FRAME_RATIO = 1920 / 1080


@functools.lru_cache(maxsize=8192)
def measure_metrics(text: str, font_size: float) -> tuple:
    """``(width, height)`` in manim units of the label ``text`` at the manim
    ``font_size`` (the ``metrics`` backend). TeX outside the subset of
    ``labels/tex.py`` is estimated as the classic renderer does when LaTeX
    fails (``label_placement._estimate_label_bbox``)."""
    from ...labels import correctedLabel
    try:
        return tex.measure(correctedLabel(text), font_size)
    except tex.Unsupported:
        from ...label_placement import _estimate_label_bbox
        return _estimate_label_bbox(text, font_size)


def _tex_measurer():
    try:
        from ... import ui  # noqa: F401  (manim and the label template)
        from ...label_placement import _measure_label_bbox
    except ModuleNotFoundError as exc:
        if exc.name == 'manim' or (exc.name or '').startswith('manim.'):
            raise RuntimeError("layout_labels(backend='tex') needs manim; "
                               "backend='metrics' does not") from None
        raise
    return _measure_label_bbox


def frame_bounds(export: dict, ratio: float = FRAME_RATIO) -> tuple:
    """``(left, bottom, right, top)`` in scene units of the camera frame the
    renderer sets for ``export`` (``AnimaGeoScene._set_camera_from_export``):
    the canvas widened to the frame aspect ``ratio``."""
    unit = float(export['ptUnit'])
    width, height = float(export['ptWidth']), float(export['ptHeight'])
    xzero, yzero = float(export['ptXZero']), float(export['ptYZero'])
    if width / height >= ratio:
        frame_w = width / unit
        frame_h = frame_w / ratio
        left = -xzero / unit
        cy = yzero / unit - height / (2 * unit)
        return (left, cy - frame_h / 2, left + frame_w, cy + frame_h / 2)
    frame_h = height / unit
    frame_w = ratio * frame_h
    cx = width / (2 * unit) - xzero / unit
    top = yzero / unit
    return (cx - frame_w / 2, top - frame_h, cx + frame_w / 2, top)


def _load_style(style_config):
    """``(StyleConfig, rendering)`` of ``applyStyle``: the style over the
    built-in one with the effective background mirrored into
    ``presets.color``, and the ``rendering`` section of the style itself
    (``GeoStyle.rendering``, not merged with the built-in style: the
    renderer's default ``label_anchor`` comes from there)."""
    from ...style import _is_concrete_color
    from ...style.config import StyleConfig, resolve_style_input, style_path_for_geostyle

    style = resolve_style_input(style_config)
    cfg = StyleConfig.load(style)
    raw = style_path_for_geostyle(style) or {}
    if isinstance(raw, str):
        with open(raw, encoding='utf-8') as fh:
            raw = json.load(fh)
    user_color = (raw.get('presets') or {}).get('color') or {}
    explicit = (_is_concrete_color(user_color.get('background'))       # GeoStyle.background_explicit
                or _is_concrete_color((raw.get('rendering') or {}).get('background')))
    background = cfg.presets.get('color', {}).get('background', '#ffffff')
    if explicit:
        rendering_bg = cfg.rendering.get('background')
        if _is_concrete_color(rendering_bg):
            background = rendering_bg
    else:
        background = '#ffffff'          # a document has no applet background
    cfg.presets.setdefault('color', {})['background'] = background
    return cfg, dict(raw.get('rendering') or {})


def _shown(scene, elem) -> bool:
    from ...geo import construction as geo
    from ...style.resolver import resolve
    return (isinstance(elem, geo.Element) and geo.is_drawn(elem.data)
            and bool(resolve(scene, elem, 'visible', default=getattr(elem, 'visible', True)))
            and resolve(scene, elem, 'label_visible', default=False) is True)


def _label_geometry(scene, elem, placement):
    """``(spot, center, half, offset, anchor)`` of a label as the renderer
    draws it (scene units): the box centre is ``spot + offset / ptUnit_ggb −
    edge · half``, ``edge`` the anchor's corner (``ui.create_label``; ``BL``
    when no layer names one); ``anchor`` — the name of that corner (``None``
    for a direction vector that is none of the nine)."""
    from ...label_placement import ANCHOR_EDGES, label_size, label_spot, point_label_clearance
    from ...style.resolver import resolve

    width, height = label_size(scene, elem)
    half = (float(width) / 2, float(height) / 2)
    spot = label_spot(scene, elem)
    if placement is not None:
        offset, anchor = placement.offset_ggb, placement.label_anchor
    else:
        offset = resolve(scene, elem, 'label_offset_px', default=None)
        anchor = resolve(scene, elem, 'label_anchor', default=scene.style.rendering.get('label_anchor'))
        cleared = point_label_clearance(scene, elem, anchor)
        if cleared is not None:
            offset = cleared
        if offset is None:
            offset = elem.style.get('label_offset_px')
        if anchor is None:
            anchor = elem.style.get('label_anchor')
    if isinstance(anchor, str):
        edge = ANCHOR_EDGES.get(anchor, ANCHOR_EDGES['BL'])
    elif anchor is not None:
        edge = (float(anchor[0]), float(anchor[1]))
    else:
        edge = ANCHOR_EDGES['BL']       # create_label's align_edge=DL
    export = scene.style.export
    scale = float(export.get('ptUnit_ggb') or export.get('ptUnit_style') or export['ptUnit'])
    off = (0.0, 0.0) if offset is None else (float(offset[0]) / scale, float(offset[1]) / scale)
    center = (float(spot[0]) + off[0] - edge[0] * half[0], float(spot[1]) + off[1] - edge[1] * half[1])
    name = next((k for k, v in ANCHOR_EDGES.items() if v == tuple(edge)), None)
    return (float(spot[0]), float(spot[1])), center, half, off, name


def _drawing_bounds(scene, infinite_policy: str, labels: bool, placements: dict):
    """``(left, bottom, right, top)`` of the drawing in scene units, or
    ``None``: an approximation of ``AnimaGeoScene._rendered_bounds_source_view``
    from the geometry (point markers, circles, angle markers; lines and rays
    clipped to the frame or ignored by ``infinite_policy``) and, with
    ``labels``, the label boxes where they stand."""
    import numpy as np

    from ...geo import construction as geo
    from ...label_placement import DOT_SIZE_PX, _angle_label_params, _style_ptUnit
    from ...style.resolver import resolve

    unit = _style_ptUnit(scene.style)
    xs, ys = [], []

    def add(x, y, rx=0.0, ry=0.0):
        xs.extend((float(x) - rx, float(x) + rx))
        ys.extend((float(y) - ry, float(y) + ry))

    for elem in scene.geo.elements:
        data = elem.data
        if not geo.is_drawn(data) or not resolve(scene, elem, 'visible', default=getattr(elem, 'visible', True)):
            continue
        # as the classic measure: Line and its subclasses (Segment, Ray) skipped
        if infinite_policy == 'ignore' and isinstance(data, (geo.Line, geo.Ray)):
            continue
        if isinstance(data, geo.Point):
            r = float(resolve(scene, elem, 'size_px', default=DOT_SIZE_PX)) / 2 / unit
            add(data.coords[0], data.coords[1], r, r)
        elif isinstance(data, geo.Segment) or isinstance(data, geo.Vector):
            for p in data.endpoints:
                add(p[0], p[1])
        elif isinstance(data, (geo.Line, geo.Ray)):
            left, bottom, right, top = scene._get_scene_bounds()
            ends = data.get_endpoints([(left, bottom), (right, top)])
            for p in ends or ():
                add(p[0], p[1])
        elif isinstance(data, geo.Circle):
            add(data.center[0], data.center[1], float(data.radius), float(data.radius))
        elif isinstance(data, geo.Polygon):
            for p in data.vertices:
                add(p[0], p[1])
        elif isinstance(data, geo.Angle):
            ap = _angle_label_params(scene, elem, 0.0, 0.0)
            vx, vy = float(data.vertex[0]), float(data.vertex[1])
            add(vx, vy)
            s1 = np.asarray(data.side1[:2], dtype=float)
            s2 = np.asarray(data.side2[:2], dtype=float)
            n1, n2 = np.linalg.norm(s1), np.linalg.norm(s2)
            if n1 == 0 or n2 == 0:
                continue
            if not math.isclose(ap.arc_r_px, ap.render_r_px):       # drawn as a right-angle square
                r = (ap.arc_r_px / math.sqrt(2)) / unit
                a, b = s1 * (r / n1), s2 * (r / n2)
                for p in (a, a + b, b):
                    add(vx + p[0], vy + p[1])
                continue
            r = ap.arc_r_px / unit
            a0 = math.atan2(s1[1], s1[0])
            size = float(data.size)
            if (ap.angle_range == 'minor' and size > math.pi) or (ap.angle_range == 'reflex' and size < math.pi):
                a0, size = math.atan2(s2[1], s2[0]), 2 * math.pi - size
            for k in range(33):
                t = a0 + size * k / 32
                add(vx + r * math.cos(t), vy + r * math.sin(t))
        if labels and _shown(scene, elem):
            _, center, half, _, _ = _label_geometry(scene, elem, placements.get(elem.name))
            add(center[0], center[1], half[0], half[1])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _px(export, x, y) -> list:
    u, ox, oy = float(export['ptUnit']), float(export['ptXZero']), float(export['ptYZero'])
    return [round(ox + u * x, 3) + 0.0, round(oy - u * y, 3) + 0.0]


def layout_labels(doc, ev=None, *, inputs=None, style_config=None, export_layout=None,
                  backend='metrics', place=None) -> dict:
    """Label positions of ``doc`` as ``native.render`` would draw them, without manim.

    ``style_config``, ``export_layout`` and ``inputs`` are those of
    ``native.render``; ``ev`` — an ``Evaluated`` of the same inputs (computed
    when ``None``). ``backend``: ``metrics`` (no manim, no LaTeX) or ``tex``
    (manim's ``Tex``, as the renderer). ``place``: run the placement solver —
    ``None`` follows the style (``overlay.label_placement.enabled``, off in
    the built-in style: labels stay at the style's anchor and offset),
    ``True`` places the labels that are not pinned whatever the style says.

    Returns ``{elementId: entry}`` for every drawn element with a shown label,
    in output pixels as the render report (y down)::

        {"text": "$A$", "anchor": "BL", "point": [x, y],
         "offsetPx": [dx, dy], "offsetWorld": [wx, wy],
         "box": [x0, y0, x1, y1], "leader": [[x, y], [x, y]] | None,
         "overlaps": ["<id>", …], "pointOverlaps": ["<id>", …],
         "placed": bool, "locked": bool}

    ``point`` is the spot of the element the label hangs from, ``offsetWorld``
    the offset in world units (y up); ``anchor`` with ``offsetWorld`` pinned
    in ``appearance`` (``label.offsetWorld``, ``overrides.label_anchor``)
    puts the label at ``box``. ``overlaps``: the other labels whose box
    covers at least 15 % of the smaller box, ``pointOverlaps``: the drawn
    points whose marker the box enters, its own included (as the report's
    ``overlaps`` and ``pointOverlaps``). An unplaced point label hangs clear
    of its marker (``label_placement.point_label_clearance``). Under
    ``content.source = 'rendered_bounds'`` the crop is approximated from the
    geometry and the label boxes (the renderer measures its mobjects).
    """
    if backend not in BACKENDS:
        raise ValueError(f'backend {backend!r}: one of {", ".join(BACKENDS)}')
    layout = _check_layout(export_layout)
    doc = as_document(doc)
    from ..kernel.evaluate import check_inputs, evaluate
    check_inputs(doc, inputs)
    if ev is None:
        ev = evaluate(doc, inputs=inputs)
    measure = measure_metrics if backend == 'metrics' else _tex_measurer()

    from ...export_layout import normalize_content_options, source_view_from_bounds_px, static_export_dict
    from ...label_placement import LayoutInput, apply_label_layout, compute_label_layout
    from ..kernel.bridge import build_construction

    cfg, rendering = _load_style(style_config)
    solver_cfg = dict(cfg.overlay.label_placement or {})
    if place is None:
        place = bool(solver_cfg.get('enabled'))
    solver_cfg['enabled'] = True
    canonicalize = bool(solver_cfg.get('canonicalize_anchor', False))

    view = source_view(doc)
    view['ptUnit_ggb'] = view['ptUnit']     # offsets in world units, as loadDocument
    construction, names = build_construction(doc, inputs=inputs)
    construction.rebuild(full=True)
    plan, _ = appearance_plan(doc, view['ptUnit'], inputs=inputs, evaluated=ev, roles=cfg.source.get('roles'))
    apply_appearance(construction, names, plan)

    def scene(export, camera=None):
        return LayoutInput(geo=construction, style=SimpleNamespace(export=export, rendering=rendering),
                           style_config=cfg,
                           bounds=frame_bounds(camera or export), measure_label=measure,
                           label_point_clearance=True)

    def solve(inp):
        placements = compute_label_layout(inp, cfg=solver_cfg, canonicalize=canonicalize)
        apply_label_layout(inp, placements, rerender=False)
        return placements

    content = normalize_content_options(layout.get('content'))
    kwargs = {'style_reference': getattr(cfg, 'reference', {}), 'reference': layout.get('reference'),
              'content': layout.get('content'), 'export': layout.get('export')}
    rendered = None
    if content['source'] == 'rendered_bounds':
        policy = content.get('infinite_policy', 'ignore')
        if content.get('bounds') is not None:
            rendered = source_view_from_bounds_px(view, content['bounds'], infinite_policy=policy)
        else:
            from ...export_layout import rendered_view_from_bounds
            reserve = content.get('label_bounds', 'reserve') != 'exclude'
            # applyStyle: measured at the source view, labels where they stand;
            # with placement, placed at that crop and measured again
            bounds = _drawing_bounds(scene(dict(view)), policy, reserve, {})
            rendered = rendered_view_from_bounds(view, bounds, infinite_policy=policy)
            if place:
                first = static_export_dict(view, **kwargs, rendered_view=rendered, decoration=False)
                placements = solve(scene(first))
                bounds = _drawing_bounds(scene(first, camera=view), policy, reserve, placements)
                rendered = rendered_view_from_bounds(view, bounds, infinite_policy=policy)
    export = static_export_dict(view, **kwargs, rendered_view=rendered)
    final = scene(export)
    placements = solve(final) if place else {}

    from ...geo import construction as geo
    from ...label_placement import DOT_SIZE_PX, _style_ptUnit
    from ...style.resolver import resolve
    u = float(export['ptUnit'])
    markers = {}
    for el_id in sorted(doc.elements):
        elem = construction.objectByName(names.by_id[el_id])
        if (isinstance(elem, geo.Element) and type(elem.data) is geo.Point
                and resolve(final, elem, 'visible', default=getattr(elem, 'visible', True))):
            r = float(resolve(final, elem, 'size_px', default=DOT_SIZE_PX) or 0.0) / 2 / _style_ptUnit(final.style)
            markers[el_id] = (*_px(export, elem.data.coords[0], elem.data.coords[1]), r * u)
    boxes, entries = {}, {}
    for el_id in sorted(doc.elements):
        elem = construction.objectByName(names.by_id[el_id])
        if elem is None or not _shown(final, elem):
            continue
        placement = placements.get(elem.name)
        spot, center, half, off, anchor = _label_geometry(final, elem, placement)
        x0, y1 = _px(export, center[0] - half[0], center[1] - half[1])
        x1, y0 = _px(export, center[0] + half[0], center[1] + half[1])
        leader = None
        if placement is not None and placement.leader is not None:
            leader = [_px(export, *placement.leader.anchor[:2]), _px(export, *placement.leader.attach[:2])]
        entries[el_id] = {
            'text': _label_text(final, elem),
            'anchor': anchor,
            'point': _px(export, *spot),
            'offsetPx': [round(off[0] * u, 3) + 0.0, round(-off[1] * u, 3) + 0.0],
            'offsetWorld': [round(off[0], 9) + 0.0, round(off[1], 9) + 0.0],
            'box': [x0, y0, x1, y1],
            'leader': leader,
            'overlaps': [],
            'pointOverlaps': [],
            'placed': placement is not None,
            'locked': bool(resolve(final, elem, 'label_placement_locked', default=False)),
        }
        boxes[el_id] = entries[el_id]['box']
    for a, b in label_overlaps(boxes):
        entries[a]['overlaps'].append(b)
        entries[b]['overlaps'].append(a)
    for label_id, point_id in label_point_overlaps(boxes, markers):
        entries[label_id]['pointOverlaps'].append(point_id)
    return entries


def _label_text(scene, elem) -> str:
    from ...labels import resolve_label_text
    return resolve_label_text(scene, elem)
