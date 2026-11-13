# `region.by_boundary` — the region bounded by pieces and contours

Registry 1.9 · group `region` · status `beta` · branch `null` · see [kernel.md](../kernel.md) §16.

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
