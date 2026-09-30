"""Regression: AnimaGeoScene.setStyle must not mutate manim class defaults.

manim's Mobject.set_default wraps the CURRENT cls.__init__ in a fresh
functools.partialmethod on every call: reading cls.__init__ off the class
goes through the partialmethod descriptor and returns the compiled _method
function, so nested partialmethods never flatten. Repeated applyStyle calls
therefore grew MathTex/Text/MarkupText.__init__ by one layer each, and after
~1000 renders in one long-lived process every label construction died with
RecursionError.
"""
import functools
import logging

import pytest
from manim import ManimColor, MarkupText, MathTex, Tex, Text

from animageo.animageo import AnimaGeoScene

_CLASSES = (Text, MathTex, MarkupText)


def _chain_len(cls):
    """Depth of the partialmethod chain around cls.__init__ (ТЗ §2)."""
    init = cls.__dict__.get('__init__')
    n = 0
    while isinstance(init, functools.partialmethod):
        n += 1
        pm = getattr(init.func, '__partialmethod__', None)
        if pm is None:
            break
        init = pm
    return n


@pytest.fixture(autouse=True)
def _reset_manim_class_defaults():
    """Restore pristine __init__ before and after each test."""
    for cls in _CLASSES:
        cls.set_default()
    yield
    for cls in _CLASSES:
        cls.set_default()


class TestSetDefaultLeak:
    def test_apply_style_does_not_grow_init_chain(self):
        """ТЗ §6.1: chain depth stays bounded (== 0) across style applies."""
        scene = AnimaGeoScene()
        for _ in range(50):
            scene.applyStyle()
        for cls in _CLASSES:
            assert _chain_len(cls) == 0, cls.__name__

    def test_tex_constructible_after_more_applies_than_recursion_limit(self):
        """ТЗ §6.2 proxy: more setStyle calls than sys.getrecursionlimit()
        (default 1000) must leave MathTex constructible. Before the fix this
        was exactly the state that raised RecursionError on every label."""
        scene = AnimaGeoScene()
        scene.applyStyle()
        for _ in range(1200):
            scene.setStyle(scene.style)
        for cls in _CLASSES:
            assert _chain_len(cls) == 0, cls.__name__
        MathTex("1")  # must not raise RecursionError

    def test_point_label_color_unchanged(self):
        """ТЗ §6.3: label colour still comes out presets.color.strong —
        the render path passes col_label explicitly, no global default
        needed. Passes before AND after the fix (regression lock)."""
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(1, 1)
A.style.label_visible = True
""")
        scene.applyStyle()
        scene.addAllGeometry(show=True)
        labels = [m for m in scene.mobject('A').submobjects
                  if isinstance(m, Tex)]
        assert labels, "point label missing"
        expected = ManimColor(scene.style.strong).to_hex()
        leaf_fills = {m.get_fill_color().to_hex()
                      for m in labels[0].family_members_with_points()}
        assert leaf_fills == {expected}


class TestRecursionErrorDiagnostics:
    def test_recursion_error_render_failure_logs_root_cause_hint(
            self, caplog, monkeypatch):
        """A RecursionError caught by per-element recovery must point at the
        process-wide root cause instead of reading like an element bug."""
        scene = AnimaGeoScene()
        scene.putCode("A = Point(1, 1)")
        elem = scene.geo.element('A')

        def _boom(elem, z_auto):
            raise RecursionError('maximum recursion depth exceeded')

        monkeypatch.setattr(scene, '_build_render_ctx', _boom)
        with caplog.at_level(logging.WARNING, logger='animageo.animageo'):
            result = scene.CreateMObject(elem)

        assert result is None
        assert any('set_default' in r.getMessage()
                   and 'gotchas' in r.getMessage()
                   for r in caplog.records)

    def test_ordinary_render_failure_has_no_recursion_hint(
            self, caplog, monkeypatch):
        scene = AnimaGeoScene()
        scene.putCode("A = Point(1, 1)")
        elem = scene.geo.element('A')

        def _boom(elem, z_auto):
            raise ValueError('plain element failure')

        monkeypatch.setattr(scene, '_build_render_ctx', _boom)
        with caplog.at_level(logging.WARNING, logger='animageo.animageo'):
            result = scene.CreateMObject(elem)

        assert result is None
        assert not any('set_default' in r.getMessage()
                       for r in caplog.records)
