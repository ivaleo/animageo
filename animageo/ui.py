"""UI components for AnimaGeo: TeX templates, labels, frames, arrow tips.

Provides reusable manim components used by AnimaGeoScene for rendering
geometric labels, numbered frames, and custom visual elements.
"""
import logging
import re
import numpy as np

from manim import (
    TexTemplate, Tex, Text, VGroup, VMobject, Polygon, Circle,
    ArcBetweenPoints, ArrowTip, FadeIn, DecimalNumber,
    PI, ORIGIN, DOWN, LEFT, UP, RIGHT, DL, UL, DR, UR,
    DEFAULT_FONT_SIZE,
)

from .constants import GGB_FONT_SCALE
from .geo.lib_elements import latex_escape_text, textify_cyrillic
from .style import hasParam
from . import _tex_failure_cache, _tex_security

# every Tex of a label compiles with -no-shell-escape (1.11.0rc1)
_tex_security.install()
# a body that failed to compile is not compiled again in the process
_tex_failure_cache.install()

logger = logging.getLogger(__name__)


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


def install_cyrillic_tex_template(force=False):
    """Make :data:`RusTex` the process-wide default manim TeX template.

    Manim's stock template has neither ``babel russian`` nor ``T2A`` font
    encoding, so any ``Tex(...)`` built without an explicit ``tex_template``
    dies on ``Unicode character Б (U+0411) not set up for use with LaTeX`` —
    and the element that owned the label is swallowed whole. Relying on every
    call site to remember ``tex_template=RusTex`` is a discipline, not an
    invariant; setting the config default once closes the whole class.

    A template the caller installed themselves is left alone (pass ``force``
    to override) — only manim's stock default is replaced.

    Idempotent and stateless: unlike ``Mobject.set_default`` this is a plain
    assignment, so it accumulates no ``partialmethod`` chain no matter how
    often it runs (see ``docs/gotchas.md``).

    Returns:
        True if :data:`RusTex` is the active default afterwards.
    """
    from manim import config

    current = config.tex_template
    if current is RusTex:
        return True
    if not force and current is not None and current != TexTemplate():
        return False        # caller runs their own template — respect it
    config.tex_template = RusTex
    return True


# ── Label utilities ────────────────────────────────────────────────────

# The label TeX helpers live in ``animageo.labels`` (manim-free: the native
# label layout uses them too); re-exported here for existing imports.
from .labels import (  # noqa: E402,F401
    _NONASCII_SCRIPT_RE, _TEX_SYMBOLS, _brace_nonascii_scripts, correctedLabel, mathify_text_symbols,
)


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

# The exact layout of a ValueLabel (1.11.0rc7): per TeX template, the ink
# offset of each digit against ``0`` at the same pen position; per pattern
# (the label with every digit ``0``), the glyph boxes and the baseline —
# both at DEFAULT_FONT_SIZE, measured once.
_DIGIT_OFFSETS = {}
_PATTERN_PROBES = {}


def _digit_offsets(tex_template):
    """``{digit: (dx, dy)}`` at ``DEFAULT_FONT_SIZE``: where the ink of a
    digit starts against the ink of ``0`` typeset at the same pen position —
    from ``$00123456789$`` (the two zeros give the advance, one for every
    digit of the font). ``None`` when it cannot be measured."""
    key = id(tex_template)
    if key not in _DIGIT_OFFSETS:
        offsets = None
        try:
            leaves = Tex('$00123456789$', tex_template=tex_template).family_members_with_points()
            if len(leaves) == 11:
                lefts = [float(m.get_corner(DL)[0]) for m in leaves]
                bottoms = [float(m.get_corner(DL)[1]) for m in leaves]
                advance = lefts[1] - lefts[0]
                offsets = {str(d): (lefts[d + 1] - lefts[0] - (d + 1) * advance, bottoms[d + 1] - bottoms[0])
                           for d in range(10)}
        except Exception:
            logger.debug('digit offsets: the atlas did not compile', exc_info=True)
        _DIGIT_OFFSETS[key] = offsets
    return _DIGIT_OFFSETS[key]


def _pattern_probe(tex_string, tex_template):
    """``[x0, y0, x1, y1]`` of every glyph of ``tex_string`` at
    ``DEFAULT_FONT_SIZE`` in the frame of its pen: compiled between two
    ``.`` (``.`` + label + ``.``), ``x`` from the ink of the first dot (a
    fixed step before the start of the label, whatever the label), ``y``
    from the baseline (the bottom of the dots, as
    ``_label_baseline_depth_mu`` probes a label) — the same frame for every
    pattern of a label. ``None`` when it does not compile."""
    key = (id(tex_template), tex_string)
    if key not in _PATTERN_PROBES:
        probe = None
        try:
            tex = Tex('.', tex_string, '.', tex_template=tex_template)
            pen = np.array([float(tex[0].get_corner(DL)[0]), float(tex[2].get_corner(DOWN)[1])])
            probe = [np.concatenate([m.get_corner(DL)[:2] - pen, m.get_corner(UR)[:2] - pen])
                     for m in tex[1].family_members_with_points()]
        except Exception:
            logger.debug('value label pattern %r did not compile', tex_string, exc_info=True)
        _PATTERN_PROBES[key] = probe
    return _PATTERN_PROBES[key]


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


class _LabelNumber(DecimalNumber):
    """A :class:`~manim.DecimalNumber` whose digits are the text of the static
    label (``labels._format_number``): ``num_decimal_places`` places, trailing
    zeros stripped when ``strip_zeros``, no thousands separator, no ``-0``. A
    value that is not finite keeps manim's text (``nan``, ``inf``): the TeX of
    the static label (``\\infty``) is no string of glyphs."""

    def __init__(self, number=0.0, *, strip_zeros=False, **kwargs):
        self.strip_zeros = bool(strip_zeros)
        super().__init__(number, group_with_commas=False, **kwargs)

    def _get_num_string(self, number):
        import math
        from .labels import _format_number
        try:
            value = float(number)
        except (TypeError, ValueError):
            return super()._get_num_string(number)
        if not math.isfinite(value):
            return super()._get_num_string(number)
        return _format_number(value, self.num_decimal_places, self.strip_zeros)


class ValueLabel(VGroup):
    r"""A label of the form ``prefix value suffix`` whose numeric ``value`` is
    drawn with a :class:`~manim.DecimalNumber` so it updates without a LaTeX
    recompile.

    Mirrors the layout of the equivalent single ``Tex`` (``$\alpha = 90^\circ$``)
    while keeping the number as a separate, cheaply-updatable mobject. The
    digits are those of the static label (1.11.0rc3): ``num_decimal_places``
    places, trailing zeros stripped with ``strip_zeros`` (the label of a
    scene passes its ``label_value_strip_zeros``), no thousands separator —
    so a frame of the video reads as the still frame (``60°``, not
    ``60.0°``); :attr:`tex` is that static label.

    Args:
        value: Initial numeric value.
        prefix_tex: Static leading TeX (e.g. ``$\alpha = $``) or ``None``.
        suffix_tex: Static trailing TeX inner (e.g. ``^{\circ}``) or ``None``.
        suffix_raised: Align the suffix to the top of the number (degree
            superscript) instead of the baseline (unit).
        num_decimal_places: Decimal places of the value (``label_value_precision``).
        strip_zeros: Strip trailing zeros (and a trailing point) as the static
            label does; ``False`` keeps ``num_decimal_places`` fixed.
        color / font_size: Applied to every part.
        z_index: Stacking order.

    Attributes:
        value: The :class:`~manim.DecimalNumber` carrying the number.
        prefix / suffix: The static :class:`~manim.Tex` parts (or ``None``).
    """

    def __init__(self, value=0.0, prefix_tex=None, suffix_tex=None,
                 suffix_raised=False, num_decimal_places=1, color=None,
                 font_size=48, z_index=0, tex_template=None, strip_zeros=False, **kwargs):
        super().__init__(**kwargs)
        prewarm_decimal_glyphs()
        tex_template = tex_template or RusTex
        self._font_size = font_size
        self._color = color
        self._suffix_raised = suffix_raised
        self._prefix_tex = prefix_tex
        self._suffix_tex = suffix_tex

        self.prefix = None
        if prefix_tex:
            self.prefix = Tex(
                correctedLabel(prefix_tex), color=color, tex_template=tex_template,
            ).set(font_size=font_size)
            self.add(self.prefix)

        dn_kwargs = {'num_decimal_places': num_decimal_places, 'font_size': font_size,
                     'strip_zeros': strip_zeros}
        if color is not None:
            dn_kwargs['color'] = color
        self.value = _LabelNumber(value, **dn_kwargs)
        self.add(self.value)

        self.suffix = None
        if suffix_tex:
            inner = suffix_tex if suffix_tex.startswith('$') else '$' + suffix_tex + '$'
            self.suffix = Tex(
                correctedLabel(inner), color=color, tex_template=tex_template,
            ).set(font_size=font_size)
            self.add(self.suffix)

        self._tex_template = tex_template
        self._frame = None          # where the pattern frame sits (exact layout)
        self._first_target = None   # the lower-left corner the first glyph was put at
        self._depth = None          # ink below the baseline, MU (exact layout)
        self._layout()
        self.set_z_index(z_index)

    def _layout(self, frame=None):
        """Place the glyphs where the ``Tex`` of :attr:`tex` puts them
        (:meth:`_exact_layout`, 1.11.0rc7); when that cannot be measured, the
        approximate layout of before: the number after the prefix and the
        suffix after the number, baseline-aligned (degree suffix top-aligned),
        anchored on the prefix (or the number)."""
        if self._exact_layout(frame):
            return
        self._depth = None
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
        """Update the displayed number in place (no LaTeX recompile of the
        digits; a new count of digits measures its pattern once, cached).
        The frame of the label stays put: the prefix does not move."""
        frame = self._current_frame()
        self.value.set_value(number)
        self._layout(frame)
        return self

    @property
    def baseline_depth_mu(self):
        """How far the ink goes below the baseline, MU — that of the
        ``Tex`` of :attr:`tex` (``_label_baseline_depth_mu``); ``None`` with
        the approximate layout."""
        return self._depth

    def _current_frame(self):
        """The offset of the pattern frame as the label stands now (moved
        by its placement): the first glyph against where it was put."""
        if self._frame is None or self._first_target is None:
            return None
        leaves = self.family_members_with_points()
        if not leaves:
            return None
        return self._frame + (leaves[0].get_corner(DL)[:2] - self._first_target)

    def _exact_layout(self, frame=None):
        """Every glyph where the ``Tex`` of :attr:`tex` puts it.

        The digits are cached glyphs of the ``DecimalNumber``; their places
        come from the *pattern* of the label — :attr:`tex` with every digit
        ``0``, compiled once per pattern (with a ``.`` on the baseline, as
        ``_label_baseline_depth_mu`` probes it, :func:`_pattern_probe`) and
        cached — and the ink offset of each digit against ``0`` at the same
        pen position (:func:`_digit_offsets`; the digits of the font are of
        one width). The prefix and the suffix glyphs go to their places in
        the pattern. ``frame`` — where the pen of the pattern sits, on the
        baseline (``None``: the origin); the same for every pattern, so the
        prefix stays put as the number reflows.
        ``False`` when the pattern does not map glyph for glyph onto the
        parts (the caller lays them out approximately)."""
        text = self.number_text
        chars = list(self.value.submobjects)
        if len(chars) != len(text) or any(len(c.family_members_with_points()) != 1 for c in chars):
            return False
        offsets = _digit_offsets(self._tex_template)
        if offsets is None:
            return False
        from .labels import _math_inner, _math_wrap
        prefix = _math_inner(self._prefix_tex) if self._prefix_tex else ''
        suffix = _math_inner(self._suffix_tex) if self._suffix_tex else ''
        pattern = ''.join('0' if ch.isdigit() else ch for ch in text)
        probe = _pattern_probe(correctedLabel(_math_wrap(prefix + pattern + suffix)), self._tex_template)
        if probe is None:
            return False
        boxes = probe
        head = self.prefix.family_members_with_points() if self.prefix is not None else []
        tail = self.suffix.family_members_with_points() if self.suffix is not None else []
        if len(boxes) != len(head) + len(chars) + len(tail):
            return False
        k = float(self._font_size) / DEFAULT_FONT_SIZE
        origin = np.zeros(2) if frame is None else np.asarray(frame, dtype=float)
        boxes = [np.asarray(b) * k + np.concatenate([origin, origin]) for b in boxes]
        tol = 1e-3 * k + 1e-6

        def same_size(leaf, box):
            lo, hi = leaf.get_corner(DL)[:2], leaf.get_corner(UR)[:2]
            return np.allclose(hi - lo, box[2:] - box[:2], atol=tol)

        number_boxes = boxes[len(head):len(head) + len(chars)]
        pairs = list(zip(head, boxes[:len(head)])) + list(zip(tail, boxes[len(head) + len(chars):]))
        if not all(same_size(leaf, box) for leaf, box in pairs):
            return False
        if not all(ch.isdigit() or same_size(c, box) for ch, c, box in zip(text, chars, number_boxes)):
            return False

        parts = [p for p in (self.prefix, self.value, self.suffix) if p is not None]
        heights = [p.height for p in parts]
        for leaf, box in pairs:
            centre = (box[:2] + box[2:]) / 2.0
            leaf.shift(np.append(centre - leaf.get_center()[:2], 0.0))
        for ch, c, box in zip(text, chars, number_boxes):
            target = box[:2] + (np.asarray(offsets[ch]) * k if ch.isdigit() else 0.0)
            c.shift(np.append(target - c.get_corner(DL)[:2], 0.0))
        # the glyphs moved, none was scaled: the parts keep their font size
        for part, height in zip(parts, heights):
            if height > 1e-12 and part.height > 1e-12:
                part.initial_height *= part.height / height
        self._frame = origin
        self._first_target = self.family_members_with_points()[0].get_corner(DL)[:2].copy()
        self._depth = max(origin[1] - float(self.get_corner(DL)[1]), 0.0)
        return True

    def get_value(self):
        return self.value.get_value()

    @property
    def number_text(self) -> str:
        """The digits drawn for the current value (``labels._format_number``)."""
        return self.value._get_num_string(self.value.number)

    @property
    def tex(self) -> str:
        """The TeX of the static label this one stands for: ``prefix``, the
        digits and ``suffix`` in one ``$…$`` (``labels.resolve_label_text``)."""
        from .labels import _math_inner, _math_wrap
        prefix = _math_inner(self._prefix_tex) if self._prefix_tex else ''
        suffix = _math_inner(self._suffix_tex) if self._suffix_tex else ''
        return _math_wrap(prefix + self.number_text + suffix)


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


_BASELINE_DEPTH_RATIO_CACHE = {}


def _label_baseline_depth_mu(mobj, font_size):
    """Distance the label's ink extends below its typographic baseline, in MU.

    A Tex tight bbox ends at the lowest ink, not at the baseline, so glyphs
    with descenders (Д, Щ, у, subscripts) would ride higher than their
    neighbours when anchored by bbox bottom. The depth is measured once per
    tex string by compiling it next to a baseline probe glyph ('.', zero
    depth) in a single LaTeX run and cached as a ratio of the compile-time
    font size. A ValueLabel gives the depth its exact layout measured (that
    of the Tex of its label); probe failures fall back to 0 (bottom ==
    baseline, exact for capital letters and digits).
    """
    if isinstance(mobj, ValueLabel):
        # the depth of the Tex of its label, measured by its exact layout
        return mobj.baseline_depth_mu or 0.0
    tex_string = getattr(mobj, 'tex_string', None)
    if not tex_string or not font_size:
        return 0.0
    ratio = _BASELINE_DEPTH_RATIO_CACHE.get(tex_string)
    if ratio is None:
        try:
            probe = Tex(tex_string, ".", tex_template=RusTex)
            baseline_y = float(probe[1].get_corner(DOWN)[1])
            label_bottom = float(probe[0].get_corner(DOWN)[1])
            ratio = max(baseline_y - label_bottom, 0.0) / DEFAULT_FONT_SIZE
        except Exception:
            logger.debug("baseline probe failed for %r", tex_string, exc_info=True)
            ratio = 0.0
        _BASELINE_DEPTH_RATIO_CACHE[tex_string] = ratio
    return ratio * float(font_size)


def _place_label(mobj, elem, pos, edge, ptUnit, ptUnit_ggb, ggb_font_px,
                 label_offset_px, auto_placed, ggb_manual_base_px=None,
                 font_size=None, attach=None):
    """Apply anchor/offset/descender placement shared by Tex and ValueLabel."""
    if ggb_manual_base_px is not None:
        # GGB-faithful path for imported manual labels: the applet draws a
        # point label with its LEFT edge
        # on the BASELINE at (x + 4, y − 2·pointSize) + labelOffset screen px,
        # and the stored offset is relative to that base — so the style's
        # aesthetic anchor and the descender fudge below must not apply here.
        # Scale: ptUnit (= ptUnit_style at the call site), NOT ptUnit_ggb.
        # In GGB both the glyphs and the offset are screen px — their
        # proportion survives any zoom — so the offset must live in the same
        # pixel space as the font. Dividing by ptUnit_ggb shrank offsets with
        # the FIGURE while the font stayed at reference px; at low reference
        # density (style-editor preview: 480px canvas for an 1160px view)
        # labels swallowed their offsets and sat on their points.
        scale = ptUnit
        off = label_offset_px
        if off is None and hasParam(elem.style, 'label_offset_px'):
            off = elem.style['label_offset_px']
        off = off if off is not None else (0.0, 0.0)
        # Applet px from `pos` to the label's left/baseline, y up.
        rel = (ggb_manual_base_px[0] + float(off[0]), ggb_manual_base_px[1] + float(off[1]))
        depth = _label_baseline_depth_mu(mobj, font_size)
        w = float(mobj.width)
        h = float(mobj.height)
        g_px = float(ggb_font_px) if ggb_font_px else 16.0
        fs_px = (float(font_size) * float(ptUnit) / GGB_FONT_SCALE
                 if font_size and ptUnit else g_px)
        r = g_px / fs_px if fs_px > 1e-9 else 1.0

        # An element with extent: re-attach the label to the spot of the
        # element nearest to where the APPLET drew it. That spot is geometry —
        # it scales with the figure (ptUnit_ggb); only the rest of the offset
        # stays in font space, as for a point label. Replayed wholly in font
        # space, a label parked near a segment's endpoint drifted far past it
        # whenever the export drew the figure at another scale than the applet.
        # At the applet's own scale this is an identity.
        if attach is not None and ptUnit_ggb:
            g = float(ptUnit_ggb)
            w0_px, h0_px, d0_px = w * r * scale, h * r * scale, depth * r * scale
            center = (pos[0] + (rel[0] + w0_px / 2.0) / g,
                      pos[1] + (rel[1] - d0_px + h0_px / 2.0) / g)
            spot = attach(center)
            if spot is not None:
                rel = (rel[0] + (float(pos[0]) - float(spot[0])) * g,
                       rel[1] + (float(pos[1]) - float(spot[1])) * g)
                pos = [float(spot[0]), float(spot[1]), 0.0]

        # Left/baseline origin exactly as the applet showed it (native font).
        origin = (pos[0] + rel[0] / scale, pos[1] + rel[1] / scale)

        # Size-invariant anchoring: when the rendered font differs from the
        # applet's, anchoring at left/baseline lets the glyphs grow TOWARD the
        # point for labels dragged left/below (В at 48px swallowed its point).
        # Instead the label is anchored by the spot facing the point, so it
        # grows away and the visual gap survives any кегль. The anchor is the
        # PROJECTION of the point onto the native bbox: for an outside point
        # that pins the box's nearest face/corner, so the nearest distance is
        # preserved EXACTLY under scaling; a projection onto a convex box is
        # 1-Lipschitz in the box position, so an animated offset (including
        # one passing straight through the point) moves the label without
        # jumps — no sector quantisation, no hysteresis. At the native font
        # the whole scheme reduces to the applet placement identically.
        if w < 1e-9 or h < 1e-9:
            mobj.move_to([origin[0], origin[1], 0.0], aligned_edge=DL)
            if depth:
                mobj.shift([0.0, -depth, 0.0])
            return mobj

        # The box the applet user saw: our metrics scaled to the native font.
        w0, h0, depth0 = w * r, h * r, depth * r
        left0, bottom0 = origin[0], origin[1] - depth0
        ax = min(max(float(pos[0]), left0), left0 + w0)
        ay = min(max(float(pos[1]), bottom0), bottom0 + h0)
        fx = (ax - left0) / w0
        fy = (ay - bottom0) / h0
        # Place the rendered label so ITS (fx, fy) bbox point sits at (ax, ay).
        mobj.move_to([ax + (0.5 - fx) * w, ay + (0.5 - fy) * h, 0.0])
        return mobj

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


def _label_plain_text(label):
    """Strip math delimiters and escape what is left, so a label whose LaTeX
    does not compile can still be shown as readable plain text."""
    return mathify_text_symbols(latex_escape_text(label.replace('$', '').strip()))


def _compile_label_tex(label, col_label, font_size, zz_label, name):
    """Compile a label to ``Tex``, degrading rather than taking the element
    down with it: proper LaTeX → escaped plain text → no label at all.

    Mirrors the fallback ``_render_text`` already applies to free-text objects
    (``animageo.py``), which point/angle/segment labels used to lack: a failed
    label compile propagated out of ``CreateMObject`` and the marker vanished
    together with its label.
    """
    try:
        return (Tex(correctedLabel(label), color=col_label, tex_template=RusTex)
                .set_z_index(zz_label).set(font_size=font_size))
    except Exception as e:
        logger.warning("Label '%s': LaTeX compile failed (%s); "
                       "falling back to escaped plain text", name, e)

    plain = _label_plain_text(label)
    if plain:
        try:
            return (Tex(plain, color=col_label, tex_template=RusTex)
                    .set_z_index(zz_label).set(font_size=font_size))
        except Exception as e:
            logger.warning("Label '%s': plain-text fallback failed too (%s); "
                           "rendering the element without its label", name, e)
    return None


def create_label(elem, pos, col_label, font_size, zz_label, ptUnit, align_edge=DL,
                 ptUnit_ggb=None, anchor=None, ggb_font_px=None,
                 label_text=None, label_offset_px=None, auto_placed=None,
                 label_spec=None, dynamic=False, ggb_manual_base_px=None,
                 ggb_label_attach=None):
    """Create a label mobject for a geometric element.

    When ``dynamic`` is True and ``label_spec`` carries a live numeric value, a
    fast :class:`ValueLabel` (DecimalNumber-backed) is built so per-frame value
    changes don't trigger a LaTeX recompile; its digits are the text of the
    ``Tex`` label. Otherwise a plain ``Tex`` is used — the default for static
    export.

    Args:
        anchor: Label anchor point — which part of the label is placed at
            pos+offset. One of 'TL','TC','TR','ML','MC','MR','BL','BC','BR'
            or a manim direction vector. Default None = use align_edge (BL).
        ggb_font_px: GGB font size in pixels. When set, applies a vertical
            correction to compensate for GGB's text-field descender padding.
        label_spec: Optional ``LabelSpec`` enabling the fast value path.
        dynamic: Build a ``ValueLabel`` for value-bearing labels.
        ggb_manual_base_px: When set — ``(4, 2·pointSize)`` GGB base offset in
            applet px — the label takes the GGB-faithful path: left edge on
            the baseline at ``pos + (base + label_offset_px)/ptUnit_ggb``,
            ignoring ``anchor``/``align_edge`` and the descender correction.

    Returns:
        The label mobject, or ``None`` when its LaTeX could not be compiled at
        all — the caller then draws the element without a label rather than
        losing the geometry too.
    """
    edge = _resolve_label_edge(elem, anchor, align_edge)
    label = label_text if label_text is not None else elem.style.get('label_text', '$' + elem.name + '$')
    name = getattr(elem, 'name', '?')

    mobj = None
    if dynamic and label_spec is not None and label_spec.has_dynamic_value:
        try:
            mobj = ValueLabel(
                value=label_spec.value,
                prefix_tex=label_spec.prefix_tex,
                suffix_tex=label_spec.suffix_tex,
                suffix_raised=label_spec.suffix_raised,
                num_decimal_places=label_spec.num_decimal_places,
                strip_zeros=label_spec.strip_zeros,
                color=col_label, font_size=font_size, z_index=zz_label,
            )
        except Exception as e:
            logger.warning("Label '%s': fast value label failed (%s); "
                           "falling back to Tex", name, e)

    if mobj is None:
        mobj = _compile_label_tex(label, col_label, font_size, zz_label, name)
    if mobj is None:
        return None

    # Tag so bounds measurement can tell a label apart from geometry (the label is
    # a submobject of the element's VGroup). Used by rendered-bounds framing to
    # crop to the geometry only, without letting a label inflate the extent.
    mobj._animageo_is_label = True

    return _place_label(
        mobj, elem, pos, edge, ptUnit, ptUnit_ggb, ggb_font_px,
        label_offset_px, auto_placed,
        ggb_manual_base_px=ggb_manual_base_px, font_size=font_size,
        attach=ggb_label_attach,
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
        theader = Tex(textify_cyrillic(header), font_size=37, tex_template=RusTex,
                      color=scene.style.strong)
        theader.set_fill(color=scene.style.col)
        theader.move_to(pos, aligned_edge=LEFT + UP)
        pos += 0.7 * DOWN
        scene.play(FadeIn(theader))

    if body:
        tbody = Tex(textify_cyrillic(body), font_size=34, tex_template=RusTex,
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
