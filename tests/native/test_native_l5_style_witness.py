"""Style witness of the import (plan L5 §8, stage 3; 1.10.0a2).

Ten files are drawn twice: by the classic ``loadGGB`` and by
``native.render`` of the document of ``from_ggb`` with ``ggb_style`` of the
report as ``appearance.overrides`` (what the web does with «Взять цвета из
GeoGebra»). The drawings are compared by features, not by pixels — the
canvas of the two differs (the applet window against ``viewDefaults``): each
``<path>`` of the SVG gives its stroke (colour, width in pixels of the
canvas, opacity) and its fill (colour, opacity), and the two multisets must
be equal. The objects that do not translate are hidden in the classic
drawing, the document has none of them. Needs manim and LaTeX; ``slow``.
"""
import re
import uuid
from collections import Counter

import pytest

pytest.importorskip('manim')
pytestmark = [pytest.mark.manim, pytest.mark.slow]

from animageo import native  # noqa: E402
from animageo.animageo import AnimaGeoScene  # noqa: E402 — not ``from animageo``: a ``.ggb`` in argv skips it
from tests.native.conftest import REPO_ROOT  # noqa: E402

NS = uuid.UUID('9d3c1e27-4b6a-4f08-8a5e-1c2b3d4e5f60')
FILES = ['docs/guide/assets/ggb/sample_triangle.ggb', 'examples/ai_style_generation_scene10/scene10.ggb',
         'tests/fixtures/label_anchor_types.ggb', 'tests/fixtures/label_offset_points.ggb',
         'tests/fixtures/text_dynamic.ggb', 'tests/fixtures/text_static.ggb',
         'tests/native/import/synthetic/style_labels.ggb', 'tests/native/import/synthetic/triangle_editable.ggb',
         'tests/native/import/synthetic/regular_polygon.ggb', 'tests/native/import/synthetic/dropped_effects.ggb']
_ATTR = re.compile(r'([a-z-]+)="([^"]*)"')
_SCALE = re.compile(r'matrix\(([-\d.e]+),')


def features(svg: str) -> Counter:
    """``Counter`` of ``('stroke', colour, width px, opacity, dashed)`` and
    ``('fill', colour, opacity)`` over the ``<path>`` of an SVG."""
    out = Counter()
    for tag in re.findall(r'<path\b[^>]*>', svg):
        a = dict(_ATTR.findall(tag))
        m = _SCALE.match(a.get('transform', ''))
        scale = abs(float(m.group(1))) if m else 1.0
        if a.get('stroke', 'none') != 'none':
            width = round(float(a.get('stroke-width', 1)) * scale, 1)
            out[('stroke', a['stroke'], width, a.get('stroke-opacity'), 'stroke-dasharray' in a)] += 1
        if a.get('fill', 'none') != 'none':
            out[('fill', a['fill'], a.get('fill-opacity'))] += 1
    return out


def classic_features(path, hide, tmp_path) -> Counter:
    scene = AnimaGeoScene()
    scene.loadGGB(str(path), generate_stubs=False)
    scene.setVisible([n for n in hide if scene.element(n) is not None], False)
    out = tmp_path / 'classic.svg'
    scene.exportSVG(str(out))
    return features(out.read_text(encoding='utf-8'))


def native_features(doc, report, tmp_path, *, with_style=True) -> Counter:
    looks = doc.setdefault('appearance', {})
    for e in report['elements']:
        if with_style and e.get('ggb_style') and e['category'] in ('editable', 'differs'):
            for nid in e['native_ids']:
                if nid in doc['elements']:
                    looks.setdefault(nid, {})['overrides'] = dict(e['ggb_style'])
    out = tmp_path / 'native.svg'
    native.render(doc, fmt='svg', out=str(out), report=False)
    return features(out.read_text(encoding='utf-8'))


def _imported(rel):
    doc, report = native.from_ggb(str(REPO_ROOT / rel), id_namespace=NS)
    hide = [e['ggb_name'] for e in report['elements'] if e['category'] not in ('editable', 'differs')]
    return doc, report, hide


@pytest.mark.parametrize('rel', FILES, ids=[f.rsplit('/', 1)[-1][:-4] for f in FILES])
def test_the_native_drawing_has_the_style_of_the_classic(rel, tmp_path):
    doc, report, hide = _imported(rel)
    classic = classic_features(REPO_ROOT / rel, hide, tmp_path)
    drawn = native_features(doc, report, tmp_path)
    assert len(classic) >= 3
    assert drawn - classic == Counter() and classic - drawn == Counter(), (
        f'native only {dict(drawn - classic)}, classic only {dict(classic - drawn)}')


def test_the_witness_sees_a_style_that_is_not_carried(tmp_path):
    """Without ``ggb_style`` the drawing has the colours of the style, not of
    the file — the comparison tells them apart."""
    rel = 'docs/guide/assets/ggb/sample_triangle.ggb'
    doc, report, hide = _imported(rel)
    classic = classic_features(REPO_ROOT / rel, hide, tmp_path)
    assert native_features(doc, report, tmp_path, with_style=False) != classic
