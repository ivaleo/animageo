"""07-line-widths.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 07-line-widths.py

Produces: 07-line-widths.svg next to this script.
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
A = Point(-4, 2); B = Point(4, 2); C = Point(-4, 0); D = Point(4, 0); E = Point(-4, -2); F = Point(4, -2)
s1 = Segment(A, B); s2 = Segment(C, D); s3 = Segment(E, F)
""")
        for n, props in {'s1': {'stroke_width_px': 0.75}, 's2': {'stroke_width_px': 1.5}, 's3': {'stroke_width_px': 3}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        self.exportSVG(str(HERE / '07-line-widths.svg'))


if __name__ == '__main__':
    Scene().construct()
