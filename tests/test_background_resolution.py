"""Background resolution: style primary, GeoGebra secondary (opt-in), white fallback."""
from animageo.style import GeoStyle, _is_concrete_color


class TestIsConcreteColor:
    def test_hex_is_concrete(self):
        assert _is_concrete_color('#0d2a54') is True

    def test_empty_is_not(self):
        assert _is_concrete_color('') is False

    def test_none_is_not(self):
        assert _is_concrete_color(None) is False

    def test_self_ref_is_not(self):
        assert _is_concrete_color('presets.color.background') is False
        assert _is_concrete_color('color.background') is False


class TestBackgroundExplicit:
    def test_explicit_from_presets_color(self):
        gs = GeoStyle(style={'presets': {'color': {'background': '#123456'}}})
        assert gs.background_explicit is True

    def test_not_explicit_when_absent(self):
        gs = GeoStyle(style={'presets': {'color': {'main': '#000000'}}})
        assert gs.background_explicit is False

    def test_not_explicit_when_rendering_is_self_ref(self):
        gs = GeoStyle(style={'rendering': {'background': 'presets.color.background'}})
        assert gs.background_explicit is False

    def test_explicit_from_rendering_concrete_color(self):
        gs = GeoStyle(style={'rendering': {'background': '#0d2a54'}})
        assert gs.background_explicit is True

    def test_empty_string_is_not_explicit(self):
        gs = GeoStyle(style={'presets': {'color': {'background': ''}}})
        assert gs.background_explicit is False


def _scene_with_ggb_bg(ggb_bg=None):
    from animageo.animageo import AnimaGeoScene
    sc = AnimaGeoScene()
    sc.style.export.update({
        'ptUnit': 50, 'ptWidth': 600, 'ptHeight': 400,
        'ptXZero': 300, 'ptYZero': 200, 'ptUnit_ggb': 50,
    })
    if ggb_bg is not None:
        sc.style.export['background'] = ggb_bg  # simulate parsed <bgColor>
    sc.putCode("A = Point(0,0)\nB = Point(1,0)\n")
    return sc


def _hexeq(a, b):
    from manim import ManimColor
    return ManimColor(a).to_hex().upper() == ManimColor(b).to_hex().upper()


class TestEffectiveBackground:
    def test_explicit_style_bg_wins_over_ggb(self):
        sc = _scene_with_ggb_bg('#16322A')
        sc.applyStyle(style={'presets': {'color': {'background': '#0D2A54'}}})
        assert _hexeq(sc.style.background, '#0D2A54')

    def test_cleared_style_bg_falls_back_to_ggb(self):
        sc = _scene_with_ggb_bg('#16322A')
        sc.applyStyle(style={'presets': {'color': {'main': '#000000'}}})
        assert _hexeq(sc.style.background, '#16322A')

    def test_cleared_and_no_ggb_is_white(self):
        sc = _scene_with_ggb_bg(None)
        sc.applyStyle(style={'presets': {'color': {'main': '#000000'}}})
        assert _hexeq(sc.style.background, '#FFFFFF')

    def test_fill_ref_follows_effective_ggb_bg(self):
        sc = _scene_with_ggb_bg('#16322A')
        sc.applyStyle(style={'presets': {'color': {'main': '#000000'}}})
        assert _hexeq(sc.style_config.resolve_ref('presets.color.background'), '#16322A')

    def test_explicit_presets_bg_with_concrete_rendering_override(self):
        sc = _scene_with_ggb_bg('#16322A')
        sc.applyStyle(style={'presets': {'color': {'background': '#0D2A54'}},
                             'rendering': {'background': '#123456'}})
        assert _hexeq(sc.style.background, '#123456')
