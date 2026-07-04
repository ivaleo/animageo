"""20-tex-labels.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 20-tex-labels.py

Produces: 20-tex-labels.svg next to this script.
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
A = Point(-4, 1.5); B = Point(0, 1.5); C = Point(4, 1.5)
D = Point(-4, -1.5); E = Point(0, -1.5); F = Point(4, -1.5)
""")
        for n, props in {'A': {'label_visible': True, 'label_text': '$A_1$', 'size_px': 5}, 'B': {'label_visible': True, 'label_text': '$\\alpha + \\beta$', 'size_px': 5}, 'C': {'label_visible': True, 'label_text': '$\\dfrac{a}{b}$', 'size_px': 5}, 'D': {'label_visible': True, 'label_text': '$\\triangle ABC$', 'size_px': 5}, 'E': {'label_visible': True, 'label_text': '$x \\in \\mathbb{R}$', 'size_px': 5}, 'F': {'label_visible': True, 'label_text': '$60^{\\circ}$', 'size_px': 5}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '20-tex-labels.svg'))


if __name__ == '__main__':
    Scene().construct()
