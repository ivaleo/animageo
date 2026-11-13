# `region.by_boundary` — the region bounded by pieces and contours

Registry 1.9 · group `region` · status `beta` · branch `null` · see [kernel.md](../kernel.md) §16.2.

| | |
|---|---|
| inputs | `curves: curve[]`, `from: point[]`, `to: point[]` (min 0; one length); `inside: contour[]`, `outside: contour[]` (min 0; family `contour` = polygon, circle, sector, circlesegment) |
| params | none |
| outputs | `region: region` (`stepKind` `region_boundary`) |
| undefined | `unsupported_signature`, `not_on_curve`, `outside_part`, `empty_region`, `boundary_crossing`, `flipped`, `upstream`; error `schema` (the chain), `limit_exceeded` |
| checks | `on_carriers` |

## The chain

Piece `i` runs on `curves[i]` from `from[i]` to `to[i]`: a line, segment or ray
gives a straight piece, a circle or an arc the arc counterclockwise from
`from` to `to`; `from == to` (one ID) the whole circle. Graphs and conics as
carriers come later: `unsupported/unsupported_signature`, `detail.slot`.

The rings are assembled by IDs only (`region.boundary_chain`):

- the first piece of a ring runs forward;
- the next one starts where the ring has come (forward) or ends there
  (backward: an arc is then walked clockwise);
- the ring closes when it comes back to its first vertex; the next piece
  opens a new ring;
- a whole circle is a ring of its own, on a circle or an arc;
- the last ring is closed, and some ring exists (pieces or contours).

A break is the issue `region_chain` of `validate` (`path` `…/args`) and the
state `error/schema` in evaluation.

## The value

The rings of the chain in document order, then the contours of `inside`
(walked counterclockwise), then those of `outside` (clockwise).
A contour is walked from a fixed start:

- a polygon: its sides in the order of the vertices when their shoelace sum
  is not negative, else `v0, v(n−1), …, v1`;
- a circle: the whole circle from `(cx + r, cy)`;
- a sector: centre → the start of its arc, the arc, its end → centre;
- a circle segment: the arc, then the chord from its end to its start;
- a sector or a circle segment of a full turn (`a1 − a0 ≥ 2π`): the whole
  circle from the start of its arc.

A contour of `outside` is that ring reversed (from the same start). A piece
keeps the source of its carrier (`curves.<i>`, `inside.<k>`, `outside.<k>`)
in `shape`. The value is `{rings, shape, area}` of kernel.md §16.2: outer rings
counterclockwise, holes clockwise, `area` the sum of the signed areas of the
rings.

## The algorithm (the contract of the web copy)

    0. the chain (region.boundary_chain, by IDs) — a break is error "schema";
       a carrier other than a line, segment, ray, circle or arc
                                       → "unsupported_signature", detail.slot "curves.i";
       more than 256 pieces in all rings → error "limit_exceeded"
    1. incidence: from[i] and to[i] within tol.inc = tol.check.failed of the line or
       circle of curves[i] (decision off_carrier; a segment of zero length: its point)
                                       → "not_on_curve", detail.slot "from.i" / "to.i"
       (the pieces in document order, from before to)
    2. the part of the carrier (decisions piece_part, tol.decide):
         segment: the parameter of both ends in [−tol, length + tol];
         ray: the parameter of both ends ≥ −tol; line, circle: any;
         arc {a0, a1}: φ = (θ_from − a0) mod 2π, φ := 0 when r·(2π − φ) ≤ tol;
                       r·(φ + sweep − (a1 − a0)) ≤ tol
                                       → "outside_part", detail.slot "curves.i"
       an arc piece: sweep = (θ_to − θ_from) mod 2π (exactly 0 for equal angles),
       2π for from == to; a backward piece is walked clockwise
    3. A_k = Σ −∫ y dx over the pieces of ring k (lines and arcs exactly);
       |A_k| ≤ tol.decide·S (decision empty_region)         → "empty_region"
    4. a simple boundary: for every pair of pieces in the order of the value,
       their common points within tol.decide —
         two lines: an end of one within tol of the other (decision touch), and a
           proper crossing (the ends of each strictly on both sides of the other);
         a line and an arc: the points of the line and the circle (one point when
           |h − r| ≤ tol, decision tangent) on both pieces (decisions crossing);
         two arcs on one circle (decisions same_centre, same_curve): an overlap
           longer than tol (decision touch) → "boundary_crossing", else the ends of
           each on the other; on two circles: their points (decisions tangent) on
           both arcs;
       a common point is allowed only within tol.inc of a vertex the two pieces
       share (decision at_vertex): adjacent pieces of a ring, the last and the
       first too; a ring of two pieces shares both ends
                                       → "boundary_crossing"
    5. nesting: the depth of ring k is the number of other rings that hold the
       middle of its first piece (the exact even-odd test: a ray to +x over the
       y-monotone parts — arcs cut at π/2 + kπ — decision nesting);
       an even depth needs A_k > 0, an odd one A_k < 0;
       a ring of the chain that breaks it → "flipped", a contour → "boundary_crossing"
    6. A = Σ A_k ≤ tol.decide·S (decision empty_region)      → "empty_region"

Pairs whose boxes (a line: its ends, an arc: the square of its circle) are
apart by more than `tol` are skipped in step 4: they have no common point, so
the shortcut changes no result.

## Degenerate cases

- A triangle of lines through its free vertices: a vertex on the opposite
  side (collinear) — `empty_region`; a vertex across it — `flipped` (the
  ring turned over through zero area). Three lines with their intersections:
  concurrent lines — `empty_region`, past it the opposite face (the same
  walk is counterclockwise again) — defined.
- A vertex that leaves its carrier — `not_on_curve`; a vertex past the end
  of a segment, a ray or an arc — `outside_part`.
- An intersection that disappears (a line misses a circle, two circles
  apart) — `upstream`; at the tangency the piece between equal points is
  empty: the lune and the lens give `empty_region`.
- A bow tie or a figure eight (a vertex visited twice) — `boundary_crossing`;
  a hole that crosses, touches or leaves its ring — `boundary_crossing`, also
  when the touch is a vertex of both: a vertex is shared only by adjacent
  pieces of one ring.
- A chain ring walked clockwise inside an outer ring is a hole (an odd
  depth); alone it is `flipped`.
- Two arcs of one circle that overlap — `boundary_crossing`; that meet at
  their ends — the circle in two arcs.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `off_carrier` | the distance of a vertex to its carrier | `tol.check.failed` |
| `piece_part` | the parameter of an end past the part of a segment or a ray; `r·(2π − φ)`, `r·(φ + sweep − (a1 − a0))` of an arc | `tol.decide` (length) |
| `empty_region` | the area of a ring, of the region | `tol.decide · S` (area) |
| `touch` | the distance of an end to the other line; the overlap of two arcs | `tol.decide` (length) |
| `tangent` | `h − r` of a line, `d − (r1 + r2)`, `|r1 − r2| − d` of two circles | `tol.decide` (length) |
| `same_centre`, `same_curve` | the distance of the centres, `r1 − r2` | `tol.decide` (length) |
| `crossing` | a common point on a piece: its parameter, `r·(φ − w)`, `r·(2π − φ)` | `tol.decide` (length) |
| `at_vertex` | the distance of a common point to a shared vertex | `tol.check.failed` |
| `nesting` | `x_c − x` of the even-odd ray | `tol.decide` (length) |

`off_carrier`, `piece_part`, `empty_region`, `touch`, `crossing` and
`at_vertex` are noise decisions for the fixture generator (kernel.md §6): a
vertex built on its carrier and at the end of its part, a ring of exactly zero
area, pieces that meet exactly at an end or at their common vertex are
rounding noise. (`tangent`, `same_centre` and `same_curve` are noise
decisions already.)

## Checks

`on_carriers` — the largest distance from `from[i]` and `to[i]` to the line or
the circle of `curves[i]`; `0` without pieces.

## Label obstacles

The format of the key for the web is in `kernel.md` ("For the web: the key `regions` of the display list of the label solver").


Only a drawn stroke (width and opacity above 0) keeps labels off a region;
its fill does not, as with a polygon. The label solver of the web client
(`native/labels/r4.py`) reads the key `regions` of the display list —
`[{id, pieces: [{kind: "segment", x1, y1, x2, y2} | {kind: "arc", cx, cy,
r, start, sweep} | {kind: "chain", pts}]}]`, CSS px, the arc
as the arcs of the list (screen start angle, y down, signed sweep), after
the arcs in the order of the obstacles; a paint width of `0` drops a region.
The classic placement collects the same pieces of a `Region` (an arc
sampled, a whole circle as a circle).
