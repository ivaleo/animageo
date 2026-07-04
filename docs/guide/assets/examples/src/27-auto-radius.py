"""27-auto-radius.py — sample from the AnimaGeo Style Guide.

Run (from this directory):
    PYTHONPATH=/path/to/animageo python3 27-auto-radius.py

Produces: 27-auto-radius.svg next to this script.
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
        self.style_config.overlay.angle_radius.update({'enabled': True, 'exp': 0.35, 'pivot_rad': 1.5708, 'min_px': 16, 'max_arm_fraction': 0.6})
        self.putCode("""
A = Point(-5, -1.5)
B = Point(5, -1.5)
C = Point(-3.6, 0.6)
p, a, b, c = Polygon(A, B, C)
alpha = Angle(B, A, C)   # ~53°
beta  = Angle(C, B, A)   # ~13° — узкий
gamma = Angle(A, C, B)   # ~114° — тупой
""")
        for n in ['A', 'B', 'C']:
            el = self.element(n)
            if el: el.style['label_visible'] = True
        for n, tex in {'alpha': '$\\alpha$', 'beta': '$\\beta$', 'gamma': '$\\gamma$'}.items():
            el = self.element(n)
            if el:
                el.style['label_visible'] = True
                el.style['label_text'] = tex
        for n, props in {'alpha': {'fill': '#fdddd7', 'fill_opacity': 0.7}, 'beta': {'fill': '#d6e5f6', 'fill_opacity': 0.7}, 'gamma': {'fill': '#dff5e6', 'fill_opacity': 0.7}}.items():
            el = self.element(n)
            if el:
                for k, v in props.items(): el.style[k] = v
        self.addAllGeometry(show=True)
        self.updateAllGeometry()
        try: self.autoPlaceLabels()
        except Exception: pass
        self.exportSVG(str(HERE / '27-auto-radius.svg'))


if __name__ == '__main__':
    Scene().construct()
