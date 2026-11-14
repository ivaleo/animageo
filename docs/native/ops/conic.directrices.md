# conic.directrices

Finite directrices of a `conic_section` (`conic` or `circle`). Registry 1.13, beta; module group `conic_elements`.

Optional `count: number` (unit `count`, default 2, integer 1–100) is output capacity. Repeated outputs are `directrix.1` … `directrix.count`, each a native line `{p,dir}` whose p is the projection of the world origin. The entire set is computed before capacity: each defined slot has `detail:{found:N}` even when count=1. For N>0 excess slots are `branch_absent`; for N=0 every slot is `no_directrix`. Undefined records carry no found detail. An unrepresentable finite member makes the entire requested set `non_finite`.

Write X=C+s u+t n, n=CCW90(u), using the existing native frame. For an ellipse or hyperbola, e=c/a, with c=sqrt(a²−b²) or hypot(a,b). Slots are **+a/e, then −a/e** along u, both with dir=n. The first directrix corresponds to focus `second`, the second to focus `first`. For a parabola t²=2ps, the only directrix is s=−p/2 relative to the vertex, with dir=n. A circle has no finite directrix.

Policy: `conic_directrix_order`; orientation: `conic_normal_ccw`. Scaling the source equation by any nonzero factor, including −1, preserves the native frame order. GeoGebra can reverse its eigenvector and consequently reverse its directrix order; native does not follow that sign change.

The focal distance uses the difference of the axes before division; all computations use local geometry and scaled products. Degenerate inputs give `degenerate_conic` or inherited `upstream`, distinct from the empty circle set.

Check `focus_directrix` tests |X−F|=e dist(X,d) at independent curve points for **each defined slot**, including partial sets, and measures orientation error times S. Residuals are lengths. Step kind: `conic_directrices`.
