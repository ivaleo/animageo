"""Render a document to SVG, PNG or PDF (``native.render``) and its report.

The construction is built by the bridge (``kernel/bridge.py``) as a classic
``animageo.geo.Construction`` and drawn by ``AnimaGeoScene.loadDocument`` —
the same renderer, style and layout as a ``.ggb``. Only :func:`render`
needs manim; it is imported inside the function, so ``import
animageo.native`` stays manim-free, and so do :func:`source_view` and
:func:`appearance_plan`.

Source view (the analogue of the applet window of a ``.ggb``)::

    bounds = viewDefaults.bounds or defaultBounds      # [xmin, ymin, xmax, ymax]
    ptWidth = 800, ptUnit = 800 / (xmax - xmin)
    ptHeight = (ymax - ymin) · ptUnit
    ptXZero = -xmin · ptUnit, ptYZero = ymax · ptUnit

Report ``animageo-render-report/v1`` (keys are document element IDs; pixels
of the output, for PDF px at 96 dpi; the y axis points down)::

    {"format": "animageo-render-report/v1", "documentId": …,
     "kernel": {"library": "1.8.0a2", "registry": "1.1"}, "fmt": "svg",
     "canvas": {"width": W, "height": H, "unit": u, "origin": [ox, oy]},
     "elements": {"<id>": {"state": "defined", "visible": true,
                           "box": [x0, y0, x1, y1] | null,
                           "label": {"box": […], "anchor": [x, y], "text": "$A$"} | null}},
     "overlaps": [["<id>", "<id>"], …],
     "diagnostics": [{"code": …, "elementId": …, …}]}

    px = ox + u·x,  py = oy − u·y
"""
from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass

from .document import as_document
from .kernel.numeric import default_bounds

__all__ = [
    'APPEARANCE_STYLE_KEYS',
    'LABEL_MODES',
    'REPORT_FORMAT',
    'RENDER_FORMATS',
    'RenderResult',
    'appearance_plan',
    'build_report',
    'label_overlaps',
    'render',
    'source_view',
]

REPORT_FORMAT = 'animageo-render-report/v1'
RENDER_FORMATS = ('svg', 'png', 'pdf')
LAYOUT_KEYS = ('reference', 'content', 'export')
SOURCE_WIDTH = 800.0
OVERLAP_SHARE = 0.15

# appearance.label.mode → classic label_mode ('none' hides the label)
LABEL_MODES = {
    'none': None,
    'name': 'label',
    'value': 'value',
    'name_value': 'label_value',
    'caption': 'label',
}

# Element style keys appearance.overrides may set (the ``elem.style`` keys of
# the style schema: the animatable keys of ``animageo/style/animatable.py``
# plus the static ones). Other keys are reported, not applied.
APPEARANCE_STYLE_KEYS = frozenset({
    # stroke and fill
    'stroke', 'stroke_width_px', 'stroke_opacity', 'stroke_dash_ratio', 'stroke_dash_period_px',
    'stroke_linecap', 'fill', 'fill_opacity',
    # points
    'size_px', 'point_shape',
    # labels
    'label_color', 'label_anchor', 'label_radial_offset_px', 'font_size_px',
    'label_value_precision', 'label_value_strip_zeros', 'label_value_separator', 'label_angle_unit',
    # ticks and arrows
    'tick_count', 'tick_style', 'tick_length_px', 'tick_width_px', 'tick_shift_px', 'tick_radius_px',
    'arrow_length_px', 'arrow_width_px',
    # angles
    'angle_range', 'arc_size_px', 'arc_shift_px', 'right_angle_size_px', 'right_angle_marker',
    'right_angle_joint', 'auto_radius',
    # layers
    'z_index', 'z_index_fill',
})


def source_view(doc) -> dict:
    """``{ptWidth, ptHeight, ptUnit, ptXZero, ptYZero}`` of ``viewDefaults.bounds``."""
    doc = as_document(doc)
    xmin, ymin, xmax, ymax = (float(v) for v in (doc.bounds or default_bounds()))
    unit = SOURCE_WIDTH / (xmax - xmin)
    return {
        'ptWidth': SOURCE_WIDTH,
        'ptHeight': (ymax - ymin) * unit,
        'ptUnit': unit,
        'ptXZero': -xmin * unit,
        'ptYZero': ymax * unit,
    }


def _finite_pair(value) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in value))


def appearance_plan(doc, unit: float) -> tuple:
    """``({elementId: {"visible": bool, "style": {key: value}}}, diagnostics)``.

    Every element gets an entry. ``label.mode`` defaults to ``name`` for a
    point and ``none`` otherwise (as the web canvas); a name label needs a
    ``displayName``. ``offsetWorld`` (world units) becomes ``label_offset_px``
    at the source ``unit`` (y up) and locks the label against automatic
    placement. ``overrides`` set :data:`APPEARANCE_STYLE_KEYS` only.
    """
    doc = as_document(doc)
    appearance = doc.data.get('appearance')
    appearance = appearance if isinstance(appearance, dict) else {}
    diagnostics = []
    for el_id in sorted(appearance):
        if el_id not in doc.elements:
            diagnostics.append({'code': 'unknown_element', 'elementId': el_id})
    plan = {}
    for el_id in sorted(doc.elements):
        el = doc.elements[el_id]
        entry = appearance.get(el_id)
        entry = entry if isinstance(entry, dict) else {}
        style = {}
        visible = entry.get('visible')
        name = el.get('displayName')
        if isinstance(name, str) and name:
            style['display_name'] = name
        label = entry.get('label')
        label = label if isinstance(label, dict) else {}
        mode = label.get('mode', 'name' if el.get('type') == 'point' else 'none')
        if mode not in LABEL_MODES:
            diagnostics.append({'code': 'bad_label_mode', 'elementId': el_id, 'mode': mode})
            mode = 'none'
        text = label.get('text')
        shown = LABEL_MODES[mode] is not None
        if mode == 'caption':
            if isinstance(text, str) and text:
                style['label_text'] = text
            elif 'display_name' not in style:
                shown = False
        elif mode in ('name', 'name_value') and 'display_name' not in style:
            shown = False
        style['label_visible'] = shown
        if shown:
            style['label_mode'] = LABEL_MODES[mode]
        offset = label.get('offsetWorld')
        if offset is not None:
            if _finite_pair(offset):
                style['label_offset_px'] = [float(offset[0]) * unit, float(offset[1]) * unit]
                style['label_placement_locked'] = True
            else:
                diagnostics.append({'code': 'bad_label_offset', 'elementId': el_id})
        overrides = entry.get('overrides')
        if isinstance(overrides, dict):
            for key in sorted(overrides):
                if key in APPEARANCE_STYLE_KEYS:
                    style[key] = overrides[key]
                else:
                    diagnostics.append({'code': 'unknown_style_key', 'elementId': el_id, 'key': key})
        plan[el_id] = {'visible': visible if isinstance(visible, bool) else True, 'style': style}
    return plan, diagnostics


@dataclass(frozen=True)
class RenderResult:
    """``path`` of the written file, its ``fmt`` and the ``report`` (a dict or ``None``)."""

    path: str
    fmt: str
    report: dict | None


def _check_layout(export_layout) -> dict:
    if export_layout is None:
        return {}
    if not isinstance(export_layout, dict):
        raise ValueError('export_layout must be a mapping with reference, content and export')
    unknown = sorted(set(export_layout) - set(LAYOUT_KEYS))
    if unknown:
        raise ValueError(f'export_layout: unknown keys {unknown}; allowed: {list(LAYOUT_KEYS)}')
    return export_layout


def render(doc, *, style_config=None, export_layout=None, fmt='svg', out=None,
           inputs=None, t=None, timeline=None, report=True) -> RenderResult:
    """Render ``doc`` to ``out`` (a temporary file when ``None``).

    ``style_config``: a style dict (already through the web's
    ``migrate_style_config`` and ``style_config_for_animageo``), a style
    file path, a packaged preset name or ``None`` (built-in);
    ``styleBinding`` of the document is not read. ``export_layout``: the
    placement keyword arguments of ``loadGGB`` — ``{reference?, content?,
    export?}``. ``fmt``: ``svg``, ``png`` (SVG rasterised by cairosvg) or
    ``pdf`` (96 dpi). ``t`` and ``timeline`` are not supported yet.
    """
    if fmt not in RENDER_FORMATS:
        raise NotImplementedError(f'format {fmt!r}: native.render writes {", ".join(RENDER_FORMATS)}')
    if t is not None or timeline is not None:
        raise NotImplementedError('native.render: t and timeline are not supported yet')
    layout = _check_layout(export_layout)
    doc = as_document(doc)
    from .kernel.evaluate import check_inputs
    check_inputs(doc, inputs)
    try:
        from ..animageo import AnimaGeoScene
    except ModuleNotFoundError as exc:
        if exc.name == 'manim' or (exc.name or '').startswith('manim.'):
            raise RuntimeError('native.render needs manim (pip install animageo[render] '
                               'or a manim environment)') from None
        raise

    if out is None:
        fd, out = tempfile.mkstemp(prefix='animageo_', suffix='.' + fmt)
        os.close(fd)
    out = os.path.abspath(os.fspath(out))

    scene = AnimaGeoScene()
    scene.loadDocument(doc, style=style_config, inputs=inputs,
                       reference=layout.get('reference'), content=layout.get('content'),
                       export=layout.get('export'))
    if fmt == 'svg':
        scene.exportSVG(out)
    elif fmt == 'pdf':
        scene.exportPDF(out)
    else:
        try:
            import cairosvg
        except (ImportError, OSError) as exc:
            raise RuntimeError(f'png needs cairosvg: {exc}') from None
        fd, svg_path = tempfile.mkstemp(prefix='animageo_', suffix='.svg')
        os.close(fd)
        try:
            scene.exportSVG(svg_path)
            cairosvg.svg2png(url=svg_path, write_to=out)
        finally:
            os.unlink(svg_path)
    body = build_report(scene, doc, fmt=fmt, inputs=inputs) if report else None
    return RenderResult(path=out, fmt=fmt, report=body)


# ── report ───────────────────────────────────────────────────────────────

def _round(v: float) -> float:
    return round(float(v), 3) + 0.0


def _px_box(box, export) -> list:
    x0, y0, x1, y1 = box
    u, ox, oy = float(export['ptUnit']), float(export['ptXZero']), float(export['ptYZero'])
    return [_round(ox + u * x0), _round(oy - u * y1), _round(ox + u * x1), _round(oy - u * y0)]


def _leaf_boxes(mobj, *, labels: bool):
    """Bounding box (scene units) of the leaves of ``mobj`` inside (``labels``)
    or outside a label; a label's leader line is not part of it."""
    xs, ys = [], []

    def visit(node, inside):
        inside = inside or bool(getattr(node, '_animageo_is_label', False))
        subs = getattr(node, 'submobjects', None) or ()
        if subs:
            for sub in subs:
                visit(sub, inside)
            return
        if inside != labels or (labels and type(node).__name__ == 'Line'):
            return
        points = getattr(node, 'points', None)
        if points is None or len(points) == 0:
            return
        xs.extend((float(node.get_left()[0]), float(node.get_right()[0])))
        ys.extend((float(node.get_bottom()[1]), float(node.get_top()[1])))

    visit(mobj, False)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _label_node(mobj):
    stack = [mobj]
    while stack:
        node = stack.pop()
        if getattr(node, '_animageo_is_label', False):
            return node
        stack.extend(reversed(getattr(node, 'submobjects', None) or ()))
    return None


def label_overlaps(boxes: dict, share: float = OVERLAP_SHARE) -> list:
    """Pairs of label boxes ``[x0, y0, x1, y1]`` whose intersection is at
    least ``share`` of the smaller one's area, sorted by ID."""
    ids = sorted(boxes)
    pairs = []
    for i, a in enumerate(ids):
        ax0, ay0, ax1, ay1 = boxes[a]
        area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
        for b in ids[i + 1:]:
            bx0, by0, bx1, by1 = boxes[b]
            area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
            smaller = min(area_a, area_b)
            if smaller <= 0:
                continue
            dx = min(ax1, bx1) - max(ax0, bx0)
            dy = min(ay1, by1) - max(ay0, by0)
            if dx > 0 and dy > 0 and dx * dy >= share * smaller:
                pairs.append([a, b])
    return pairs


def build_report(scene, doc, *, fmt: str, inputs=None) -> dict:
    """The ``animageo-render-report/v1`` of a scene loaded by ``loadDocument``."""
    from .. import __version__
    from .kernel.evaluate import evaluate
    from .registry import REGISTRY_VERSION

    doc = as_document(doc)
    export = scene.style.export
    names = scene.native_names
    states = evaluate(doc, inputs=inputs).elements
    by_name = {getattr(m, 'name', None): m for m in scene.mobjects}
    elements = {}
    label_boxes = {}
    for el_id in sorted(doc.elements):
        name = names.by_id[el_id]
        elem = scene.geo.element(name)
        mobj = by_name.get(name)
        record = {'state': states[el_id]['state'], 'visible': mobj is not None, 'box': None, 'label': None}
        if mobj is not None:
            box = _leaf_boxes(mobj, labels=False)
            record['box'] = _px_box(box, export) if box is not None else None
            node = _label_node(mobj)
            label_box = _leaf_boxes(mobj, labels=True) if node is not None else None
            if label_box is not None:
                ax, ay = getattr(node, '_animageo_label_anchor', (None, None))
                anchor = None
                if ax is not None:
                    px = _px_box((ax, ay, ax, ay), export)
                    anchor = [px[0], px[1]]
                from ..labels import resolve_label_text
                record['label'] = {'box': _px_box(label_box, export), 'anchor': anchor,
                                   'text': resolve_label_text(scene, elem)}
                label_boxes[el_id] = record['label']['box']
        elements[el_id] = record
    return {
        'format': REPORT_FORMAT,
        'documentId': doc.document_id,
        'kernel': {'library': __version__, 'registry': REGISTRY_VERSION},
        'fmt': fmt,
        'canvas': {'width': int(export['ptWidth']), 'height': int(export['ptHeight']),
                   'unit': float(export['ptUnit']),
                   'origin': [float(export['ptXZero']), float(export['ptYZero'])]},
        'elements': elements,
        'overlaps': label_overlaps(label_boxes),
        'diagnostics': list(getattr(scene, 'native_diagnostics', [])),
    }
