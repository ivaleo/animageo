"""Round-12 region-aware (cluster) consistency.

Aligns label directions within a collinear row/column of free points (a grid like
test6) so they are systematic, WITHOUT touching scattered free points or vertices
— the global ``consistent_placement`` got that wrong (it yanked correct labels to
the overall majority; the round-11 "в бок влево" bug).
"""
import math
import numpy as np

from animageo.animageo import AnimaGeoScene
from animageo.label_placement import compute_label_layout


def _scene(code):
    sc = AnimaGeoScene()
    sc.style.export.update({'ptUnit': 50, 'ptWidth': 800, 'ptHeight': 800,
                            'ptXZero': 400, 'ptYZero': 400, 'ptUnit_ggb': 50})
    sc.putCode(code)
    for el in sc.geo.elements:
        el.style['label_visible'] = True
    sc.applyStyle(style={'overlay': {'label_placement': {'enabled': True}}})
    return sc


CFG = {'enabled': True, 'point_bisector': True,
       'continuous_placement': True, 'continuous_steps': 72}


def _oct(off):
    return round((math.degrees(math.atan2(off[1], off[0])) % 360) / 45) % 8


class TestClusterConsistency:
    def test_column_of_free_points_is_aligned(self):
        # a vertical column of free points (shared x) → labels share one side
        sc = _scene("P1 = Point(0, 0)\nP2 = Point(0, 1)\nP3 = Point(0, 2)\n"
                    "P4 = Point(0, 3)\n")
        layout = compute_label_layout(sc, cfg={**CFG, 'cluster_consistency': True})
        dirs = {_oct(layout[n].offset_ggb) for n in ('P1', 'P2', 'P3', 'P4')}
        assert len(dirs) == 1                      # all the same direction
        assert dirs <= {0, 4}                      # sideways (E or W) for a column

    def test_scattered_free_points_untouched(self):
        # not a row/column → cluster pass must leave them exactly as the solver
        sc = _scene("A = Point(0, 0)\nB = Point(3, 1)\nC = Point(-2, 4)\n")
        base = compute_label_layout(sc, cfg=CFG)
        clust = compute_label_layout(sc, cfg={**CFG, 'cluster_consistency': True})
        for n in ('A', 'B', 'C'):
            assert np.allclose(base[n].offset_ggb, clust[n].offset_ggb)

    def test_off_by_default(self):
        sc = _scene("P1 = Point(0, 0)\nP2 = Point(0, 1)\nP3 = Point(0, 2)\n")
        a = compute_label_layout(sc, cfg=CFG)
        b = compute_label_layout(sc, cfg={**CFG, 'cluster_consistency': False})
        for n in ('P1', 'P2', 'P3'):
            assert np.allclose(a[n].offset_ggb, b[n].offset_ggb)
