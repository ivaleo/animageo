# conic.from_circle

Converts a native `circle` into a native `conic` without a world coefficient matrix. Registry 1.13, beta; module group `conic_elements`.

Input: `circle: circle`. Output: **`conic: conic`**, a stable slot name. No parameters.

For center C and radius r>0 the result is `{kind:"ellipse", c:C, axis:[1,0], a:r, b:r}`. Center coordinates and radii are copied directly; neither world coordinates nor radii are squared. Radius zero gives `degenerate_conic`; nonfinite data gives `non_finite`; an undefined source propagates `upstream` and its cause.

The catalog marks this conversion `helper: {ownership:"owned", role:"aux"}`. An editor composing circle focus, vertex or axis actions should create it as a hidden owned auxiliary in the same revision as its consumers, hide it from steps, canvas descriptions and object lists, and remove it with its owner. This metadata describes the editor composition; calling the operation directly still creates an ordinary conic output. The circle remains the dependency source. The four existing conic-part operations and their output slots are unchanged: a circle has two named coincident foci and four chosen horizontal/vertical axis points.

Check `same_circle` compares centers and both radii in length units, and the selected axis with an angular error multiplied by scene scale S. Step kind: `conic_conversion`.

`has("conic_elements")` is true. Import map 10 uses this operation as a hidden,
locked, owned `aux` helper for circle foci, vertices and axes, including axis
selectors. Its stable output slot is `conic`; `origin: {kind: auto, source:
<owner operation ID>}` records ownership. Deleting the owner cleans nested
helpers; surviving users adopt shared helpers. Center uses `point.center`
directly and needs no adapter. This representation has no classic factory.
