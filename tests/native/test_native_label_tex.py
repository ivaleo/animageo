"""The ``metrics`` label measurer without manim (``native/labels/tex.py``);
its agreement with manim's ``Tex`` is ``test_label_metrics_corpus.py``."""
import json

import pytest

from animageo.native.labels import tex


def test_metrics_file():
    data = tex.metrics()
    assert data['format'] == 'animageo-label-metrics/v1'
    assert data['template'].startswith('sha256:')
    for font in ('cmmi10', 'cmr10', 'cmsy10'):
        assert font in data['fonts']
    with open(tex.METRICS_PATH, encoding='utf-8') as fh:
        assert json.load(fh)['format'] == data['format']


def test_measure_scales_with_the_font_size():
    w, h = tex.measure('$A$', 48.0)
    assert w > 0 and h > 0
    w2, h2 = tex.measure('$A$', 24.0)
    assert (w2, h2) == pytest.approx((w / 2, h / 2))


@pytest.mark.parametrize('longer, shorter', [
    ('$A_1$', '$A$'),
    ("$A'$", '$A$'),
    ('$AB$', '$A$'),
    ('$A = 1$', '$A$'),
    ('Центр', 'Цен'),
])
def test_more_material_is_wider(longer, shorter):
    assert tex.measure(longer, 48.0)[0] > tex.measure(shorter, 48.0)[0]


def test_math_spacing_follows_tex():
    # a relation gets thick spaces on both sides, an ordinary pair none
    rel = tex.measure('$a=b$', 48.0)[0]
    ords = tex.measure('$ab$', 48.0)[0] + tex.measure('$=$', 48.0)[0]
    assert rel > ords


def test_deterministic():
    texts = ['$A_1$', r'$\alpha = 30^{\circ}$', r'$\triangle ABC$', 'точка $M$']
    assert [tex.measure(t, 20.0) for t in texts] == [tex.measure(t, 20.0) for t in texts]


@pytest.mark.parametrize('text', [r'$\frac{a}{b}$', r'$\sqrt{2}$', r'$\hat{a}$', r'$\unknowncommand$'])
def test_outside_the_subset(text):
    with pytest.raises(tex.Unsupported):
        tex.measure(text, 20.0)
