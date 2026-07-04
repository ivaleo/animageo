"""10-segment-marks.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 10-segment-marks.py

Produces: 10-segment-marks.svg next to this script.
"""
import sys
from pathlib import Path

# Point to the animageo repo so `from animageo...` resolves.
# Adjust this if you install animageo differently.
HERE = Path(__file__).resolve().parent

# If animageo isn't installed, uncomment the next line and point it
# to the repo root:
# sys.path.insert(0, '/path/to/animageo')

from animageo.animageo import AnimaGeoScene

STYLE_FILE = str(HERE / 'guide_style.json')


class Scene(AnimaGeoScene):
    def construct(self):
        w, h, scale = 520, 340, 46
        self.style.export['ptUnit'] = scale
        self.style.export['ptWidth'] = w
        self.style.export['ptHeight'] = h
        self.style.export['ptXZero'] = w / 2
        self.style.export['ptYZero'] = h / 2
        self.applyStyle(style=STYLE_FILE, export={"size": {"width": w, "height": h}})
        self.putCode("""
A1 = Point(-4.5, 1.9);  B1 = Point(-1.2, 1.9)
A2 = Point(-4.5, 0);    B2 = Point(-1.2, 0)
A3 = Point(-4.5, -1.9); B3 = Point(-1.2, -1.9)
C1 = Point(1.2, 1.9);   D1 = Point(4.5, 1.9)
C2 = Point(1.2, 0);     D2 = Point(4.5, 0)
C3 = Point(1.2, -1.9);  D3 = Point(4.5, -1.9)
s1 = Segment(A1, B1); s2 = Segment(A2, B2); s3 = Segment(A3, B3)
w1 = Segment(C1, D1); w2 = Segment(C2, D2); w3 = Segment(C3, D3)
""")
        for n, props in {'s1': {'tick_count': 1}, 's2': {'tick_count': 2}, 's3': {'tick_count': 3}, 'w1': {'tick_count': 1, 'tick_style': 'wave'}, 'w2': {'tick_count': 2, 'tick_style': 'wave'}, 'w3': {'tick_count': 3, 'tick_style': 'wave'}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        self.exportSVG(str(HERE / '10-segment-marks.svg'))


if __name__ == '__main__':
    Scene().construct()
