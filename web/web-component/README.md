# &lt;animageo-board&gt;

A custom element that embeds an **AnimaGeo interactive geometry board** anywhere
on the web — any framework or none. It wraps [`@animageo/runtime`](../runtime),
turns runtime **signals** into DOM `CustomEvent`s, and exposes **actions** as
element methods.

## Use (no framework)

```html
<script type="module">
  import '@animageo/web-component'; // registers <animageo-board>
</script>

<animageo-board id="b" spec="/board.json" debounce="50"
                style="display:block;width:640px;height:480px"></animageo-board>

<script type="module">
  const el = document.getElementById('b');
  el.addEventListener('animageo:change', (e) => console.log(e.detail.state));
  el.addEventListener('animageo:commit', (e) => save(e.detail));
  // drive it:
  // el.setState({ A: { x: 1, y: 2 } });
</script>
```

`spec` may be a URL (fetched) or inline JSON. Or set the property:
`el.spec = await fetch('/board.json').then(r => r.json())`.

JSXGraph is auto-loaded from a CDN if no `JXG` global is present; override with
the `jsxgraph-src` attribute, or pre-load it yourself, or inject `el.engine`.

## Events (`animageo:<signal>`)

`ready`, `change` (continuous, on drag), `commit` (drag end), `viewchange`,
`error`. `event.detail` is the runtime payload (`{ name, kind, value, state }`
for change/commit). Events bubble and cross shadow DOM (`composed`).

## Methods

`getState()`, `setState(partial)`, `getValue(name)`, `setValue(name, value)`,
`getElement(name)`, `reset()`, `setVisible(name, on)`, `setStyle(name, attrs)`,
`inputs()`, `toSVG()`. `el.handle` exposes the underlying runtime handle.

## Framework interop

Custom elements work in every framework:

- **React** — render `<animageo-board ref={...} />`, set `.spec` and add
  listeners in `useEffect`. (Or use the `useAnimageoBoard` hook example.)
- **Vue** — bind `:spec` and `@animageo:change`; mark the tag as a custom
  element in the compiler options.
- **Angular** — `CUSTOM_ELEMENTS_SCHEMA`, then `(animageo:change)`.

See `examples/web/` for thin adapter templates.

`npm test` runs the suite (Node's built-in runner + a tiny DOM shim).
