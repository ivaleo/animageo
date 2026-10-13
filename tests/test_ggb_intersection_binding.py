"""Imported root identity and undefined-output lifecycle regressions."""
from xml.etree.ElementTree import fromstring

import numpy as np

from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command, intersect_cs
from animageo.geo.lib_elements import Circle, Element, Point, Segment
from animageo.parsers.ggb_parser import parse_constr


def point(name, x, y, *, z=1, visible=True):
    return (f'<element type="point" label="{name}">'
            f'<coords x="{x}" y="{y}" z="{z}"/>'
            f'<show object="{str(visible).lower()}" label="true"/>'
            '<objColor r="20" g="30" b="40" alpha="0"/>'
            '</element>')


def command(name, inputs, outputs):
    def attrs(values):
        return ' '.join(f'a{i}="{v}"' for i, v in enumerate(values))
    xml = (f'<command name="{name}"><input {attrs(inputs)}/>'
           f'<output {attrs(outputs)}/></command>')
    types = {'Circle': 'conic', 'Translate': 'point',
             'LineBisector': 'line', 'Segment': 'segment'}
    if name in types:
        xml += ''.join(f'<element type="{types[name]}" label="{output}"/>'
                       for output in outputs)
    return xml


def imported(xml):
    geo = Construction()
    parse_constr(geo, fromstring(f'<construction>{xml}</construction>'))
    return geo


def limited_geometry(*, second_defined=False):
    root = np.sqrt(24)
    return imported(
        point('C', 0, 0) + point('G', 0, 1) + point('A', 0, 5)
        + command('Circle', ['C', '5'], ['c'])
        + command('Translate', ['G', 'Vector[(20, 0)]'], ['T'])
        + command('Segment', ['G', 'T'], ['s'])
        + command('Intersect', ['c', 's'], ['H', 'L'])
        + point('H', 'NaN' if second_defined else root,
                'NaN' if second_defined else 1, visible=False)
        + point('L', root if second_defined else 'NaN',
                1 if second_defined else 'NaN', visible=False)
        + command('CircleArc', ['C', 'L', 'A'], ['arc'])
        + '<element type="conicpart" label="arc"><show object="true" label="false"/></element>'
    )


def test_undefined_output_retains_metadata_and_recomputes_dependents():
    geo = limited_geometry()
    second = geo.element('L')
    assert second is not None and second.data is None
    assert second.visible is False
    assert second.ggb_raw['show_object'] is False
    assert second.ggb_style['fill'] == '#141e28'

    geo.update('G', Point([-8, 1]))
    geo.rebuild()
    assert geo.element('L') is second
    assert second.visible is False
    assert np.allclose(second.data.coords, [np.sqrt(24), 1])
    assert geo.element('arc').data is not None

    geo.update('G', Point([0, 1]))
    geo.rebuild()
    assert geo.element('H').data is None
    assert np.allclose(second.data.coords, [np.sqrt(24), 1])

    geo.update('G', Point([0, 6]))
    geo.rebuild()
    assert geo.element('H').data is None
    assert second.data is None
    assert geo.element('arc').data is None


def test_snapshot_with_only_second_solution_defined_keeps_its_slot():
    geo = limited_geometry(second_defined=True)
    assert geo.element('H').data is None
    assert np.allclose(geo.element('L').data.coords, [np.sqrt(24), 1])
    assert geo.element('arc').data is not None
    geo.rebuild(full=True)
    assert geo.element('H').data is None
    assert geo.element('L').visible is False


def test_imported_index_selects_saved_root_and_keeps_it_dynamic():
    geo = imported(
        point('C', 0, 0) + point('A', -1, 0) + point('B', 1, 0)
        + command('Circle', ['C', '1'], ['c'])
        + command('LineBisector', ['A', 'B'], ['line'])
        + command('Intersect', ['c', 'line', '2'], ['P'])
        # Saved homogeneous coordinates; the library's line orientation
        # gives the opposite analytic ordering to GeoGebra's bisector.
        + point('P', 0, -2, z=2)
        + command('Segment', ['A', 'P'], ['dependent'])
    )
    assert np.allclose(geo.element('P').data.coords, [0, -1])
    geo.rebuild(full=True)
    assert np.allclose(geo.element('P').data.coords, [0, -1])
    geo.update('C', Point([0, 1]))
    geo.rebuild()
    assert np.allclose(geo.element('P').data.coords, [0, 0])
    assert np.allclose(geo.element('dependent').data.end, [0, 0])


def test_imported_circle_circle_outputs_follow_saved_names():
    root = np.sqrt(3)
    geo = imported(
        point('A', -1, 0) + point('B', 1, 0)
        + command('Circle', ['A', '2'], ['c1'])
        + command('Circle', ['B', '2'], ['c2'])
        + command('Intersect', ['c1', 'c2'], ['P', 'Q'])
        + point('P', 0, root) + point('Q', 0, -root)
    )
    assert np.allclose(geo.element('P').data.coords, [0, root])
    assert np.allclose(geo.element('Q').data.coords, [0, -root])
    geo.update('A', Point([-1, 1]))
    geo.update('B', Point([1, 1]))
    geo.rebuild()
    assert np.allclose(geo.element('P').data.coords, [0, 1 + root])
    assert np.allclose(geo.element('Q').data.coords, [0, 1 - root])


def test_nonimported_intersection_still_clears_missing_outputs():
    geo = Construction()
    geo.add(Element('c', Circle([0, 0], 1), fixed=True))
    geo.add(Element('s', Segment(np.array([-2, 0]), np.array([2, 0])), fixed=True))
    geo.add(Command('Intersect', ['c', 's'], ['P', 'Q']))
    geo.rebuild()
    assert geo.element('Q').data is not None
    geo.update('s', Segment(np.array([0, 0]), np.array([2, 0])))
    geo.rebuild()
    assert geo.element('Q').data is None
    # Direct command functions keep their documented compact result lists.
    assert len(intersect_cs(Circle([0, 0], 1),
                            Segment(np.array([0, 0]), np.array([2, 0])))) == 1


def test_static_seek_establishes_the_same_root_slots_as_playback(monkeypatch):
    from animageo.animageo import AnimaGeoScene

    scene = AnimaGeoScene()
    scene.geo = limited_geometry()
    monkeypatch.setattr(scene, 'updateGeoElements', lambda *args, **kwargs: None)
    monkeypatch.setattr(scene, '_bind_label_snapshots', lambda *args, **kwargs: None)
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'G': [0, 1]}},
        {'t': 1, 'values': {'G': [-8, 1]}},
        {'t': 2, 'values': {'G': [0, 1]}},
        {'t': 3, 'values': {'G': [0, 1]}},
    ]}
    scene.apply_keyframes_at(timeline, 2.5)
    assert scene.geo.element('H').data is None
    assert np.allclose(scene.geo.element('L').data.coords, [np.sqrt(24), 1])
    assert scene.geo.element('arc').data is not None
    assert scene.geo.element('L').visible is False


def test_label_snapshot_pass_restores_intersection_history(monkeypatch):
    from animageo.animageo import AnimaGeoScene
    from animageo.keyframes import KeyframeSequence
    from animageo import label_placement

    scene = AnimaGeoScene()
    scene.geo = limited_geometry()
    monkeypatch.setattr(label_placement, 'compute_label_layout',
                        lambda *args, **kwargs: {})
    timeline = {'version': 2, 'keyframes': [
        {'t': 0, 'values': {'G': [0, 1]}},
        {'t': 1, 'values': {'G': [-8, 1]}},
        {'t': 2, 'values': {'G': [0, 1]}},
    ]}
    scene._compute_keyframe_label_layouts(
        KeyframeSequence.from_json(timeline, scene.geo), {})
    assert np.allclose(scene.geo.element('G').data.coords, [0, 1])
    assert np.allclose(scene.geo.element('H').data.coords, [np.sqrt(24), 1])
    assert scene.geo.element('L').data is None
    assert scene.geo.element('L').visible is False
