"""ShowText must not depend on manim class-level default colours.

Part of the MathTex.set_default leak fix (docs/TZ-mathtex-set-default-
recursion-leak.md): after the set_default calls are removed from
AnimaGeoScene.setStyle, every Tex in the package must receive its colour
explicitly. ShowText's body Tex was the only consumer of the class default
(it rendered strong-coloured only because setStyle had previously mutated
MathTex.__init__ globally).
"""
import numpy as np
import pytest
from manim import ManimColor, MarkupText, MathTex, Text

from animageo.style import GeoStyle
from animageo.ui import ShowText

_CLASSES = (Text, MathTex, MarkupText)


@pytest.fixture(autouse=True)
def _reset_manim_class_defaults():
    """Isolate from any set_default made elsewhere in the test session."""
    for cls in _CLASSES:
        cls.set_default()
    yield
    for cls in _CLASSES:
        cls.set_default()


class _StubScene:
    """Minimal stand-in: ShowText only touches scene.style and scene.play."""

    def __init__(self):
        self.style = GeoStyle()
        self.played = []

    def play(self, *anims, **kwargs):
        self.played.extend(anims)


def _leaf_fills(mobj):
    return {m.get_fill_color().to_hex() for m in mobj.family_members_with_points()}


class TestShowTextColors:
    def test_body_uses_style_strong(self):
        scene = _StubScene()
        ShowText(scene, header=None, body='Тело', pos=np.array([0.0, 0.0, 0.0]))
        (anim,) = scene.played
        expected = ManimColor(scene.style.strong).to_hex()
        assert _leaf_fills(anim.mobject) == {expected}

    def test_header_keeps_style_col_fill(self):
        scene = _StubScene()
        ShowText(scene, header='Заголовок', body=None, pos=np.array([0.0, 0.0, 0.0]))
        (anim,) = scene.played
        expected = ManimColor(scene.style.col).to_hex()
        assert _leaf_fills(anim.mobject) == {expected}
