"""Keyframes v2 phase 3: label_text swap, write effect, reveal_construction."""
import pytest

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import KeyframeSequence, StyleInterpolator, EASING_FUNCTIONS
from animageo.style.animatable import (
    ANIMATABLE_STYLE_KEYS, TEXT, style_kind, normalize_style_value, validate_style_value,
)


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes, **top):
    return {'version': 2, 'keyframes': keyframes, **top}


class TestLabelTextRegistry:
    def test_label_text_is_text_kind(self):
        assert ANIMATABLE_STYLE_KEYS['label_text'] == TEXT
        assert style_kind('label_text') == TEXT

    def test_text_value_normalized_to_str(self):
        assert normalize_style_value('label_text', 'hi') == 'hi'
        assert normalize_style_value('label_text', 42) == '42'
        assert normalize_style_value('label_text', None) is None
        validate_style_value('label_text', 'anything')   # no raise


class TestTextInterpolator:
    def test_text_snaps_at_eased_half(self):
        si = StyleInterpolator('M', 'label_text', 'text', 'old', 'new',
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.49) == 'old'
        assert si.at(0.5) == 'new'


class TestLabelTextTrack:
    def test_label_text_track_binds(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'M': {'label_text': 'P'}}},
            {'t': 1, 'styles': {'M': {'label_text': 'Q'}}},
        ]), _construction())

        class _E:
            def __init__(self): self.style = {}
        seq.bind_style_tracks(get_element=lambda n: _E(),
                              resolve=lambda e, k: 'P')
        (si,) = seq.intervals[0].style_interps
        assert si.kind == 'text'
        assert si.at(1.0) == 'Q'


from animageo.keyframes import ENTER_EFFECTS


class TestWriteEffect:
    def test_write_in_enter_effects(self):
        assert 'write' in ENTER_EFFECTS

    def test_write_accepted_for_enter(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'visible': {'M': False}},
            {'t': 1, 'visible': {'M': True}, 'enter': {'M': 'write'}},
        ]), _construction())
        seq.bind_visibility(get_element=_construction().element)
        assert seq.keyframes[1].enter['M']['effect'] == 'write'

    def test_write_rejected_for_exit(self):
        with pytest.raises(ValueError, match='exit'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'visible': {'M': True}},
                {'t': 1, 'visible': {'M': False}, 'exit': {'M': 'write'}},
            ]), _construction())


class TestWriteAdapter:
    def test_write_reveals_prefix_of_glyphs(self):
        # A real animageo label is a single Tex; its glyphs live below the
        # top-level submobject, as leaf VMobjects. `_effect_write` must
        # reveal a prefix of those LEAVES, not top-level submobjects (which
        # would make a single-Tex label pop in all-at-once past alpha 0.5).
        from animageo.animageo import AnimaGeoScene
        from manim import Tex, VGroup
        s = AnimaGeoScene()
        grp = VGroup(Tex("ABCD"))          # real structure: ONE Tex, glyphs are leaves
        leaves = grp.family_members_with_points()
        n = len(leaves)
        assert n >= 3                        # 'ABCD' compiles to >= 3-4 glyph leaves
        s._effect_write(grp, 0.5)
        visible = [lf for lf in grp.family_members_with_points()
                   if lf.get_fill_opacity() > 0 or lf.get_stroke_opacity() > 0]
        # about half the glyph leaves visible at alpha 0.5 (progressive, not all-or-nothing)
        assert 0 < len(visible) < n

        grp2 = VGroup(Tex("ABCD"))
        s._effect_write(grp2, 1.0)
        visible_all = [lf for lf in grp2.family_members_with_points()
                       if lf.get_fill_opacity() > 0 or lf.get_stroke_opacity() > 0]
        assert len(visible_all) == len(grp2.family_members_with_points())   # all shown at alpha 1

        grp3 = VGroup(Tex("ABCD"))
        s._effect_write(grp3, 0.0)
        visible_none = [lf for lf in grp3.family_members_with_points()
                        if lf.get_fill_opacity() > 0 or lf.get_stroke_opacity() > 0]
        assert len(visible_none) == 0                                       # none shown at alpha 0


class TestStyleAwarePrepass:
    """The keyframe_snapshots pre-pass must apply per-keyframe ``styles``
    (not just values/visibility) so label bboxes reflect animated
    font_size_px/label_visible/arc_size_px, then restore elem.style."""

    def test_prepass_applies_font_size_style(self, monkeypatch):
        from animageo.animageo import AnimaGeoScene
        import animageo.label_placement as lp_mod

        s = AnimaGeoScene()
        s.geo = _construction()
        # enable snapshots + label placement
        s.applyStyle({'overlay': {'label_placement': {
            'enabled': True, 'keyframe_snapshots': True}}})
        for e in s.geo.elements:
            e.style['label_visible'] = True

        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'M': {'font_size_px': 10}}},
            {'t': 1, 'styles': {'M': {'font_size_px': 40}}},
        ]), s.geo)
        cfg = s.style_config.overlay.label_placement

        # Spy on compute_label_layout to record the font_size_px actually
        # present on M's elem.style at the moment each snapshot is taken —
        # this is what makes the test discriminating: a pre-pass that
        # ignores kf.styles would see the *original* (unset) value at every
        # call, not 10 then 40.
        seen = []
        real_compute = lp_mod.compute_label_layout

        def _spy(scene, *, cfg=None, canonicalize=False):
            seen.append(scene.geo.element('M').style.get('font_size_px'))
            return real_compute(scene, cfg=cfg, canonicalize=canonicalize)

        monkeypatch.setattr(lp_mod, 'compute_label_layout', _spy)

        original_font_size = s.geo.element('M').style.get('font_size_px')
        layouts = s._compute_keyframe_label_layouts(seq, cfg)

        # The pre-pass must have actually applied each keyframe's style
        # before snapshotting — not just carried the original value forward.
        assert seen == [10.0, 40.0]

        # After the pre-pass, elem.style is restored to its pre-call state
        # (the whole point of the pre-pass is to be side-effect-free).
        assert s.geo.element('M').style.get('font_size_px') == original_font_size

        assert len(layouts) == 2


class TestBuildRevealKeyframes:
    def test_two_keyframes_hidden_then_staggered(self):
        from animageo.keyframes import build_reveal_keyframes
        kfs = build_reveal_keyframes(
            ['A', 'B', 'M'],
            type_effects={'A': 'fade', 'B': 'fade', 'M': 'create'},
            lag=0.3, duration=0.5)
        assert kfs['version'] == 2
        k0, k1 = kfs['keyframes']
        assert k0['t'] == 0 and k0['visible'] == {'A': False, 'B': False, 'M': False}
        assert k1['visible'] == {'A': True, 'B': True, 'M': True}
        assert k1['enter']['A'] == {'effect': 'fade', 'duration': 0.5, 'at': 0.0}
        assert k1['enter']['B']['at'] == pytest.approx(0.3)
        assert k1['enter']['M'] == {'effect': 'create', 'duration': 0.5, 'at': pytest.approx(0.6)}
        assert k1['t'] == pytest.approx(0.6 + 0.5)

    def test_default_effect_fallback(self):
        from animageo.keyframes import build_reveal_keyframes
        kfs = build_reveal_keyframes(['A'], type_effects={}, default_effect='grow')
        assert kfs['keyframes'][1]['enter']['A']['effect'] == 'grow'


class TestRevealConstructionScene:
    def _scene(self):
        from animageo.animageo import AnimaGeoScene
        s = AnimaGeoScene()
        s.geo = _construction()
        s.applyStyle()
        return s

    def test_reveal_returns_valid_v2_keyframes(self):
        s = self._scene()
        kfs = s.reveal_construction(lag=0.2, duration=0.4, play=False)
        assert kfs['version'] == 2
        names = set(kfs['keyframes'][0]['visible'])
        assert 'xAxis' not in names and 'yAxis' not in names
        assert {'A', 'B', 'M'}.issubset(names)
        # per-type: points fade, midpoint (a Point) fade too
        assert kfs['keyframes'][1]['enter']['A']['effect'] == 'fade'

    def test_reveal_parses_through_from_json(self):
        s = self._scene()
        kfs = s.reveal_construction(play=False)
        # must be a valid sequence the player accepts
        seq = KeyframeSequence.from_json(kfs, s.geo)
        seq.bind_visibility(get_element=s.geo.element)
        assert seq.has_visibility_effects()


class TestLabelSnapshotsFollowAutoPlacement:
    """Keyframe label snapshots ARE auto-placement at keyframes. With
    auto-placement off they must not run: the web backfills
    ``keyframe_snapshots: true`` into every style, and the snapshots then
    overrode the applet-placed offsets — a segment label flew off-frame
    (repro: «Хроматические числа», label «1» of AB)."""

    def _scene(self, enabled):
        from animageo.animageo import AnimaGeoScene
        s = AnimaGeoScene()
        s.geo = _construction()
        s.applyStyle({'overlay': {'label_placement': {
            'enabled': enabled, 'keyframe_snapshots': True}}})
        for e in s.geo.elements:
            e.style['label_visible'] = True
        return s

    def _seq(self, s):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'M': {'label_offset_px': [0, 0]}}},
            {'t': 1, 'styles': {'M': {'label_offset_px': [12, 6]}}},
        ]), s.geo)
        seq.bind_style_tracks(get_element=s.geo.element,
                              resolve=lambda e, k: e.style.get(k))
        return seq

    def test_no_snapshots_when_auto_placement_is_off(self, monkeypatch):
        import animageo.label_placement as lp_mod
        s = self._scene(enabled=False)
        seq = self._seq(s)
        calls = []
        monkeypatch.setattr(lp_mod, 'compute_label_layout',
                            lambda *a, **k: calls.append(1) or {})
        assert s._bind_label_snapshots(seq) is None
        assert calls == []
        # the applet-placed offsets keep animating through their style track
        keys = {(si.name, si.key) for si in seq.intervals[0].style_interps}
        assert ('M', 'label_offset_px') in keys

    def test_snapshots_own_label_positions_when_auto_placement_is_on(self):
        s = self._scene(enabled=True)
        seq = self._seq(s)
        layouts = s._bind_label_snapshots(seq)
        assert layouts is not None and len(layouts) == 2
        # The keyframes' own label_offset_px only fed the solver: as a style
        # track it would fight the snapshots and, where no snapshot
        # interpolator runs, put a solver-placed label back on its line.
        for iv in seq.intervals:
            assert all(si.key != 'label_offset_px' for si in iv.style_interps)
            assert all(fin[2] != 'label_offset_px' for fin in iv.style_finalizers)

    def test_still_frame_places_labels_like_playback(self):
        """apply_keyframes_at (the web's «Точный кадр») must take label
        positions from the same snapshots as playback — not from the manual
        offset track, which put a solver-placed label onto its line."""
        s = self._scene(enabled=True)
        data = _v2([
            {'t': 0, 'styles': {'M': {'label_offset_px': [0, 0]}}},
            {'t': 1, 'styles': {'M': {'label_offset_px': [12, 6]}}},
        ])
        s.apply_keyframes_at(data, 0.5)
        m = s.geo.element('M')
        assert m.style.get('_auto_placed') is True
        assert m.style.get('label_offset_px') != [6.0, 3.0]

    def test_still_frame_keeps_manual_offsets_without_auto_placement(self):
        s = self._scene(enabled=False)
        data = _v2([
            {'t': 0, 'styles': {'M': {'label_offset_px': [0, 0]}}},
            {'t': 1, 'styles': {'M': {'label_offset_px': [12, 6]}}},
        ])
        s.apply_keyframes_at(data, 0.5)
        m = s.geo.element('M')
        assert not m.style.get('_auto_placed')
        assert list(m.style.get('label_offset_px')) == pytest.approx([6.0, 3.0])
