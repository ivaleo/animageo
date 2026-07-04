"""In-process renderer for interactive guide examples.

Wraps AnimaGeoScene + exportSVG into a single `render_example(spec)` call
that returns SVG text. Reuses the canonical example schema from the static
generator (generate_svg.py) so there's one source of truth for how an
example dict translates to a picture.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'docs/guide/examples'))

logging.getLogger().setLevel(logging.ERROR)
for noisy in ['manim', 'animageo', 'animageo.parsers.ggb_parser']:
    logging.getLogger(noisy).setLevel(logging.ERROR)

from manim import config  # noqa: E402
config.verbosity = "ERROR"

from animageo.animageo import AnimaGeoScene  # noqa: E402
from generate_svg import STYLE as DEFAULT_STYLE  # noqa: E402
try:
    from generate_svg import _align_tick_width  # noqa: E402
except ImportError:
    def _align_tick_width(scene, style):
        return None

# Manim / AnimaGeoScene hold global state (config.pixel_width, TeX cache,
# etc.); two concurrent renders would clobber each other. A single lock is
# the simplest correct serialization.
_render_lock = threading.Lock()


@dataclass
class ExampleSpec:
    """Full render spec. The `code` field is what the user edits; everything
    else comes from the guide's static example registry and travels with
    the request as `template`."""
    code: str
    w: int = 520
    h: int = 340
    scale: int = 46
    labels: list[str] = field(default_factory=list)
    tex_labels: dict[str, str] = field(default_factory=dict)
    hide: list[str] = field(default_factory=list)
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    rendering_extra: dict[str, Any] = field(default_factory=dict)
    overlay_extra: dict[str, Any] = field(default_factory=dict)
    auto_place: bool = True
    style: str = DEFAULT_STYLE


def render_example(spec: ExampleSpec) -> str:
    """Build a scene from the spec, export SVG, return SVG text."""
    with _render_lock:
        scene = AnimaGeoScene()
        scene.style.export['ptUnit'] = spec.scale
        scene.style.export['ptWidth'] = spec.w
        scene.style.export['ptHeight'] = spec.h
        scene.style.export['ptXZero'] = spec.w / 2
        scene.style.export['ptYZero'] = spec.h / 2
        scene.applyStyle(style=spec.style, export={"size": {"width": spec.w, "height": spec.h}})

        if spec.rendering_extra:
            scene.style.rendering.update(spec.rendering_extra)
        if 'angle_radius' in spec.overlay_extra:
            scene.style_config.overlay.angle_radius.update(spec.overlay_extra['angle_radius'])
        if 'label_placement' in spec.overlay_extra:
            scene.style_config.overlay.label_placement.update(spec.overlay_extra['label_placement'])
        if 'per_type' in spec.overlay_extra:
            scene.style_config.overlay.per_type.update(spec.overlay_extra['per_type'])
        if 'per_name' in spec.overlay_extra:
            scene.style_config.overlay.per_name.update(spec.overlay_extra['per_name'])

        scene.putCode(spec.code)
        _align_tick_width(scene, spec.style)

        for n in spec.hide:
            el = scene.element(n)
            if el:
                el.visible = False

        for n in spec.labels:
            el = scene.element(n)
            if el:
                el.style['label_visible'] = True

        for n, tex in spec.tex_labels.items():
            el = scene.element(n)
            if el:
                el.style['label_visible'] = True
                el.style['label_text'] = tex

        for n, props in spec.overrides.items():
            el = scene.element(n)
            if el:
                for k, v in props.items():
                    el.style[k] = v

        scene.addAllGeometry(show=True)
        scene.updateAllGeometry()

        if spec.auto_place:
            try:
                scene.autoPlaceLabels()
            except Exception:
                pass

        f = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
        f.close()
        try:
            scene.exportSVG(f.name)
            with open(f.name, encoding='utf-8') as fp:
                return fp.read()
        finally:
            os.unlink(f.name)
