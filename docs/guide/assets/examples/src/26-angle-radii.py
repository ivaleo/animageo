"""26-angle-radii.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 26-angle-radii.py

Produces: 26-angle-radii.svg next to this script.
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
A = Point(-3.6, -1.6)
B = Point(3.6, -1.6)
P = Point(-1.6, 2.6)
Q = Point(1.8, 2.6)
s_AB = Segment(A, B)
s_AP = Segment(A, P)
s_AQ = Segment(A, Q)
beta  = Angle(B, A, Q)
gamma = Angle(Q, A, P)
""")
        for n in ['A', 'B', 'P', 'Q']:
            el = self.element(n)
            if el: el.style['label_visible'] = True
        for n, tex in {'beta': '$\\beta$', 'gamma': '$\\gamma$'}.items():
            el = self.element(n)
            if el:
                el.style['label_visible'] = True
                el.style['label_text'] = tex
        for n, props in {'beta': {'arc_size_px': 18, 'fill': '#fdddd7', 'fill_opacity': 0.7}, 'gamma': {'arc_size_px': 32, 'fill': '#d6e5f6', 'fill_opacity': 0.7}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '26-angle-radii.svg'))


if __name__ == '__main__':
    Scene().construct()
