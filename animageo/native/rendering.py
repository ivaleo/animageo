"""Render a document to SVG, PNG, PDF, EPS or TikZ (``native.render``) and its report.

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
     "pointOverlaps": [["<labelId>", "<pointId>"], …],
     "diagnostics": [{"code": …, "elementId": …, …}]}

    px = ox + u·x,  py = oy − u·y

1.9.0a1: ``elements.<id>.role`` — the role of ``appearance`` (given, aux,
sought) when the element has one; a ``locus`` reports the box of its
defined samples.

An equality mark (``mark.equal_segments``, ``mark.equal_angles``) has no
drawing of its own: its ``box`` is the union of the boxes of its drawn
targets (``null`` when none is drawn, the mark is hidden or undefined), its
``label`` is ``null``. A right-angle mark is drawn as an angle with the
right-angle marker and reports its own box.

``overlaps``: pairs of label boxes whose intersection is at least 15 % of
the smaller one; ``pointOverlaps`` (1.8.1a2): a label box entering the
marker of a drawn point (its own point included) — the circle inscribed in
the point's ``box``.
"""
from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass

from .document import ROLES, as_document
from .kernel.numeric import default_bounds

__all__ = [
    'APPEARANCE_STYLE_KEYS',
    'LABEL_MODES',
    'REPORT_FORMAT',
    'RENDER_FORMATS',
    'STATIC_FORMATS',
    'VIDEO_FORMATS',
    'RenderResult',
    'document_at',
    'appearance_plan',
    'apply_appearance',
    'role_style',
    'build_report',
    'label_overlaps',
    'label_point_overlaps',
    'mark_targets',
    'render',
    'source_view',
]

REPORT_FORMAT = 'animageo-render-report/v1'
STATIC_FORMATS = ('svg', 'png', 'pdf', 'eps', 'tikz', 'tex')
VIDEO_FORMATS = ('mp4', 'gif', 'webm', 'mov')
RENDER_FORMATS = STATIC_FORMATS + VIDEO_FORMATS
# video={quality}: the scale of the pixel size of the canvas (1.9.0a4)
VIDEO_QUALITY = {'low': 0.5, 'medium': 1.0, 'high': 1.5, 'production': 2.0}
VIDEO_DEFAULTS = {'fps': 30, 'quality': 'medium'}
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


EQUALITY_MARKS = ('mark.equal_segments', 'mark.equal_angles')


def mark_targets(doc) -> dict:
    """``{markId: [targetId, …]}`` of the elements bound to an equality mark
    (``mark.equal_segments``, ``mark.equal_angles``): the elements of its list
    argument in order (a right-angle mark draws itself and is not listed)."""
    from .document import bound_producer, iter_refs
    doc = as_document(doc)
    out = {}
    for el_id in sorted(doc.elements):
        if doc.elements[el_id].get('type') != 'mark':
            continue
        producer = bound_producer(doc, el_id)
        op = doc.operations.get(producer) if producer is not None else None
        if op is None or op.get('op') not in EQUALITY_MARKS:
            continue
        out[el_id] = [r for arg in op.get('args', {}).values() if isinstance(arg, dict) and arg.get('kind') == 'list'
                      for r in iter_refs(arg) if r in doc.elements]
    return out


def role_style(roles, role: str, type_: str) -> dict:
    """The style keys of ``role`` for an element of ``type_`` from a style's
    ``roles`` section (``{}`` when the section or the role is absent): the
    ``point`` keys for a point, the other keys for any other element."""
    entry = roles.get(role) if isinstance(roles, dict) else None
    if not isinstance(entry, dict):
        return {}
    if type_ == 'point':
        keys = entry.get('point')
        return dict(keys) if isinstance(keys, dict) else {}
    return {k: v for k, v in entry.items() if k != 'point' and not k.startswith('_')}


def appearance_plan(doc, unit: float, *, inputs=None, evaluated=None, roles=None) -> tuple:
    """``({elementId: {"visible": bool, "style": {key: value}}}, diagnostics)``.

    Every element gets an entry. ``label.mode`` defaults to ``name`` for a
    point and ``none`` otherwise (as the web canvas); a name label needs a
    ``displayName``. ``offsetWorld`` (world units) becomes ``label_offset_px``
    at the source ``unit`` (y up) and locks the label against automatic
    placement. ``overrides`` set :data:`APPEARANCE_STYLE_KEYS` only.

    Roles (1.9.0a1): ``role`` (given, aux, sought) puts the keys of
    ``roles[role]`` (the style's ``roles`` section, :func:`role_style`)
    under the ``overrides``; token references stay for the resolver. An
    unknown role or no ``roles`` leaves the element as it is.

    Marks (registry 1.3): a visible, defined equality mark sets
    ``tick_count = count`` on its targets (:func:`mark_targets`) — an
    explicit ``overrides.tick_count`` of a target wins, and of several marks
    on one target the first in ID order wins; a visible, defined right-angle
    mark gets ``right_angle_marker = True`` unless overridden. Definedness
    comes from ``evaluated`` (an ``Evaluated``) or a fresh ``evaluate`` with
    ``inputs``.
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
        role = entry.get('role')
        if isinstance(role, str):
            for key, value in sorted(role_style(roles, role, el.get('type')).items()):
                if key in APPEARANCE_STYLE_KEYS:
                    style[key] = value
                else:
                    diagnostics.append({'code': 'unknown_style_key', 'elementId': el_id, 'key': key,
                                        'role': role})
        overrides = entry.get('overrides')
        if isinstance(overrides, dict):
            for key in sorted(overrides):
                if key in APPEARANCE_STYLE_KEYS:
                    style[key] = overrides[key]
                else:
                    diagnostics.append({'code': 'unknown_style_key', 'elementId': el_id, 'key': key})
        plan[el_id] = {'visible': visible if isinstance(visible, bool) else True, 'style': style}
    marks = sorted(el_id for el_id, el in doc.elements.items() if el.get('type') == 'mark')
    if marks:
        if evaluated is None:
            from .kernel.evaluate import evaluate
            evaluated = evaluate(doc, inputs=inputs)
        targets = mark_targets(doc)
        for mark_id in marks:
            record = evaluated.elements.get(mark_id, {})
            if record.get('state') != 'defined' or not plan[mark_id]['visible']:
                continue
            kind, count = record['value']['kind'], record['value']['count']
            if kind == 'right_angle':
                plan[mark_id]['style'].setdefault('right_angle_marker', True)
                continue
            for target in targets.get(mark_id, ()):
                plan[target]['style'].setdefault('tick_count', count)
    return plan, diagnostics


def apply_appearance(construction, names, plan) -> None:
    """Write an :func:`appearance_plan` into the classic elements of the
    bridge (``AnimaGeoScene.loadDocument`` and ``layout_labels``).

    Visibility (of drawn elements, not of a classic ``Var``) and the style
    keys of each entry. An element the renderer does not draw (no value, an
    equality mark, a number, a free number's ``Var``; ``geo.is_drawn``) gets
    ``label_visible = False``: automatic placement would otherwise see a
    label that is never drawn.
    """
    from ..geo import construction as geo
    for el_id, entry in plan.items():
        elem = construction.objectByName(names.by_id[el_id])
        if isinstance(elem, geo.Element):
            elem.visible = entry['visible']
        for key, value in entry['style'].items():
            elem.style[key] = value
        if not isinstance(elem, geo.Element) or not geo.is_drawn(elem.data):
            elem.style['label_visible'] = False


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


def document_at(doc, sample: dict):
    """A copy of ``doc`` whose ``appearance.<id>.visible`` is ``sample["visible"]``
    where it differs from the document (``sample_timeline``)."""
    from .document import load
    from .timeline import appearance_visible
    doc = as_document(doc)
    data = None
    for el_id, flag in sorted(sample['visible'].items()):
        if appearance_visible(doc, el_id) == flag:
            continue
        if data is None:
            import copy
            data = copy.deepcopy(doc.data)
            if not isinstance(data.get('appearance'), dict):
                data['appearance'] = {}
        entry = data['appearance'].get(el_id)
        entry = dict(entry) if isinstance(entry, dict) else {}
        entry['visible'] = flag
        data['appearance'][el_id] = entry
    return doc if data is None else load(data)


def _check_video(video) -> dict:
    out = dict(VIDEO_DEFAULTS)
    if video is None:
        return out
    if not isinstance(video, dict):
        raise ValueError('video must be a mapping {fps, quality}')
    unknown = sorted(set(video) - set(VIDEO_DEFAULTS))
    if unknown:
        raise ValueError(f'video: unknown keys {unknown}; allowed: {sorted(VIDEO_DEFAULTS)}')
    out.update(video)
    fps = out['fps']
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not 1 <= fps <= 120:
        raise ValueError(f'video.fps must be a number in [1, 120], got {fps!r}')
    if out['quality'] not in VIDEO_QUALITY:
        raise ValueError(f'video.quality must be one of {list(VIDEO_QUALITY)}, got {out["quality"]!r}')
    return out


def _import_scene():
    try:
        from ..animageo import AnimaGeoScene
    except ModuleNotFoundError as exc:
        if exc.name == 'manim' or (exc.name or '').startswith('manim.'):
            raise RuntimeError('native.render needs manim (pip install animageo[render] '
                               'or a manim environment)') from None
        raise
    return AnimaGeoScene


def render(doc, *, style_config=None, export_layout=None, fmt='svg', out=None,
           inputs=None, t=None, timeline=None, report=True, video=None) -> RenderResult:
    """Render ``doc`` to ``out`` (a temporary file when ``None``).

    ``style_config``: a style dict (already through the web's
    ``migrate_style_config`` and ``style_config_for_animageo``), a style
    file path, a packaged preset name or ``None`` (built-in);
    ``styleBinding`` of the document is not read. ``export_layout``: the
    placement keyword arguments of ``loadGGB`` — ``{reference?, content?,
    export?}``. ``fmt``: ``svg``, ``png`` (SVG rasterised by cairosvg),
    ``pdf`` (96 dpi), ``eps`` (``exportEPS``), ``tikz`` (a ``tikzpicture``
    to include, ``exportTikZ(standalone=False)``) or ``tex`` (a compilable
    standalone document).

    1.9.0a4 (docs/native/timeline.md §3): ``t`` with ``timeline`` (keyframes
    by element ID) renders the frame at time ``t``: the document with the
    inputs and the visibility of ``sample_timeline`` (``inputs`` on top);
    the report gains ``t`` and ``visible``, boxes are those of the drawn
    elements. ``fmt`` ``mp4``, ``gif``, ``webm``, ``mov``: the video of
    ``timeline`` (required: ``ValueError("timeline_required")``) played by
    the classic ``play_keyframes`` on the scene of the bridge
    (``timeline_to_bridge``), manim + ffmpeg; ``video={fps, quality}``
    (``fps`` 30, ``quality`` ``low`` | ``medium`` | ``high`` |
    ``production`` — 0.5, 1, 1.5, 2 times the canvas in pixels); the
    report of a video is short: ``video`` ``{fps, quality, width, height,
    duration}``, and ``t``/``visible`` of the last keyframe.
    """
    if fmt not in RENDER_FORMATS:
        raise NotImplementedError(f'format {fmt!r}: native.render writes {", ".join(RENDER_FORMATS)}')
    layout = _check_layout(export_layout)
    doc = as_document(doc)
    from .kernel.evaluate import check_inputs
    check_inputs(doc, inputs)
    if fmt in VIDEO_FORMATS:
        if timeline is None:
            raise ValueError('timeline_required')
        return _render_video(doc, style_config, layout, fmt, out, inputs, timeline, report, _check_video(video))
    if video is not None:
        raise ValueError('video applies to mp4, gif, webm and mov only')
    sample = None
    if t is not None or timeline is not None:
        if t is None or timeline is None:
            raise ValueError('native.render: t and timeline go together')
        from .timeline import sample_timeline
        sample = sample_timeline(doc, timeline, t)
        merged = dict(sample['inputs'])
        merged.update(inputs or {})
        inputs = merged
        doc = document_at(doc, sample)
    AnimaGeoScene = _import_scene()

    if out is None:
        fd, out = tempfile.mkstemp(prefix='animageo_', suffix='.' + ('tex' if fmt == 'tikz' else fmt))
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
    elif fmt == 'eps':
        scene.exportEPS(out)
    elif fmt in ('tikz', 'tex'):
        scene.exportTikZ(out, standalone=(fmt == 'tex'))
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
    if body is not None and sample is not None:
        body['t'] = sample['t']
        body['visible'] = sample['visible']
    return RenderResult(path=out, fmt=fmt, report=body)


def _even(v: float) -> int:
    return max(2, int(round(v / 2.0)) * 2)


def _render_video(doc, style_config, layout, fmt, out, inputs, timeline, report, video) -> RenderResult:
    """The video of ``timeline`` (``render`` with a video ``fmt``)."""
    import glob
    import shutil
    from .timeline import normalize_timeline, sample_timeline, timeline_to_bridge
    bridge = timeline_to_bridge(doc, timeline)
    if len(bridge['keyframes']) < 2:
        raise ValueError('timeline: a video needs at least two keyframes')
    end = normalize_timeline(doc, timeline)['keyframes'][-1]['t']
    AnimaGeoScene = _import_scene()
    from manim import tempconfig
    from ..render_config import configure_render

    if out is None:
        fd, out = tempfile.mkstemp(prefix='animageo_', suffix='.' + fmt)
        os.close(fd)
    out = os.path.abspath(os.fspath(out))
    export = (layout.get('export') or {}) if isinstance(layout.get('export'), dict) else {}
    view = source_view(doc)
    scale = VIDEO_QUALITY[video['quality']]
    width = _even(float(export.get('ptWidth', view['ptWidth'])) * scale)
    height = _even(float(export.get('ptHeight', view['ptHeight'])) * scale)
    holder = {}

    class NativeTimelineScene(AnimaGeoScene):
        def construct(self):
            self.loadDocument(doc, style=style_config, inputs=inputs,
                              reference=layout.get('reference'), content=layout.get('content'),
                              export=layout.get('export'))
            self.play_keyframes(bridge)
            holder['scene'] = self

    with tempfile.TemporaryDirectory(prefix='animageo_video_') as media:
        with tempconfig({'media_dir': media, 'pixel_width': width, 'pixel_height': height,
                         'frame_rate': float(video['fps']), 'output_file': 'native_timeline',
                         'disable_caching': True, 'verbosity': 'ERROR', 'progress_bar': 'none',
                         'write_to_movie': True}):
            configure_render(format=fmt, fps=video['fps'])
            NativeTimelineScene().render()
        found = [p for p in glob.glob(os.path.join(media, '**', '*.' + fmt), recursive=True)
                 if 'partial_movie_files' not in p]
        if not found:
            raise RuntimeError(f'native.render: manim wrote no {fmt} file')
        shutil.move(max(found, key=os.path.getmtime), out)
    body = None
    if report:
        sample = sample_timeline(doc, timeline, end)
        merged = dict(sample['inputs'])
        merged.update(inputs or {})
        from .. import __version__
        from .registry import REGISTRY_VERSION
        body = {'format': REPORT_FORMAT, 'documentId': doc.document_id,
                'kernel': {'library': __version__, 'registry': REGISTRY_VERSION}, 'fmt': fmt,
                'video': {'fps': video['fps'], 'quality': video['quality'], 'width': width, 'height': height,
                          'duration': end - normalize_timeline(doc, timeline)['keyframes'][0]['t']},
                't': sample['t'], 'visible': sample['visible']}
    return RenderResult(path=out, fmt=fmt, report=body)


# ── report ───────────────────────────────────────────────────────────────

def _round(v: float) -> float:
    return round(float(v), 3) + 0.0


def _px_box(box, export) -> list:
    x0, y0, x1, y1 = box
    u, ox, oy = float(export['ptUnit']), float(export['ptXZero']), float(export['ptYZero'])
    return [_round(ox + u * x0), _round(oy - u * y1), _round(ox + u * x1), _round(oy - u * y0)]


def _leaf_boxes(mobj, *, labels: bool):
    """Bounding box (scene units) of the points of ``mobj`` inside (``labels``)
    or outside a label; a label's leader line is not part of it. A node's own
    points outside a label count as well as its children's (an arrow's shaft
    carries its tip); inside a label only the leaves count."""
    xs, ys = [], []

    def add(points):
        xs.extend(float(v) for v in points[:, 0])
        ys.extend(float(v) for v in points[:, 1])

    def visit(node, inside):
        inside = inside or bool(getattr(node, '_animageo_is_label', False))
        subs = getattr(node, 'submobjects', None) or ()
        points = getattr(node, 'points', None)
        has_points = points is not None and len(points) > 0
        if subs:
            for sub in subs:
                visit(sub, inside)
            if has_points and not labels and not inside:
                add(points)
            return
        if inside != labels or (labels and type(node).__name__ == 'Line') or not has_points:
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
    ids = sorted(boxes, key=lambda k: (boxes[k][0], k))       # sweep along x
    pairs = []
    for i, a in enumerate(ids):
        ax0, ay0, ax1, ay1 = boxes[a]
        area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
        for b in ids[i + 1:]:
            bx0, by0, bx1, by1 = boxes[b]
            if bx0 >= ax1:
                break
            area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
            smaller = min(area_a, area_b)
            if smaller <= 0:
                continue
            dx = min(ax1, bx1) - max(ax0, bx0)
            dy = min(ay1, by1) - max(ay0, by0)
            if dx > 0 and dy > 0 and dx * dy >= share * smaller:
                pairs.append(sorted((a, b)))
    return sorted(pairs)


def label_point_overlaps(label_boxes: dict, points: dict) -> list:
    """Pairs ``[labelId, pointId]`` of a label box ``[x0, y0, x1, y1]`` that
    enters the marker of a drawn point (``{pointId: (cx, cy, r)}``, the same
    pixels), the label's own point included; sorted by ID."""
    import bisect
    order = sorted(points, key=lambda k: (points[k][0], k))
    xs = [points[k][0] for k in order]
    reach = max((points[k][2] for k in order), default=0.0)
    pairs = []
    for label_id in sorted(label_boxes):
        x0, y0, x1, y1 = label_boxes[label_id]
        hits = []
        for j in range(bisect.bisect_left(xs, x0 - reach), bisect.bisect_right(xs, x1 + reach)):
            cx, cy, r = points[order[j]]
            dx = cx - min(max(cx, x0), x1)
            dy = cy - min(max(cy, y0), y1)
            if r > 0 and dx * dx + dy * dy < r * r:
                hits.append(order[j])
        pairs.extend([label_id, p] for p in sorted(hits))
    return pairs


def _locus_box(value):
    pts = [p for p in value['points'] if p is not None]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


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
    appearance = doc.data.get('appearance')
    appearance = appearance if isinstance(appearance, dict) else {}
    roles_of = {el_id: entry['role'] for el_id, entry in appearance.items()
                if isinstance(entry, dict) and entry.get('role') in ROLES}
    elements = {}
    label_boxes = {}
    markers = {}
    from ..geo import construction as geo
    for el_id in sorted(doc.elements):
        name = names.by_id[el_id]
        elem = scene.geo.element(name)
        mobj = by_name.get(name)
        record = {'state': states[el_id]['state'], 'visible': mobj is not None, 'box': None, 'label': None}
        role = roles_of.get(el_id)
        if role is not None:
            record['role'] = role
        if mobj is not None:
            box = _leaf_boxes(mobj, labels=False)
            if states[el_id]['state'] == 'defined' and states[el_id]['type'] == 'locus':
                box = _locus_box(states[el_id]['value'])
            record['box'] = _px_box(box, export) if box is not None else None
            if box is not None and isinstance(getattr(elem, 'data', None), geo.Point):
                x0, y0, x1, y1 = record['box']
                markers[el_id] = ((x0 + x1) / 2, (y0 + y1) / 2, min(x1 - x0, y1 - y0) / 2)
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
    for mark_id, targets in mark_targets(doc).items():
        record = elements[mark_id]
        elem = scene.geo.element(names.by_id[mark_id])
        shown = record['state'] == 'defined' and elem is not None and bool(getattr(elem, 'visible', True))
        boxes = [elements[t]['box'] for t in targets if shown and elements[t]['box'] is not None]
        record['visible'] = bool(boxes)
        record['box'] = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                         max(b[2] for b in boxes), max(b[3] for b in boxes)] if boxes else None
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
        'pointOverlaps': label_point_overlaps(label_boxes, markers),
        'diagnostics': list(getattr(scene, 'native_diagnostics', [])),
    }
