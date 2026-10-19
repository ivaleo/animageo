"""The camera of a space construction and its projector.

World: a right-handed frame with **z up**; the ground is the plane Oxy.

Orbit (``orthographic``, ``perspective``): ``azimuthDeg`` is the direction of
the eye around z, counted from +x towards +y; ``elevationDeg`` is the height
of the eye above the plane Oxy (90 looks straight down). The unit vector
from the target towards the eye is

    dir = (cos el · cos az, cos el · sin az, sin el)

and the picture frame is ``r = (−sin az, cos az, 0)`` (right),
``f = −dir`` (forward, into the scene), ``u = r × f`` (up). The closed
form of ``r`` keeps the top view (``el = ±90``) defined.

``oblique`` — the cabinet projection of school textbooks: the plane Oxz is
drawn in true shape and the receding axis y at ``oblique.angleDeg`` to x,
shortened by ``oblique.ratio`` (45° and 1/2 by default); the orbit angles are
not used.

Picture coordinates are in world units with y up. A parallel projection
maps the world 1:1; a perspective one is 1:1 in the plane through the target
square to the view, ``distance`` away from the eye. Pixels are the business
of the export layout, not of the camera. ``depth`` grows away from the eye.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import vec

__all__ = ['PROJECTIONS', 'Camera', 'Projector']

PROJECTIONS = ('orthographic', 'perspective', 'oblique')


def _finite(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{what}: a finite number expected, got {value!r}')
    return value


@dataclass(frozen=True)
class Camera:
    """A view of a space construction; ``to_dict`` gives the JSON of a
    document camera (``viewDefaults.camera``)."""

    projection: str = 'orthographic'
    azimuth_deg: float = -60.0
    elevation_deg: float = 20.0
    target: tuple = (0.0, 0.0, 0.0)
    distance: float = 12.0
    oblique_angle_deg: float = 45.0
    oblique_ratio: float = 0.5

    def __post_init__(self):
        if self.projection not in PROJECTIONS:
            raise ValueError(f'projection: one of {", ".join(PROJECTIONS)} expected, got {self.projection!r}')
        _finite(self.azimuth_deg, 'azimuthDeg')
        _finite(self.elevation_deg, 'elevationDeg')
        if not -90 <= self.elevation_deg <= 90:
            raise ValueError(f'elevationDeg: within [-90, 90], got {self.elevation_deg!r}')
        target = tuple(self.target)
        if len(target) != 3:
            raise ValueError('target: three coordinates expected')
        for c in target:
            _finite(c, 'target')
        object.__setattr__(self, 'target', target)
        if _finite(self.distance, 'distance') <= 0:
            raise ValueError(f'distance: positive expected, got {self.distance!r}')
        _finite(self.oblique_angle_deg, 'oblique.angleDeg')
        if _finite(self.oblique_ratio, 'oblique.ratio') <= 0:
            raise ValueError(f'oblique.ratio: positive expected, got {self.oblique_ratio!r}')

    def to_dict(self) -> dict:
        out = {'projection': self.projection}
        if self.projection == 'oblique':
            out['target'] = list(self.target)
            out['oblique'] = {'angleDeg': self.oblique_angle_deg, 'ratio': self.oblique_ratio}
            return out
        out.update({'azimuthDeg': self.azimuth_deg, 'elevationDeg': self.elevation_deg,
                    'target': list(self.target)})
        if self.projection == 'perspective':
            out['distance'] = self.distance
        return out

    @classmethod
    def from_dict(cls, data) -> 'Camera':
        if not isinstance(data, dict):
            raise ValueError('camera: an object expected')
        kwargs = {'projection': data.get('projection', 'orthographic')}
        for key, name in (('azimuthDeg', 'azimuth_deg'), ('elevationDeg', 'elevation_deg'),
                          ('distance', 'distance')):
            if key in data:
                kwargs[name] = data[key]
        if 'target' in data:
            kwargs['target'] = tuple(data['target'])
        oblique = data.get('oblique')
        if isinstance(oblique, dict):
            if 'angleDeg' in oblique:
                kwargs['oblique_angle_deg'] = oblique['angleDeg']
            if 'ratio' in oblique:
                kwargs['oblique_ratio'] = oblique['ratio']
        return cls(**kwargs)


class Projector:
    """Projection of points of space to the picture (``project``) and the
    direction towards the eye (``toward_eye``) the visibility tests use."""

    def __init__(self, camera: Camera):
        self.camera = camera
        self.parallel = camera.projection != 'perspective'
        self.eye = None
        self._target = camera.target
        if camera.projection == 'oblique':
            a = math.radians(camera.oblique_angle_deg)
            k = camera.oblique_ratio
            self._ox, self._oy = k * math.cos(a), k * math.sin(a)
            # p and p + s·w have one image: w runs into the picture along +y
            self._view = vec.unit((self._ox, -1.0, self._oy))
            return
        az, el = math.radians(camera.azimuth_deg), math.radians(camera.elevation_deg)
        direction = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
        self._f = vec.mul(direction, -1.0)
        self._r = (-math.sin(az), math.cos(az), 0.0)
        self._u = vec.cross(self._r, self._f)
        if self.parallel:
            self._view = direction
        else:
            self.eye = vec.add(camera.target, vec.mul(direction, camera.distance))

    def project(self, p) -> tuple:
        """``(x, y, depth)``: picture coordinates (y up) and the depth along
        the view; in perspective ``depth ≤ 0`` means behind the eye (the
        picture coordinates are then meaningless)."""
        if self.camera.projection == 'oblique':
            d = vec.sub(p, self._target)
            return (d[0] + self._ox * d[1], d[2] + self._oy * d[1], d[1])
        if self.parallel:
            d = vec.sub(p, self._target)
            return (vec.dot(d, self._r), vec.dot(d, self._u), vec.dot(d, self._f))
        d = vec.sub(p, self.eye)
        z = vec.dot(d, self._f)
        if z <= 0.0:
            return (0.0, 0.0, z)
        k = self.camera.distance / z
        return (vec.dot(d, self._r) * k, vec.dot(d, self._u) * k, z)

    def toward_eye(self, p) -> tuple:
        """The unit vector from ``p`` towards the eye."""
        if self.parallel:
            return self._view
        return vec.unit(vec.sub(self.eye, p))

    def facing(self, normal, point) -> float:
        """The cosine between a plane's unit ``normal`` and the direction from
        ``point`` of the plane towards the eye: > 0 — the side of the normal
        faces the eye."""
        if self.parallel:
            return vec.dot(normal, self._view)
        to_eye = vec.sub(self.eye, point)
        length = vec.norm(to_eye)
        return vec.dot(normal, to_eye) / length if length > 0.0 else 0.0

    def side_normal(self, q1, q2) -> tuple:
        """A normal (not unit) of the plane through ``q1``, ``q2`` and the eye
        direction — the side plane of a silhouette edge."""
        if self.parallel:
            return vec.cross(vec.sub(q2, q1), self._view)
        return vec.cross(vec.sub(q1, self.eye), vec.sub(q2, self.eye))
