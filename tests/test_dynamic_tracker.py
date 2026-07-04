"""Tests for dynamic label tracker primitives (EMA + anchor hysteresis).

End-to-end behavior (run the solver every frame via updateVar) requires the
full manim scene and is exercised visually in the examples. These tests
lock in the pure-math pieces that determine temporal smoothness:

- apply_ema_step: monotone convergence, rate controlled by alpha.
- anchor_hysteresis_step: Schmitt-trigger behavior — no flip on a single
  deviant frame, flip once sustained.
"""
import numpy as np
import pytest

from animageo.label_placement import apply_ema_step, anchor_hysteresis_step


class TestApplyEmaStep:
    def test_alpha_zero_freezes(self):
        """alpha=0 ignores target — output stays at prev."""
        out = apply_ema_step([1.0, 2.0], [100.0, 200.0], alpha=0.0)
        assert np.allclose(out, [1.0, 2.0])

    def test_alpha_one_snaps_to_target(self):
        """alpha=1 ignores prev — output snaps to target in one step."""
        out = apply_ema_step([1.0, 2.0], [100.0, 200.0], alpha=1.0)
        assert np.allclose(out, [100.0, 200.0])

    def test_damps_large_solver_jump(self):
        """A +10-unit solver jump moves the applied offset by only alpha*10.

        Guarantees that a sudden solver flip does not translate into a visible
        label jump — the headline anti-jitter guarantee of the tracker.
        """
        prev = np.array([0.0, 0.0])
        target = np.array([10.0, 0.0])
        alpha = 0.2
        out = apply_ema_step(prev, target, alpha)
        # Step length bounded by alpha * delta
        assert np.isclose(out[0], 2.0)
        # Never overshoots
        assert out[0] <= target[0]

    def test_converges_over_many_steps(self):
        """With alpha=0.2, 40 steps bring offset within 1e-2 of the target.

        Residual = (1 - alpha)^N * delta → (0.8)^40 * 10 ≈ 1.3e-3 << 1e-2.
        """
        prev = np.array([0.0, 0.0])
        target = np.array([10.0, -5.0])
        alpha = 0.2
        for _ in range(40):
            prev = apply_ema_step(prev, target, alpha)
        assert np.allclose(prev, target, atol=1e-2)

    def test_returns_numpy_array(self):
        out = apply_ema_step((1.0, 2.0), (3.0, 4.0), alpha=0.5)
        assert isinstance(out, np.ndarray)


class TestAnchorHysteresisStep:
    def test_same_anchor_resets_counter(self):
        anchor, counter = anchor_hysteresis_step('NE', 'NE', counter=5, flip_frames=6)
        assert anchor == 'NE'
        assert counter == 0

    def test_single_deviant_does_not_flip(self):
        """One frame of a different proposed anchor → stay."""
        anchor, counter = anchor_hysteresis_step('NE', 'N', counter=0, flip_frames=6)
        assert anchor == 'NE'
        assert counter == 1

    def test_sustained_deviation_flips(self):
        """After `flip_frames` consecutive deviant frames, flip and reset counter."""
        anchor, counter = 'NE', 0
        for i in range(5):
            anchor, counter = anchor_hysteresis_step(anchor, 'N', counter, flip_frames=6)
            assert anchor == 'NE', f"flipped too early at step {i + 1}"
        anchor, counter = anchor_hysteresis_step(anchor, 'N', counter, flip_frames=6)
        assert anchor == 'N'
        assert counter == 0

    def test_oscillating_proposal_does_not_flip(self):
        """NE, N, NE, N, NE, N — counter never accumulates to flip_frames."""
        anchor, counter = 'NE', 0
        proposals = ['N', 'NE', 'N', 'NE', 'N', 'NE', 'N', 'NE']
        for p in proposals:
            anchor, counter = anchor_hysteresis_step(anchor, p, counter, flip_frames=6)
        assert anchor == 'NE'

    def test_flip_frames_one_flips_immediately(self):
        """flip_frames=1 means no hysteresis — any deviation flips at once."""
        anchor, counter = anchor_hysteresis_step('NE', 'N', counter=0, flip_frames=1)
        assert anchor == 'N'
        assert counter == 0


class TestRecommendedPresetIsAnimationSafe:
    """The recommended static preset (continuous placement + cluster consistency)
    must also drive the per-frame dynamic tracker without errors and stay smooth
    (EMA + hysteresis). Guards against a static-only feature breaking animation.
    """
    PRESET = {"overlay": {"label_placement": {
        "enabled": True, "repair_iterations": 6, "soft_falloff_px": 0.0,
        "respect_current_position": True, "point_bisector": True,
        "geom_gap_px": 2.0, "directional_placement": False,
        "viewport_clamp": True, "declutter_labels": True, "label_gap_px": 2.5,
        "w_assoc": 3.0, "dashed_overlap_factor": 0.3,
        "continuous_placement": True, "continuous_steps": 72,
        "angle_label_max_arm_fraction": 0.45, "cluster_consistency": True,
        "dynamic_angles": True}}}

    def test_dynamic_tracker_runs_and_is_smooth(self):
        from animageo.animageo import AnimaGeoScene
        from animageo.label_placement import _resolve_style
        sc = AnimaGeoScene()
        sc.putCode("A = Point(-3, 0)\nB = Point(0, 2)\nC = Point(3, 0)\n"
                   "p = Polygon(A, B, C)\n")
        for n in ('A', 'B', 'C'):
            sc.element(n).style['label_visible'] = True
        sc.applyStyle(style=self.PRESET)
        sc.autoPlaceLabels(dynamic=True)
        assert sc._label_tracker is not None
        prev, jumps = None, []
        for _ in range(10):
            sc._apply_dynamic_labels()                 # one frame
            off = _resolve_style(sc, sc.geo.element('B'),
                                 'label_offset_px', default=[0, 0])
            if prev is not None:
                jumps.append(abs(off[0] - prev[0]) + abs(off[1] - prev[1]))
            prev = off
        # geometry is static here → tracker must converge, not oscillate
        assert max(jumps) < 12.0


class TestDynamicLabelVisibilitySync:
    def _scene_with_fake_layout(self, monkeypatch, layout_for_visible):
        from animageo.animageo import AnimaGeoScene
        import animageo.label_placement as lp

        sc = AnimaGeoScene()
        sc.putCode("A = Point(0, 0)\nB = Point(1, 0)\n", show=False)
        for name in ("A", "B"):
            sc.element(name).style["label_visible"] = True

        compute_calls = []

        def fake_compute(scene_arg, *, cfg=None, canonicalize=False):
            visible = tuple(
                elem.name for elem in scene_arg.geo.elements
                if scene_arg._element_visible(elem)
            )
            compute_calls.append(visible)
            offsets = layout_for_visible.get(visible, {})
            return {
                name: lp.LabelPlacement(name, offset, "MC")
                for name, offset in offsets.items()
            }

        monkeypatch.setattr(lp, "compute_label_layout", fake_compute)
        sc.autoPlaceLabels(dynamic=True)
        return sc, compute_calls

    def _capture_created_offsets(self, monkeypatch, sc):
        from manim import Dot

        created = []

        def fake_create(elem, z_auto=False, debug=False):
            if not sc._element_visible(elem):
                return None
            created.append((
                elem.name,
                tuple(elem.style.get("label_offset_px", ())),
            ))
            mob = Dot(point=[0.0, 0.0, 0.0], radius=0.01)
            mob.name = elem.name
            return mob

        monkeypatch.setattr(sc, "CreateMObject", fake_create)
        return created

    def test_show_syncs_before_creating_new_mobjects(self, monkeypatch):
        sc, compute_calls = self._scene_with_fake_layout(monkeypatch, {
            ("A", "B"): {"A": (11.0, 21.0), "B": (12.0, 22.0)},
        })
        created = self._capture_created_offsets(monkeypatch, sc)

        sc.Show(["A", "B"])

        assert compute_calls[-1] == ("A", "B")
        assert created == [
            ("A", (11.0, 21.0)),
            ("B", (12.0, 22.0)),
        ]
        tracker = sc._label_tracker
        assert np.allclose(tracker["prev_offset"]["A"], [11.0, 21.0])
        assert np.allclose(tracker["last_target_offset"]["B"], [12.0, 22.0])

    def test_hide_resyncs_remaining_visible_mobjects(self, monkeypatch):
        sc, compute_calls = self._scene_with_fake_layout(monkeypatch, {
            ("A", "B"): {"A": (11.0, 21.0), "B": (12.0, 22.0)},
            ("A",): {"A": (31.0, 41.0)},
        })
        created = self._capture_created_offsets(monkeypatch, sc)
        sc.Show(["A", "B"])
        created.clear()

        sc.Hide(["B"])

        assert compute_calls[-1] == ("A",)
        assert created == [("A", (31.0, 41.0))]
        assert sc.element("A").style["label_offset_px"] == [31.0, 41.0]
        assert "B" not in sc._label_tracker["prev_offset"]

    def test_set_visible_syncs_before_update_geo_elements(self, monkeypatch):
        sc, compute_calls = self._scene_with_fake_layout(monkeypatch, {
            ("A",): {"A": (5.0, 6.0)},
        })
        created = self._capture_created_offsets(monkeypatch, sc)

        sc.setVisible(["A"], True, update=True)

        assert compute_calls[-1] == ("A",)
        assert created == [("A", (5.0, 6.0))]
        assert np.allclose(sc._label_tracker["prev_offset"]["A"], [5.0, 6.0])
