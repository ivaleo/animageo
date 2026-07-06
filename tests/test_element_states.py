"""get_element_states(): per-element visibility + resolved animatable styles."""
from animageo.animageo import AnimaGeoScene
from animageo.geo.construction import Construction
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.style.animatable import ANIMATABLE_STYLE_KEYS


def _scene():
    s = AnimaGeoScene()
    c = Construction()
    c.add(Element('A', Point([-4, -1])))
    c.add(Element('B', Point([4, 0])))
    c.add(Command('Midpoint', ['A', 'B'], ['M']))
    c.rebuild(full=True)
    s.geo = c
    s.applyStyle()
    return s


class TestElementStates:
    def test_returns_all_non_axis_elements(self):
        s = _scene()
        st = s.get_element_states()
        assert {'A', 'B', 'M'}.issubset(st)
        assert 'xAxis' not in st and 'yAxis' not in st

    def test_state_shape(self):
        s = _scene()
        st = s.get_element_states()['A']
        assert st['type'] == 'Point'
        assert st['visible'] in (True, False)
        assert isinstance(st['style'], dict)

    def test_style_keys_are_animatable(self):
        s = _scene()
        st = s.get_element_states()['A']
        for key in st['style']:
            assert key in ANIMATABLE_STYLE_KEYS

    def test_reflects_visibility(self):
        s = _scene()
        s.geo.element('M').visible = False
        assert s.get_element_states()['M']['visible'] is False

    def test_reflects_explicit_style(self):
        s = _scene()
        s.geo.element('A').style['stroke'] = '#123456'
        assert s.get_element_states()['A']['style'].get('stroke') == '#123456'

    def test_no_mutation(self):
        s = _scene()
        before = {e.name: dict(e.style) for e in s.geo.elements}
        s.get_element_states()
        after = {e.name: dict(e.style) for e in s.geo.elements}
        assert before == after
