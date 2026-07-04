"""12-right-angle.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 12-right-angle.py

Produces: 12-right-angle.svg next to this script.
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
A = Point(-3.5, -2)
B = Point(3.5, -2)
C = Point(-3.5, 2.5)
p, a, b, c = Polygon(A, B, C)
gamma = Angle(A, C, B)
alpha = Angle(B, A, C)
beta  = Angle(C, B, A)
""")
        for n in ['A', 'B', 'C']:
            el = self.element(n)
            if el: el.style['label_visible'] = True
        for n, tex in {'alpha': '$90^{\\circ}$'}.items():
            el = self.element(n)
            if el:
                el.style['label_visible'] = True
                el.style['label_text'] = tex
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '12-right-angle.svg'))


if __name__ == '__main__':
    Scene().construct()
