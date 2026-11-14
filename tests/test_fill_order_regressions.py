"""Compatibility, finite domains and export coverage of fill ordering."""
import json
import math
from time import perf_counter

import pytest

from animageo import AnimaGeoScene
from animageo.fill_order import polygon_area
from animageo.geo.construction import Element
from animageo.geo.lib_elements import Polygon
from tests.test_fill_order_writers import tikz_parts


@pytest.mark.parametrize('independent_fill', [False, True])
def test_combined_classic_ellipse_survives_geometry_updates(independent_fill):
    scene = AnimaGeoScene()
    scene.putCode('e=Conic("x^2/4+y^2=1")\nc=Circle(Point(0,0),2)')
    scene.geo.element('e').style.fill_opacity = 0
    scene.geo.element('c').style.z_index_fill = 0
    if independent_fill:
        scene.putCode('p=Polygon(Point(0,0),Point(1,0),Point(0,1))')
        scene.geo.element('p').style.z_index_fill = 7
    for _ in range(2):
        scene.updateAllGeometry()
        leaves = scene.mobject('e').family_members_with_points()
        assert len(leaves) == 1  # the combined ellipse on main
        assert leaves[0] in scene._ordered_display_family()
        assert leaves[0].get_stroke_opacity() == 1
        assert scene._fill_display_enabled() is independent_fill
        if not independent_fill:
            assert not hasattr(leaves[0], '_animageo_owner')
    updates = []
    def rebuild_from_updater(mob, dt):
        updates.append(dt)
        scene._update_mobject(scene.geo.element('e'))
    group = scene.mobject('e')
    group.add_updater(rebuild_from_updater)
    scene.update_mobjects(0)
    group.clear_updaters()
    assert updates and all(m in scene._ordered_display_family() for m in group.family_members_with_points())


def test_classic_render_context_never_measures_a_polygon(monkeypatch):
    import animageo.fill_order as fills
    scene = AnimaGeoScene()
    points = [(3*math.cos(math.tau*i/2000), 3*math.sin(math.tau*i/2000)) for i in range(2000)]
    elem = Element('shape', Polygon(points))
    scene.geo.add(elem)
    def unexpected_area(*args, **kwargs):
        pytest.fail('legacy construction must not calculate fill area')
    monkeypatch.setattr(fills, 'fill_area', unexpected_area)
    start = perf_counter()
    scene._build_render_ctx(elem, True)
    assert perf_counter() - start < .15


def test_large_simple_polygon_uses_a_fast_exact_area():
    from animageo.fill_order import _polygon_area
    points = [(3*math.cos(math.tau*i/2000), 3*math.sin(math.tau*i/2000)) for i in range(2000)]
    _polygon_area.cache_clear()
    start = perf_counter()
    area = polygon_area(points)
    assert perf_counter() - start < .15
    assert area == pytest.approx(2000*9*math.sin(math.tau/2000)/2)
    start = perf_counter()
    assert polygon_area(points) == area
    assert perf_counter() - start < .02
    points[0] = (4, 0)
    assert polygon_area(points) > area


def test_halo_unsupported_by_writers_keeps_label_and_other_parts():
    from animageo import native
    from tests.test_fill_order_defaults import nested_document
    doc = nested_document()
    doc['appearance']['inner']['label'] = {'mode': 'name'}
    doc['appearance']['inner']['overrides'].update(label_halo_px=3, z_index_fill=100)
    expected_paint = native.resolve_paint(doc)
    assert {'id': 'inner', 'part': 'labelHalo'} in expected_paint['partOrder']
    scene = AnimaGeoScene()
    scene.loadDocument(doc)
    expected = [p for p in expected_paint['partOrder'] if p['part'] != 'labelHalo']
    text = scene.exportTikZ()
    assert tikz_parts(scene) == expected
    assert '{$inner$}' in text
    assert 'Unsupported labelHalo' in text
    spec = json.loads(scene.exportJSXGraph(output='spec'))
    assert [{k: p[k] for k in ('id', 'part')} for p in spec['paintOrder']['partOrder']] == expected
    label = next(e for e in spec['elements'] if e.get('name') == 'e_inner')
    assert label['attrs']['withLabel'] is True
    assert any(c['kind'] == 'skip' and 'labelHalo' in c['detail'] for c in spec['coverage'])


def test_open_conic_keeps_its_stroke_part_in_area_mode():
    scene = AnimaGeoScene()
    scene.applyStyle(style={'rendering': {'fill_order': 'area'}})
    scene.putCode('c=Conic("y=x^2")')
    leaves = scene.mobject('c').family_members_with_points()
    assert leaves and all(m._animageo_part == 'stroke' for m in leaves)


@pytest.mark.parametrize('gap', [0, 1e-12, 1e-6])
def test_native_prepared_arc_preserves_almost_full_domain(gap):
    from animageo.fill_order import arc_sweep
    from animageo.native.kernel.bridge import to_classic
    value = {'c':[0,0], 'r':2, 'a0':2.8, 'a1':2.8+math.tau-gap}
    arc = to_classic('arc', value)
    assert arc_sweep(arc, mode='area') == pytest.approx(math.tau-gap, abs=2e-15)
    arc.angles = [2.8,2.8]
    assert arc_sweep(arc, mode='area') == 0
