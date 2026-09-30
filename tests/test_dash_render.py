"""Dashes as a stroke property: one path with a pattern in style pixels.

Acceptance tests for the 1.7.10 dash pattern: the pattern follows
``ptUnit_style`` like line widths (not the zoom of the geometry), a dashed
stroke exports as a single ``<path stroke-dasharray=…>``, it is fitted to
finite paths, round caps keep the visible dash nominal, it survives
``updateGeoElements`` and reaches video frames through the scene camera.
"""
import math
import re
import textwrap
from unittest import mock

import numpy as np
import pytest

from animageo.animageo import AnimaGeoScene, DashCamera
from animageo.dash import dash_pattern, get_dash, path_length
from animageo.geo import construction as geo


W, H = 800, 600


def _scene(code, *, ptUnit=60, ptUnit_style=None, style=None, extra=None):
    """DSL scene on a deterministic ``W``x``H`` frame (origin at the centre),
    rebuilt at the final scale."""
    s = AnimaGeoScene()
    s.putCode(textwrap.dedent(code))
    if extra is not None:
        extra(s)
    kwargs = dict(export={"size": {"width": W, "height": H}})
    if style is not None:
        kwargs["style"] = style
    s.applyStyle(**kwargs)
    exp = s.style.export
    exp.update(ptUnit=ptUnit, ptUnit_style=ptUnit_style or ptUnit, ptUnit_ggb=ptUnit,
               ptWidth=W, ptHeight=H, ptXZero=W / 2, ptYZero=H / 2)
    s._set_camera_from_export(exp)
    s.updateAllGeometry()
    return s


def _dashed_paths(scene, tmp_path):
    out = scene.exportSVG(str(tmp_path / "out.svg"))
    tags = re.findall(r"<path\b[^>]*>", open(out).read())
    return [t for t in tags if "stroke-dasharray" in t]


def _px(tag):
    """(dash, gap, stroke width) of a cairo SVG path tag, in output px."""
    nums = re.search(r'stroke-dasharray="([^"]*)"', tag).group(1)
    dash, gap = (float(x) for x in re.split(r"[ ,]+", nums.strip())[:2])
    width = float(re.search(r'stroke-width="([^"]*)"', tag).group(1))
    m = re.search(r'transform="matrix\(([^,]+),', tag)
    k = abs(float(m.group(1))) if m else 1.0
    return dash * k, gap * k, width * k


def _stroke(scene, name):
    """The dashed stroke sub-mobject of element ``name``."""
    subs = [m for m in scene.mobject(name).get_family() if get_dash(m) is not None]
    assert len(subs) == 1, subs
    return subs[0]


POINTS = "A = Point(-2, -1)\nB = Point(2, 1)\nM = Point(0, 1)\n"

ONE_PATH = {
    "segment":  "x = Segment(A, B)",
    "line":     "x = Line(A, B)",
    "ray":      "x = Ray(A, B)",
    "vector":   "x = Vector(A, B)",
    "circle":   "x = Circle(M, 2)",
    "arc":      "x = CircleArc(M, B, A)",
    "ellipse":  'x = Conic("x^2/9 + y^2/4 = 1")',
    "parabola": 'x = Conic("y = 0.25*x^2 - 2")',
    "function": 'x = Function("y = 0.2*x^2 - 2")',
    "implicit": 'x = ImplicitCurve("x^2 + y^2 = 4")',
}


class TestOnePath:
    @pytest.mark.parametrize("kind", sorted(ONE_PATH))
    def test_single_dashed_path(self, kind, tmp_path):
        s = _scene(POINTS + ONE_PATH[kind] + "\nx.style.stroke_dash_ratio = 0.65")
        tags = _dashed_paths(s, tmp_path)
        assert len(tags) == 1, (kind, len(tags))
        dash, gap, width = _px(tags[0])
        assert dash / gap == pytest.approx(0.65 / 0.35, rel=1e-3)

    def test_hyperbola_one_path_per_branch(self, tmp_path):
        s = _scene('x = Conic("x^2 - y^2 = 1")\nx.style.stroke_dash_ratio = 0.5')
        assert len(_dashed_paths(s, tmp_path)) == 2

    def test_locus(self, tmp_path):
        t = np.linspace(0, 2 * np.pi, 200)
        pts = np.c_[2 * np.cos(t), np.sin(t)]

        def add(s):
            el = geo.Element("loc", geo.LocusCurve(pts))
            el.style["stroke_dash_ratio"] = 0.5
            s.geo.add(el)

        s = _scene("A = Point(5, 5)", extra=add)
        assert len(_dashed_paths(s, tmp_path)) == 1

    def test_vector_keeps_solid_tip(self, tmp_path):
        s = _scene(POINTS + ONE_PATH["vector"] + "\nx.style.stroke_dash_ratio = 0.65")
        arrow = _stroke(s, "x")
        tip = arrow.tip
        assert len(tip.points) and get_dash(tip) is None
        assert tip.get_fill_opacity() > 0

    def test_solid_stays_undashed(self, tmp_path):
        s = _scene(POINTS + ONE_PATH["circle"])
        assert _dashed_paths(s, tmp_path) == []

    @pytest.mark.parametrize("ratio", [0, 1, 1.5, -0.2])
    def test_out_of_range_ratio_is_solid(self, ratio, tmp_path):
        s = _scene(POINTS + f"x = Line(A, B)\nx.style.stroke_dash_ratio = {ratio}")
        assert _dashed_paths(s, tmp_path) == []


class TestPixelInvariance:
    CODE = POINTS + "x = Line(A, B)\nx.style.stroke_dash_ratio = 0.65\n" \
                    "y = Segment(A, B)\ny.style.stroke_dash_ratio = 0.65"

    def _px_of(self, tmp_path, **kw):
        s = _scene(self.CODE, **kw)
        line = _px([t for t in _dashed_paths(s, tmp_path)][0])
        return s, line

    def test_applet_zoom_keeps_px(self, tmp_path):
        # Applet zoom ×2: geometry scale and style base both double
        # (TZ measurement: ptUnit = ptUnit_style 45 → 90).
        _, a = self._px_of(tmp_path, ptUnit=45)
        _, b = self._px_of(tmp_path, ptUnit=90)
        # (cairo writes SVG numbers with 6 significant digits)
        assert a == pytest.approx((6.5, 3.5, 1.5), rel=1e-4)
        assert b == pytest.approx(a, rel=1e-4)

    def test_segment_within_fit(self, tmp_path):
        for pu in (45, 90):
            s = _scene(self.CODE, ptUnit=pu)
            seg = _stroke(s, "y")
            assert seg is not None
            dash_px = get_dash(seg).on * pu
            assert dash_px == pytest.approx(6.5, rel=0.25)

    def test_dash_scales_like_width(self, tmp_path):
        # Same style base, geometry ×2: dash and width both double.
        _, a = self._px_of(tmp_path, ptUnit=45, ptUnit_style=45)
        _, b = self._px_of(tmp_path, ptUnit=90, ptUnit_style=45)
        assert b == pytest.approx(tuple(2 * v for v in a), rel=1e-4)

    def test_prominence_doubles_dash_with_width(self, tmp_path):
        # "Крупность" 2: ptUnit_style halves, decorations double.
        _, a = self._px_of(tmp_path, ptUnit=60, ptUnit_style=60)
        _, b = self._px_of(tmp_path, ptUnit=60, ptUnit_style=30)
        assert b == pytest.approx((13.0, 7.0, 3.0), rel=1e-4)
        assert b == pytest.approx(tuple(2 * v for v in a), rel=1e-4)


class TestFit:
    def test_segment_both_ends_are_dashes(self):
        s = _scene(POINTS + "x = Segment(A, B)\nx.style.stroke_dash_ratio = 0.65")
        seg = _stroke(s, "x")
        pat = get_dash(seg)
        L = float(np.linalg.norm(np.array([4.0, 2.0])))
        n = round((L + pat.off) / pat.period)
        assert n * pat.on + (n - 1) * pat.off == pytest.approx(L, abs=1e-6)
        assert pat.offset == 0.0

    def test_circle_whole_periods(self):
        s = _scene(POINTS + "x = Circle(M, 2)\nx.style.stroke_dash_ratio = 0.5")
        pat = get_dash(_stroke(s, "x"))
        k = (2 * math.pi * 2) / pat.period
        assert k == pytest.approx(round(k), rel=1e-3)

    def test_ellipse_whole_periods_on_its_own_path(self):
        s = _scene('x = Conic("x^2/9 + y^2/4 = 1")\nx.style.stroke_dash_ratio = 0.5')
        ell = _stroke(s, "x")
        k = path_length(ell.points) / get_dash(ell).period
        assert k == pytest.approx(round(k), abs=1e-9)

    def test_ray_anchored_at_clipped_vertex(self):
        # Vertex far left of the canvas: the pattern phase is the clipped-off
        # distance, so dashes still start at the vertex.
        s = _scene("A = Point(-30, 0)\nB = Point(-29, 0)\n"
                   "x = Ray(A, B)\nx.style.stroke_dash_ratio = 0.5")
        ray = _stroke(s, "x")
        start = ray.points[0][:2]
        dist = float(np.linalg.norm(start - np.array([-30.0, 0.0])))
        pat = get_dash(ray)
        assert pat.offset == pytest.approx(dist % pat.period, abs=1e-9)
        assert start[0] < ray.points[-1][0]          # runs away from the vertex


class TestCaps:
    def test_round_cap_visible_dash_is_nominal(self):
        code = POINTS + ("x = Segment(A, B)\nx.style.stroke_dash_ratio = 0.65\n"
                         "x.style.stroke_linecap = 'round'\nx.style.stroke_width_px = 3")
        s = _scene(code)
        seg = _stroke(s, "x")
        pat = get_dash(seg)
        w = seg.get_stroke_width() * 0.01
        L = float(np.linalg.norm(np.array([4.0, 2.0])))
        nominal = dash_pattern(L, 6.5 / 60, 3.5 / 60, fit_ends=True)
        assert pat.on + w == pytest.approx(nominal.on)
        assert pat.period == pytest.approx(nominal.period)

    def test_butt_cap_unchanged(self):
        s = _scene(POINTS + "x = Line(A, B)\nx.style.stroke_dash_ratio = 0.65")
        pat = get_dash(_stroke(s, "x"))
        assert pat.on == pytest.approx(6.5 / 60) and pat.offset == 0.0


class TestStylePeriod:
    CODE = POINTS + "x = Line(A, B)\nx.style.stroke_dash_ratio = 0.5"

    def _on_px(self, style=None, elem_period=None):
        code = self.CODE
        if elem_period is not None:
            code += f"\nx.style.stroke_dash_period_px = {elem_period}"
        s = _scene(code, style=style)
        return get_dash(_stroke(s, "x")).on * 60

    def test_default_period_is_10(self):
        assert self._on_px() == pytest.approx(5.0)

    def test_rendering_period(self):
        assert self._on_px({"rendering": {"dash_period_px": 20}}) == pytest.approx(10.0)

    def test_defaults_period(self):
        style = {"rendering": {"dash_period_px": 20},
                 "defaults": {"line": {"stroke_dash_period_px": 16}}}
        assert self._on_px(style) == pytest.approx(8.0)

    def test_overlay_per_name_period(self):
        style = {"defaults": {"line": {"stroke_dash_period_px": 16}},
                 "overlay": {"per_name": {"x": {"stroke_dash_period_px": 30}}}}
        assert self._on_px(style) == pytest.approx(15.0)

    def test_element_style_wins(self):
        style = {"overlay": {"per_name": {"x": {"stroke_dash_period_px": 30}}}}
        assert self._on_px(style, elem_period=6) == pytest.approx(3.0)

    @pytest.mark.parametrize("bad", ["0", "-4", "'abc'"])
    def test_invalid_period_falls_back(self, bad):
        style = {"rendering": {"dash_period_px": 20}}
        assert self._on_px(style, elem_period=bad) == pytest.approx(10.0)


class TestAnimation:
    CODE = POINTS + "x = Segment(A, B)\nc = Circle(M, 2)"

    def test_solid_dashed_solid_through_update(self):
        s = _scene(self.CODE)
        mobj = s.mobject("x")
        elem = s.geo.element("x")
        assert all(get_dash(m) is None for m in mobj.get_family())

        elem.style["stroke_dash_ratio"] = 0.65
        s.updateGeoElements(["x"])
        assert s.mobject("x") is mobj                  # become(), same mobject
        dashed = [m for m in mobj.get_family() if get_dash(m) is not None]
        assert len(dashed) == 1

        elem.style["stroke_dash_period_px"] = 20
        s.updateGeoElements(["x"])
        (stroke,) = [m for m in mobj.get_family() if get_dash(m) is not None]
        assert get_dash(stroke).period * 60 == pytest.approx(20, rel=0.25)

        elem.style["stroke_dash_ratio"] = None
        s.updateGeoElements(["x"])
        assert all(get_dash(m) is None for m in mobj.get_family())

    def test_cap_style_follows_update(self):
        from manim import CapStyleType
        s = _scene(self.CODE)
        elem = s.geo.element("x")
        elem.style["stroke_linecap"] = "round"
        s.updateGeoElements(["x"])
        line = s.mobject("x")[0]
        assert line.cap_style == CapStyleType.ROUND

    def test_keyframe_period_track_lerps_from_rendering_default(self):
        s = _scene(self.CODE + "\nx.style.stroke_dash_ratio = 0.5")
        kf = {"version": 2, "keyframes": [
            {"t": 0},
            {"t": 2, "styles": {"x": {"stroke_dash_period_px": 30}}, "easing": "linear"},
        ]}
        s.apply_keyframes_at(kf, 1.0)
        assert s.geo.element("x").style["stroke_dash_period_px"] == pytest.approx(20.0)

    def test_partial_reveal_keeps_pattern(self):
        s = _scene(self.CODE + "\nc.style.stroke_dash_ratio = 0.5")
        mobj = s.mobject("c")
        before = get_dash(_stroke(s, "c"))
        s._effect_partial(mobj, 0.4)
        assert get_dash(_stroke(s, "c")) == before


class TestVideoCamera:
    CODE = ("A = Point(-4, 0)\nB = Point(4, 0)\nx = Segment(A, B)\n"
            "x.style.stroke_width_px = 4\nA.style.visible = False\nB.style.visible = False")

    def _row(self, dashed):
        code = self.CODE + ("\nx.style.stroke_dash_ratio = 0.5" if dashed else "")
        s = _scene(code)
        assert isinstance(s.camera, DashCamera)
        s.camera.reset()
        s.camera.capture_mobjects(s.mobjects)
        px = s.camera.pixel_array
        h, w = px.shape[:2]
        row = px[h // 2, int(w * 0.35): int(w * 0.65), :3].mean(axis=1)  # inside the line
        return row < 128                                         # dark = ink

    @staticmethod
    def _runs(ink):
        return int(np.count_nonzero(np.diff(ink.astype(int)) == 1))

    def test_dashed_frame_has_gaps(self):
        solid = self._row(dashed=False)
        dashed = self._row(dashed=True)
        assert solid.all()
        assert 0.3 < dashed.mean() < 0.7
        assert self._runs(dashed) >= 5

    def test_camera_sets_and_resets_dash(self):
        s = _scene(self.CODE + "\nx.style.stroke_dash_ratio = 0.5")
        stroke = _stroke(s, "x")
        ctx = mock.MagicMock()
        s.camera.apply_stroke(ctx, stroke)
        pat = get_dash(stroke)
        names = [c[0] for c in ctx.method_calls]
        i_set = names.index("set_dash")
        assert ctx.method_calls[i_set] == mock.call.set_dash([pat.on, pat.off], pat.offset)
        assert names.index("stroke_preserve") > i_set
        assert ctx.method_calls[-1] == mock.call.set_dash([])


class TestTikZ:
    def test_pattern_from_style_px(self):
        s = _scene(POINTS + "x = Line(A, B)\nx.style.stroke_dash_ratio = 0.65\n"
                            "x.style.stroke_dash_period_px = 20")
        tex = s.exportTikZ()
        m = re.search(r"dash pattern=on ([\d.]+)pt off ([\d.]+)pt", tex)
        on, off = float(m.group(1)), float(m.group(2))
        # px → pt at the default 96 dpi: 0.75 pt per px
        assert on == pytest.approx(13 * 0.75, abs=0.01)
        assert off == pytest.approx(7 * 0.75, abs=0.01)
        assert "dash phase" not in tex

    def test_round_cap_compensated(self):
        s = _scene(POINTS + "x = Line(A, B)\nx.style.stroke_dash_ratio = 0.65\n"
                            "x.style.stroke_linecap = 'round'\nx.style.stroke_width_px = 2")
        tex = s.exportTikZ()
        m = re.search(r"dash pattern=on ([\d.]+)pt off ([\d.]+)pt, dash phase=([\d.]+)pt", tex)
        on, off, phase = (float(g) for g in m.groups())
        assert on + 2 * 0.75 == pytest.approx(6.5 * 0.75, abs=0.01)
        assert on + off == pytest.approx(10 * 0.75, abs=0.01)
        assert phase == pytest.approx(10 * 0.75 - 0.75, abs=0.01)
