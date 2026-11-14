# line.conjugate_diameter

The conjugate diameter for `direction: straight` (`line`, `segment`, `ray`, `vector`) and `conic: conic_section`. Registry 1.13, beta; module group `conic_elements`. Output `line: line`; no parameters. Segment/ray inputs are a native extension; no GeoGebra overload is claimed for them.

Only the input direction d matters, not the carrier position or the sign of d. The result is the infinite line (Qd)·X+l·d=0, or the polar of the ideal point (dx,dy,0). It does not require two finite intersection points.

In a central native frame the normal is proportional to (du/a², ±dv/b²), with plus for ellipse/circle and minus for hyperbola; the line passes through C. For a circle this is the diameter perpendicular to d. For an asymptotic hyperbola direction the result is that asymptote itself.

For a parabola t²=2ps the equation is dv t=p du. Exactly dv=0 gives `no_finite_line`. Any nonzero dv is retained, including dv=±1e−12 producing t=±2e12 when p=2 and du=1. Zero d gives `invalid_parameter`; an unrepresentable finite offset gives `non_finite`; degenerate or undefined conics give `degenerate_conic`/`upstream`.

The native line uses the projection of the world origin. Orientation `conic_normal_ccw` first selects the unit normal sign: nx>0 when |nx|>decide.scalar, otherwise ny>0, without zeroing nx. Then dir=CCW90(normal). This is invariant under d↔−d.

Checks `conjugacy` and, for central conics, `through_center` measure the bilinear direction relation, the parabola midpoint equation and center incidence. Residuals are lengths, with angular errors multiplied by S. Step kind: `conjugate_diameter`.
