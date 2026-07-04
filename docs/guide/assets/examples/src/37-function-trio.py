"""37-function-trio.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 37-function-trio.py

Produces: 37-function-trio.svg next to this script.
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
f(x) = sin(x)
g(x) = sin(2 * x) / 2
h(x) = sin(3 * x) / 3
""")
        for n, props in {'f': {'stroke': '#4d87c6', 'stroke_width_px': 2.2}, 'g': {'stroke': '#f15b5b', 'stroke_width_px': 1.6}, 'h': {'stroke': '#58c57e', 'stroke_width_px': 1.2}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        self.exportSVG(str(HERE / '37-function-trio.svg'))


if __name__ == '__main__':
    Scene().construct()
