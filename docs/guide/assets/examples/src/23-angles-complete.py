"""23-angles-complete.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 23-angles-complete.py

Produces: 23-angles-complete.svg next to this script.
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
A = Point(-4.5, -2)
B = Point(4.5, -2)
C = Point(-0.5, 2.8)
p, a, b, c = Polygon(A, B, C)
alpha = Angle(B, A, C)
beta  = Angle(C, B, A)
gamma = Angle(A, C, B)
""")
        for n in ['A', 'B', 'C']:
            el = self.element(n)
            if el: el.style['label_visible'] = True
        for n, tex in {'alpha': '$\\alpha$', 'beta': '$\\beta$', 'gamma': '$\\gamma$'}.items():
            el = self.element(n)
            if el:
                el.style['label_visible'] = True
                el.style['label_text'] = tex
        for n, props in {'alpha': {'tick_count': 1}, 'beta': {'tick_count': 2, 'fill': '#d6e5f6'}, 'gamma': {'tick_count': 3, 'fill': '#fdddd7'}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '23-angles-complete.svg'))


if __name__ == '__main__':
    Scene().construct()
