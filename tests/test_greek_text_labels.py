"""Greek letters in the text-mode part of a label or a free text.

``RusTex`` sets text in T2A, which has no Greek glyphs, and ``correctedLabel``
turns a Unicode letter into its TeX command (``γ`` → ``\\gamma``), which is
math-only. So a caption ``γ``, ``ω_1``, ``cos α`` or a bare ``\\alpha`` outside
``$…$`` did not compile at all: the label degraded to its plain-text fallback,
which fails the same way, and the element lost its label — and, because a
failed compile leaves nothing in manim's SVG cache, LaTeX ran again on every
render.

The fix typesets such a letter (with its index and primes) in math mode,
``$\\gamma$``, and leaves math segments, Cyrillic and escaped dollars as they
were; a body that fails to compile is remembered for the process.
"""
import re
import shutil

import pytest

from animageo.ui import correctedLabel, mathify_text_symbols

latex_required = pytest.mark.skipif(
    shutil.which('latex') is None, reason='requires a LaTeX toolchain',
)


# ── the TeX a label becomes (no LaTeX needed) ─────────────────────────

@pytest.mark.parametrize('label, tex', [
    ('γ', r'$\gamma$'),
    ('ω_1', r'$\omega_1$'),
    ('ω_{12}', r'$\omega_{12}$'),
    ('cos α', r'cos $\alpha$'),
    ('α + β', r'$\alpha$ + $\beta$'),
    ('αβ', r'$\alpha\beta$'),
    ("α'", r"$\alpha'$"),
    ('угол φ', r'угол $\varphi$'),
    ('Γ', r'$\Gamma$'),
    ('Ω_A', r'$\Omega_A$'),
    ('θ', r'$\theta$'),
    ('ϑ ϕ ϖ ϵ ϱ ς', r'$\theta$ $\phi$ $\varpi$ $\epsilon$ $\varrho$ $\varsigma$'),
    (r'\alpha', r'$\alpha$'),
    (r'\alpha_1 и \beta', r'$\alpha_1$ и $\beta$'),
    (r'угол \varphi', r'угол $\varphi$'),
    ('a × b', r'a $\times$ b'),
])
def test_text_mode_greek_goes_to_math(label, tex):
    assert correctedLabel(label) == tex


@pytest.mark.parametrize('label, tex', [
    ('$γ$', r'$\gamma$'),
    ('$ω_1$', r'$\omega_1$'),
    ('$\\alpha + β$', r'$\alpha + \beta$'),
    ('$$α$$', r'$$\alpha$$'),
    (r'\(α\)', r'\(\alpha\)'),
    ('$θ$', r'$\theta$'),
])
def test_math_segments_keep_their_tex(label, tex):
    assert correctedLabel(label) == tex


@pytest.mark.parametrize('label, tex', [
    ('A $x+γ$ γ', r'A $x+\gamma$ $\gamma$'),
    (r'цена \$5 γ', r'цена \$5 $\gamma$'),
    (r'\$γ\$', r'\$$\gamma$\$'),
    ('$AB$ и φ', r'$AB$ и $\varphi$'),
])
def test_mixed_math_and_escaped_dollars(label, tex):
    assert correctedLabel(label) == tex


@pytest.mark.parametrize('label', [
    'угол', 'Дано: AB = 5', 'A_1', r'\textbackslash{}alpha', r'\alphabet', r'\textbf{x}',
    'a~b', '30°', '', r'50\%',
])
def test_text_without_greek_is_untouched(label):
    assert correctedLabel(label) == label


def test_cyrillic_in_math_still_leaves_math():
    assert correctedLabel('$Б_1$ и γ') == r'$\text{Б}_1$ и $\gamma$'


def test_math_environment_is_math():
    body = r'\begin{align*} α \end{align*}'
    assert mathify_text_symbols(body) == body


def test_unclosed_dollar_leaves_the_rest_alone():
    assert mathify_text_symbols('γ $x γ') == r'$\gamma$ $x γ'


def test_plain_text_fallback_keeps_greek_compilable():
    from animageo.ui import _label_plain_text
    assert _label_plain_text('$\\frac{γ$') == r'\textbackslash{}frac\{$\gamma$'


# ── real LaTeX: the label appears ─────────────────────────────────────

LABELS = ['γ', 'ω_1', 'cos α', 'α + β', 'угол φ', r'\alpha', 'A $x_1$ и γ', r'цена \$5 γ']


@pytest.fixture
def isolated_tex(tmp_path, monkeypatch):
    from manim import tempconfig
    from animageo import _tex_failure_cache
    monkeypatch.setenv('TEXMFOUTPUT', str(tmp_path))
    _tex_failure_cache.clear()
    with tempconfig({'tex_dir': str(tmp_path / 'tex'), 'media_dir': str(tmp_path / 'media')}):
        yield
    _tex_failure_cache.clear()


@latex_required
@pytest.mark.parametrize('label', LABELS)
def test_label_compiles_with_glyphs(label, isolated_tex):
    from manim import Tex
    from animageo.ui import RusTex
    tex = Tex(correctedLabel(label), tex_template=RusTex)
    assert len(tex.get_all_points()) > 0


def _point_scene(label_text):
    from animageo.animageo import AnimaGeoScene
    scene = AnimaGeoScene()
    scene.putCode("P = Point(0,0)\nP.style.label_visible = True\n")
    elem = scene.geo.element('P')
    elem.style['label_text'] = label_text
    return scene, elem


@latex_required
@pytest.mark.parametrize('label', ['cos α', 'ω_1', r'\alpha'])
def test_point_keeps_its_label(label, isolated_tex):
    scene, elem = _point_scene(label)
    mob = scene.CreateMObject(elem)
    assert mob is not None
    labels = [m for m in mob.get_family() if getattr(m, '_animageo_is_label', False)]
    assert labels and len(labels[0].get_all_points()) > 0


@latex_required
@pytest.mark.parametrize('content, latex', [('угол α = 30°', False), (r'Угол \alpha', True)])
def test_free_text_with_greek_renders(content, latex, isolated_tex):
    from animageo.animageo import AnimaGeoScene
    from animageo.geo.lib_elements import Element, Text
    scene = AnimaGeoScene()
    elem = Element('txt', Text([('str', content)], position=[0, 0], is_latex=latex))
    scene.geo.add(elem)
    mob = scene.CreateMObject(elem, z_auto=True)
    assert mob is not None and len(mob.get_all_points()) > 0
    # the Greek letter is drawn: more glyphs than the text without it
    bare = Element('txt2', Text([('str', content.replace('α', '').replace(r'\alpha', ''))],
                                position=[0, 0], is_latex=latex))
    scene.geo.add(bare)
    assert (len(mob.family_members_with_points())
            > len(scene.CreateMObject(bare, z_auto=True).family_members_with_points()))


# ── a body that does not compile is compiled once per process ─────────

@latex_required
def test_failed_body_is_not_recompiled(isolated_tex, monkeypatch):
    import subprocess

    from manim import Tex
    from animageo.ui import RusTex

    runs = []
    real_run = subprocess.run

    def counting_run(cmd, *args, **kwargs):
        if cmd and 'latex' in str(cmd[0]):
            runs.append(cmd)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', counting_run)
    body = r'\undefinedcommandforthecache'
    for _ in range(3):
        with pytest.raises(ValueError):
            Tex(body, tex_template=RusTex)
    assert len(runs) == 1
