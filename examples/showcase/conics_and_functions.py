"""Conics, functions, and implicit curves built in the pure-Python DSL.

Run:  python conics_and_functions.py   (writes conics_and_functions.svg)
"""
from manim import config
config.pixel_width, config.pixel_height = 900, 600

from animageo.animageo import AnimaGeoScene

W, H = 900, 600


class Showcase(AnimaGeoScene):
    def construct(self):
        self.applyStyle(style='default',
                        export={'size': {'width': W, 'height': H}})
        self.putCode('''
            g = Conic("x^2 / 9 + y^2 / 4 = 1")
            f = Function("y = 0.25 * x^2 - 2.5")
            A, B = Intersect(f, g)
            O = Center(g)
            F1, F2 = Focus(g)
            lemn = ImplicitCurve("(x^2 + y^2)^2 = 12 * (x^2 - y^2)")

            style(g, stroke="color.main", stroke_width_px="line_width.bold")
            style(f, stroke="color.accent")
            style(lemn, stroke="color.aux")
            style(A, B, fill="color.accent", label_visible=True)
            style(O, F1, F2, fill="color.main", size_px="point_size.aux",
                  label_visible=True)
        ''')
        self.fitView(W, H, padding=30)
        self.autoPlaceLabels()
        self.exportSVG('conics_and_functions.svg')


if __name__ == '__main__':
    Showcase().construct()
