# line.polar_conic

The polar line of `point: point` with respect to `conic: conic_section`. Registry 1.13, beta; module group `conic_elements`. Output `line: line`; no parameters.

For the canonical-sign homogeneous quadratic M*, the polar is L=M* P_h. In the existing local native frame its equation is

- ellipse: (s0/a²)s+(t0/b²)t=1;
- hyperbola: (s0/a²)s−(t0/b²)t=1;
- parabola t²=2ps: −ps+t0 t=p s0;
- circle: (P−C)·(X−C)=r².

The point may be inside, on or outside the conic. At the exact center of a central conic the projective polar is the line at infinity: `no_finite_line`. Every nonzero displacement is retained; a polar as far away as x=9e12 for P=(1e−12,0) on x²/9+y²/4=1 is finite. An unrepresentable finite line gives `non_finite`. Degenerate inputs give `degenerate_conic` or inherited `upstream`.

The result stores the projection p of the world origin and dir=CCW90 of the canonical normal. The sign is F(C)<0 for central conics and positive nonzero quadratic eigenvalue for a parabola, shared with conic tangency. On the curve the line and its direction agree with `line.tangent_conic_at`. No extra normal-sign flip is applied to the polar.

Scaled local products avoid world coefficient matrices, axis squares and unnecessary intermediate overflow. Exact binary significands are summed before the final binary64 rounding, preserving small terms when large translated terms cancel. Check `polar_incidence` measures the normalized bilinear relation, perpendicularity and oriented unit-direction error, all in length units (angular errors times S). Step kind: `polar_line`. This is the point-to-line polar; the pole of a line is outside its scope.

Map 10 lowers GeoGebra `Polar(Point,Conic/Circle)` and the existing Python
DSL factories, including its reversed `Polar(K,P)` alias. Safe inline point
and quadratic expressions retain live references through owned aux helpers.
Line-to-point poles and scalar inputs are `unsupported_signature`.
`has("conic_elements")` is true; the separate Commands printer reports
`unprintable_operation` for this operation.
