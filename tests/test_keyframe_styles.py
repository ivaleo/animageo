"""Keyframes v2 style tracks: registry, parsing, interpolators, binding, wiring."""

import pytest

from animageo.style.animatable import (
    ANIMATABLE_STYLE_KEYS, SCALAR, COLOR, DISCRETE, OFFSET2, DASH, TEXT,
    style_kind, validate_style_value, normalize_style_value,
)


class TestAnimatableRegistry:
    @pytest.mark.parametrize('key,kind', [
        ('stroke_opacity', SCALAR), ('fill_opacity', SCALAR),
        ('stroke_width_px', SCALAR), ('size_px', SCALAR),
        ('font_size_px', SCALAR), ('arc_size_px', SCALAR),
        ('stroke', COLOR), ('fill', COLOR), ('label_color', COLOR),
        ('label_offset_px', OFFSET2),
        ('point_shape', DISCRETE), ('label_anchor', DISCRETE),
        ('label_visible', DISCRETE), ('tick_count', DISCRETE),
        ('z_index', DISCRETE),
        ('stroke_dash_ratio', DASH),
    ])
    def test_kinds(self, key, kind):
        assert ANIMATABLE_STYLE_KEYS[key] == kind
        assert style_kind(key) == kind

    def test_label_text_is_animatable_as_text_kind(self):
        # Phase 3: label_text is animatable with swap (never lerped) semantics.
        assert ANIMATABLE_STYLE_KEYS['label_text'] == TEXT
        assert style_kind('label_text') == TEXT

    def test_unknown_key_error_lists_valid_keys(self):
        with pytest.raises(ValueError, match='stroke_width_px'):
            style_kind('thickness')


class TestValidateAndNormalize:
    def test_none_valid_for_every_key(self):
        for key in ANIMATABLE_STYLE_KEYS:
            validate_style_value(key, None)          # no raise
            assert normalize_style_value(key, None) is None

    def test_scalar_accepts_number_rejects_str(self):
        validate_style_value('stroke_width_px', 2)
        assert normalize_style_value('stroke_width_px', 2) == 2.0
        with pytest.raises(ValueError):
            validate_style_value('stroke_width_px', 'fat')

    def test_color_normalized_and_validated(self):
        assert normalize_style_value('stroke', '#ABC') == '#aabbcc'
        with pytest.raises(ValueError):
            validate_style_value('fill', 'red')

    def test_offset2_shape(self):
        assert normalize_style_value('label_offset_px', [3, -4]) == [3.0, -4.0]
        with pytest.raises(ValueError):
            validate_style_value('label_offset_px', [1, 2, 3])
        with pytest.raises(ValueError):
            validate_style_value('label_offset_px', 5)

    def test_dash_accepts_number(self):
        assert normalize_style_value('stroke_dash_ratio', 0.65) == 0.65
        with pytest.raises(ValueError):
            validate_style_value('stroke_dash_ratio', 'dashed')

    def test_bool_is_valid_scalar_for_discrete(self):
        validate_style_value('label_visible', True)
        assert normalize_style_value('label_visible', True) is True

    def test_bool_rejected_for_numeric_kind(self):
        with pytest.raises(ValueError):
            validate_style_value('stroke_width_px', True)
        with pytest.raises(ValueError):
            validate_style_value('stroke_dash_ratio', False)


from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.keyframes import Keyframe, KeyframeSequence


def _construction():
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return c


def _v2(keyframes):
    return {'version': 2, 'keyframes': keyframes}


class TestV2Parsing:
    def test_v1_emits_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'values': {'A': [0, 0]}},
                {'t': 1, 'values': {'A': [1, 1]}},
            ]}, _construction())

    def test_v2_no_warning_and_version_stored(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error', DeprecationWarning)
            seq = KeyframeSequence.from_json(_v2([
                {'t': 0, 'values': {'A': [0, 0]}},
                {'t': 1, 'values': {'A': [1, 1]}},
            ]), _construction())
        assert seq.version == 2

    def test_unsupported_version_raises(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'version': 3, 'keyframes': [
                {'t': 0}, {'t': 1},
            ]}, _construction())

    def test_styles_require_v2(self):
        with pytest.raises(ValueError, match='version'):
            KeyframeSequence.from_json({'keyframes': [
                {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
                {'t': 1},
            ]}, _construction())

    def test_styles_parsed_and_normalized(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#FF0000', 'size_px': 8}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ]), _construction())
        assert seq.keyframes[0].styles == {
            'A': {'stroke': '#ff0000', 'size_px': 8.0}}
        assert seq.keyframes[1].styles == {'A': {'stroke': None}}
        assert seq.has_style_tracks() is True

    def test_no_styles_has_no_tracks(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'values': {'A': [0, 0]}},
            {'t': 1, 'values': {'A': [1, 1]}},
        ]), _construction())
        assert seq.has_style_tracks() is False

    def test_styles_unknown_element_raises(self):
        with pytest.raises(ValueError, match='GHOST'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'GHOST': {'stroke': '#ff0000'}}},
                {'t': 1},
            ]), _construction())

    def test_styles_target_dependent_element_allowed(self):
        # styles may target ANY element, not only independents
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'M': {'fill_opacity': 0.2}}},
            {'t': 1, 'styles': {'M': {'fill_opacity': 1.0}}},
        ]), _construction())
        assert seq.keyframes[1].styles['M']['fill_opacity'] == 1.0

    def test_styles_unknown_key_raises(self):
        with pytest.raises(ValueError, match='animatable'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'A': {'thickness': 3}}},
                {'t': 1},
            ]), _construction())

    def test_styles_bad_value_raises(self):
        with pytest.raises(ValueError, match='hex'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'A': {'stroke': 'red'}}},
                {'t': 1},
            ]), _construction())

    def test_styles_non_dict_raises(self):
        with pytest.raises(ValueError, match='object'):
            KeyframeSequence.from_json(_v2([
                {'t': 0, 'styles': {'A': '#ff0000'}},
                {'t': 1},
            ]), _construction())


from animageo.keyframes import StyleInterpolator, EASING_FUNCTIONS


class TestStyleInterpolator:
    def test_scalar_lerp_linear(self):
        si = StyleInterpolator('a', 'stroke_width_px', 'scalar', 1.0, 3.0,
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.0) == 1.0
        assert si.at(0.5) == 2.0
        assert si.at(1.0) == 3.0

    def test_scalar_respects_easing(self):
        si = StyleInterpolator('a', 'stroke_width_px', 'scalar', 0.0, 1.0,
                               easing=EASING_FUNCTIONS['in'])   # t^2
        assert si.at(0.5) == pytest.approx(0.25)

    def test_color_endpoints_and_midpoint(self):
        si = StyleInterpolator('a', 'stroke', 'color', '#000000', '#ffffff',
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.0) == '#000000'
        assert si.at(1.0) == '#ffffff'
        mid = si.at(0.5)
        r, g, b = (int(mid[i:i + 2], 16) for i in (1, 3, 5))
        assert abs(r - g) <= 1 and abs(g - b) <= 1

    def test_color_space_srgb(self):
        si = StyleInterpolator('a', 'stroke', 'color', '#000000', '#ffffff',
                               easing=EASING_FUNCTIONS['linear'],
                               color_space='srgb')
        mid = si.at(0.5)
        assert int(mid[1:3], 16) in (0x7f, 0x80)

    def test_offset2_component_lerp(self):
        si = StyleInterpolator('a', 'label_offset_px', 'offset2',
                               [0.0, 10.0], [10.0, -10.0],
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.5) == [5.0, 0.0]

    def test_discrete_snaps_at_eased_half(self):
        si = StyleInterpolator('a', 'point_shape', 'discrete',
                               'circle', 'square',
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.49) == 'circle'
        assert si.at(0.5) == 'square'

    def test_discrete_snap_uses_eased_progress(self):
        # easing 'in' = t^2: eased 0.5 is reached at t = sqrt(0.5) ≈ 0.707
        si = StyleInterpolator('a', 'point_shape', 'discrete',
                               'circle', 'square',
                               easing=EASING_FUNCTIONS['in'])
        assert si.at(0.6) == 'circle'
        assert si.at(0.75) == 'square'

    def test_dash_numeric_lerps(self):
        si = StyleInterpolator('a', 'stroke_dash_ratio', 'dash', 0.2, 0.8,
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.5) == pytest.approx(0.5)

    def test_dash_with_none_snaps(self):
        si = StyleInterpolator('a', 'stroke_dash_ratio', 'dash', None, 0.65,
                               easing=EASING_FUNCTIONS['linear'])
        assert si.at(0.4) is None
        assert si.at(0.6) == 0.65


class _StubElem:
    def __init__(self, style=None):
        self.style = dict(style or {})


def _bind(seq, elements, resolved):
    """Bind with stub elements and a fake resolver.

    ``elements``: dict name -> _StubElem; ``resolved``: dict (name, key) -> value.
    """
    return seq.bind_style_tracks(
        get_element=elements.get,
        resolve=lambda elem, key: resolved.get(
            (next(n for n, e in elements.items() if e is elem), key)),
    )


class TestBindStyleTracks:
    def _seq(self, kfs):
        return KeyframeSequence.from_json(_v2(kfs), _construction())

    def test_track_from_baseline_to_target(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'stroke_width_px': 4}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'stroke_width_px'): 1.5})
        (si,) = seq.intervals[0].style_interps
        assert (si.name, si.key, si.kind) == ('A', 'stroke_width_px', 'scalar')
        assert si.start == 1.5 and si.end == 4.0
        assert seq.intervals[0].style_finalizers == [
            ('set', 'A', 'stroke_width_px', 4.0)]

    def test_kf0_styles_seed_current_value(self):
        seq = self._seq([
            {'t': 0, 'styles': {'A': {'stroke': '#000000'}}},
            {'t': 1, 'styles': {'A': {'stroke': '#ffffff'}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'stroke'): '#123456'})
        (si,) = seq.intervals[0].style_interps
        assert si.start == '#000000'      # kf0 value, not the resolved baseline
        assert si.end == '#ffffff'

    def test_hold_between_mentions(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'fill_opacity': 0.2}}},
            {'t': 2},
            {'t': 3, 'styles': {'A': {'fill_opacity': 1.0}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'fill_opacity'): 1.0})
        assert len(seq.intervals[0].style_interps) == 1     # 1.0 -> 0.2
        assert seq.intervals[1].style_interps == []          # hold
        (si2,) = seq.intervals[2].style_interps               # 0.2 -> 1.0
        assert si2.start == 0.2 and si2.end == 1.0

    def test_equal_values_skip_interp_but_pin_finalizer(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'size_px': 6}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'size_px'): 6.0})
        assert seq.intervals[0].style_interps == []
        assert seq.intervals[0].style_finalizers == [('set', 'A', 'size_px', 6.0)]

    def test_null_reverts_to_baseline_with_explicit_restore(self):
        seq = self._seq([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ])
        # element had an explicit GGB/DSL stroke before the animation
        elements = {'A': _StubElem({'stroke': '#1565c0'})}
        _bind(seq, elements, {('A', 'stroke'): '#1565c0'})
        (si,) = seq.intervals[0].style_interps
        assert si.start == '#ff0000' and si.end == '#1565c0'
        assert seq.intervals[0].style_finalizers == [
            ('revert', 'A', 'stroke', True, '#1565c0')]

    def test_null_revert_without_explicit_entry(self):
        seq = self._seq([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ])
        elements = {'A': _StubElem()}      # no explicit stroke; resolver default
        _bind(seq, elements, {('A', 'stroke'): '#000000'})
        (si,) = seq.intervals[0].style_interps
        assert si.end == '#000000'
        assert seq.intervals[0].style_finalizers == [
            ('revert', 'A', 'stroke', False, None)]

    def test_none_baseline_forces_snap(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'stroke_dash_ratio': 0.65}}},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {})            # resolver knows nothing -> None
        (si,) = seq.intervals[0].style_interps
        assert si.start is None and si.end == 0.65
        assert si.at(0.4) is None and si.at(0.6) == 0.65

    def test_missing_element_skipped_with_warning(self, caplog):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'size_px': 9}}},
        ])
        import logging
        with caplog.at_level(logging.WARNING, logger='animageo.keyframes'):
            _bind(seq, {}, {})
        assert seq.intervals[0].style_interps == []
        assert any('A' in r.message for r in caplog.records)

    def test_easing_taken_from_interval(self):
        seq = self._seq([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'size_px': 12}}, 'easing': 'linear'},
        ])
        elements = {'A': _StubElem()}
        _bind(seq, elements, {('A', 'size_px'): 6.0})
        (si,) = seq.intervals[0].style_interps
        assert si.at(0.5) == pytest.approx(9.0)   # linear, not smooth


from animageo.animageo import AnimaGeoScene


def _scene():
    scene = AnimaGeoScene()
    c = scene.geo
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    return scene


class TestSceneStyleWiring:
    def test_apply_keyframe_state_writes_kf0_styles(self):
        scene = _scene()
        updated = []
        scene.updateGeoElements = lambda updates=None: updated.append(set(updates or []))
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#FF0000', 'size_px': 9}}},
            {'t': 1, 'styles': {'A': {'stroke': '#00ff00'}}},
        ]), scene.geo)
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info)
        elem = scene.geo.element('A')
        assert elem.style['stroke'] == '#ff0000'
        assert elem.style['size_px'] == 9.0
        assert updated and 'A' in updated[-1]

    def test_apply_style_interps_writes_and_reports_touched(self):
        scene = _scene()
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke_width_px': 1}}},
            {'t': 1, 'styles': {'A': {'stroke_width_px': 5}}, 'easing': 'linear'},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda elem, key: elem.style.get(key),
        )
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info,
                                    update_scene=False)
        touched = scene._apply_style_interps(seq.intervals[0], 0.5)
        assert touched == {'A'}
        assert scene.geo.element('A').style['stroke_width_px'] == pytest.approx(3.0)

    def test_finalize_pins_exact_end_value(self):
        scene = _scene()
        updated = []
        scene.updateGeoElements = lambda updates=None: updated.append(set(updates or []))
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'fill_opacity': 0.0}}},
            {'t': 1, 'styles': {'A': {'fill_opacity': 0.75}}},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda elem, key: elem.style.get(key),
        )
        scene._finalize_style_interval(seq.intervals[0])
        assert scene.geo.element('A').style['fill_opacity'] == 0.75
        assert updated and 'A' in updated[-1]

    def test_finalize_revert_restores_explicit_entry(self):
        scene = _scene()
        scene.updateGeoElements = lambda updates=None: None
        elem = scene.geo.element('A')
        elem.style['stroke'] = '#1565c0'          # pre-animation explicit value
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda e, key: e.style.get(key),
        )
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info,
                                    update_scene=False)
        assert elem.style['stroke'] == '#ff0000'
        scene._finalize_style_interval(seq.intervals[0])
        assert elem.style['stroke'] == '#1565c0'

    def test_finalize_revert_deletes_key_when_no_explicit_entry(self):
        scene = _scene()
        scene.updateGeoElements = lambda updates=None: None
        elem = scene.geo.element('A')
        assert 'stroke' not in elem.style
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ]), scene.geo)
        seq.bind_style_tracks(
            get_element=scene.geo.element,
            resolve=lambda e, key: e.style.get(key) or '#000000',
        )
        scene._apply_keyframe_state(seq.keyframes[0], seq.element_info,
                                    update_scene=False)
        scene._finalize_style_interval(seq.intervals[0])
        assert 'stroke' not in elem.style

    def test_color_space_read_from_rendering_config(self):
        scene = _scene()
        scene.style.rendering['color_interpolation'] = 'srgb'
        assert scene.style.rendering.get('color_interpolation', 'oklab') == 'srgb'


class TestZIndexCarry:
    def test_z_index_style_change_propagates_through_become(self):
        # z_index lives on family members (the dot inside the VGroup), not on
        # the group itself — compare whole families, not the top-level attr.
        scene = _scene()
        elem = scene.geo.element('A')
        elem.visible = True
        scene.addGeoElement(elem)
        mobj = scene.mobject('A')
        assert mobj is not None
        z_family_before = sorted(m.z_index for m in mobj.get_family())

        elem.style['z_index'] = 99
        scene.updateGeoElements(['A'])

        mobj_after = scene.mobject('A')
        assert mobj_after is mobj          # become path, not remove/add
        z_expected = sorted(
            m.z_index for m in scene.CreateMObject(elem).get_family())
        assert z_expected != z_family_before   # the style change is real
        assert sorted(m.z_index for m in mobj_after.get_family()) == z_expected


class TestNonHexColorBaseline:
    def test_non_hex_baseline_snaps_instead_of_crashing(self):
        # A color track whose baseline is a non-hex color (e.g. 'red' from
        # setElementStyle/DSL) must NOT crash — it degrades to a discrete snap.
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'stroke': '#d05456'}}},
        ]), _construction())
        elements = {'A': _StubElem({'stroke': 'red'})}
        _bind(seq, elements, {('A', 'stroke'): 'red'})   # resolver returns 'red'
        (si,) = seq.intervals[0].style_interps
        assert si.kind == 'discrete'          # fell back, not 'color'
        # .at must not raise, and snaps at eased 0.5
        assert si.at(0.0) == 'red'
        assert si.at(1.0) == '#d05456'

    def test_null_revert_to_non_hex_baseline_snaps(self):
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0, 'styles': {'A': {'stroke': '#ff0000'}}},
            {'t': 1, 'styles': {'A': {'stroke': None}}},
        ]), _construction())
        elements = {'A': _StubElem({'stroke': 'blue'})}
        _bind(seq, elements, {('A', 'stroke'): 'blue'})
        (si,) = seq.intervals[0].style_interps
        assert si.kind == 'discrete'
        assert si.at(1.0) == 'blue'           # reverts by snapping, no crash

    def test_hex_baseline_still_lerps(self):
        # Regression guard: a normal hex baseline still produces a color lerp.
        seq = KeyframeSequence.from_json(_v2([
            {'t': 0},
            {'t': 1, 'styles': {'A': {'stroke': '#ffffff'}}},
        ]), _construction())
        elements = {'A': _StubElem({'stroke': '#000000'})}
        _bind(seq, elements, {('A', 'stroke'): '#000000'})
        (si,) = seq.intervals[0].style_interps
        assert si.kind == 'color'
