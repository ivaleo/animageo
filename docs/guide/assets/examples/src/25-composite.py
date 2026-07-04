"""25-composite.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 25-composite.py

Produces: 25-composite.svg next to this script.
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
A = Point(-4, -1.8)
B = Point(4, -1.8)
C = Point(-0.8, 2.6)
p, a, b, c = Polygon(A, B, C)
M = Midpoint(A, B)
j = Segment(A, M)
k = Segment(M, B)
f = AngularBisector(C, A, B)
L = Intersect(f, b)
E = L + (L - A) * 0.12
bis = Segment(A, E)
beta = Angle(C, A, L)
gamma = Angle(L, A, B)
""")
        for n in ['f', 'E']:
            el = self.element(n)
            if el: el.visible = False
        for n in ['A', 'B', 'C', 'M', 'L']:
            el = self.element(n)
            if el: el.style['label_visible'] = True
        for n, tex in {'beta': '$\\beta$', 'gamma': '$\\gamma$'}.items():
            el = self.element(n)
            if el:
                el.style['label_visible'] = True
                el.style['label_text'] = tex
        for n, props in {'p': {'fill': '#d6e5f6', 'fill_opacity': 0.38}, 'j': {'tick_count': 2}, 'k': {'tick_count': 2}, 'bis': {'stroke': '#f15b5b', 'stroke_width_px': 1.2}, 'beta': {'arc_size_px': 22, 'fill': '#fdddd7', 'fill_opacity': 0.7}, 'gamma': {'arc_size_px': 34, 'fill': '#d6e5f6', 'fill_opacity': 0.7}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '25-composite.svg'))


if __name__ == '__main__':
    Scene().construct()
