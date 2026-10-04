"""The ``metrics`` label measurer against manim's ``Tex`` on a seeded corpus
(spec §9.3: p95 error of width and height ≤ 5 %). Needs manim and LaTeX."""
import pytest

pytest.importorskip('manim')
pytestmark = [pytest.mark.manim, pytest.mark.slow]

from animageo.labels import correctedLabel  # noqa: E402
from animageo.native.labels import tex  # noqa: E402
from tests.native.label_corpus import corpus  # noqa: E402

FONT_SIZE = 48.0
BATCH = 100


def _tex_dims(texts):
    """``(width, height)`` of each text set by manim: one LaTeX run per batch,
    a part per line (the same boxes as one ``Tex`` per text)."""
    from manim import Tex

    from animageo.ui import RusTex
    out = []
    for i in range(0, len(texts), BATCH):
        parts = texts[i:i + BATCH]
        mob = Tex(*parts, tex_template=RusTex, arg_separator=r'\\ ').set(font_size=FONT_SIZE)
        assert len(mob.submobjects) == len(parts)
        out.extend((float(p.width), float(p.height)) for p in mob.submobjects)
    return out


def _p95(values):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))]


def test_metrics_match_tex_on_the_corpus():
    labels = corpus()
    assert len(labels) == 2000 and corpus() == labels          # seeded
    texts = [correctedLabel(text) for text in labels]
    reference = _tex_dims(texts)
    width_err, height_err = [], []
    for text, (w, h) in zip(texts, reference):
        mw, mh = tex.measure(text, FONT_SIZE)                  # the corpus is inside the subset
        width_err.append(abs(mw - w) / w)
        height_err.append(abs(mh - h) / h)
    assert _p95(width_err) <= 0.05, _p95(width_err)
    assert _p95(height_err) <= 0.05, _p95(height_err)
    # in practice the set is exact: the boxes of the same glyph outlines
    assert max(width_err) < 0.01 and max(height_err) < 0.01, (max(width_err), max(height_err))
