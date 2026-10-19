"""The contract of style keys by element type (1.11.0rc3).

``native.style_keys()`` lists, for every element type of the document, the
keys of ``appearance.overrides`` its renderer reads, with their unit and
default. ``appearance_plan`` warns ``style_key_ineffective`` about a key it
accepts but the element does not read; the tick sizes of an equality mark go
to the targets of the mark, as its count does.
"""
import pytest

from animageo import native
from animageo.native.rendering import APPEARANCE_STYLE_KEYS, appearance_plan
from tests.native.conftest import DocBuilder, num, ref, ref_list

DRAWN = ('point', 'segment', 'line', 'ray', 'vector', 'circle', 'polygon', 'arc', 'sector', 'polyline',
         'locus', 'angle', 'text', 'mark.right_angle')
NOT_DRAWN = ('number', 'expr', 'template', 'mark.equal_segments', 'mark.equal_angles')


def zoo():
    """One element of each drawn type and the three marks."""
    b = DocBuilder('zoo', bounds=(-1, -1, 7, 5), registry_version='1.5')
    b.free('A', 0, 0).free('B', 4, 0).free('C', 1, 3).free('D', 5, 3)
    b.segment('s', 'A', 'B').segment('u', 'B', 'C').line('l', 'C', 'D').ray('r', 'A', 'D').vector('v', 'C', 'A')
    b.circle('c', 'D', 'B').polygon('T', 'A', 'B', 'C')
    b.op('op_k', 'arc.center_two_points', {'center': ref('D'), 'a': ref('B'), 'b': ref('C')}, [('arc', 'k', 'arc')])
    b.op('op_q', 'sector.center_two_points', {'center': ref('A'), 'a': ref('B'), 'b': ref('C')},
         [('sector', 'q', 'sector')])
    b.op('op_w', 'polyline.by_points', {'points': ref_list('A', 'C', 'D')}, [('polyline', 'w', 'polyline')])
    b.angle('alpha', 'B', 'A', 'C').angle('beta', 'C', 'B', 'A')
    b.right_mark('ra', 'B', 'A', 'C')
    b.equal_segments('mk', 's', 'u', count=2).equal_angles('ma', 'alpha', 'beta', count=2)
    b.number('n', 2.5)
    b.op('op_t', 'text.free', {'text': {'kind': 'template', 'value': 'x'}, 'anchor': ref('D'),
                               'refs': ref_list()}, [('text', 't', 'text')])
    return b


def warnings(diagnostics, el_id=None):
    return [(d['elementId'], d['key'], d['reason']) for d in diagnostics
            if d['code'] == 'style_key_ineffective' and (el_id is None or d['elementId'] == el_id)]


def plan_of(doc, unit=100.0):
    return appearance_plan(doc, unit)


class TestStyleKeys:
    def test_format_and_types(self):
        keys = native.style_keys()
        assert keys['format'] == 'animageo-style-keys/v1'
        assert set(keys['types']) == set(DRAWN) | set(NOT_DRAWN)
        for type_ in NOT_DRAWN:
            assert keys['types'][type_]['keys'] == {}
        assert keys['types']['mark.equal_segments']['transfers'] == [
            'tick_length_px', 'tick_radius_px', 'tick_shift_px', 'tick_style', 'tick_width_px']
        assert keys['types']['mark.equal_angles']['transfers'] == ['arc_shift_px']

    def test_every_key_is_accepted_and_read_somewhere(self):
        types = native.style_keys()['types']
        read = set()
        for entry in types.values():
            assert set(entry['keys']) <= APPEARANCE_STYLE_KEYS
            read |= set(entry['keys'])
        assert read == set(APPEARANCE_STYLE_KEYS)

    def test_units_defaults_and_values(self):
        keys = native.style_keys()
        seg = keys['types']['segment']
        assert seg['style'] == 'segment'
        assert seg['keys']['tick_length_px'] == {'unit': 'px', 'default': 9}
        assert seg['keys']['stroke'] == {'unit': 'color', 'default': '#000000'}
        assert seg['keys']['stroke_width_px'] == {'unit': 'px', 'default': 1.5}
        assert seg['keys']['stroke_linecap'] == {'unit': 'enum', 'default': 'butt',
                                                 'values': ['butt', 'round', 'square']}
        assert seg['keys']['stroke_dash_ratio'] == {'unit': 'ratio', 'default': None}
        assert keys['types']['point']['keys']['point_shape']['values'][0] == 'circle'
        assert keys['types']['point']['keys']['size_px']['default'] == 6
        angle = keys['types']['angle']['keys']
        assert angle['arc_size_px']['default'] == 17 and angle['arc_shift_px']['default'] == 1.5
        assert angle['fill']['default'] == '#ffffff'
        assert angle['label_angle_unit'] == {'unit': 'enum', 'default': 'degree', 'values': ['degree', 'radian']}
        assert keys['types']['sector']['style'] == 'circlesector'
        assert keys['types']['polyline']['style'] == 'locuscurve'
        assert keys['types']['mark.right_angle']['style'] == 'angle'
        assert keys['types']['text']['keys']['font_size_px']['default'] == 16
        assert keys['types']['segment']['keys']['label_value_precision']['default'] == 1
        assert keys['types']['segment']['keys']['z_index'] == {'unit': 'number', 'default': None}

    def test_not_read_keys(self):
        types = native.style_keys()['types']
        assert 'stroke_dash_ratio' not in types['polygon']['keys']      # the stroke of a polygon is solid
        assert 'stroke_dash_ratio' not in types['sector']['keys']
        assert 'z_index_fill' not in types['polygon']['keys']
        assert 'tick_length_px' not in types['angle']['keys']
        assert 'stroke_linecap' not in types['circle']['keys']
        assert 'label_anchor' not in types['polyline']['keys']
        assert 'label_value_precision' not in types['point']['keys']   # a point has no value

    def test_keys_is_a_copy(self):
        native.style_keys()['types']['segment']['keys'].clear()
        assert native.style_keys()['types']['segment']['keys']


class TestIneffective:
    @pytest.mark.parametrize('el_id, key, reason', [
        ('T', 'stroke_dash_ratio', 'not_read'),
        ('q', 'stroke_dash_ratio', 'not_read'),
        ('alpha', 'tick_length_px', 'not_read'),
        ('A', 'tick_count', 'not_read'),
        ('c', 'stroke_linecap', 'not_read'),
        ('w', 'label_anchor', 'not_read'),
        ('t', 'stroke', 'not_read'),
        ('ra', 'tick_count', 'not_read'),
        ('n', 'stroke', 'not_drawn'),
        ('mk', 'stroke', 'mark_transfers_only'),
        ('mk', 'tick_count', 'mark_transfers_only'),
        ('ma', 'tick_length_px', 'mark_transfers_only'),
    ])
    def test_warned(self, el_id, key, reason):
        b = zoo()
        b.doc['appearance'] = {el_id: {'overrides': {key: 0.5 if key.endswith('ratio') else 3}}}
        plan, diagnostics = plan_of(b.doc)
        assert warnings(diagnostics) == [(el_id, key, reason)]
        assert plan[el_id]['style'][key] == b.doc['appearance'][el_id]['overrides'][key]   # still applied

    @pytest.mark.parametrize('type_', DRAWN)
    def test_read_keys_are_not_warned(self, type_):
        b = zoo()
        el_id = {t: e for e, t in (('A', 'point'), ('s', 'segment'), ('l', 'line'), ('r', 'ray'),
                                   ('v', 'vector'), ('c', 'circle'), ('T', 'polygon'), ('k', 'arc'),
                                   ('q', 'sector'), ('w', 'polyline'), ('alpha', 'angle'), ('t', 'text'),
                                   ('ra', 'mark.right_angle'))}.get(type_)
        if el_id is None:
            pytest.skip('no element of this type in the zoo')
        defaults = native.style_keys()['types'][type_]['keys']
        b.doc['appearance'] = {el_id: {'overrides': {k: v['default'] for k, v in defaults.items()
                                                     if v['default'] is not None}}}
        _, diagnostics = plan_of(b.doc)
        assert warnings(diagnostics) == []

    def test_a_right_angle_mark_drawn_as_arcs_reads_their_keys(self):
        """``right_angle_marker: false`` draws the mark as the arcs of an
        angle: their count and spacing are read, the square's are not."""
        b = zoo()
        b.doc['appearance'] = {'ra': {'overrides': {'right_angle_marker': False, 'tick_count': 2,
                                                    'arc_shift_px': 3, 'tick_length_px': 4}}}
        _, diagnostics = plan_of(b.doc)
        assert warnings(diagnostics) == [('ra', 'tick_length_px', 'not_read')]
        b.doc['appearance'] = {'ra': {'overrides': {'right_angle_marker': True, 'tick_count': 2}}}
        _, diagnostics = plan_of(b.doc)
        assert warnings(diagnostics) == [('ra', 'tick_count', 'not_read')]

    def test_role_keys_are_not_warned(self):
        b = zoo()
        b.doc['appearance'] = {'T': {'role': 'aux'}, 'n': {'role': 'aux'}}
        roles = {'aux': {'stroke': '#808080', 'stroke_dash_ratio': 0.5}}
        _, diagnostics = appearance_plan(b.doc, 100.0, roles=roles)
        assert warnings(diagnostics) == []

    def test_unknown_key_stays_unknown(self):
        b = zoo()
        b.doc['appearance'] = {'s': {'overrides': {'no_such_key': 1}}}
        _, diagnostics = plan_of(b.doc)
        assert [d['code'] for d in diagnostics] == ['unknown_style_key']


class TestMarkTransfer:
    def test_tick_sizes_go_to_the_targets(self):
        b = zoo()
        b.doc['appearance'] = {'mk': {'overrides': {'tick_length_px': 14, 'tick_width_px': 2.5,
                                                    'tick_style': 'wave'}}}
        plan, diagnostics = plan_of(b.doc)
        assert warnings(diagnostics) == []
        for target in ('s', 'u'):
            style = plan[target]['style']
            assert (style['tick_count'], style['tick_length_px'], style['tick_width_px'], style['tick_style']) \
                == (2, 14, 2.5, 'wave')

    def test_an_override_of_the_target_wins(self):
        b = zoo()
        b.doc['appearance'] = {'mk': {'overrides': {'tick_length_px': 14}},
                               'u': {'overrides': {'tick_length_px': 6}}}
        plan, _ = plan_of(b.doc)
        assert plan['s']['style']['tick_length_px'] == 14
        assert plan['u']['style']['tick_length_px'] == 6

    def test_arc_shift_of_equal_angles(self):
        b = zoo()
        b.doc['appearance'] = {'ma': {'overrides': {'arc_shift_px': 4}}}
        plan, diagnostics = plan_of(b.doc)
        assert warnings(diagnostics) == []
        assert plan['alpha']['style']['arc_shift_px'] == 4 and plan['beta']['style']['arc_shift_px'] == 4

    def test_a_hidden_mark_passes_nothing(self):
        b = zoo()
        b.doc['appearance'] = {'mk': {'visible': False, 'overrides': {'tick_length_px': 14}}}
        plan, _ = plan_of(b.doc)
        assert 'tick_length_px' not in plan['s']['style'] and 'tick_count' not in plan['s']['style']

    def test_the_first_mark_wins(self):
        b = zoo()
        b.op('op_m2', 'mark.equal_segments', {'segments': ref_list('s'), 'count': num(3)},
             [('mark', 'mz', 'mark')])
        b.doc['appearance'] = {'mk': {'overrides': {'tick_length_px': 14}},
                               'mz': {'overrides': {'tick_length_px': 20}}}
        plan, _ = plan_of(b.doc)
        assert plan['s']['style']['tick_length_px'] == 14 and plan['s']['style']['tick_count'] == 2

    def test_an_entry_that_is_not_an_object_passes_nothing(self):
        b = zoo()
        b.doc['appearance'] = {'mk': ['x']}
        plan, _ = plan_of(b.doc)
        assert plan['s']['style']['tick_count'] == 2 and 'tick_length_px' not in plan['s']['style']
