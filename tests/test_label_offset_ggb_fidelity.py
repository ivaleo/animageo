"""Manual GGB label offsets must reproduce the applet's label positions.

Spec: docs/TZ-label-offset-ggb-fidelity.md. GeoGebra draws a point label at
``(x + 4, y - 2*pointSize) + labelOffset`` in screen px (y down), where the
position is the text's LEFT edge at its BASELINE. These tests check the
renderer against that formula on a real .ggb captured from the bug report
(six points with hand-dragged labels).
"""
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pytest

from animageo.animageo import AnimaGeoScene

FIXTURE = Path(__file__).parent / "fixtures" / "label_offset_points.ggb"

GGB_SCALE = 50.0   # px per MU in the fixture's euclidianView
GGB_PS = 5.0       # <pointSize val="5"/> on every fixture point

# <labelOffset x= y=> from the fixture XML (screen px, y down)
XML_OFFSETS = {
    "В": (-11, 34), "Г": (-20, -2), "Д": (2, 1),
    "Е": (-18, 30), "А": (-6, -4), "Б": (-11, 34),
}

X_TOL_MU = 2.0 / GGB_SCALE    # left-side-bearing slack (≤2 applet px)
Y_TOL_MU = 0.5 / GGB_SCALE    # baseline must be near-exact (≤0.5 applet px)


def _expected_origin(pt, offset):
    """GGB label origin (left edge, baseline) in math MU, y up."""
    offx, offy = offset
    return (
        float(pt[0]) + (4.0 + offx) / GGB_SCALE,
        float(pt[1]) + (2.0 * GGB_PS - offy) / GGB_SCALE,
    )


def _load_scene(ggb_path, style=None):
    scene = AnimaGeoScene()
    kwargs = {"generate_stubs": False}
    if style is not None:
        kwargs["style"] = style
    scene.loadGGB(str(ggb_path), **kwargs)
    return scene


def _label_bbox(scene, name):
    """(left, bottom, right, top) of the rendered label mobject, scene MU."""
    elem = scene.element(name)
    mobj = scene.CreateMObject(elem, z_auto=True)
    assert mobj is not None, f"element {name} did not render"
    subs = list(mobj)
    assert len(subs) >= 2, f"no label mobject rendered for point {name}"
    label = subs[1]
    ul = label.get_corner(np.array([-1.0, 1.0, 0.0]))
    dr = label.get_corner(np.array([1.0, -1.0, 0.0]))
    return float(ul[0]), float(dr[1]), float(dr[0]), float(ul[1])


class TestManualOffsetRoundtrip:
    """TZ §6.1: label origin == GGB formula for every hand-placed label."""

    @pytest.mark.parametrize("name", sorted(XML_OFFSETS))
    def test_label_origin_matches_geogebra(self, name):
        scene = _load_scene(FIXTURE)
        elem = scene.element(name)
        exp_x, exp_y = _expected_origin(elem.data.coords, XML_OFFSETS[name])
        left, bottom, _, _ = _label_bbox(scene, name)

        assert left == pytest.approx(exp_x, abs=X_TOL_MU), (
            f"{name}: left edge {left:.4f} != expected {exp_x:.4f} "
            f"(err {abs(left - exp_x) * GGB_SCALE:.1f} applet px)"
        )
        # Cyrillic capitals of this fixture sit on the baseline (no descender)
        # except Д, whose tail legs extend below it.
        if name != "Д":
            assert bottom == pytest.approx(exp_y, abs=Y_TOL_MU), (
                f"{name}: baseline {bottom:.4f} != expected {exp_y:.4f} "
                f"(err {abs(bottom - exp_y) * GGB_SCALE:.1f} applet px)"
            )

    def test_style_label_anchor_does_not_move_manual_labels(self, tmp_path):
        """TZ §4.4: rendering.label_anchor (web default 'BC') must not apply
        to GGB-imported manual labels."""
        style_path = tmp_path / "style.json"
        style_path.write_text('{"rendering": {"label_anchor": "BC"}}')

        plain = {n: _label_bbox(_load_scene(FIXTURE), n) for n in ("В", "Д")}
        styled = {
            n: _label_bbox(_load_scene(FIXTURE, style=str(style_path)), n)
            for n in ("В", "Д")
        }
        for name in plain:
            assert styled[name] == pytest.approx(plain[name], abs=1e-6), (
                f"{name}: 'BC' style anchor moved a manual label"
            )


class TestUntouchedLabel:
    """TZ §6.2: a point whose label was never dragged sits up-right of the
    point at the GGB default position (x+4, y-2*ps), not centred above it."""

    def test_default_position_up_right(self, tmp_path):
        stripped = tmp_path / "no_offset.ggb"
        with zipfile.ZipFile(FIXTURE) as zin, \
                zipfile.ZipFile(stripped, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "geogebra.xml":
                    xml = data.decode("utf-8")
                    xml = xml.replace('\t<labelOffset x="-11" y="34"/>\n', "", 1)
                    data = xml.encode("utf-8")
                zout.writestr(item, data)

        scene = _load_scene(stripped)
        elem = scene.element("В")   # first element in the XML — offset removed
        assert "label_offset_px" not in (getattr(elem, "ggb_raw", {}) or {}), (
            "fixture edit failed: В still carries a labelOffset"
        )
        exp_x, exp_y = _expected_origin(elem.data.coords, (0, 0))
        left, bottom, _, _ = _label_bbox(scene, "В")

        assert left == pytest.approx(exp_x, abs=X_TOL_MU)
        assert bottom == pytest.approx(exp_y, abs=Y_TOL_MU)


class TestBaselineAlignment:
    """TZ §6.3: glyphs with different descender depths must share a baseline.

    With identical offsets, А (no tail) and Д (tail below the baseline) must
    be TOP-aligned (equal cap height above a shared baseline); anchoring by
    tight-bbox bottom instead lifts Д by its tail depth.
    """

    def test_deep_glyph_shares_baseline(self):
        scene = _load_scene(FIXTURE)
        for name in ("А", "Д"):
            scene.element(name).style["label_offset_px"] = [0.0, 0.0]

        boxes = {n: _label_bbox(scene, n) for n in ("А", "Д")}
        pts = {n: scene.element(n).data.coords for n in ("А", "Д")}

        top_rel = {n: boxes[n][3] - float(pts[n][1]) for n in boxes}
        assert top_rel["А"] == pytest.approx(top_rel["Д"], abs=1.0 / GGB_SCALE), (
            "А and Д are not top-aligned: Д is anchored by its bbox bottom, "
            "so its below-baseline tail lifts the letter body"
        )

        bottom_rel = {n: boxes[n][1] - float(pts[n][1]) for n in boxes}
        assert bottom_rel["Д"] < bottom_rel["А"] - 0.1 / GGB_SCALE, (
            "Д's tail should extend below the shared baseline"
        )


# ── Part 2: auto-placement must not discard the manual side (TZ §5.3) ──

import json


def _autoplace_style(tmp_path, **lp_overrides):
    """Style JSON enabling the web's recommended auto-placement preset."""
    lp = {
        "enabled": True,
        "respect_current_position": True,
        "respect_min_offset_px": 6.0,
        "point_bisector": True,
        "compact_labels": True,
        "compact_max_push_px": 4,
        "continuous_placement": True,
        "continuous_steps": 72,
        "canonicalize_anchor": True,
        "declutter_labels": True,
        "cluster_consistency": True,
        "repair_iterations": 6,
        "distance_px": 7,
        "padding_px": 2,
        "w_assoc": 3,
        "viewport_clamp": True,
    }
    lp.update(lp_overrides)
    path = tmp_path / "autoplace_style.json"
    path.write_text(json.dumps({"overlay": {"label_placement": lp}}))
    return str(path)


def _visual_dir(scene, name):
    """Unit direction of the label's visual centre relative to its point."""
    elem = scene.element(name)
    off = elem.style.get("label_offset_px")
    assert off is not None, f"{name}: no placed offset"
    v = np.array([float(off[0]), float(off[1])])
    n = np.linalg.norm(v)
    assert n > 1e-9, f"{name}: zero offset"
    return v / n


def _manual_visual_dir(scene, name):
    """Unit direction the label visually had in the applet (GGB semantics):
    raw offset + GGB base (4, 2*pointSize), y flipped to math-up."""
    elem = scene.element(name)
    raw = (getattr(elem, "ggb_raw", {}) or {})["label_offset_px"]
    ps = float((getattr(elem, "ggb_raw", {}) or {}).get("point_size", 5.0))
    v = np.array([raw[0] + 4.0, -raw[1] + 2.0 * ps])
    return v / np.linalg.norm(v)


class TestAutoplaceKeepsManualSide:
    """TZ §5.3: with respect_current_position, a hand-placed point label must
    stay on its manual side — not flip across the point (В/Б went bottom-left
    → bottom-right; Е drifted 43° off its manual direction)."""

    MAX_DEV_DEG = 30.0

    def _assert_sides(self, scene, tag):
        limit = np.cos(np.radians(self.MAX_DEV_DEG))
        for name in ("В", "Б", "Е"):
            got = _visual_dir(scene, name)
            want = _manual_visual_dir(scene, name)
            dev = np.degrees(np.arccos(np.clip(np.dot(got, want), -1, 1)))
            assert float(np.dot(got, want)) >= limit, (
                f"{tag}: {name} placed {dev:.0f}° away from its manual side "
                f"(dir {got.round(2)} vs manual {want.round(2)})"
            )

    def test_single_placement_run(self, tmp_path):
        scene = _load_scene(FIXTURE, style=_autoplace_style(tmp_path))
        self._assert_sides(scene, "run 1")

    def test_second_run_is_idempotent(self, tmp_path):
        """The web loads a scene twice (rendered-bounds auto config); the second
        placement pass must not lose the manual-intent signal recorded in
        ggb_raw and re-solve from scratch."""
        scene = _load_scene(FIXTURE, style=_autoplace_style(tmp_path))
        scene.autoPlaceLabels()
        self._assert_sides(scene, "run 2")


class TestAutoplaceEvenness:
    """TZ §5.1/5.2 (§6.4): with zeroed distances the point→label-bbox gap must
    be near-uniform across the six points (was 7–13 px: the arc registered as
    its FULL circle pushed В out, and Д's tail inflated its bbox)."""

    def test_gap_spread_at_zero_distance(self, tmp_path):
        style = _autoplace_style(
            tmp_path, distance_px=0, padding_px=0,
            geom_gap_px=0.0, angle_gap_arc_px=0, angle_gap_sides_px=2,
        )
        scene = _load_scene(FIXTURE, style=style)
        pt_unit = float(scene.style.export.get("ptUnit_style")
                        or scene.style.export.get("ptUnit"))
        gaps = {}
        for name in XML_OFFSETS:
            left, bottom, right, top = _label_bbox(scene, name)
            px, py = (float(c) for c in scene.element(name).data.coords[:2])
            dx = max(left - px, 0.0, px - right)
            dy = max(bottom - py, 0.0, py - top)
            gaps[name] = (dx * dx + dy * dy) ** 0.5 * pt_unit
        spread = max(gaps.values()) - min(gaps.values())
        # ≤ 2 px per the TZ; +0.5 px slack for the solver's 1-px step grid.
        assert spread <= 2.5, f"gap spread {spread:.1f}px: {gaps}"


class TestArcObstacleIsNotFullCircle:
    """The phantom part of an arc's circle must not act as an obstacle: В sits
    at the arc's endpoint, and the label space past the endpoint is free."""

    def test_arc_registers_as_polyline_segments(self):
        from animageo import label_placement as lp

        scene = _load_scene(FIXTURE)
        segments, circles, arc_pts, seg_dashed, circ_dashed = (
            lp._collect_obstacles(scene))
        assert circles == [], "arc leaked into obstacles as a full circle"
        # 5 straight segments (f, g, h, i, k) + the sampled arc polyline
        assert len(segments) > 5, "arc polyline missing from segment obstacles"


class TestOffsetDensityInvariance:
    """Manual offsets must live in the same pixel space as the font.

    GGB draws both the label glyphs and the labelOffset in screen px — their
    proportion survives any zoom. The style-editor preview renders the source
    view into a 480px reference (density 20.7 px/MU vs the applet's 50), and
    dividing offsets by ptUnit_ggb shrank them with the FIGURE while the font
    stayed at reference px: labels swallowed their offsets and sat on their
    points. Offsets must divide by ptUnit_style, like every decoration px.
    """

    def test_offset_in_style_px_at_low_density(self, tmp_path):
        style_path = tmp_path / "ref480.json"
        style_path.write_text(json.dumps({
            "reference": {"size": {"width": 480, "height": "auto"},
                          "source": "source_view"},
        }))
        scene = _load_scene(FIXTURE, style=str(style_path))
        u = float(scene.style.export.get("ptUnit_style"))
        assert u < 25, f"reference did not downscale the view (ptUnit_style={u})"

        for name in ("В", "Б"):
            offx, offy = XML_OFFSETS[name]
            left, bottom, _, _ = _label_bbox(scene, name)
            px, py = (float(c) for c in scene.element(name).data.coords[:2])
            got = ((left - px) * u, (bottom - py) * u)
            want = (4.0 + offx, 2.0 * GGB_PS - offy)
            assert got == pytest.approx(want, abs=1.0), (
                f"{name}: label origin {got[0]:.1f},{got[1]:.1f} style-px from "
                f"the point; applet proportion demands {want[0]:.1f},{want[1]:.1f}"
            )


# ── Size-invariant anchoring: gap survives font changes, continuously ──

def _font_style(tmp_path, font_px, tag=""):
    path = tmp_path / f"font_{font_px}{tag}.json"
    path.write_text(json.dumps(
        {"overlay": {"per_type": {"point": {"font_size_px": font_px}}}}))
    return str(path)


def _point_label_gap_px(scene, name):
    """Nearest distance point→label bbox in style px (0 = touching/overlap)."""
    left, bottom, right, top = _label_bbox(scene, name)
    px, py = (float(c) for c in scene.element(name).data.coords[:2])
    dx = max(left - px, 0.0, px - right)
    dy = max(bottom - py, 0.0, py - top)
    u = float(scene.style.export.get("ptUnit_style")
              or scene.style.export.get("ptUnit"))
    return (dx * dx + dy * dy) ** 0.5 * u


class TestSizeInvariantAnchoring:
    """A manual label keeps its visual gap to the point when the font size
    (кегль) changes: the label must grow AWAY from the point, anchored by the
    side facing it — for every direction around the point, not just the
    GGB-natural up-right one."""

    # label_offset_px (math-up, style convention), ~40 px in all 8 sectors
    DIRS = {
        "E": (40, 0), "NE": (28, 28), "N": (0, 40), "NW": (-32, 28),
        "W": (-44, 0), "SW": (-32, -28), "S": (0, -44), "SE": (28, -28),
    }

    @pytest.mark.parametrize("dname", sorted(DIRS))
    def test_gap_survives_font_scaling(self, tmp_path, dname):
        gaps = {}
        for font in (16, 48):
            scene = _load_scene(FIXTURE, style=_font_style(tmp_path, font, dname))
            scene.element("В").style["label_offset_px"] = list(self.DIRS[dname])
            gaps[font] = _point_label_gap_px(scene, "В")
        assert gaps[16] > 3.0, f"{dname}: bad testcase, no native gap"
        assert gaps[48] == pytest.approx(gaps[16], abs=1.5), (
            f"{dname}: gap {gaps[16]:.1f}px at 16px font became "
            f"{gaps[48]:.1f}px at 48px font"
        )

    def _label_center(self, scene, name):
        left, bottom, right, top = _label_bbox(scene, name)
        return np.array([(left + right) / 2.0, (bottom + top) / 2.0])

    def _max_step(self, scene, name, offsets_fn, n):
        u = float(scene.style.export.get("ptUnit_style"))
        elem = scene.element(name)
        centers = []
        for k in range(n + 1):
            elem.style["label_offset_px"] = offsets_fn(k / n)
            centers.append(self._label_center(scene, name))
        return max(float(np.linalg.norm(centers[i + 1] - centers[i])) * u
                   for i in range(n))

    def _assert_continuous(self, scene, offsets_fn):
        """True continuity criterion: halving the animation step must halve the
        largest per-step movement. A genuine jump (e.g. a quantized-anchor
        flip at a sector boundary) keeps its size no matter how finely the
        offset is interpolated; smooth motion — even lever-amplified while the
        near face slides past the point — scales down linearly."""
        coarse = self._max_step(scene, "В", offsets_fn, 48)
        fine = self._max_step(scene, "В", offsets_fn, 96)
        assert fine <= 0.65 * coarse + 0.3, (
            f"jump detected: max step {coarse:.1f}px stays {fine:.1f}px "
            f"after halving the animation step"
        )

    def test_orbit_animation_has_no_jumps(self, tmp_path):
        """Sweeping the offset around the point at a non-native font must move
        the label without discontinuities (all anchor sides are traversed)."""
        scene = _load_scene(FIXTURE, style=_font_style(tmp_path, 48))
        self._assert_continuous(
            scene,
            lambda t: [45.0 * np.cos(2 * np.pi * t),
                       45.0 * np.sin(2 * np.pi * t)],
        )

    def test_pass_through_point_has_no_jumps(self, tmp_path):
        """An offset animating THROUGH the anchor point (direction flips, the
        point crosses the label bbox) must move the label smoothly too."""
        scene = _load_scene(FIXTURE, style=_font_style(tmp_path, 48, "p"))
        self._assert_continuous(
            scene,
            lambda t: [-60 + 120 * t - 4.0, -20 + 40 * t - 10.0],
        )


# ── Clearance beats respect (TZ §5.3 addendum) ─────────────────────────

def _dragged_fixture(tmp_path):
    """Fixture with А's label dragged down ALONG segment k toward Б, and Б's
    dragged up along k toward А — the collinear case where a radial
    clear-push can never escape the line."""
    out = tmp_path / "dragged.ggb"
    with zipfile.ZipFile(FIXTURE) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "geogebra.xml":
                xml = data.decode()
                xml = xml.replace('<labelOffset x="-6" y="-4"/>',
                                  '<labelOffset x="45" y="80"/>', 1)
                xml = xml.replace(
                    '<labelOffset x="-11" y="34"/>\n\t<labelMode val="0"/>'
                    '\n\t<animation step="0.1" type="1" playing="false"/>'
                    '\n\t<pointSize val="5"/>\n\t<pointStyle val="0"/>'
                    '\n\t<coords x="-2.3" y="-0.1" z="1"/>',
                    '<labelOffset x="-55" y="-75"/>\n\t<labelMode val="0"/>'
                    '\n\t<animation step="0.1" type="1" playing="false"/>'
                    '\n\t<pointSize val="5"/>\n\t<pointStyle val="0"/>'
                    '\n\t<coords x="-2.3" y="-0.1" z="1"/>', 1)
                data = xml.encode()
            zout.writestr(item, data)
    return out


def _segment_bbox_overlap_px(scene, name):
    """Exact total segment length inside the label bbox, in style pixels."""
    from animageo.geo import lib_elements as geo_mod
    from animageo.label_placement import _segment_bbox_overlap

    left, bottom, right, top = _label_bbox(scene, name)
    cx, cy = (left + right) / 2, (bottom + top) / 2
    half_w, half_h = (right - left) / 2, (top - bottom) / 2
    u = float(scene.style.export.get("ptUnit_style")
              or scene.style.export.get("ptUnit"))
    overlap = 0.0
    for elem in scene.geo.elements:
        if not isinstance(elem.data, geo_mod.Segment):
            continue
        p1, p2 = elem.data.endpoints[0][:2], elem.data.endpoints[1][:2]
        overlap += _segment_bbox_overlap(
            p1, p2, cx, cy, half_w, half_h) * u
    return overlap


class TestClearanceBeatsRespect:
    """«Не налезать на линии» is a hard constraint; «уважать ручной сдвиг»
    is a preference. A manual position that cannot be kept without overlap
    (dragged collinearly along the label's own segment) must yield: the
    label is placed clear of geometry like an unrespected label."""

    def test_collinear_dragged_labels_stay_clear_of_lines(self, tmp_path):
        ggb = _dragged_fixture(tmp_path)
        style = _autoplace_style(
            tmp_path, distance_px=0, padding_px=0, geom_gap_px=0.0,
            angle_gap_arc_px=0, angle_gap_sides_px=2,
            w_anchor=0.5, w_label=10, w_geom=2,
            compact_gap_px=1, overlap_tol_px=2.5,
            label_gap_px=2.5, angle_marker_obstacle=True,
            dashed_overlap_factor=0.3,
            angle_label_max_arm_fraction=0.45,
        )
        scene = _load_scene(ggb, style=style)
        for name in ("А", "Б"):
            overlap = _segment_bbox_overlap_px(scene, name)
            assert overlap <= 1e-6, (
                f"{name}: {overlap:.1f}px of segment runs through the label "
                "bbox although "
                f"clear space exists — respect must yield to clearance"
            )

    def test_clear_manual_positions_still_respected(self, tmp_path):
        """Control: the untouched fixture's В keeps its manual side (regression
        guard that the clearance override does not disable respect)."""
        style = _autoplace_style(tmp_path)
        scene = _load_scene(FIXTURE, style=style)
        got = _visual_dir(scene, "В")
        want = _manual_visual_dir(scene, "В")
        assert float(np.dot(got, want)) >= np.cos(np.radians(30.0))

    def test_guard_leaves_an_already_clear_label_unchanged(self):
        from animageo.label_placement import LabelInfo, _clearance_guard_pass

        label = LabelInfo("A", np.array([0.0, 0.0]), 0.5, 0.25)
        original = np.array([2.0, 2.0])
        result = [("A", original.copy(), 1)]

        _clearance_guard_pass(
            [label], result,
            [(np.array([-1.0, 0.0]), np.array([1.0, 0.0]))],
            [], np.empty((0, 2)),
            distance=0.0, padding=0.0, ptUnit=1.0,
        )

        assert np.array_equal(result[0][1], original)

    def test_guard_separates_overlapping_labels(self):
        from animageo.label_placement import (
            LabelInfo, _bbox_overlap_area, _clearance_guard_pass,
        )

        labels = [
            LabelInfo("A", np.array([0.0, 0.0]), 0.6, 0.4),
            LabelInfo("B", np.array([2.0, 0.0]), 0.6, 0.4),
        ]
        result = [
            ("A", np.array([1.0, 0.0]), 0),
            ("B", np.array([1.0, 0.0]), 4),
        ]

        _clearance_guard_pass(
            labels, result, [], [], np.empty((0, 2)),
            distance=0.0, padding=0.0, ptUnit=1.0,
        )

        a, b = result[0][1], result[1][1]
        assert _bbox_overlap_area(
            a[0], a[1], labels[0].half_w, labels[0].half_h,
            b[0], b[1], labels[1].half_w, labels[1].half_h,
        ) == 0.0



TYPES_FIXTURE = Path(__file__).parent / "fixtures" / "label_anchor_types"
TYPES_TOL_PX = 2.0   # ink vs ink: GeoGebra's glyph vs our Tex glyph


def _types_ground_truth():
    import json
    return json.loads(TYPES_FIXTURE.with_suffix(".json").read_text())


class TestLabelAnchorPerType:
    """Every element type GeoGebra has a label rule for must put an
    applet-placed label where the applet drew it. Ground truth: label ink
    measured on the live GeoGebra applet (with and without labelOffset) —
    not our own formulas. Repro: «Хроматические числа», the label «1» of
    segment AB sat in the middle of the segment; circles drew no label."""

    @pytest.mark.parametrize("name", sorted(_types_ground_truth()["labels_canvas_px"]))
    def test_label_lands_where_geogebra_drew_it(self, name):
        truth = _types_ground_truth()
        view, ref = truth["view"], truth["labels_canvas_px"][name]
        scene = _load_scene(TYPES_FIXTURE.with_suffix(".ggb"))
        mobj = scene.CreateMObject(scene.element(name), z_auto=True)
        assert mobj is not None, f"{name} did not render"
        labels = [m for m in mobj.get_family() if getattr(m, "_animageo_is_label", False)]
        assert labels, f"{name}: no label rendered"
        label = labels[0]
        left_px = (float(label.get_left()[0]) - view["xMin"]) / view["invXscale"]
        bottom_px = view["height"] - (float(label.get_bottom()[1]) - view["yMin"]) / view["invYscale"]
        assert left_px == pytest.approx(ref["left"], abs=TYPES_TOL_PX), (
            f"{name}: left edge {left_px - ref['left']:+.1f} px from the applet"
        )
        assert bottom_px == pytest.approx(ref["bottom"], abs=TYPES_TOL_PX), (
            f"{name}: baseline {bottom_px - ref['bottom']:+.1f} px from the applet"
        )


def _label_center(scene, name):
    mobj = scene.CreateMObject(scene.element(name), z_auto=True)
    label = [m for m in mobj.get_family() if getattr(m, "_animageo_is_label", False)][0]
    return np.array(label.get_center()[:2], dtype=float)


class TestLabelKeepsItsPlaceOnTheFigure:
    """An applet-placed label must stay next to the same PART of its element
    when the export draws the figure at another scale than the applet did
    (labels relatively 3× larger in a small preview). The offset used to live
    wholly in font space, so a label parked near a segment's endpoint drifted
    far past it (repro: «Хроматические числа», label «1» near A)."""

    @pytest.mark.parametrize(
        "name", ["s1", "s2", "v1", "v2", "r1", "r2", "c1", "e1", "arc1", "arc2", "sec1", "poly1", "poly2"],
    )
    def test_attachment_point_survives_a_scale_change(self, name):
        from animageo.label_anchor import nearest_point

        native = _load_scene(TYPES_FIXTURE.with_suffix(".ggb"))
        elem = native.element(name)
        attach_native = nearest_point(elem, _label_center(native, name), native.geo)

        small = _load_scene(TYPES_FIXTURE.with_suffix(".ggb"))
        ggb = small.style.export.get("ptUnit_ggb", small.style.export["ptUnit"])
        small.style.export["ptUnit_style"] = ggb / 3.0     # labels 3× larger vs the figure
        attach_small = nearest_point(small.element(name), _label_center(small, name), small.geo)

        assert np.linalg.norm(attach_small - attach_native) < 3.0 / ggb, (
            f"{name}: label moved along its element by "
            f"{np.linalg.norm(attach_small - attach_native) * ggb:.1f} applet px"
        )
