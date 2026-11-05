"""``Math`` of JavaScript, for the R4 port (``r4.py``).

The port computes as the client does, so that its numbers are the client's
where they can be. The C library of the platform rounds differently from a
JavaScript engine in a few per cent of the arguments, so:

* ``hypot`` follows ``MathHypot`` of V8 (``src/builtins/math.tq``: scaled
  by the larger value, a compensated sum) and ``js_round`` ``Math.round``
  (halves up); both are checked against values computed by V8;
* ``atan``, ``atan2``, ``sin`` and ``cos`` are fdlibm 5.3 as V8 ports it
  (``src/base/ieee754.cc``); they are checked against fdlibm's special
  values and to lie within an ulp of the platform library, not against V8
  itself. A build that contracts into FMA (Node on arm64) differs from
  fdlibm in the last bit for some arguments; the tie rule of ``r4.py``
  keeps ``k`` independent of that.

``sin`` and ``cos`` reduce the argument as fdlibm for ``|x| <= 2^19·π/2``;
a larger argument (never an angle of a display list) falls back to the
platform library.
"""
from __future__ import annotations

import math
import struct

__all__ = ['atan', 'atan2', 'cos', 'hypot', 'js_round', 'sin']

_D = struct.Struct('<d')
_Q = struct.Struct('<Q')


def _words(x: float) -> tuple[int, int]:
    """High word (signed int32) and low word (uint32) of a double."""
    u = _Q.unpack(_D.pack(x))[0]
    hi = u >> 32
    if hi & 0x80000000:
        hi -= 0x100000000
    return hi, u & 0xFFFFFFFF


def _high(x: float) -> int:
    return _words(x)[0]


def _with_words(hi: int, lo: int) -> float:
    return _D.unpack(_Q.pack(((hi & 0xFFFFFFFF) << 32) | (lo & 0xFFFFFFFF)))[0]


def js_round(x: float) -> int:
    """``Math.round`` for a finite number: the nearest integer, halves up."""
    f = math.floor(x)
    return f + 1 if x - f >= 0.5 else f


def hypot(x: float, y: float) -> float:
    """``Math.hypot(x, y)``: V8 normalises by the larger value and sums with Kahan compensation."""
    ax = abs(x)
    ay = abs(y)
    if x != x or y != y:
        return math.inf if (ax == math.inf or ay == math.inf) else math.nan
    m = 0.0
    if ax > m:
        m = ax
    if ay > m:
        m = ay
    if m == math.inf:
        return math.inf
    if m == 0:
        return 0.0
    total = 0.0
    compensation = 0.0
    for v in (ax, ay):
        n = v / m
        summand = n * n - compensation
        preliminary = total + summand
        compensation = (preliminary - total) - summand
        total = preliminary
    return math.sqrt(total) * m


# ---- atan, atan2 (fdlibm s_atan.c, e_atan2.c) ----

_ATANHI = (
    4.63647609000806093515e-01,
    7.85398163397448278999e-01,
    9.82793723247329054082e-01,
    1.57079632679489655800e00,
)
_ATANLO = (
    2.26987774529616870924e-17,
    3.06161699786838301793e-17,
    1.39033110312309984516e-17,
    6.12323399573676603587e-17,
)
_AT = (
    3.33333333333329318027e-01,
    -1.99999999998764832476e-01,
    1.42857142725034663711e-01,
    -1.11111104054623557880e-01,
    9.09088713343650656196e-02,
    -7.69187620504482999495e-02,
    6.66107313738753120669e-02,
    -5.83357013379057348645e-02,
    4.97687799461593236017e-02,
    -3.65315727442169155270e-02,
    1.62858201153657823623e-02,
)


def atan(x: float) -> float:
    hx, lx = _words(x)
    ix = hx & 0x7FFFFFFF
    if ix >= 0x44100000:  # |x| >= 2^66
        if ix > 0x7FF00000 or (ix == 0x7FF00000 and lx != 0):
            return x + x  # NaN
        if hx > 0:
            return _ATANHI[3] + _ATANLO[3]
        return -_ATANHI[3] - _ATANLO[3]
    if ix < 0x3FDC0000:  # |x| < 0.4375
        if ix < 0x3E400000:  # |x| < 2^-27
            return x
        idx = -1
    else:
        x = abs(x)
        if ix < 0x3FF30000:  # |x| < 1.1875
            if ix < 0x3FE60000:  # 7/16 <= |x| < 11/16
                idx = 0
                x = (2.0 * x - 1.0) / (2.0 + x)
            else:  # 11/16 <= |x| < 19/16
                idx = 1
                x = (x - 1.0) / (x + 1.0)
        elif ix < 0x40038000:  # |x| < 2.4375
            idx = 2
            x = (x - 1.5) / (1.0 + 1.5 * x)
        else:  # 2.4375 <= |x| < 2^66
            idx = 3
            x = -1.0 / x
    z = x * x
    w = z * z
    at = _AT
    s1 = z * (at[0] + w * (at[2] + w * (at[4] + w * (at[6] + w * (at[8] + w * at[10])))))
    s2 = w * (at[1] + w * (at[3] + w * (at[5] + w * (at[7] + w * at[9]))))
    if idx < 0:
        return x - x * (s1 + s2)
    z = _ATANHI[idx] - ((x * (s1 + s2) - _ATANLO[idx]) - x)
    return -z if hx < 0 else z


_PI_O_4 = 7.8539816339744827900e-01
_PI_O_2 = 1.5707963267948965580e00
_PI = 3.1415926535897931160e00
_PI_LO = 1.2246467991473531772e-16
_TINY = 1.0e-300


def atan2(y: float, x: float) -> float:
    if x != x or y != y:
        return x + y
    hx, lx = _words(x)
    ix = hx & 0x7FFFFFFF
    hy, ly = _words(y)
    iy = hy & 0x7FFFFFFF
    if hx == 0x3FF00000 and lx == 0:  # x = 1.0
        return atan(y)
    m = ((hy >> 31) & 1) | ((hx >> 30) & 2)  # 2*sign(x) + sign(y)
    if (iy | ly) == 0:  # y = ±0
        if m <= 1:
            return y
        return _PI + _TINY if m == 2 else -_PI - _TINY
    if (ix | lx) == 0:  # x = ±0
        return -_PI_O_2 - _TINY if hy < 0 else _PI_O_2 + _TINY
    if ix == 0x7FF00000:  # x = ±inf
        if iy == 0x7FF00000:
            return (_PI_O_4 + _TINY, -_PI_O_4 - _TINY, 3.0 * _PI_O_4 + _TINY, -3.0 * _PI_O_4 - _TINY)[m]
        return (0.0, -0.0, _PI + _TINY, -_PI - _TINY)[m]
    if iy == 0x7FF00000:  # y = ±inf
        return -_PI_O_2 - _TINY if hy < 0 else _PI_O_2 + _TINY
    k = (iy - ix) >> 20
    if k > 60:  # |y/x| > 2^60
        z = _PI_O_2 + 0.5 * _PI_LO
        m &= 1
    elif hx < 0 and k < -60:  # 0 > |y|/x > -2^-60
        z = 0.0
    else:
        z = atan(abs(y / x))
    if m == 0:
        return z
    if m == 1:
        return -z
    if m == 2:
        return _PI - (z - _PI_LO)
    return (z - _PI_LO) - _PI


# ---- sin, cos (fdlibm k_sin.c, k_cos.c, e_rem_pio2.c, s_sin.c, s_cos.c) ----

_S1 = -1.66666666666666324348e-01
_S2 = 8.33333333332248946124e-03
_S3 = -1.98412698298579493134e-04
_S4 = 2.75573137070700676789e-06
_S5 = -2.50507602534068634195e-08
_S6 = 1.58969099521155010221e-10

_C1 = 4.16666666666666019037e-02
_C2 = -1.38888888888741095749e-03
_C3 = 2.48015872894767294178e-05
_C4 = -2.75573143513906633035e-07
_C5 = 2.08757232129817482790e-09
_C6 = -1.13596475577881948265e-11


def _kernel_sin(x: float, y: float, iy: int) -> float:
    ix = _high(x) & 0x7FFFFFFF
    if ix < 0x3E400000 and int(x) == 0:  # |x| < 2^-27
        return x
    z = x * x
    v = z * x
    r = _S2 + z * (_S3 + z * (_S4 + z * (_S5 + z * _S6)))
    if iy == 0:
        return x + v * (_S1 + z * r)
    return x - ((z * (0.5 * y - v * r) - y) - v * _S1)


def _kernel_cos(x: float, y: float) -> float:
    ix = _high(x) & 0x7FFFFFFF
    if ix < 0x3E400000 and int(x) == 0:  # |x| < 2^-27
        return 1.0
    z = x * x
    r = z * (_C1 + z * (_C2 + z * (_C3 + z * (_C4 + z * (_C5 + z * _C6)))))
    if ix < 0x3FD33333:  # |x| < 0.3
        return 1.0 - (0.5 * z - (z * r - x * y))
    if ix > 0x3FE90000:  # |x| > 0.78125
        qx = 0.28125
    else:
        qx = _with_words(ix - 0x00200000, 0)  # x/4
    hz = 0.5 * z - qx
    a = 1.0 - qx
    return a - (hz - (z * r - x * y))


_NPIO2_HW = (
    0x3FF921FB, 0x400921FB, 0x4012D97C, 0x401921FB, 0x401F6A7A, 0x4022D97C,
    0x4025FDBB, 0x402921FB, 0x402C463A, 0x402F6A7A, 0x4031475C, 0x4032D97C,
    0x40346B9C, 0x4035FDBB, 0x40378FDB, 0x403921FB, 0x403AB41B, 0x403C463A,
    0x403DD85A, 0x403F6A7A, 0x40407E4C, 0x4041475C, 0x4042106C, 0x4042D97C,
    0x4043A28C, 0x40446B9C, 0x404534AC, 0x4045FDBB, 0x4046C6CB, 0x40478FDB,
    0x404858EB, 0x404921FB,
)
_INVPIO2 = 6.36619772367581382433e-01
_PIO2_1 = 1.57079632673412561417e00
_PIO2_1T = 6.07710050650619224932e-11
_PIO2_2 = 6.07710050630396597660e-11
_PIO2_2T = 2.02226624879595063154e-21
_PIO2_3 = 2.02226624871116645580e-21
_PIO2_3T = 8.47842766036889956997e-32


def _rem_pio2(x: float, hx: int) -> tuple[int, float, float] | None:
    """``x − n·π/2`` as ``(n, y0, y1)``; ``None`` above the medium range."""
    ix = hx & 0x7FFFFFFF
    if ix < 0x4002D97C:  # |x| < 3π/4, n = ±1
        if hx > 0:
            z = x - _PIO2_1
            if ix != 0x3FF921FB:
                y0 = z - _PIO2_1T
                return 1, y0, (z - y0) - _PIO2_1T
            z -= _PIO2_2
            y0 = z - _PIO2_2T
            return 1, y0, (z - y0) - _PIO2_2T
        z = x + _PIO2_1
        if ix != 0x3FF921FB:
            y0 = z + _PIO2_1T
            return -1, y0, (z - y0) + _PIO2_1T
        z += _PIO2_2
        y0 = z + _PIO2_2T
        return -1, y0, (z - y0) + _PIO2_2T
    if ix > 0x413921FB:  # |x| > 2^19·π/2
        return None
    t = abs(x)
    n = int(t * _INVPIO2 + 0.5)
    fn = float(n)
    r = t - fn * _PIO2_1
    w = fn * _PIO2_1T
    if n < 32 and ix != _NPIO2_HW[n - 1]:
        y0 = r - w
    else:
        j = ix >> 20
        y0 = r - w
        i = j - ((_high(y0) >> 20) & 0x7FF)
        if i > 16:  # second iteration, good to 118 bits
            t = r
            w = fn * _PIO2_2
            r = t - w
            w = fn * _PIO2_2T - ((t - r) - w)
            y0 = r - w
            i = j - ((_high(y0) >> 20) & 0x7FF)
            if i > 49:  # third iteration, 151 bits
                t = r
                w = fn * _PIO2_3
                r = t - w
                w = fn * _PIO2_3T - ((t - r) - w)
                y0 = r - w
    y1 = (r - y0) - w
    if hx < 0:
        return -n, -y0, -y1
    return n, y0, y1


def sin(x: float) -> float:
    hx = _high(x)
    ix = hx & 0x7FFFFFFF
    if ix <= 0x3FE921FB:  # |x| <= π/4
        return _kernel_sin(x, 0.0, 0)
    if ix >= 0x7FF00000:
        return math.nan
    red = _rem_pio2(x, hx)
    if red is None:
        return math.sin(x)
    n, y0, y1 = red
    q = n & 3
    if q == 0:
        return _kernel_sin(y0, y1, 1)
    if q == 1:
        return _kernel_cos(y0, y1)
    if q == 2:
        return -_kernel_sin(y0, y1, 1)
    return -_kernel_cos(y0, y1)


def cos(x: float) -> float:
    hx = _high(x)
    ix = hx & 0x7FFFFFFF
    if ix <= 0x3FE921FB:  # |x| <= π/4
        return _kernel_cos(x, 0.0)
    if ix >= 0x7FF00000:
        return math.nan
    red = _rem_pio2(x, hx)
    if red is None:
        return math.cos(x)
    n, y0, y1 = red
    q = n & 3
    if q == 0:
        return _kernel_cos(y0, y1)
    if q == 1:
        return -_kernel_sin(y0, y1, 1)
    if q == 2:
        return -_kernel_cos(y0, y1)
    return _kernel_sin(y0, y1, 1)
