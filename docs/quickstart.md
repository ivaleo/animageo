# Quickstart

## Installation

```bash
pip install animageo
```

Core dependencies (`numpy`, `manim >= 0.20.1`, `pycairo`, `sympy`, `scipy`)
are installed automatically. Rendering MP4/GIF additionally needs a working
manim toolchain (ffmpeg, and a LaTeX install for text labels).

## Minimal example

```python
from animageo import *

class MyScene(AnimaGeoScene):
    def construct(self):
        # Load a GeoGebra construction
        self.loadGGB('triangle.ggb',
                     style='default',
                     export={'size': {'width': 800, 'height': 600}})

        # Show all elements
        self.wait(2)

        # Export to SVG
        self.exportSVG('triangle.svg')
```

Run:

```bash
manim my_scene.py MyScene -ql
```

Bare style names (`default`, `book_blue`, `book_green`, `book_purple`,
`book_red`) resolve to presets shipped inside the package; a path to your own
style JSON works too, and omitting `style` uses the builtin defaults.

## Adding your own geometry

Constructions are extended with an exec-based Python DSL — full Python
(loops, conditionals, functions, kwargs, comprehensions). Details:
[docs/python_dsl.md](python_dsl.md).

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.loadGGB('scene.ggb', style='default',
                     export={'size': {'width': 800, 'height': 600}})

        # Add elements through the Python DSL
        self.putCode('''
            M = Midpoint(A, B)
            h = Segment(C, M)

            # Python constructs work too
            for i in range(3):
                p = Point(i, 0)          # creates p, p_2, p_3

            # Field access and styling
            M.style.stroke = '#ff0000'
            x_val = A.x                  # coordinate as float
        ''')

        # Or load from a file (a .py file next to the scene)
        self.loadCode('extra_constructions.py')
```

## Animating with variables

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.loadGGB('scene.ggb', style='default',
                     export={'size': {'width': 400, 'height': 400}})

        # Create a variable and bind it to the construction
        t = self.addVar('t', 0.0)
        self.addUpdater(t)

        # Animate
        self.play(t.animate.set_value(1.0), run_time=3)
        self.clearUpdater(t)
```

## Keyframe animation

For saved timelines, web previews, and repeatable renders use
`play_keyframes()`. First check which inputs are animatable:

```python
independents = self.get_independent_elements()
```

A minimal v2 timeline:

```python
self.play_keyframes({
    "version": 2,
    "keyframes": [
        {"t": 0, "values": {"A": [0, 0], "x": 35}},
        {"t": 2, "values": {"A": [4, 2], "x": 110},
         "styles": {"a": {"stroke": "#d05456"}},
         "visible": {"helper": False},
         "easing": "smooth"},
    ],
})
```

V2 supports style tracks, visibility with entrance/exit effects, 17 easing
names, `@camera`, emphasis events, `reveal_construction()`, and static
previews via `apply_keyframes_at()`. The format is fully described in
[docs/keyframes.md](keyframes.md).

## Controlling visibility

```python
self.HideAll()                              # Hide everything
self.playShow(['A', 'B', 'C'])              # Reveal points
self.playShow(['poly1'], mode='Create')     # Construction animation
self.playShade(['A', 'B'])                  # Dim
self.playRestore(['A', 'B'])                # Restore
```

## Conics, functions, and implicit curves

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.applyStyle(style='default',
                        export={'size': {'width': 800, 'height': 600}})

        self.putCode('''
            # A conic from an equation (type is classified automatically).
            g = Conic("x^2 + y^2 = 4")

            # A function through the string constructor.
            f = Function("y = x^2 - 1")

            # Or in the short "sugar" form (rewritten by the DSL preprocessor).
            h(x) = -abs(x) + 4

            # Intersections work across all types.
            A, B = Intersect(f, g)

            # GGB-style conic commands.
            O = Center(g)
            F1, F2 = Focus(g)

            # An implicit curve (marching squares).
            lemn = ImplicitCurve("(x^2 + y^2)^2 = 8 * (x^2 - y^2)")
        ''')

        self.exportSVG('conics.svg')
```

## Overriding styles

Styling in AnimaGeo has three layers (see [docs/styles.md](styles.md)):

1. **`defaults`** in the JSON (and the package-shipped `builtin.json`) —
   per-type baselines in pixels. Works for both DSL and GGB elements.
2. **`overlay.per_type` / `per_name`** — applied on top of the import,
   also works everywhere.
3. **`ImportPolicy`** (`loadGGB(..., import_policy=...)`) — specialized for
   **raw-GGB transforms** (`scale:/quantize:/remap:`); has no effect on DSL
   elements.

Unifying styles through `overlay` (identical for GGB and DSL):

```json
"overlay": {
    "per_type": {
        "point":   {"size_px": 7, "fill": "#000"},
        "segment": {"stroke_width_px": 2.2},
        "angle":   {"arc_size_px": 22, "label_color": "#222"}
    }
}
```

Alternatively — through the Python API when loading a GGB file:

```python
from animageo.style.import_policy import ImportPolicy

scene.loadGGB(
    'scene.ggb',
    style='default',
    export={'size': {'width': 800, 'height': 600}},
    import_policy=ImportPolicy(
        stroke_width_px='quantize:[1, 2, 4]',  # bucket GGB thicknesses
        label_color='#222222',                 # unified label color
    ),
)
```

The full cookbook: [docs/import_policies.md](import_policies.md).

## Export

```python
# SVG (via Cairo)
self.exportSVG('output.svg')

# TikZ for LaTeX / interactive JSXGraph
self.exportTikZ('output.tex')
self.exportJSXGraph('board.html')

# MP4 --- rendered through manim
# manim scene.py MyScene -qh
```
