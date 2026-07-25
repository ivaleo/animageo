"""Cyrillic labels must survive every Tex path.

Covers ``docs/archive/TZ-cyrillic-label-tex-template-fallback.md``:

* **6.1** a Cyrillic label compiles even when a Tex path forgets to pass a
  Cyrillic-capable template explicitly (``RusTex`` becomes the process-wide
  manim default), and a point with a Cyrillic name renders *at all* — the
  bug was that ``create_label`` applied ``tex_template=RusTex`` with
  ``.set(...)`` **after** construction, i.e. after LaTeX had already run
  under manim's non-Cyrillic default, so the whole element was swallowed.
* **6.2** Cyrillic in a sub/superscript (``$A_Б$``) no longer trips
  ``! Missing { inserted``, with no regression on ordinary names.
* **6.3** a label whose LaTeX cannot compile degrades to escaped plain text
  (and, if even that fails, is dropped) instead of taking the marker with it.
* **6.4** the renderer and the auto-placer measure labels under the same
  template, so computed offsets match what is drawn.
* **6.5** installing the global default is idempotent and accumulates no
  process state (cf. TZ-mathtex-set-default-recursion-leak).

Plus the second defect found while implementing: Cyrillic in *math* mode
compiles without error and renders **nothing** (no glyphs in the T2A math
alphabet), in manim and in the TikZ export alike.
"""
import shutil

import pytest

latex_required = pytest.mark.skipif(
    shutil.which('latex') is None, reason='requires a LaTeX toolchain',
)


@pytest.fixture
def preserve_tex_template():
    """Save/restore the global manim TeX template around a test."""
    from manim import config
    saved = config.tex_template
    yield
    config.tex_template = saved


def _point_scene(name='Б', label_text=None):
    from animageo.animageo import AnimaGeoScene
    scene = AnimaGeoScene()
    scene.putCode(f"{name} = Point(0,0)\n{name}.style.label_visible = True\n")
    elem = scene.geo.element(name)
    if label_text is not None:
        elem.style['label_text'] = label_text
    return scene, elem


# ── 6.1: Cyrillic labels render ───────────────────────────────────────

class TestCyrillicLabelRenders:
    @latex_required
    def test_point_with_cyrillic_name_renders_marker_and_label(self):
        scene, elem = _point_scene('Б')
        mob = scene.CreateMObject(elem)
        assert mob is not None, 'element was swallowed by the label compile'
        assert len(mob.submobjects) == 2, 'expected marker + label'

    @latex_required
    def test_cyrillic_label_actually_has_glyphs(self):
        """Compiling is not enough: a Cyrillic letter in *math* mode has no
        glyph in the T2A math font, so ``$Б$`` compiles fine and draws
        nothing. The label must be typeset in text mode."""
        scene, elem = _point_scene('Б')
        label = scene.CreateMObject(elem)[-1]
        assert len(label.get_all_points()) > 0, 'label rendered as empty'
        assert label.width > 0 and label.height > 0

    @latex_required
    def test_cyrillic_subscripted_name_keeps_its_base_letter(self):
        """``$Б_1$`` used to draw the ``1`` only — the base letter vanished."""
        from manim import Tex

        from animageo.ui import RusTex, correctedLabel

        base = Tex(correctedLabel('$Б$'), tex_template=RusTex)
        full = Tex(correctedLabel('$Б_1$'), tex_template=RusTex)
        assert full.width > base.width

    @latex_required
    def test_cyrillic_angle_label_renders(self):
        from animageo.animageo import AnimaGeoScene
        scene = AnimaGeoScene()
        scene.putCode("""
Б = Point(0,0)
В = Point(3,0)
Г = Point(0,2)
угол = Angle(В, Б, Г)
угол.style.label_visible = True
""")
        mob = scene.CreateMObject(scene.geo.element('угол'))
        assert mob is not None


class TestCyrillicFreeText:
    """A LaTeX free-text object hits the same math-mode trap: the Cyrillic
    inside ``$…$`` is dropped silently, leaving a gap in the sentence."""

    @latex_required
    def test_cyrillic_in_math_mode_is_not_dropped(self):
        from animageo.animageo import AnimaGeoScene
        from animageo.geo.lib_elements import Element, Text

        scene = AnimaGeoScene()
        elem = Element('txt', Text([('str', r'Отрезок $БВ$ равен')],
                                   position=[0, 0], is_latex=True))
        scene.geo.add(elem)
        with_cyr = scene.CreateMObject(elem, z_auto=True)

        gap = Element('txt2', Text([('str', 'Отрезок  равен')],
                                   position=[0, 0], is_latex=True))
        scene.geo.add(gap)
        without = scene.CreateMObject(gap, z_auto=True)

        # An empty math box still takes width, so count glyphs, not extent.
        assert len(with_cyr.get_all_points()) > len(without.get_all_points()), \
            'the $БВ$ run rendered as nothing'


class TestGlobalDefaultTemplate:
    def test_scene_init_installs_cyrillic_default(self, preserve_tex_template):
        from manim import TexTemplate, config

        from animageo.animageo import AnimaGeoScene
        from animageo.ui import RusTex

        config.tex_template = TexTemplate()   # manim stock, non-Cyrillic
        AnimaGeoScene()
        assert config.tex_template is RusTex

    def test_custom_user_template_is_not_clobbered(self, preserve_tex_template):
        from manim import TexTemplate, config

        from animageo.animageo import AnimaGeoScene

        custom = TexTemplate(preamble=r'\usepackage{amsmath}% mine')
        config.tex_template = custom
        AnimaGeoScene()
        assert config.tex_template is custom

    @latex_required
    def test_tex_without_explicit_template_compiles_cyrillic(
            self, preserve_tex_template):
        from manim import Tex, TexTemplate, config

        from animageo.ui import correctedLabel, install_cyrillic_tex_template

        config.tex_template = TexTemplate()
        install_cyrillic_tex_template()
        Tex(correctedLabel('$Б$'))   # no explicit tex_template — must not raise

    def test_repeated_installs_accumulate_no_state(self, preserve_tex_template):
        """6.5 — unlike ``Mobject.set_default``, setting ``config.tex_template``
        must stay a plain idempotent assignment."""
        from manim import Tex, TexTemplate, config

        from animageo.ui import RusTex, install_cyrillic_tex_template

        init_before = Tex.__init__
        config.tex_template = TexTemplate()
        for _ in range(2000):
            install_cyrillic_tex_template()
        assert config.tex_template is RusTex
        assert Tex.__init__ is init_before


# ── 6.2: Cyrillic in sub/superscripts ─────────────────────────────────

class TestNonAsciiScripts:
    @pytest.mark.parametrize('label, expected', [
        ('$Б$', r'$\text{Б}$'),
        ('$БВ$', r'$\text{БВ}$'),
        ('$Б_1$', r'$\text{Б}_1$'),
        (r'$\overline{Б}$', r'$\overline{\text{Б}}$'),
        ('$A_Б$', r'$A_{\text{Б}}$'),          # braced: ``_\text`` would break
        ('$x^Б$', r'$x^{\text{Б}}$'),
        (r'$\angle БВГ$', r'$\angle \text{БВГ}$'),
    ])
    def test_cyrillic_is_typeset_in_text_mode(self, label, expected):
        from animageo.ui import correctedLabel
        assert correctedLabel(label) == expected

    def test_non_cyrillic_nonascii_script_is_braced(self):
        """Any other stray non-ASCII char is at least made a single argument,
        so it cannot trip ``! Missing { inserted``."""
        from animageo.ui import correctedLabel
        assert correctedLabel('$A_∡$') == '$A_{∡}$'

    def test_escaped_underscore_is_not_a_subscript(self):
        from animageo.ui import correctedLabel
        assert correctedLabel(r'$A\_Б$') == r'$A\_\text{Б}$'

    @pytest.mark.parametrize('label', [
        '$A_1$', '$x^2$', r'$A_{\alpha}$', '$AB$', r'$\overline{AB}$',
        r'$\alpha$', r'$30.5^{\circ}$', r'$\angle ABC$',
        # Cyrillic already in text mode renders fine there and must not be
        # chopped into \mbox-es.
        'Точка Б', 'Отрезок равен',
    ])
    def test_ordinary_labels_are_unchanged(self, label):
        from animageo.ui import correctedLabel
        assert correctedLabel(label) == label

    def test_only_the_math_part_of_a_sentence_is_textified(self):
        from animageo.ui import textify_cyrillic
        assert (textify_cyrillic('Отрезок $БВ$ равен $5$')
                == r'Отрезок $\text{БВ}$ равен $5$')

    @latex_required
    @pytest.mark.parametrize('label', [
        '$Б$', '$Б_1$', '$БВ$', r'$\overline{Б}$', r'$\angle Б$', '$A_Б$',
    ])
    def test_cyrillic_labels_compile(self, label):
        from manim import Tex

        from animageo.ui import RusTex, correctedLabel

        Tex(correctedLabel(label), tex_template=RusTex)


class TestTikZExportCyrillic:
    """The TikZ exporter ships a Cyrillic-ready preamble, but its nodes go
    through the same math mode — ``\\node {$Б$}`` compiles to an empty node
    under T2A (verified with pdflatex). JSXGraph is unaffected: it renders
    labels through MathJax, which has Cyrillic in math."""

    def test_label_node_is_typeset_in_text_mode(self):
        scene, elem = _point_scene('Б')
        tex = scene.exportTikZ()
        assert r'\text{Б}' in tex
        assert '{$Б$}' not in tex

    def test_free_text_math_run_is_typeset_in_text_mode(self):
        from animageo.animageo import AnimaGeoScene
        from animageo.geo.lib_elements import Element, Text

        scene = AnimaGeoScene()
        scene.putCode('A = Point(0,0)')
        scene.geo.add(Element('txt', Text([('str', r'Длина $БВ$')],
                                          position=[0, 0], is_latex=True)))
        tex = scene.exportTikZ()
        assert r'$\text{БВ}$' in tex

    def test_latin_labels_are_untouched(self):
        scene, elem = _point_scene('A')
        assert '{$A$}' in scene.exportTikZ()


# ── 6.4: no visual regression ─────────────────────────────────────────

class TestRendererMatchesPlacementMetrics:
    """Auto-placement measures label bboxes under ``RusTex``; the renderer must
    draw them under the same template, or every computed offset is off by the
    template difference (``\\frac``, ``\\angle``, math spacing). This was the
    other half of the ``.set(tex_template=...)``-after-construction bug."""

    @latex_required
    @pytest.mark.parametrize('label_text', [
        '$A$', '$M_1$', r'$\alpha$', r'$\overline{AB}$', r'$30.5^{\circ}$',
        r'$\angle ABC$', r'$\frac{1}{2}$', '$Б$', '$Б_1$',
    ])
    def test_rendered_label_matches_measured_bbox(self, label_text):
        from animageo.label_placement import _measure_label_bbox

        scene, elem = _point_scene('A', label_text=label_text)
        mob = scene.CreateMObject(elem)
        assert mob is not None
        label = mob[-1]
        w, h = _measure_label_bbox(label_text, label.font_size)
        assert label.width == pytest.approx(w, rel=1e-6)
        assert label.height == pytest.approx(h, rel=1e-6)


# ── 6.3: soft degradation ─────────────────────────────────────────────

class TestLabelDegradation:
    @latex_required
    def test_malformed_label_falls_back_to_plain_text(self):
        scene, elem = _point_scene('A', label_text=r'$\frac{1}{$')
        mob = scene.CreateMObject(elem)
        assert mob is not None
        assert len(mob.submobjects) == 2, 'marker + plain-text label expected'

    def test_uncompilable_label_keeps_the_marker(self, monkeypatch):
        """Even when *every* Tex compile fails, the geometry survives."""
        import animageo.ui as ui

        def _boom(*a, **kw):
            raise ValueError('latex error converting to dvi')

        scene, elem = _point_scene('A')
        monkeypatch.setattr(ui, 'Tex', _boom)
        mob = scene.CreateMObject(elem)
        assert mob is not None, 'marker must survive a dead label'
        assert len(mob.submobjects) == 1, 'label dropped, marker kept'

    def test_bbox_measurement_survives_a_broken_label(self, monkeypatch):
        """Auto-placement must not crash the whole render on a bad label."""
        from animageo import label_placement

        label_placement.clear_bbox_cache()
        monkeypatch.setattr(
            'manim.Tex', lambda *a, **kw: (_ for _ in ()).throw(ValueError('boom')),
        )
        w, h = label_placement._measure_label_bbox('$Б$', 30.0)
        assert w > 0 and h > 0
