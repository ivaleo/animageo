# `intersect.line_sector` — intersections of a line and a sector boundary

Registry 1.4 · group `intersect` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `line: linear`, `sector: sector` |
| outputs | `arc.1: point`, `arc.2: point`, `side.1: point`, `side.2: point` |
| policy | `sector_sides` |
| undefined | `zero_length`, `no_intersection`, `outside_part`, `parallel`, `coincident`, `upstream` |
| checks | `incident_both` |

The intersections of a line, segment or ray with the boundary of a sector
(policy `sector_sides`): `arc.1`, `arc.2` on the arc in the order of the line
parameter (slots fixed on the carrier circle before the filters, as
`intersect.line_circle`), `side.1` on the radius from `c` to `S0`, `side.2`
on the radius from `c` to `S1` (`Si = c + r·(cos ai, sin ai)`). A line
through the centre gives `side.1 = side.2 = c`. Circle and sector are not
in 1.0.

## Value

    c = carrier(line)                                   (zero_length)
    arc.1, arc.2 = line_circle_points(line, carrier circle)   (no_intersection, multiplicity 2)
                   then the arc filter (outside_part, slot "sector")
    side.i = carrier × segment c → S(i−1):
        |d × u| ≤ tol.scalar → "coincident" if dist(c, carrier) ≤ tol.decide else "parallel"
        outside the radius → outside_part (slot "sector"); outside the part → outside_part (slot "line")

Arc filter (registry 1.4, also for arcs in `intersect.line_circle`,
`intersect.circle_circle`, `intersect.other_than`): `θ = angle(X − c)`,
`φ = θ − a0` (`< 0 → += 2π`); the point is on the arc when
`r·(φ − (a1 − a0)) ≤ tol.decide` or `r·(2π − φ) ≤ tol.decide`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `tangent` | `h − r` | `tol.decide` |
| `outside_part` | line part and arc values | `tol.decide` |
| `parallel` | `d × u` | `tol.scalar` |
| `coincident` | distance | `tol.decide` |

## Checks

- `incident_both`: the larger of the distances from each point to the line carrier and to the sector boundary
