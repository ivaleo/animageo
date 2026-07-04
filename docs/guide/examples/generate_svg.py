"""Generate SVG examples for the HTML style guide.

Each example is declared as a dict (see EXAMPLES below). Two things happen
for every example:

 1. A sample SVG is exported to docs/guide/assets/examples/<name>.svg
 2. A runnable standalone .py source is emitted next to it so readers can
    download and reproduce the picture.

Run:
    cd /path/to/animageo
    PYTHONPATH=. python3.13 docs/guide/examples/generate_svg.py
"""
from __future__ import annotations

import logging
import shutil
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

logging.getLogger().setLevel(logging.ERROR)
for noisy in ['manim', 'animageo', 'animageo.parsers.ggb_parser']:
    logging.getLogger(noisy).setLevel(logging.ERROR)

from manim import config
config.pixel_width = 820
config.pixel_height = 520
config.verbosity = "ERROR"

from animageo.animageo import AnimaGeoScene


HERE = Path(__file__).resolve().parent
OUT = REPO / 'docs/guide/assets/examples'
SRC_OUT = OUT / 'src'
OUT.mkdir(parents=True, exist_ok=True)
SRC_OUT.mkdir(parents=True, exist_ok=True)

STYLE = str(HERE / 'guide_style.json')
shutil.copy(STYLE, SRC_OUT / 'guide_style.json')


# ── Build + render ───────────────────────────────────────────────────

def run_example(name: str, ex: dict, style=STYLE):
    """Build scene from ex-dict, export SVG."""
    scene = AnimaGeoScene()
    w = ex.get('w', 520)
    h = ex.get('h', 340)
    scale = ex.get('scale', 46)
    scene.style.export['ptUnit'] = scale
    scene.style.export['ptWidth'] = w
    scene.style.export['ptHeight'] = h
    scene.style.export['ptXZero'] = w / 2
    scene.style.export['ptYZero'] = h / 2
    scene.applyStyle(style=style, export={"size": {"width": w, "height": h}})

    if ex.get('rendering_extra'):
        scene.style.rendering.update(ex['rendering_extra'])
    overlay_extra = ex.get('overlay_extra') or {}
    if 'angle_radius' in overlay_extra:
        scene.style_config.overlay.angle_radius.update(overlay_extra['angle_radius'])
    if 'label_placement' in overlay_extra:
        scene.style_config.overlay.label_placement.update(overlay_extra['label_placement'])
    if 'per_type' in overlay_extra:
        scene.style_config.overlay.per_type.update(overlay_extra['per_type'])
    if 'per_name' in overlay_extra:
        scene.style_config.overlay.per_name.update(overlay_extra['per_name'])

    scene.putCode(ex['code'])

    for nh in ex.get('hide', ()):
        el = scene.element(nh)
        if el:
            el.visible = False

    for n in ex.get('labels', ()):
        el = scene.element(n)
        if el:
            el.style['label_visible'] = True

    for n, tex in ex.get('tex_labels', {}).items():
        el = scene.element(n)
        if el:
            el.style['label_visible'] = True
            el.style['label_text'] = tex

    for n, props in ex.get('overrides', {}).items():
        el = scene.element(n)
        if el:
            for k, v in props.items():
                el.style[k] = v

    scene.addAllGeometry(show=True)
    scene.updateAllGeometry()

    if ex.get('auto_place', True):
        try:
            scene.autoPlaceLabels()
        except Exception as e:
            print(f'    auto-place warning: {e}')

    svg_path = OUT / f'{name}.svg'
    scene.exportSVG(str(svg_path))
    print(f'  → {svg_path.relative_to(REPO)}')


# ── Emit standalone .py ──────────────────────────────────────────────

def emit_source(name: str, ex: dict):
    """Write a runnable standalone .py reproducing this example."""
    # Serialize example parameters into a compact code block.
    def _repr_dict(d, indent='    '):
        if not d:
            return '{}'
        items = []
        for k, v in d.items():
            items.append(f'{indent}    {k!r}: {v!r},')
        return '{\n' + '\n'.join(items) + '\n' + indent + '}'

    code_block = ex['code'].strip('\n')
    hide = list(ex.get('hide', ()))
    labels = list(ex.get('labels', ()))
    tex_labels = ex.get('tex_labels', {})
    overrides = ex.get('overrides', {})
    rendering_extra = ex.get('rendering_extra', {})
    overlay_extra = ex.get('overlay_extra', {})
    auto_place = ex.get('auto_place', True)
    w = ex.get('w', 520)
    h = ex.get('h', 340)
    scale = ex.get('scale', 46)
    style = ex.get('style', 'guide_style.json')

    # Build the script
    parts = [
        f'"""{name}.py — sample from the AnimaGeo Style Guide.',
        '',
        'Run (from this directory):',
        '    PYTHONPATH=/path/to/animageo python3 ' + f'{name}.py',
        '',
        'Produces: ' + name + '.svg next to this script.',
        '"""',
        'import sys',
        'from pathlib import Path',
        '',
        "# Point to the animageo repo so `from animageo...` resolves.",
        "# Adjust this if you install animageo differently.",
        'HERE = Path(__file__).resolve().parent',
        '',
        "# If animageo isn't installed, uncomment the next line and point it",
        "# to the repo root:",
        "# sys.path.insert(0, '/path/to/animageo')",
        '',
        'from animageo.animageo import AnimaGeoScene',
        '',
        f'STYLE_FILE = str(HERE / {style!r})',
        '',
        f'class Scene(AnimaGeoScene):',
        '    def construct(self):',
        f'        w, h, scale = {w}, {h}, {scale}',
        '        self.style.export[\'ptUnit\'] = scale',
        '        self.style.export[\'ptWidth\'] = w',
        '        self.style.export[\'ptHeight\'] = h',
        '        self.style.export[\'ptXZero\'] = w / 2',
        '        self.style.export[\'ptYZero\'] = h / 2',
        '        self.applyStyle(style=STYLE_FILE, export={"size": {"width": w, "height": h}})',
    ]
    if rendering_extra:
        parts.append(f'        self.style.rendering.update({rendering_extra!r})')
    if overlay_extra:
        if 'angle_radius' in overlay_extra:
            parts.append(f'        self.style_config.overlay.angle_radius.update({overlay_extra["angle_radius"]!r})')
        if 'label_placement' in overlay_extra:
            parts.append(f'        self.style_config.overlay.label_placement.update({overlay_extra["label_placement"]!r})')
        if 'per_type' in overlay_extra:
            parts.append(f'        self.style_config.overlay.per_type.update({overlay_extra["per_type"]!r})')
        if 'per_name' in overlay_extra:
            parts.append(f'        self.style_config.overlay.per_name.update({overlay_extra["per_name"]!r})')
    parts.append(f'        self.putCode("""\n{code_block}\n""")')
    if hide:
        parts.append(f'        for n in {hide!r}:')
        parts.append('            el = self.element(n)')
        parts.append('            if el: el.visible = False')
    if labels:
        parts.append(f'        for n in {labels!r}:')
        parts.append('            el = self.element(n)')
        parts.append('            if el: el.style[\'label_visible\'] = True')
    if tex_labels:
        parts.append(f'        for n, tex in {tex_labels!r}.items():')
        parts.append('            el = self.element(n)')
        parts.append('            if el:')
        parts.append('                el.style[\'label_visible\'] = True')
        parts.append('                el.style[\'label_text\'] = tex')
    if overrides:
        parts.append(f'        for n, props in {overrides!r}.items():')
        parts.append('            el = self.element(n)')
        parts.append('            if el:')
        parts.append('                for k, v in props.items(): el.style[k] = v')
    parts.append('        self.addAllGeometry(show=True)')
    parts.append('        self.updateAllGeometry()')
    if auto_place:
        parts.append('        try: self.autoPlaceLabels()')
        parts.append('        except Exception: pass')
    parts.append(f"        self.exportSVG(str(HERE / '{name}.svg'))")
    parts.append('')
    parts.append('')
    parts.append('if __name__ == \'__main__\':')
    parts.append('    Scene().construct()')

    script = '\n'.join(parts) + '\n'
    (SRC_OUT / f'{name}.py').write_text(script)


# ── Canonical constructions ──────────────────────────────────────────

TRIANGLE = """
A = Point(-4.5, -2)
B = Point(4.5, -2)
C = Point(-0.5, 2.8)
p, a, b, c = Polygon(A, B, C)
alpha = Angle(B, A, C)
beta  = Angle(C, B, A)
gamma = Angle(A, C, B)
"""

RIGHT_TRIANGLE = """
A = Point(-3.5, -2)
B = Point(3.5, -2)
C = Point(-3.5, 2.5)
p, a, b, c = Polygon(A, B, C)
gamma = Angle(A, C, B)
alpha = Angle(B, A, C)
beta  = Angle(C, B, A)
"""

ALL_ANGLES = {'alpha': r'$\alpha$', 'beta': r'$\beta$', 'gamma': r'$\gamma$'}


# ── Example declarations ─────────────────────────────────────────────

EXAMPLES: dict[str, dict] = {

    '01-basic': dict(
        code=TRIANGLE, labels=['A', 'B', 'C'],
        tex_labels=ALL_ANGLES,
    ),

    '02-no-labels': dict(code=TRIANGLE),

    '05-point-types': dict(
        # В Python-DSL у точек нет ggb_raw, поэтому point_type сам по себе ничего
        # не меняет — нужно явно задать stroke / fill / opacity. Здесь три
        # типичных варианта: сплошная чёрная, кольцо, сплошная с цветной заливкой.
        code="A = Point(-3, 0)\nB = Point(0, 0)\nC = Point(3, 0)\n",
        labels=['A', 'B', 'C'],
        overrides={
            'A': {'size_px': 8, 'fill': '#000000', 'fill_opacity': 1,
                  'stroke': '#000000', 'stroke_opacity': 1, 'stroke_width_px': 0.8},
            'B': {'size_px': 8, 'fill': '#ffffff', 'fill_opacity': 1,
                  'stroke': '#000000', 'stroke_opacity': 1, 'stroke_width_px': 1.4},
            'C': {'size_px': 9, 'fill': '#f15b5b', 'fill_opacity': 1,
                  'stroke': '#000000', 'stroke_opacity': 1, 'stroke_width_px': 0.8},
        }),

    '07-line-widths': dict(
        code="A = Point(-4, 2); B = Point(4, 2); C = Point(-4, 0); D = Point(4, 0); E = Point(-4, -2); F = Point(4, -2)\n"
             "s1 = Segment(A, B); s2 = Segment(C, D); s3 = Segment(E, F)\n",
        auto_place=False,
        overrides={
            's1': {'stroke_width_px': 0.75},
            's2': {'stroke_width_px': 1.5},
            's3': {'stroke_width_px': 3},
        }),

    '08-line-dashed': dict(
        code="A = Point(-4, 1.5); B = Point(4, 1.5); C = Point(-4, 0); D = Point(4, 0); E = Point(-4, -1.5); F = Point(4, -1.5)\n"
             "s1 = Segment(A, B); s2 = Segment(C, D); s3 = Segment(E, F)\n",
        auto_place=False,
        overrides={
            's2': {'stroke_dash_ratio': 0.5},
            's3': {'stroke_dash_ratio': 0.8},
        }),

    '10-segment-marks': dict(
        # Слева — прямые штрихи (1/2/3), справа — волнистые (1/2/3).
        # Шесть одинаковых горизонтальных сегментов, разложены в 3 ряда.
        code="""
A1 = Point(-4.5, 1.9);  B1 = Point(-1.2, 1.9)
A2 = Point(-4.5, 0);    B2 = Point(-1.2, 0)
A3 = Point(-4.5, -1.9); B3 = Point(-1.2, -1.9)
C1 = Point(1.2, 1.9);   D1 = Point(4.5, 1.9)
C2 = Point(1.2, 0);     D2 = Point(4.5, 0)
C3 = Point(1.2, -1.9);  D3 = Point(4.5, -1.9)
s1 = Segment(A1, B1); s2 = Segment(A2, B2); s3 = Segment(A3, B3)
w1 = Segment(C1, D1); w2 = Segment(C2, D2); w3 = Segment(C3, D3)
""",
        auto_place=False,
        overrides={
            # Левая колонка — прямые штрихи
            's1': {'tick_count': 1},
            's2': {'tick_count': 2},
            's3': {'tick_count': 3},
            # Правая колонка — волнистые
            'w1': {'tick_count': 1, 'tick_style': 'wave'},
            'w2': {'tick_count': 2, 'tick_style': 'wave'},
            'w3': {'tick_count': 3, 'tick_style': 'wave'},
        }),

    '11-angle-multi-arcs': dict(
        code=TRIANGLE, labels=['A', 'B', 'C'],
        tex_labels=ALL_ANGLES,
        overrides={
            'alpha': {'tick_count': 1},
            'beta':  {'tick_count': 2},
            'gamma': {'tick_count': 3},
        }),

    '12-right-angle': dict(
        code=RIGHT_TRIANGLE, labels=['A', 'B', 'C'],
        # В этом треугольнике прямой угол при вершине A: AB⊥AC.
        # alpha = Angle(B, A, C) — угол при A.
        tex_labels={'alpha': r'$90^{\circ}$'}),

    '16-label-offsets': dict(
        code="P = Point(-2, 0)\nQ = Point(2, 0)\n",
        labels=['P', 'Q'], auto_place=False,
        overrides={
            'P': {'label_offset_px': [0, 0]},
            'Q': {'label_offset_px': [14, 16]},
        }),

    '20-tex-labels': dict(
        code="""
A = Point(-4, 1.5); B = Point(0, 1.5); C = Point(4, 1.5)
D = Point(-4, -1.5); E = Point(0, -1.5); F = Point(4, -1.5)
""",
        overrides={
            'A': {'label_visible': True, 'label_text': r'$A_1$', 'size_px': 5},
            'B': {'label_visible': True, 'label_text': r'$\alpha + \beta$', 'size_px': 5},
            'C': {'label_visible': True, 'label_text': r'$\dfrac{a}{b}$', 'size_px': 5},
            'D': {'label_visible': True, 'label_text': r'$\triangle ABC$', 'size_px': 5},
            'E': {'label_visible': True, 'label_text': r'$x \in \mathbb{R}$', 'size_px': 5},
            'F': {'label_visible': True, 'label_text': r'$60^{\circ}$', 'size_px': 5},
        }),

    '21-vector': dict(
        code="O = Point(-3, -1); A = Point(2, 1.5); v = Vector(O, A)\n",
        labels=['O', 'A'],
        overrides={'v': {'stroke': '#4d87c6', 'stroke_width_px': 2.5}}),

    '22-arc': dict(
        code="""
O = Point(0, 0)
R = Point(2.5, 0)
c = Circle(O, R)
P = Point(-1.9, 1.6)
Q = Point(1.9, 1.6)
arc1 = CircleArc(O, Q, P)
""",
        labels=['O', 'P', 'Q'],
        overrides={'arc1': {'stroke': '#f15b5b', 'stroke_width_px': 2.5}}),

    '23-angles-complete': dict(
        # Используем канонический TRIANGLE (CCW-ориентированный), иначе
        # Angle(B, A, C) даёт reflex-сектор и заливка не совпадает с дугой.
        code=TRIANGLE,
        labels=['A', 'B', 'C'],
        tex_labels=ALL_ANGLES,
        overrides={
            'alpha': {'tick_count': 1},
            'beta':  {'tick_count': 2, 'fill': '#d6e5f6'},
            'gamma': {'tick_count': 3, 'fill': '#fdddd7'},
        }),

    '24-stroke-colors': dict(
        code="""
A = Point(-4, 1.5); B = Point(4, 1.5)
C = Point(-4, 0); D = Point(4, 0)
E = Point(-4, -1.5); F = Point(4, -1.5)
s1 = Segment(A, B); s2 = Segment(C, D); s3 = Segment(E, F)
""",
        auto_place=False,
        overrides={
            's1': {'stroke': '#4d87c6'},
            's2': {'stroke': '#f15b5b'},
            's3': {'stroke': '#58c57e'},
        }),

    '25-composite': dict(
        # По мотивам examples/ex_general.ggb:
        # треугольник ABC, M — середина AB (AM = MB с двойным штрихом),
        # биссектриса угла A пересекает противоположную сторону BC в
        # точке L. Сегмент-биссектриса от A через L чуть выходит за
        # пределы треугольника (экстра 12% длины AL за L).
        #
        # Важно: Polygon(A, B, C) возвращает сегменты в порядке AB, BC,
        # CA, поэтому b = Segment(B, C) — это сторона, противолежащая A,
        # и с ней пересекаем биссектрису.
        code="""
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
""",
        labels=['A', 'B', 'C', 'M', 'L'],
        tex_labels={'beta': r'$\beta$', 'gamma': r'$\gamma$'},
        # Скрываем бесконечную прямую-биссектрису и служебную точку E,
        # видимым остаётся только сегмент A→E (через L с небольшим
        # запасом за треугольник).
        hide=['f', 'E'],
        overrides={
            'p': {'fill': '#d6e5f6', 'fill_opacity': 0.38},
            'j': {'tick_count': 2},
            'k': {'tick_count': 2},
            'bis': {'stroke': '#f15b5b', 'stroke_width_px': 1.2},
            'beta':  {'arc_size_px': 22, 'fill': '#fdddd7',
                      'fill_opacity': 0.7},
            'gamma': {'arc_size_px': 34, 'fill': '#d6e5f6',
                      'fill_opacity': 0.7},
        }),

    '26-angle-radii': dict(
        # Два смежных угла при общей вершине: параметр arc_size_px
        # позволяет дать каждому свой радиус дуги и увидеть их отдельно.
        # Аналогично работает r_offset (без arc_size_px) — добавляется к
        # авто-вычисленному радиусу.
        code="""
A = Point(-3.6, -1.6)
B = Point(3.6, -1.6)
P = Point(-1.6, 2.6)
Q = Point(1.8, 2.6)
s_AB = Segment(A, B)
s_AP = Segment(A, P)
s_AQ = Segment(A, Q)
beta  = Angle(B, A, Q)
gamma = Angle(Q, A, P)
""",
        labels=['A', 'B', 'P', 'Q'],
        tex_labels={'beta': r'$\beta$', 'gamma': r'$\gamma$'},
        overrides={
            'beta':  {'arc_size_px': 18, 'fill': '#fdddd7',
                      'fill_opacity': 0.7},
            'gamma': {'arc_size_px': 32, 'fill': '#d6e5f6',
                      'fill_opacity': 0.7},
        }),

    # ── Conics / Functions / Implicit curves ─────────────────────────

    '30-conic-parabola': dict(
        # Conic.from_string → ConicType.PARABOLA. Renderer автоматически
        # ограничивает sample-range видимой частью viewport
        # (viewport_t_ranges_parabola).
        code="parab = Conic(\"y - 0.4 = (x - 0.3)^2 / 1.6\")\n",
        auto_place=False,
        overrides={'parab': {'stroke': '#4d87c6', 'stroke_width_px': 2.2}},
    ),

    '31-conic-ellipse': dict(
        # Ellipse как Conic. Для замкнутых типов (CIRCLE/ELLIPSE) рендерится
        # manim-примитив, поэтому работает fill и stroke_dash.
        code="ell = Conic(\"(x+0.3)^2 / 5 + (y-0.2)^2 / 2.2 = 1\")\n",
        auto_place=False,
        overrides={'ell': {'stroke': '#4d87c6', 'stroke_width_px': 2.2,
                           'fill': '#d6e5f6', 'fill_opacity': 0.55}},
    ),

    '32-conic-hyperbola': dict(
        # Hyperbola — две ветви, каждая sample-ется независимо по
        # viewport_t_range_hyperbola_branch.
        code="hyp = Conic(\"x^2 / 1.8 - y^2 / 1.2 = 1\")\n",
        auto_place=False,
        overrides={'hyp': {'stroke': '#4d87c6', 'stroke_width_px': 2.2}},
    ),

    '33-conic-circle-dashed': dict(
        # Строковый Conic, который классифицируется как CIRCLE → отрисовка
        # через manim.Circle → поддерживает stroke_dash.
        code="c = Conic(\"x^2 + y^2 = 6\")\n",
        auto_place=False,
        overrides={'c': {'stroke': '#4d87c6', 'stroke_width_px': 2.0,
                         'stroke_dash_ratio': 0.5}},
    ),

    '34-function-basic': dict(
        # Сугар f(x) = expr → Function("y = ...") (см. short_parser).
        code="f(x) = x^2 / 2 - 1\n",
        auto_place=False,
        overrides={'f': {'stroke': '#4d87c6', 'stroke_width_px': 2.2}},
    ),

    '35-function-asymptote': dict(
        # Natural_singularities автоматически определяет x=0, и sampler
        # разрезает диапазон там — никакой «соединяющей» линии нет.
        code="f(x) = 1/x\n",
        auto_place=False,
        overrides={'f': {'stroke': '#f15b5b', 'stroke_width_px': 2.2}},
    ),

    '36-function-piecewise': dict(
        # If[...] → sympy.Piecewise. Область определения ограничена [-2, 2];
        # вне её значение NaN, sampler даёт пустоту.
        code="f(x) = If[-2 <= x <= 2, x^2 - 1]\n",
        auto_place=False,
        overrides={'f': {'stroke': '#4d87c6', 'stroke_width_px': 2.5}},
    ),

    '37-function-trio': dict(
        # Три тригонометрические функции разными цветами/толщинами —
        # демонстрация per-element stroke.
        code="""
f(x) = sin(x)
g(x) = sin(2 * x) / 2
h(x) = sin(3 * x) / 3
""",
        auto_place=False,
        overrides={
            'f': {'stroke': '#4d87c6', 'stroke_width_px': 2.2},
            'g': {'stroke': '#f15b5b', 'stroke_width_px': 1.6},
            'h': {'stroke': '#58c57e', 'stroke_width_px': 1.2},
        },
    ),

    '38-implicit-lemniscate': dict(
        # ImplicitCurve (лемниската Бернулли). Рендер через marching squares
        # на сетке 128×128 внутри viewport.
        code="L = ImplicitCurve(\"(x^2 + y^2)^2 = 4 * (x^2 - y^2)\")\n",
        auto_place=False,
        overrides={'L': {'stroke': '#4d87c6', 'stroke_width_px': 2.2}},
    ),

    '39-implicit-folium': dict(
        # Декартов лист: x³ + y³ = 3axy. Самопересечение в начале координат
        # honestly ловится marching-squares-ом (не нужно вручную его искать).
        code="F = ImplicitCurve(\"x^3 + y^3 = 3 * x * y\")\n",
        auto_place=False,
        overrides={'F': {'stroke': '#f15b5b', 'stroke_width_px': 2.0}},
    ),

    '27-auto-radius': dict(
        # Демонстрация overlay.angle_radius: опциональное масштабирование
        # радиуса дуги в зависимости от раствора угла.
        #
        #   effective_arc = arc_size_px * (pivot_rad / angle) ** exp
        #   clamp: [min_px, max_arm_fraction * min(|v1|, |v2|) * ptUnit]
        #
        # При exp=0.25 узкие углы получают заметно бо́льшую дугу
        # (сохраняя читаемость), тупые — чуть меньше стандарта.
        # Треугольник намеренно сильно вытянут — 13° / 53° / 114°.
        code="""
A = Point(-5, -1.5)
B = Point(5, -1.5)
C = Point(-3.6, 0.6)
p, a, b, c = Polygon(A, B, C)
alpha = Angle(B, A, C)   # ~53°
beta  = Angle(C, B, A)   # ~13° — узкий
gamma = Angle(A, C, B)   # ~114° — тупой
""",
        labels=['A', 'B', 'C'],
        tex_labels={'alpha': r'$\alpha$', 'beta': r'$\beta$',
                    'gamma': r'$\gamma$'},
        overlay_extra={
            'angle_radius': {
                'enabled': True,
                'exp': 0.35,            # Чуть агрессивнее дефолтного 0.25
                'pivot_rad': 1.5708,    # π/2
                'min_px': 16,
                'max_arm_fraction': 0.6,
            }
        },
        overrides={
            # Все три угла с общей базой arc_size_px (через fallback),
            # но радиус при рендере масштабируется по formula(angle).
            'alpha': {'fill': '#fdddd7', 'fill_opacity': 0.7},
            'beta':  {'fill': '#d6e5f6', 'fill_opacity': 0.7},
            'gamma': {'fill': '#dff5e6', 'fill_opacity': 0.7},
        }),
}


# ── Multi-output groups (emitted without per-example .py) ────────────

def gen_palettes():
    for name in ['default', 'book_blue', 'book_red', 'pandora']:
        style = str(REPO / f'style/{name}.json')
        shutil.copy(style, SRC_OUT / f'style-{name}.json')
        # Read color preset hexes from the style file for overrides
        with open(style) as f:
            col = json.load(f)['presets']['color']
        ex = dict(
            code=TRIANGLE, labels=['A', 'B', 'C'],
            tex_labels={'alpha': r'$\alpha$'},
            overrides={
                'p': {'fill': col['light'], 'fill_opacity': 0.6},
                'alpha': {'fill': col['accent_light'], 'fill_opacity': 0.75},
            })
        run_example(f'03-palette-{name}', ex, style=style)


def gen_point_sizes():
    for size in [3, 6, 10]:
        ex = dict(code=TRIANGLE, labels=['A', 'B', 'C'],
                  overrides={n: {'size_px': size} for n in ['A', 'B', 'C']})
        run_example(f'04-point-size-{size}', ex)


def gen_points_display():
    for mode in ['auto', 'only_labels', 'only_points']:
        ex = dict(code=TRIANGLE, labels=['A', 'B', 'C'],
                  rendering_extra={'points_display': mode})
        run_example(f'06-points-display-{mode}', ex)


def gen_line_caps():
    for cap in ['butt', 'round', 'square']:
        ex = dict(code="A = Point(-3, 0); B = Point(3, 0); s = Segment(A, B)\n",
                  auto_place=False,
                  overrides={'s': {'stroke_width_px': 8, 'stroke_linecap': cap}})
        run_example(f'09-line-cap-{cap}', ex)


def gen_polygon_fill():
    for op in [0.15, 0.4, 0.75]:
        ex = dict(code=TRIANGLE, labels=['A', 'B', 'C'],
                  overrides={'p': {'fill': '#4d87c6', 'fill_opacity': op,
                                   'stroke': '#4d87c6'}})
        run_example(f'13-polygon-fill-{int(op*100)}', ex)


def gen_polygon_boundary_top():
    code = """
A = Point(-4, -1.5); B = Point(4, -1.5); C = Point(3, 2.5); D = Point(-3, 2.5)
p, a, b, c, d = Polygon(A, B, C, D)
"""
    for mode in [None, 'top']:
        tag = 'default' if mode is None else 'top'
        tech = {'polygon_boundary_layer': mode} if mode else {}
        ex = dict(code=code, labels=['A', 'B', 'C', 'D'],
                  rendering_extra=tech,
                  overrides={'p': {
                      'fill': '#d6e5f6', 'fill_opacity': 0.7,
                      'stroke_width_px': 2.5, 'stroke': '#4d87c6'}})
        run_example(f'14-polygon-boundary-{tag}', ex)


def gen_label_anchors():
    for anchor in ['BL', 'BC', 'MC', 'TC', 'MR']:
        ex = dict(code="A = Point(0, 0)\n", labels=['A'], auto_place=False,
                  overrides={'A': {'label_anchor': anchor, 'size_px': 8}})
        run_example(f'15-anchor-{anchor}', ex)


def gen_auto_layout_before_after():
    code = """
A = Point(-2, 1.5); B = Point(2, 1.5); C = Point(0, -1.5)
s1 = Segment(A, C); s2 = Segment(B, C); s3 = Segment(A, B)
M = Midpoint(A, B)
D = Midpoint(A, C)
E = Midpoint(B, C)
"""
    labels = ['A', 'B', 'C', 'D', 'E', 'M']
    ex_before = dict(code=code, labels=labels, auto_place=False)
    run_example('17-autolayout-before', ex_before)
    ex_after = dict(code=code, labels=labels, auto_place=True,
                    overlay_extra={'label_placement': {
                        'enabled': True, 'distance_px': 8,
                        'padding_px': 2, 'w_label': 12, 'w_geom': 8,
                    }})
    run_example('17-autolayout-after', ex_after)


def gen_import_policy_mixed_vs_unified():
    code = """
A = Point(-3, -1.5); B = Point(3, -1.5); C = Point(0, 2.5)
M = Midpoint(A, B)
p, a, b, c = Polygon(A, B, C)
"""
    labels = ['A', 'B', 'C', 'M']
    run_example('18-policy-mixed-sizes', dict(
        code=code, labels=labels,
        overrides={
            'A': {'size_px': 5}, 'B': {'size_px': 5},
            'C': {'size_px': 5}, 'M': {'size_px': 3},
        }))
    run_example('18-policy-unified-sizes', dict(
        code=code, labels=labels,
        overrides={n: {'size_px': 6} for n in labels}))


def gen_zindex_demo():
    code = """
A = Point(-2.5, -1.5); B = Point(2.5, -1.5); C = Point(0, 2)
p, a, b, c = Polygon(A, B, C)
O = Point(0, 0); K = Point(2, 0)
circ = Circle(O, K)
"""
    run_example('19-zindex-default', dict(
        code=code, labels=['O'],
        overrides={
            'p': {'fill': '#d6e5f6', 'fill_opacity': 0.8},
            'circ': {'fill': '#fdddd7', 'fill_opacity': 0.5,
                     'stroke': '#f15b5b'},
        }))
    run_example('19-zindex-overridden', dict(
        code=code, labels=['O'],
        overrides={
            'p': {'fill': '#d6e5f6', 'fill_opacity': 0.8, 'z_index': 20},
            'circ': {'fill': '#fdddd7', 'fill_opacity': 0.5,
                     'stroke': '#f15b5b'},
        }))


# ── Main runner ──────────────────────────────────────────────────────

def main():
    # Single-output examples: emit both SVG and .py source
    for name, ex in EXAMPLES.items():
        print(f'▸ {name}')
        try:
            run_example(name, ex)
            emit_source(name, ex)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f'  FAILED: {e}')

    # Multi-output groups: SVGs only, no per-example source (they're sweeps)
    for fn in [gen_palettes, gen_point_sizes, gen_points_display,
               gen_line_caps, gen_polygon_fill, gen_polygon_boundary_top,
               gen_label_anchors, gen_auto_layout_before_after,
               gen_import_policy_mixed_vs_unified, gen_zindex_demo]:
        print(f'▸ {fn.__name__}')
        try:
            fn()
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f'  FAILED: {e}')

    print(f'\nSVGs → {OUT.relative_to(REPO)}')
    print(f'Source files → {SRC_OUT.relative_to(REPO)}')


if __name__ == '__main__':
    main()
