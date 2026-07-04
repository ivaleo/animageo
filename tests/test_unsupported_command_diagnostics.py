import logging

import pytest

from animageo.animageo import AnimaGeoScene
from animageo.geo.construction import Construction, UnsupportedCommandError
from animageo.geo.lib_commands import Command
from animageo.geo.lib_elements import Element, Point
from animageo.geo.lib_vars import AngleSize, Var


def test_unicode_identifier_inputs_resolve_before_dispatch():
    c = Construction()
    c.add(Var('α_2', AngleSize(1.0)))
    c.add(Command('Sub', ['α_2', '90°'], ['delta']))

    c.rebuild(full=True)

    assert c.var('delta') is not None
    assert isinstance(c.var('delta').data, AngleSize)
    assert c.command_diagnostics == []


def test_unsupported_root_diagnostic_suppresses_dependency_cascade(caplog):
    c = Construction()
    c.log_unsupported = False
    c.add(Element('A', Point([0, 0])))
    c.add(Element('B', Point([1, 0])))
    c.add(Command('UnsupportedRoot', ['A'], ['X']))
    c.add(Command('Rotate', ['A', 'X', 'B'], ['Y']))
    c.add(Command('Midpoint', ['Y', 'B'], ['M']))

    with caplog.at_level(logging.WARNING):
        c.rebuild(full=True)

    assert c.command_diagnostics == [{
        'command': 'UnsupportedRoot',
        'signature': ['Point'],
        'outputs': ['X'],
        'reason': 'unsupported_signature',
        'dependents': [
            {
                'command': 'Rotate',
                'signature': ['Point', 'NoneType', 'Point'],
                'outputs': ['Y'],
                'reason': 'depends_on_unsupported',
            },
            {
                'command': 'Midpoint',
                'signature': ['NoneType', 'Point'],
                'outputs': ['M'],
                'reason': 'depends_on_unsupported',
            },
        ],
    }]
    messages = [rec.getMessage() for rec in caplog.records]
    assert not any('Rotate' in msg and 'NoneType' in msg for msg in messages)
    assert not any('Midpoint' in msg and 'NoneType' in msg for msg in messages)


def test_unsupported_root_diagnostics_are_deduplicated():
    c = Construction()
    c.log_unsupported = False
    c.add(Element('A', Point([0, 0])))
    c.add(Command('UnsupportedRoot', ['A'], ['X']))

    c.rebuild(full=True)
    c.rebuild(full=True)

    assert len(c.command_diagnostics) == 1
    assert c.command_diagnostics[0]['command'] == 'UnsupportedRoot'


def test_strict_unsupported_raises():
    c = Construction()
    c.strict_unsupported = True
    c.log_unsupported = False
    c.add(Element('A', Point([0, 0])))
    c.add(Command('UnsupportedRoot', ['A'], ['X']))

    with pytest.raises(UnsupportedCommandError) as exc:
        c.rebuild(full=True)

    assert exc.value.diagnostic['command'] == 'UnsupportedRoot'


def test_svg_export_survives_noncritical_unsupported_chain(tmp_path):
    scene = AnimaGeoScene()
    scene.applyStyle(export={'size': [200, 120]})
    scene.putCode("""
A = Point(0, 0)
B = Point(1, 0)
""")
    scene.geo.log_unsupported = False
    scene.geo.add(Command('UnsupportedRoot', ['A'], ['X']))
    scene.geo.add(Command('Rotate', ['A', 'X', 'B'], ['Y']))
    scene.geo.rebuild(full=True)
    scene.addAllGeometry(show=True)

    out = tmp_path / 'out.svg'
    scene.exportSVG(str(out))

    assert out.exists()
    assert '<svg' in out.read_text()
    assert [d['command'] for d in scene.geo.command_diagnostics] == ['UnsupportedRoot']
