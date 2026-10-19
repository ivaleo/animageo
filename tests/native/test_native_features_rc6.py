"""Feature flags of 1.11.0rc6: the view with axes and grid, graphs, conics
(the plane, registry 1.6) and the experimental space package.

The web asks ``native.has(...)`` instead of comparing versions. The flags of
the plane are in ``FEATURES`` (and in the public API snapshot); the
experimental ``space`` is answered by ``has`` but kept outside ``FEATURES``
(``EXPERIMENTAL_FEATURES``), as the space package is outside the snapshot.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from animageo import native

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('feature', ['view_axes_grid', 'functions', 'conics'])
def test_plane_features_of_registry_1_6(feature):
    assert native.has(feature)
    assert feature in native.FEATURES


def test_the_features_name_what_the_library_has():
    reg = native.registry()
    assert {'function', 'conic'} <= set(reg.types)
    assert {'function.expr', 'function.root', 'intersect.function_line'} <= set(reg.ops)
    assert {'conic.equation', 'conic.five_points', 'intersect.line_conic'} <= set(reg.ops)
    view = native.style_keys()['view']
    assert any(key.startswith('axes_') for key in view['keys'])
    assert any(key.startswith('grid_') for key in view['keys'])


def test_space_is_experimental():
    assert native.has('space')
    assert 'space' not in native.FEATURES
    assert native.EXPERIMENTAL_FEATURES == ('space',)
    assert 'EXPERIMENTAL_FEATURES' not in native.__all__
    assert not set(native.EXPERIMENTAL_FEATURES) & set(native.FEATURES)


def test_unknown_features():
    for feature in ('space.video', 'functions.locus', '', 'Space'):
        assert not native.has(feature)


def test_has_space_does_not_load_the_space_package():
    code = ('import sys\nfrom animageo import native\nassert native.has("space")\n'
            'print("animageo.native.space" in sys.modules)\n')
    proc = subprocess.run([sys.executable, '-c', code], cwd=REPO_ROOT, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == 'False'
