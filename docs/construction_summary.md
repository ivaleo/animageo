# Compact construction summary for AI

The `animageo-construction-summary/v1` format is designed for handing a
geometric construction to an LLM without the raw `.ggb` XML. It captures only
what is typically needed to generate a style JSON: names, types, compact
geometry, visibility, the imported GGB style, element groups, and parser
diagnostics.

The main scenario:

```python
scene.loadGGB("scene.ggb", style="base.json", export={"size": {"width": 800, "height": 600}})
summary = scene.exportStylePromptSummary("scene.summary.json")
```

If you do not need a file:

```python
summary = scene.exportStylePromptSummary()
```

Low-level helper without a Manim scene:

```python
from animageo.exporters.construction_summary import construction_to_ai_summary

summary = construction_to_ai_summary(construction)
```

## Top-level schema

```json
{
  "schema": "animageo-construction-summary/v1",
  "source": {
    "kind": "ggb",
    "name": "scene.ggb",
    "path": "/abs/path/scene.ggb"
  },
  "viewport": {
    "size": [800, 600],
    "ptUnit": 50,
    "ptUnit_ggb": 50,
    "ptXZero": 400,
    "ptYZero": 300,
    "fontSize": 16
  },
  "stats": {
    "point": 3,
    "segment": 3,
    "angle": 1
  },
  "elements": [],
  "groups": {
    "points": ["A", "B", "C"],
    "segments": ["AB", "BC", "CA"],
    "angles": ["alpha"]
  },
  "warnings": []
}
```

Fields:

| Field | Purpose |
| --- | --- |
| `schema` | Format version. Current: `animageo-construction-summary/v1` |
| `source` | Construction source: `ggb`, `dsl_file`, `dsl_inline`, `unknown` |
| `viewport` | Export size/scale, when known |
| `stats` | Count of exported elements per canonical type |
| `elements` | Compact element records |
| `groups` | Quick name lists per type |
| `warnings` | `Construction.command_diagnostics`, when the parser/rebuild found problems: unsupported commands, formulas that cannot be read (`expression_parse_error`), objects that cannot follow the numbers they mention (`parametric_dependency_frozen`) |
| `vars` | Numeric/boolean/angle variables, if any |
| `truncated` | Truncation metadata when `max_elements` is used |

The hidden built-in `xAxis` and `yAxis` are not exported by default.

## Element record

```json
{
  "name": "A",
  "type": "point",
  "visible": true,
  "label_visible": true,
  "construction": {
    "command": "Point",
    "inputs": [0, 0],
    "outputs": ["A"]
  },
  "geometry": {
    "coords": [0, 0]
  },
  "ggb_style": {
    "size_px": 10,
    "fill": "#1565c0",
    "stroke": "#000000",
    "label_color": "#1565c0",
    "label_visible": true
  },
  "ggb_raw_summary": {
    "elem_type": "point",
    "point_size": 5,
    "point_style": 0,
    "obj_color": {
      "hex": "#1565c0",
      "opacity": 0
    }
  }
}
```

Common element fields:

| Field | Purpose |
| --- | --- |
| `name` | Element name in AnimaGeo after GeoGebra name normalization |
| `type` | Canonical type: `point`, `segment`, `line`, `angle`, ... |
| `visible` | Current element visibility |
| `label_visible` | Label visibility, when known from `ggb_style` or `style` |
| `construction` | Command, inputs, and outputs, when the element was created by a command |
| `geometry` | Compact geometry, type-dependent |
| `ggb_style` | Normalized imported visual layer |
| `style` | Explicit/intrinsic `elem.style`, only with `include_style=True` |
| `resolved_style` | Effective style through the resolver, only with `include_resolved_style=True` |
| `ggb_raw_summary` | Small allow-list of raw GGB attributes; not the raw XML |

## Geometry payloads

`point`:

```json
{ "coords": [x, y] }
```

`segment`:

```json
{ "endpoints": [[x1, y1], [x2, y2]], "length": 3.0 }
```

`line`:

```json
{ "normal": [a, b], "direction": [dx, dy], "offset": c }
```

`ray`:

```json
{ "start": [x, y], "direction": [dx, dy] }
```

`vector`:

```json
{ "endpoints": [[x1, y1], [x2, y2]], "direction": [dx, dy] }
```

`angle`:

```json
{
  "vertex": [x, y],
  "side1": [dx1, dy1],
  "side2": [dx2, dy2],
  "size_rad": 1.0472,
  "size_deg": 60.0,
  "start_angle": 0.0,
  "end_angle": 1.0472
}
```

`polygon`:

```json
{ "vertices": [[x1, y1], [x2, y2], [x3, y3]], "vertex_count": 3 }
```

`circle`:

```json
{ "center": [x, y], "radius": 2.0 }
```

`arc` / `circlesector`:

```json
{ "center": [x, y], "radius": 2.0, "angles": [0.0, 1.57] }
```

`conic`:

```json
{ "kind": "ellipse", "matrix": [[...], [...], [...]] }
```

`function`:

```json
{ "source": "y=x^2", "expr": "x**2", "var": "x", "domain": null }
```

`implicitcurve`:

```json
{ "source": "x^2+y^2=1", "expr": "x**2 + y**2 - 1", "var_x": "x", "var_y": "y" }
```

## Exporter parameters

`scene.exportStylePromptSummary(filepath=None, **kwargs)` returns a dict and,
when `filepath` is given, writes the JSON.

Supported `kwargs`:

| Parameter | Default | Description |
| --- | --- | --- |
| `include_geometry` | `True` | Include `geometry` payloads |
| `include_ggb_style` | `True` | Include `ggb_style` |
| `include_style` | `False` | Include explicit/intrinsic `elem.style`; can be noisy |
| `include_resolved_style` | `False` | Include the effective style through the resolver |
| `include_axes` | `False` | Include the built-in `xAxis` / `yAxis` |
| `max_elements` | `None` | Cap the number of elements; the rest goes into `truncated` |
| `style_keys` | built-in allow-list | Restrict the keys in style payloads |
| `source` | from the scene | Override `source` |
| `viewport` | from `scene.style.export` | Override `viewport` |

Example for a large `.ggb` where the LLM only needs the object list and the
imported style, but not the coordinates:

```python
summary = scene.exportStylePromptSummary(
    "scene.summary.json",
    include_geometry=False,
    max_elements=300,
)
```

Example with the effective style after the current style JSON:

```python
summary = scene.exportStylePromptSummary(
    include_resolved_style=True,
    style_keys=["stroke", "stroke_width_px", "fill", "fill_opacity", "size_px"]
)
```

## Using the summary in an AI pipeline

For style generation, a model request typically includes:

1. The user's verbal request.
2. The style-generation context (`docs/ai_style_generation_context.md`).
3. The style JSON Schema (`docs/ai_style_json_schema.json`).
4. This compact summary, when the request depends on a specific construction.
5. Response format instructions: JSON only, or JSON + AnimaGeo Python DSL
   for `scene.loadCode(...)`.

The summary helps the model:

- not invent element names;
- decide whether a rule belongs in `overlay.per_type` or `overlay.per_name`;
- see which GGB visual styles need to be overridden or preserved;
- propose AnimaGeo Python DSL for procedural extra styling of named
  objects via `scene.loadCode(...)`.

The summary is not meant for a full reconstruction of the construction. It is
a prompt artifact, not a geometry exchange format. For AI-driven creation and
editing of constructions the summary serves as read-only context for
name-based patch editing; see
[ai_construction_generation_context.md](ai_construction_generation_context.md).
