"""05-point-types.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 05-point-types.py

Produces: 05-point-types.svg next to this script.
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
A = Point(-3, 0)
B = Point(0, 0)
C = Point(3, 0)
""")
        for n in ['A', 'B', 'C']:
            el = self.element(n)
            if el: el.style['label_visible'] = True
        for n, props in {'A': {'size_px': 8, 'fill': '#000000', 'fill_opacity': 1, 'stroke': '#000000', 'stroke_opacity': 1, 'stroke_width_px': 0.8}, 'B': {'size_px': 8, 'fill': '#ffffff', 'fill_opacity': 1, 'stroke': '#000000', 'stroke_opacity': 1, 'stroke_width_px': 1.4}, 'C': {'size_px': 9, 'fill': '#f15b5b', 'fill_opacity': 1, 'stroke': '#000000', 'stroke_opacity': 1, 'stroke_width_px': 0.8}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '05-point-types.svg'))


if __name__ == '__main__':
    Scene().construct()
