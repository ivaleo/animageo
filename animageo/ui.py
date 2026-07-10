"""UI components for AnimaGeo: TeX templates, labels, frames, arrow tips.

Provides reusable manim components used by AnimaGeoScene for rendering
geometric labels, numbered frames, and custom visual elements.
"""
import re
import numpy as np

from manim import (
    TexTemplate, Tex, Text, VGroup, VMobject, Polygon, Circle,
    ArcBetweenPoints, ArrowTip, FadeIn, DecimalNumber,
    PI, ORIGIN, DOWN, LEFT, UP, RIGHT, DL, UL, DR, UR,
)

from .style import hasParam


# ── Label anchor mapping ──────────────────────────────────────────────
# 9-point anchors: which corner/edge of the label bounding box is placed
# at the target position (point + offset).
#
#   TL ── TC ── TR
#   |           |
#   ML    MC    MR
#   |           |
#   BL ── BC ── BR
#
# GeoGebra uses BL (left-baseline ≈ bottom-left for capitals).

LABEL_ANCHORS = {
    'TL': UL,     'TC': UP,     'TR': UR,
    'ML': LEFT,   'MC': ORIGIN, 'MR': RIGHT,
    'BL': DL,     'BC': DOWN,   'BR': DR,
}


# ── TeX Template ───────────────────────────────────────────────────────

RusTex = TexTemplate(
    tex_compiler='latex',
    preamble=r"""
\usepackage[english, russian]{babel}
\usepackage[utf8]{inputenc}
\usepackage[T2A]{fontenc}
\usepackage{amsmath}
\usepackage{amssymb}

\linespread{1.1}

\usepackage{enumitem}

\usepackage{booktabs}
\usepackage{graphicx}


\newlist{mylist}{description}{1}
\setlist[mylist]{
    labelwidth=1.1em,
    leftmargin=!,
    align=left,
    labelsep=0.5em,
    format=\sffamily\bfseries,
    before={\raggedright},
    itemindent=0pt
}


\AtBeginDocument{
	\DeclareMathSizes{9}{9}{7}{5}
	\DeclareMathSizes{10}{10}{7}{5}
}

\renewcommand\frac[2]{\mathchoice%
	{\dfrac{\mbox{\fontsize{9}{12}\selectfont\(#1\)}}{\mbox{\fontsize{9}{12}\selectfont\(#2\)}}}%
	{\dfrac{\mbox{\fontsize{9}{12}\selectfont\(#1\)}}{\mbox{\fontsize{9}{12}\selectfont\(#2\)}}}%
	{\dfrac{\mbox{\raisebox{-1.5pt}{\fontsize{6}{8}\selectfont\(#1\)}}}{\mbox{\raisebox{2.5pt}{\fontsize{6}{8}\selectfont\(#2\)}}}}%
	{\dfrac{\mbox{\raisebox{-3pt}{\fontsize{5}{5}\selectfont\(#1\)}}}{\mbox{\raisebox{4pt}{\fontsize{5}{5}\selectfont\(#2\)}}}}}

\medmuskip 4mu
\thickmuskip 4mu

\makeatother

\AtBeginDocument{
    \let\oldangle\angle
    \def\angle{\mathbin{\text{\fontsize{0.8em}{0.8em}\selectfont\ensuremath\oldangle}}}
    \let\oldtriangle\triangle
    \def\triangle{\mathbin{\text{\fontsize{0.8em}{0.8em}\selectfont\ensuremath\oldtriangle}}}
}
""")


# ── Label utilities ────────────────────────────────────────────────────

# Unicode ← TeX symbol mappings for label text
_TEX_SYMBOLS = {
    '\\cdot': '·', '\\times': '×', '\\neq': '≠', '\\approx': '≈', '\\sim': '~',
    '\\leqslant': '⩽', '\\geqslant': '⩾',
    '\\degree': '°', '\\Rightarrow': '⇒', '\\Leftarrow': '⇐',
    '\\rightarrow': '→', '\\to': '→', '\\gets': '←',
    '\\mathbf': '∠', '\\triangle': '△', '\\perp': '⊥',
    '\\parallel': '∥', '\\nparralel': '∦',
    '\\in': '∈', '\\notin': '∉', '\\cap': '∩', '\\cup': '∪',
    '\\subset': '⊂', '\\supset': '⊃', '\\subseteq': '⊆', '\\supseteq': '⊇',
    '\\forall': '∀', '\\exists': '∃',
    '\\Longleftrightarrow': '⟺', '\\Leftrightarrow': '⟺',
    '\\pm': '±', '\\varnothing': '∅', '\\infty': '∞',
    '\\mathrm A': 'Α', '\\alpha': 'α',
    '\\mathrm B': 'Β', '\\beta': 'β',
    '\\Gamma': 'Γ', '\\gamma': 'γ',
    '\\Delta': 'Δ', '\\delta': 'δ',
    '\\mathrm E': 'Ε', '\\varepsilon': 'ε',
    '\\mathrm Z': 'Ζ', '\\zeta': 'ζ',
    '\\mathrm H': 'Η', '\\eta': 'η',
    '\\Theta': 'Θ', '\\theta': 'ϑ', '\\vartheta': 'ϑ',
    '\\mathrm I': 'Ι', '\\iota': 'ι',
    '\\mathrm K': 'Κ', '\\kappa': 'κ',
    '\\Lambda': 'Λ', '\\lambda': 'λ',
    '\\mathrm M': 'Μ', '\\mu': 'μ',
    '\\mathrm N': 'Ν', '\\nu': 'ν',
    '\\Xi': 'Ξ', '\\xi': 'ξ',
    '\\mathrm O': 'Ο', '\\mathrm o': 'ο',
    '\\Pi': 'Π', '\\pi': 'π', '\\varpi': 'ϖ',
    '\\mathrm P': 'Ρ', '\\rho': 'ρ',
    '\\Sigma': 'Σ', '\\sigma': 'σ', '\\varsigma': 'ς',
    '\\mathrm T': 'Τ', '\\tau': 'τ',
    '\\Upsilon': 'Υ', '\\upsilon': 'υ',
    '\\Phi': 'Φ', '\\varphi': 'φ',
    '\\mathrm X': 'Χ', '\\chi': 'χ',
    '\\Psi': 'Ψ', '\\psi': 'ψ',
    '\\Omega': 'Ω', '\\omega': 'ω',
}


def correctedLabel(label):
    """Replace Unicode math symbols with their TeX equivalents in a label string."""
    for tex, unicode_char in _TEX_SYMBOLS.items():
        label = re.sub(re.escape(unicode_char), re.sub(r'\\', r'\\\\', tex), label)
    return label


# ── Fast value labels (DecimalNumber-backed) ───────────────────────────
#
# A label that shows a changing numeric value (an angle measure, a segment
# length, a polygon area, …) used to be a single ``Tex`` rebuilt every frame.
# Because the value string changes each frame, that is a fresh LaTeX compile
# per frame — the dominant cost of animating such scenes.
#
# ``ValueLabel`` instead splits the label into a static ``Tex`` prefix
# (``\alpha =``), a :class:`~manim.DecimalNumber` for the number, and an
# optional static ``Tex`` suffix (``^{\circ}``). DecimalNumber renders each
# digit glyph once and caches it (manim's ``string_to_mob_map``), then just
# rearranges cached glyphs on ``set_value`` — no LaTeX recompile when the value
# changes. Measured ~80× faster per value label than the Tex path.

_GLYPHS_WARMED = False


def prewarm_decimal_glyphs():
    """Compile the digit/sign/dot glyphs once so the first animated frame does
    not stall building :class:`~manim.DecimalNumber` mobjects.

    ``string_to_mob_map`` is keyed by the glyph string only (colour/size are
    applied to the cached copy), so warming the ten digits, ``.`` and ``-``
    once covers every later value. Idempotent."""
    global _GLYPHS_WARMED
    if _GLYPHS_WARMED:
        return
    DecimalNumber(1234567890.5, num_decimal_places=1)
    DecimalNumber(-0.5, num_decimal_places=1)
    _GLYPHS_WARMED = True


class ValueLabel(VGroup):
    r"""A label of the form ``prefix value suffix`` whose numeric ``value`` is
    drawn with a :class:`~manim.DecimalNumber` so it updates without a LaTeX
    recompile.

    Mirrors the layout of the equivalent single ``Tex`` (``$\alpha = 90^\circ$``)
    while keeping the number as a separate, cheaply-updatable mobject.

    Args:
        value: Initial numeric value.
        prefix_tex: Static leading TeX (e.g. ``$\alpha = $``) or ``None``.
        suffix_tex: Static trailing TeX inner (e.g. ``^{\circ}``) or ``None``.
        suffix_raised: Align the suffix to the top of the number (degree
            superscript) instead of the baseline (unit).
        num_decimal_places: Fixed decimals; fixed width avoids jitter while the
            value animates.
        color / font_size: Applied to every part.
        z_index: Stacking order.

    Attributes:
        value: The :class:`~manim.DecimalNumber` carrying the number.
        prefix / suffix: The static :class:`~manim.Tex` parts (or ``None``).
    """

    def __init__(self, value=0.0, prefix_tex=None, suffix_tex=None,
                 suffix_raised=False, num_decimal_places=1, color=None,
                 font_size=48, z_index=0, tex_template=None, **kwargs):
        super().__init__(**kwargs)
        prewarm_decimal_glyphs()
        tex_template = tex_template or RusTex
        self._font_size = font_size
        self._color = color
        self._suffix_raised = suffix_raised

        self.prefix = None
        if prefix_tex:
            self.prefix = Tex(
                correctedLabel(prefix_tex), color=color, tex_template=tex_template,
            ).set(font_size=font_size)
            self.add(self.prefix)

        dn_kwargs = {'num_decimal_places': num_decimal_places, 'font_size': font_size}
        if color is not None:
            dn_kwargs['color'] = color
        self.value = DecimalNumber(value, **dn_kwargs)
        self.add(self.value)

        self.suffix = None
        if suffix_tex:
            inner = suffix_tex if suffix_tex.startswith('$') else '$' + suffix_tex + '$'
            self.suffix = Tex(
                correctedLabel(inner), color=color, tex_template=tex_template,
            ).set(font_size=font_size)
            self.add(self.suffix)

        self._layout()
        self.set_z_index(z_index)

    def _layout(self):
        """Place the number after the prefix and the suffix after the number,
        baseline-aligned (degree suffix top-aligned). Anchored on the prefix
        (or the number) so the left edge stays put as the number reflows."""
        h = max(self.value.height, 1e-3)
        gap = 0.34 * h   # ≈ one TeX medmuskip after the '=' sign
        if self.prefix is not None:
            self.value.next_to(self.prefix, RIGHT, buff=gap, aligned_edge=DOWN)
        if self.suffix is not None:
            if self._suffix_raised:
                self.suffix.next_to(self.value, RIGHT, buff=0.12 * h, aligned_edge=UP)
            else:
                self.suffix.next_to(self.value, RIGHT, buff=0.5 * gap, aligned_edge=DOWN)

    def set_value(self, number):
        """Update the displayed number in place (no LaTeX recompile)."""
        self.value.set_value(number)
        self._layout()
        return self

    def get_value(self):
        return self.value.get_value()


def _resolve_label_edge(elem, anchor, align_edge):
    """Resolve a 9-point anchor to a manim aligned-edge vector.

    Per-element style ``label_anchor`` < explicit ``anchor`` param < default.
    """
    anchor_val = anchor
    if anchor_val is None:
        anchor_val = elem.style.get('label_anchor')
    if isinstance(anchor_val, str):
        return LABEL_ANCHORS.get(anchor_val, align_edge)
    if anchor_val is not None:
        return anchor_val
    return align_edge


def _place_label(mobj, elem, pos, edge, ptUnit, ptUnit_ggb, ggb_font_px,
                 label_offset_px, auto_placed):
    """Apply anchor/offset/descender placement shared by Tex and ValueLabel."""
    mobj.move_to(pos, aligned_edge=edge)
    if label_offset_px is not None:
        scale = ptUnit_ggb if ptUnit_ggb else ptUnit
        mobj.shift([label_offset_px[0] / scale, label_offset_px[1] / scale, 0])
    elif hasParam(elem.style, 'label_offset_px'):
        scale = ptUnit_ggb if ptUnit_ggb else ptUnit
        mobj.shift([elem.style['label_offset_px'][0] / scale,
                    elem.style['label_offset_px'][1] / scale, 0])

    # GGB descender correction: GGB's labelOffset targets the bottom of the
    # text input field (which includes descender padding below the baseline).
    # Our TeX bbox is tighter, so labels appear lower without correction.
    # Skip for auto-placed labels — their offsets are already correct.
    placed = elem.style.get('_auto_placed') if auto_placed is None else auto_placed
    if ggb_font_px and not placed:
        GGB_DESCENDER_RATIO = 0.25
        mobj.shift([0, ggb_font_px * GGB_DESCENDER_RATIO / ptUnit, 0])
    return mobj


def create_label(elem, pos, col_label, font_size, zz_label, ptUnit, align_edge=DL,
                 ptUnit_ggb=None, anchor=None, ggb_font_px=None,
                 label_text=None, label_offset_px=None, auto_placed=None,
                 label_spec=None, dynamic=False):
    """Create a label mobject for a geometric element.

    When ``dynamic`` is True and ``label_spec`` carries a live numeric value, a
    fast :class:`ValueLabel` (DecimalNumber-backed) is built so per-frame value
    changes don't trigger a LaTeX recompile. Otherwise a plain ``Tex`` is used
    (full fidelity, trailing-zero stripping) — the default for static export.

    Args:
        anchor: Label anchor point — which part of the label is placed at
            pos+offset. One of 'TL','TC','TR','ML','MC','MR','BL','BC','BR'
            or a manim direction vector. Default None = use align_edge (BL).
        ggb_font_px: GGB font size in pixels. When set, applies a vertical
            correction to compensate for GGB's text-field descender padding.
        label_spec: Optional ``LabelSpec`` enabling the fast value path.
        dynamic: Build a ``ValueLabel`` for value-bearing labels.
    """
    edge = _resolve_label_edge(elem, anchor, align_edge)

    if dynamic and label_spec is not None and label_spec.has_dynamic_value:
        mobj = ValueLabel(
            value=label_spec.value,
            prefix_tex=label_spec.prefix_tex,
            suffix_tex=label_spec.suffix_tex,
            suffix_raised=label_spec.suffix_raised,
            num_decimal_places=label_spec.num_decimal_places,
            color=col_label, font_size=font_size, z_index=zz_label,
        )
    else:
        label = label_text if label_text is not None else elem.style.get('label_text', '$' + elem.name + '$')
        mobj = Tex(correctedLabel(label), color=col_label).set_z_index(zz_label).set(font_size=font_size, tex_template=RusTex)

    # Tag so bounds measurement can tell a label apart from geometry (the label is
    # a submobject of the element's VGroup). Used by rendered-bounds framing to
    # crop to the geometry only, without letting a label inflate the extent.
    mobj._animageo_is_label = True

    return _place_label(
        mobj, elem, pos, edge, ptUnit, ptUnit_ggb, ggb_font_px,
        label_offset_px, auto_placed,
    )


# ── Geometry helpers ───────────────────────────────────────────────────

def round_corners_vmobject(points, radius=0.5, components_per_rounded_corner=8):
    """Create a VMobject with rounded corners from a polyline.

    Args:
        points: List of polyline vertices
        radius: Corner rounding radius
        components_per_rounded_corner: Bezier segments per rounded corner
    """
    points = [np.array(p) for p in points]

    if len(points) < 3 or radius <= 0:
        return VMobject().set_points_as_corners(points)

    result = VMobject()
    new_points = []

    new_points.append(points[0])

    for i in range(1, len(points) - 1):
        v_prev = points[i - 1]
        v_curr = points[i]
        v_next = points[i + 1]

        vec_in = v_prev - v_curr
        vec_out = v_next - v_curr

        norm_in = np.linalg.norm(vec_in)
        norm_out = np.linalg.norm(vec_out)

        if norm_in < 1e-6 or norm_out < 1e-6:
            new_points.append(v_curr)
            continue

        unit_in = vec_in / norm_in
        unit_out = vec_out / norm_out

        dot_product = np.clip(np.dot(unit_in, unit_out), -1.0, 1.0)
        angle = np.arccos(dot_product)

        d = radius / np.tan(angle / 2)
        d = min(d, norm_in * 0.75, norm_out * 0.75)

        start_round = v_curr + unit_in * d
        end_round = v_curr + unit_out * d

        cross_vec = np.cross(unit_in, unit_out)
        sign = np.sign(cross_vec[2]) if abs(cross_vec[2]) > 1e-8 else 1.0

        arc = ArcBetweenPoints(
            start_round, end_round,
            angle=-sign * (PI - angle),
            num_components=components_per_rounded_corner,
        )

        if not np.allclose(new_points[-1], start_round):
            new_points.append(start_round)

        new_points.extend(arc.points[1:])

    new_points.append(points[-1])

    result.set_points_as_corners(new_points)
    return result


# ── UI Components ──────────────────────────────────────────────────────

def ShowText(scene, header=None, body=None, pos=ORIGIN, width=None, numeration=None, **kwargs):
    """Display a text block with optional header and body in the scene."""
    if numeration is not None:
        body = "\\begin{mylist}\\item[" + str(numeration) + "] " + body + "\\end{mylist}"
    if width is not None:
        body = "\\begin{minipage}{" + str(width) + "}" + body + "\\end{minipage}"

    if header:
        theader = Tex(header, font_size=37, tex_template=RusTex,
                      color=scene.style.strong)
        theader.set_fill(color=scene.style.col)
        theader.move_to(pos, aligned_edge=LEFT + UP)
        pos += 0.7 * DOWN
        scene.play(FadeIn(theader))

    if body:
        tbody = Tex(body, font_size=34, tex_template=RusTex,
                    color=scene.style.strong)
        tbody.move_to(pos, aligned_edge=LEFT + UP)
        scene.play(FadeIn(tbody, **kwargs))


class NumberedFrame(VGroup):
    """A numbered circle label positioned relative to the camera frame."""

    def __init__(self, number, camera=None, screen_position=None,
                 circle_radius=0.4, circle_color="#777", circle_fill_opacity=0.1,
                 font="Trebuchet MS", font_size=36, font_color="#444",
                 stroke_width=0, **kwargs):
        super().__init__(**kwargs)
        self.scale_ = 1.0

        if camera is not None:
            self.update_position(screen_position=screen_position, camera=camera)
            self.scale_ = float(self.frame_size[1] / 8.0)

        self.circle = Circle(
            radius=circle_radius * self.scale_,
            color=circle_color,
            fill_opacity=circle_fill_opacity,
            stroke_width=stroke_width * self.scale_,
        )
        self.text = Text(str(number), font=font, font_size=font_size * self.scale_, color=font_color)
        self.add(self.circle, self.text)
        self.move_to_screen_position(point=screen_position)

    def update_position(self, screen_position=None, camera=None):
        if screen_position is not None: self.screen_position = screen_position
        if camera is not None:
            self.frame_center = camera.frame_center
            self.frame_size = [camera.frame_width, camera.frame_height]

    def move_to_screen_position(self, point):
        x = (point[0] - 0.5) * self.frame_size[0]
        y = (point[1] - 0.5) * self.frame_size[1]
        self.move_to(self.frame_center).shift(x * RIGHT + y * UP)
        return self


class FixedLabel(VGroup):
    """A text label positioned relative to the camera frame."""

    def __init__(self, text, camera=None, screen_position=None,
                 font="Trebuchet MS", font_size=20.0, font_color="#888",
                 font_opacity=1.0, **kwargs):
        super().__init__(**kwargs)
        self.scale_ = 1.0

        if camera is not None:
            self.update_position(screen_position=screen_position, camera=camera)
            self.scale_ = float(self.frame_size[1] / 8.0)

        self.label = Text(str(text), font=font, font_size=font_size * self.scale_, color=font_color)
        self.add(self.label)
        self.move_to_screen_position(point=screen_position)

    def update_position(self, screen_position=None, camera=None):
        if screen_position is not None: self.screen_position = screen_position
        if camera is not None:
            self.frame_center = camera.frame_center
            self.frame_size = [camera.frame_width, camera.frame_height]

    def move_to_screen_position(self, point):
        x = (point[0] - 0.5) * self.frame_size[0]
        y = (point[1] - 0.5) * self.frame_size[1]
        self.move_to(self.frame_center).shift(x * RIGHT + y * UP)
        return self


class CustomArrowTip(ArrowTip, Polygon):
    """Custom triangular arrow tip for Vector rendering."""

    def __init__(self, length=0.35, **kwargs):
        w = kwargs.get('width', length * 0.9) * 0.5
        h = kwargs.get('height', length)
        Polygon.__init__(self, [0, h, 0], [-w, 0, 0], [w, 0, 0])
        if 'fill' in kwargs:
            self.set_fill(color=kwargs['fill'], opacity=1)
        if 'stroke' in kwargs:
            self.set_stroke(color=kwargs['stroke'], opacity=1)
        else:
            self.set_stroke(width=0, opacity=0)
