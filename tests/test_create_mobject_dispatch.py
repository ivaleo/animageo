"""Tests for the refactored CreateMObject dispatcher.

Before the refactor, CreateMObject was ~580 lines of inline per-type
`if type(elem.data) == ...` blocks sharing a common preamble. After the
refactor, it's a 20-line dispatcher that:

  1. Computes a shared render context via ``_build_render_ctx``.
  2. Looks up ``_render_<typename>`` via ``_renderer_for``.
  3. Delegates to that method.

These tests verify the dispatcher contract directly, independently of
whether the specific rendering is visually correct (that's covered by
other snapshot/regression tests).
"""
import pytest

from animageo.animageo import AnimaGeoScene, _Z_ORDER_EPSILON
from animageo.geo import construction as geo


def _expected_ordered_z(scene, elem, tier):
    return tier + scene.geo.elements.index(elem) * _Z_ORDER_EPSILON


class TestDispatcher:
    def test_renderer_for_known_types(self):
        """Every geometric type has a matching ``_render_<name>`` method."""
        scene = AnimaGeoScene()
        expected = {
            'point', 'segment', 'line', 'ray', 'angle', 'polygon',
            'circle', 'arc', 'circlesector', 'vector',
            'conic', 'function', 'implicitcurve',
        }
        for type_name in expected:
            method = getattr(scene, f'_render_{type_name}', None)
            assert method is not None, f"missing _render_{type_name}"
            assert callable(method)

    def test_line_and_ray_share_renderer(self):
        """``_render_ray`` is an alias for ``_render_line`` — same impl."""
        scene = AnimaGeoScene()
        assert scene._render_line == scene._render_ray

    def test_renderer_for_returns_none_on_unknown(self):
        """Unknown element types return None, no crash."""
        scene = AnimaGeoScene()

        class Fake:
            pass
        elem = type('E', (), {'data': Fake(), 'style': {}, 'name': 'x',
                              'visible': True})()
        assert scene._renderer_for(elem) is None


class TestBuildRenderCtx:
    def test_ctx_has_all_expected_fields(self):
        scene = AnimaGeoScene()
        scene.putCode("A = Point(0, 0)")
        elem = scene.geo.element('A')
        ctx = scene._build_render_ctx(elem, z_auto=False)

        for field in (
            'style', 'ptUnit', 'ptUnit_ggb',
            'col_s', 'col_f', 'op_s', 'op_f', 'col_label',
            'lw', 'font_size', 'label_anchor', 'ggb_font_px',
            'has_label', 'label_roff',
            'dash', 'cap', 'ra_joint',
            'zz', 'zz_fill', 'zz_stroke', 'zz_label',
        ):
            assert hasattr(ctx, field), f"ctx missing {field}"

    def test_z_auto_picks_type_tier(self):
        """``z_auto=True`` assigns the type-specific z-index tier."""
        from animageo.constants import Z_POINT, Z_STROKE
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 0)
s = Segment(A, B)
""")
        # Strip DSL-side default z_index so z_auto kicks in.
        for name in ('A', 's'):
            scene.geo.element(name).style.pop('z_index', None)
        point = scene.geo.element('A')
        segment = scene.geo.element('s')
        ctx_point = scene._build_render_ctx(point, z_auto=True)
        ctx_segment = scene._build_render_ctx(segment, z_auto=True)
        assert ctx_point.zz == pytest.approx(_expected_ordered_z(scene, point, Z_POINT))
        assert ctx_segment.zz == pytest.approx(_expected_ordered_z(scene, segment, Z_STROKE))

    def test_z_auto_false_falls_to_z_fill_without_explicit_or_type(self):
        """When no z_index and z_auto=False, zz settles on Z_FILL."""
        from animageo.constants import Z_FILL
        scene = AnimaGeoScene()
        scene.putCode("A = Point(0, 0)")
        elem = scene.geo.element('A')
        # Points default to z_index=50 in DSL. Strip it to force the fallback.
        elem.style.pop('z_index', None)
        ctx = scene._build_render_ctx(elem, z_auto=False)
        assert ctx.zz == pytest.approx(_expected_ordered_z(scene, elem, Z_FILL))

    def test_circle_sector_auto_fill_uses_fill_tier(self):
        """Circle sectors must not be hidden behind circle background fills."""
        from animageo.constants import Z_FILL
        scene = AnimaGeoScene()
        scene.putCode("""
O = Point(0, 0)
A = Point(1, 0)
B = Point(0, 1)
s = CircleSector(O, A, B)
""")
        elem = scene.geo.element('s')
        elem.style.pop('z_index', None)
        elem.style.pop('z_index_fill', None)
        ctx = scene._build_render_ctx(elem, z_auto=True)
        assert ctx.zz == pytest.approx(_expected_ordered_z(scene, elem, Z_FILL))
        assert ctx.zz_fill == pytest.approx(_expected_ordered_z(scene, elem, Z_FILL))

    def test_explicit_z_index_wins(self):
        """elem.style['z_index'] beats z_auto."""
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
A.style.z_index = 42
""")
        elem = scene.geo.element('A')
        ctx = scene._build_render_ctx(elem, z_auto=True)
        assert ctx.zz == pytest.approx(_expected_ordered_z(scene, elem, 42))


class TestCreateMObjectEndToEnd:
    """Smoke tests — every supported type gets rendered to something."""
    def test_point_renders(self):
        scene = AnimaGeoScene()
        scene.putCode("A = Point(0, 0)")
        scene.addAllGeometry(show=True)
        assert scene.mobject('A') is not None

    def test_segment_renders(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 5)
s = Segment(A, B)
""")
        scene.addAllGeometry(show=True)
        assert scene.mobject('s') is not None

    def test_circle_renders(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(1, 0)
c = Circle(A, B)
""")
        scene.addAllGeometry(show=True)
        assert scene.mobject('c') is not None

    def test_polygon_renders(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(3, 0)
C = Point(0, 3)
p = Polygon(A, B, C)
""")
        scene.addAllGeometry(show=True)
        assert scene.mobject('p') is not None

    def test_angle_renders(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
B = Point(5, 0)
C = Point(0, 5)
alpha = Angle(B, A, C)
""")
        scene.addAllGeometry(show=True)
        assert scene.mobject('alpha') is not None

    def test_invisible_returns_none(self):
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(0, 0)
A.visible = False
""")
        # visible=False → CreateMObject returns None early (no dispatcher).
        a = scene.geo.element('A')
        assert scene.CreateMObject(a) is None

    def test_dispatcher_tolerates_renderer_exception(self):
        """A crash inside _render_* is caught and logged, not propagated."""
        scene = AnimaGeoScene()
        scene.putCode("A = Point(0, 0)")

        # Monkey-patch _render_point to raise.
        original = scene._render_point.__func__
        def broken(self, elem, ctx):
            raise RuntimeError("test-induced failure")
        scene._render_point = broken.__get__(scene, type(scene))

        result = scene.CreateMObject(scene.geo.element('A'))
        assert result is None   # swallowed

        # Restore.
        scene._render_point = original.__get__(scene, type(scene))
