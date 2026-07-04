"""22-arc.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 22-arc.py

Produces: 22-arc.svg next to this script.
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
O = Point(0, 0)
R = Point(2.5, 0)
c = Circle(O, R)
P = Point(-1.9, 1.6)
Q = Point(1.9, 1.6)
arc1 = CircleArc(O, Q, P)
""")
        for n in ['O', 'P', 'Q']:
            el = self.element(n)
            if el: el.style['label_visible'] = True
        for n, props in {'arc1': {'stroke': '#f15b5b', 'stroke_width_px': 2.5}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '22-arc.svg'))


if __name__ == '__main__':
    Scene().construct()
