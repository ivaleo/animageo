# `sector.segment`

Exactly one input set: `arc` (an arc), or `circle` (a circle) with
`a`, `b` (points on it). Output `segment` has type `circlesegment` and value
`{c:[x,y], r, a0, a1}`. It preserves the arc counterclockwise from a to b,
including a reflex or full sweep. Equal directions give a defined zero sweep.
A point off the circle gives `undefined/not_on_curve`; undefined inputs
propagate their state. Mixed or incomplete input sets are schema errors.

For theta=a1-a0, area = r²(theta-sin(theta))/2 and perimeter =
r*theta+2*r*abs(sin(theta/2)). Radius is r. The boundary parameter wraps
to [0,2): [0,1] runs along the arc, [1,2) returns along the chord.
The type belongs to the sector's families, including `path`, `round`,
`bounded`, `figure`, `transformable`, but not `curve`: intersections give
`type_mismatch`. Reflection reverses the arc ends and preserves its sweep.

Rendering closes the arc by the chord and shares sector fill/hatch keys.
SVG, PNG, PDF, EPS, TikZ and video use that same region; a full sweep is
the disc. The boundary is a closed solid stroke.
