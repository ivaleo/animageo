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
