# ImportPolicy: configurable GGB → import-style conversion

`ImportPolicy` controls how `.ggb` files are translated into rendered
styles when calling `AnimaGeoScene.loadGGB()`. By default it preserves
GeoGebra values 1-to-1 (backward compatible). Override it to unify fonts,
quantize thicknesses, remap colors, or do arbitrary per-element
transformations.

> **ImportPolicy специализирован под GGB-only трансформации.**
> Для стилизации, применяемой одинаково к GGB и DSL-элементам —
> `per_type` / `per_name` по типу или имени, автоматизмы
> (`angle_radius`, `label_placement`) — используйте секцию `overlay` в
> JSON (см. `docs/styles.md`, раздел «StyleConfig: три слоя»).
>
> Кратко: **`ImportPolicy` = raw-GGB трансформации** (`scale:/quantize:/remap:`).
> **`overlay` = стилизация поверх импорта**, работает везде.

To disable the whole GGB visual import layer, use style JSON:

```json
{ "import": { "enabled": false } }
```

The `.ggb` geometry still loads and `elem.ggb_raw` is preserved, but GGB
visual values do not become the render baseline. The resolver falls back to
`StyleConfig.defaults`; `import.colors`, `import.point_size`,
`import.line_width`, and `import.policy` are skipped.

## Quick start

```python
from animageo.animageo import AnimaGeoScene
from animageo.style.import_policy import ImportPolicy

scene = AnimaGeoScene()
scene.loadGGB(
    'file.ggb',
    style='style/default.json',
    export={'size': {'width': 800, 'height': 600}},
    import_policy=ImportPolicy(font_size_px=14, label_color='#222222'),
)
```

## Configuration sources

Lowest to highest priority:

1. Built-in defaults (`ImportPolicy.faithful()`).
2. `import.policy` section in the style JSON.
3. `loadGGB(..., import_policy=...)` argument.
4. Per-element `setElementStyle()` after load.

## Fields

Each field accepts: `None` (use base mode), a literal scalar, a Python
callable `fn(raw, defaults, elem)`, or a string DSL directive. See
"Mini-DSL" below.

| Field | GGB source | `elem.ggb_style` target |
|---|---|---|
| `size_px` | `<pointSize val>` | `size_px` |
| `stroke_width_px` | `<lineStyle thickness>` | `stroke_width_px` |
| `arc_size_px` | `<arcSize val>` | `arc_size_px` |
| `label_offset_px` | `<labelOffset x y>` | `label_offset_px` |
| `label_color` | `<objColor>` as `obj_color.hex` | `label_color` |
| `label_visible` | `<show label>` | `label_visible` |
| `visible` | `<show object>` | `visible` |
| `label_text` | `<caption>` | `label_text` |
| `label_mode` | `<labelMode val>` (`0/1/2/3/9`) | `label_mode` |
| `label_value_precision` | literal / callable | `label_value_precision` |
| `label_value_strip_zeros` | literal / callable | `label_value_strip_zeros` |
| `label_angle_unit` | literal / callable | `label_angle_unit` |
| `label_value_separator` | literal / callable | `label_value_separator` |
| `angle_range` | `<angleStyle val>` | `angle_range` |
| `tick_count` | `<decoration type>` | `tick_count` |
| `font_size_px` | `<gui><font size>` / literal | `font_size_px` |
| `stroke` | `<objColor>` as `obj_color.hex` | `stroke` |
| `fill` | `<objColor>` as `obj_color.hex` | `fill` |
| `fill_opacity` | `<objColor alpha>` as `obj_color.opacity` | `fill_opacity` |
| `point_shape` | `<pointStyle val>` | `point_shape` |
| `stroke_opacity` | `<lineStyle opacity>` | `stroke_opacity` |
| `stroke_dash_ratio` | `<lineStyle type>` | `stroke_dash_ratio` |
| `stroke_linecap` | — | `stroke_linecap` |

Raw `obj_color` contains `r`, `g`, `b`, legacy `alpha`, plus normalized
`hex` (`#rrggbb`) and `opacity` aliases for policy callables and DSL remaps.

`elem.ggb_raw` remains a diagnostic/source layer. `elem.ggb_style` is the
normalized GGB import baseline consumed by the resolver between `overlay` and
`defaults`. Direct user edits still belong in `elem.style`.

## Mini-DSL (строки)

| Директива | Значение |
|---|---|
| `"const:3"` | Фиксированное значение `3`. |
| `"scale:1.5"` | Умножить сырой GGB-ввод на `1.5`. |
| `"quantize:[1,2,4]"` | Снап к ближайшему элементу списка. |
| `"remap:{'#f00':'#c00'}"` | Lookup по словарю; miss возвращает исходное. |
| `"match_element"` | Копировать stroke в label (sentinel). |
| `"auto"` | Делегировать решение downstream-алгоритму (sentinel). |

Обычные строки вроде `"#000000"` проходят насквозь.

DSL-строки одинаково работают и при загрузке из JSON (через `from_dict`), и при прямой передаче в Python-конструктор — `ImportPolicy(stroke_width_px='quantize:[1,2,4]')` эквивалентно соответствующей JSON-записи. Парсинг происходит в `__post_init__`. Полноценные лямбды всё равно доступны только из Python API.

## Project overrides

`ImportPolicy` no longer owns `per_type` / `per_name`. These rules are not
raw GeoGebra adaptation; they are project-level styling and belong to
`overlay`, where they apply uniformly to imported GGB objects and DSL-created
objects:

```json
"overlay": {
    "per_type": { "polygon": { "fill_opacity": 0.15 } },
    "per_name": { "A": { "size_px": 99 } }
}
```

## Cookbook

### 1. Verbatim GeoGebra (default — no code)

```python
scene.loadGGB('file.ggb')
```

### 2. Everything from style.json, ignore GGB sizes/colors

```python
scene.loadGGB(
    'file.ggb',
    import_policy=ImportPolicy.style_only(),
    style='style/default.json',
)
```

### 3. Unified labels (14pt, dark-gray, all elements)

```python
ImportPolicy(font_size_px=14, label_color='#222222')
```

### 4. Uniform point size

```python
ImportPolicy(size_px=3)
```

### 5. Scaled sizes

```python
ImportPolicy(
    size_px=lambda raw, d, e: raw * 1.5,
    stroke_width_px=lambda raw, d, e: raw * 1.2,
)
```

JSON equivalent:

```json
{ "size_px": "scale:1.5", "stroke_width_px": "scale:1.2" }
```

### 6. Quantized thicknesses

```python
ImportPolicy(stroke_width_px='quantize:[1, 2, 4]')
```

### 7. Brand color remap

```python
ImportPolicy(stroke="remap:{'#1565c0':'#0066cc'}")
```

### 8. Type/name overrides: use overlay

```json
{
  "overlay": {
    "per_type": {
      "polygon": { "fill_opacity": 0.1, "stroke": "#888888" }
    },
    "per_name": {
      "A": { "size_px": 18, "label_color": "#ff0000" }
    }
  }
}
```

### 9. Black & white mode

```python
ImportPolicy(
    stroke='#000000',
    fill='#cccccc',
    label_color='#000000',
)
```

### 10. Hide all labels

```python
ImportPolicy(label_visible=False)
```

### 11. Swap policies without re-parsing

```python
scene.loadGGB('file.ggb')
# ... inspect ...
scene.reloadPolicy(ImportPolicy(size_px=5))
```

## JSON format in style files

```json
{
  "import": {
    "policy": {
      "preset": "custom",
      "size_px": "scale:1.5",
      "stroke_width_px": "quantize:[1,2,4]",
      "font_size_px": 14,
      "label_color": "#222222",
      "stroke": "remap:{'#1565c0':'#0066cc'}"
    }
  }
}
```

## Notes on behavior

- `faithful()` base (default) starts from the parser's current output —
  no observable change from pre-ImportPolicy versions.
- `style_only()` base ignores `ggb_raw` entirely and starts from the
  `defaults` dict passed to `resolve()`. The downstream caller supplies
  defaults from `GeoStyle` for full effect.
- Callables always receive the *raw* GGB value (e.g., `pointSize=5`,
  not `size=10`). Conversion multipliers are bypassed when a policy
  field is active.
- `label_offset` resolves via the same path, but note that GGB `y` is
  not inverted inside the callable — pass `[x, -y]` explicitly if you
  need math-coord offsets.
