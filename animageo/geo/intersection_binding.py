"""Keep imported GeoGebra intersection names attached to their solutions.

An equation's roots are unordered geometrically. The saved output coordinates
tell us which root GeoGebra assigned to a name (or an explicit 1-based index).
This binding changes the assignment, never the computed geometry.
"""
from itertools import permutations

import numpy as np

from .lib_elements import Circle, Conic, Line, Point, Ray, Segment
from .lib_commands import Command, intersect_lc, intersect_Kl, order_points_by_reference


class ImportedIntersection:
    def __init__(self, saved_points):
        self.saved_points = saved_points
        self.permutation = None
        self.started = False
        self.initial_limited = False

    def snapshot(self):
        return self.permutation, self.started, self.initial_limited

    def restore(self, state):
        self.permutation, self.started, self.initial_limited = state

    def compute(self, inputs, points_order=None):
        if not self.saved_points or len(inputs) not in (2, 3):
            return NotImplemented
        indexed = len(inputs) == 3 and isinstance(inputs[2], (int, float))
        if len(inputs) == 3 and not indexed:
            return NotImplemented
        pair = inputs[:2]
        curve = next((obj for obj in pair if type(obj) in (Circle, Conic)), None)
        if curve is None:
            return NotImplemented
        line = next((obj for obj in pair if isinstance(obj, Line)), None)
        limited = isinstance(line, (Segment, Ray))
        if line is not None:
            result = (intersect_lc(line, curve) if isinstance(curve, Circle)
                      else intersect_Kl(curve, line))
        elif all(type(obj) in (Circle, Conic) for obj in pair):
            func = Command('Intersect', pair).func(log_unsupported=False)
            if func is None:
                return NotImplemented
            result = func(*pair)
        else:
            return NotImplemented

        roots = result if isinstance(result, list) else [result]
        roots = order_points_by_reference(roots, points_order)
        # Both named solutions coincide at a circle/line tangent in GeoGebra.
        if len(roots) == 1 and isinstance(roots[0], Point):
            if isinstance(curve, Circle) and (line is not None
                                            or isinstance(pair[1], Circle)):
                roots = [roots[0], roots[0]]
        valid = [p if isinstance(p, Point) and (not limited or line.contains(p.coords))
                 else None for p in roots]

        if not self.started:
            self.started = True
            # A newly created limited-path intersection initially fills the
            # first slot. Once both solutions have occurred, GeoGebra retains
            # their slots even while one falls outside the segment/ray.
            self.initial_limited = (limited and not indexed
                                    and len(self.saved_points) == 2
                                    and self.saved_points[1] is None)

        if self.initial_limited:
            defined = [p for p in valid if p is not None]
            if len(defined) < 2:
                return defined
            self.initial_limited = False
            self.permutation = tuple(range(len(roots)))

        if self.permutation is None and any(p is not None for p in valid):
            targets = ({int(inputs[2]) - 1: self.saved_points[0]} if indexed
                       else dict(enumerate(self.saved_points)))
            references = {i: p for i, p in targets.items()
                          if p is not None and 0 <= i < len(roots)}
            candidates = [perm for perm in permutations(range(len(roots)))
                          if all(valid[perm[i]] is not None for i in references)]
            if candidates and references:
                def distance(perm):
                    return sum(float(np.sum((roots[perm[i]].coords - p) ** 2))
                               for i, p in references.items())
                best = min(candidates, key=distance)
                # Saved coordinates identify a root only when the inputs
                # reproduce that point. Don't bind an unrelated stale snapshot.
                if all(np.allclose(roots[best[i]].coords, p, rtol=1e-7, atol=1e-7)
                       for i, p in references.items()):
                    self.permutation = best

        permutation = self.permutation or tuple(range(len(valid)))
        ordered = [valid[i] if i < len(valid) else None for i in permutation]
        if indexed:
            index = int(inputs[2]) - 1
            return [ordered[index] if 0 <= index < len(ordered) else None]
        return ordered
