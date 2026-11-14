"""Analytic conic elements, fixed slots, and reversible type transitions."""
import math


def _defined(value, found=None, type_='line'):
    rec = {'state': 'defined', 'type': type_, 'value': value}
    if found is not None:
        rec['detail'] = {'found': found}
    return rec


def _absent(reason, type_='line', cause=None):
    rec = {'state': 'undefined', 'type': type_, 'reason': reason}
    if cause:
        rec['cause'] = cause
    return rec


def _line(nx, ny, h):
    length = math.hypot(nx, ny)
    nx, ny, h = nx/length, ny/length, h/length
    return {'p': [nx*h, ny*h], 'dir': [-ny, nx]}


def _set(prefix, lines, reason, count=3, cause=None):
    return {f'{prefix}{k}': _defined(lines[k-1], len(lines)) if k <= len(lines)
            else _absent('branch_absent' if lines else reason, cause=None if lines else cause)
            for k in range(1, count+1)}


def scenes():
    from .curves_fixtures import _Doc, _ref, _num, P, N, X, Y, call, n, o, r, sq
    ellipse = o('-', o('+', o('/', sq(X), n(9)), o('/', sq(Y), n(4))), n(1))
    hyperbola = o('-', o('-', o('/', sq(X), n(4)), o('/', sq(Y), n(9))), n(1))
    parabola = o('-', sq(Y), o('*', n(4), X))

    def doc(name):
        return _Doc(name, registry_version='1.13')

    def multiple(d, name, c, base):
        return d.op('op_'+name, 'conic.'+('directrices' if base == 'directrix' else 'asymptotes'),
                    {'conic': _ref(c), 'count': _num(3)}, [(f'{base}.{k}', f'{name}{k}', 'line') for k in range(1, 4)])

    def polar(d, name, c):
        return d.op('op_'+name, 'line.polar_conic', {'point': _ref('P'), 'conic': _ref(c)}, [('line', name, 'line')])

    def diameter(d, name, c):
        return d.op('op_'+name, 'line.conjugate_diameter', {'direction': _ref('d'), 'conic': _ref(c)}, [('line', name, 'line')])

    out = []
    d = doc('conic_directrices').number('m', 1).free('O', 0, 0).free('R', 3, 0).circle('c', 'O', 'R')
    d.equation('e', o('*', r(0), ellipse), 'm').equation('h', hyperbola).equation('p', parabola)
    for name, c in [('ed', 'e'), ('hd', 'h'), ('pd', 'p'), ('cd', 'c')]:
        multiple(d, name, c, 'directrix')
    cases, answers = [], {}
    for name, m in [('ellipse', 1), ('negative_equation', -1), ('degenerate', 0), ('recovery', 1)]:
        cases.append({'name': name, 'inputs': {'m': N(m)}})
        answers[name] = {**_set('ed', [_line(1, 0, 9/math.sqrt(5)), _line(1, 0, -9/math.sqrt(5))] if m else [], 'upstream', cause='e'),
                         **_set('hd', [_line(1, 0, 4/math.sqrt(13)), _line(1, 0, -4/math.sqrt(13))], 'no_directrix'),
                         **_set('pd', [_line(1, 0, -1)], 'no_directrix'), **_set('cd', [], 'no_directrix')}
    out.append((d, cases, answers))

    d = doc('conic_asymptotes').number('m', 1).equation('h', o('*', r(0), hyperbola), 'm').equation('e', ellipse).equation('p', parabola)
    # A 3-4-5 rotation and translation of x²/4-y²/9=1.
    u = o('+', o('*', n(.6), o('-', X, n(5))), o('*', n(.8), o('+', Y, n(7))))
    v = o('+', o('*', n(-.8), o('-', X, n(5))), o('*', n(.6), o('+', Y, n(7))))
    d.equation('r', o('-', o('-', o('/', sq(u), n(4)), o('/', sq(v), n(9))), n(1)))
    for name, c in [('ha', 'h'), ('ra', 'r'), ('ea', 'e'), ('pa', 'p')]:
        multiple(d, name, c, 'asymptote')
    lines = [_line(3, -2, 0), _line(3, 2, 0)]
    # Desired directions are (2,3) and (-2,3).
    lines[0]['dir'] = [2/math.sqrt(13), 3/math.sqrt(13)]
    lines[1]['dir'] = [-2/math.sqrt(13), 3/math.sqrt(13)]
    rotated = []
    for dx, dy in [(-1.2, 3.4), (-3.6, .2)]:
        length = math.hypot(dx, dy)
        nx, ny = dy/length, -dx/length
        rotated.append(_line(nx, ny, 5*nx-7*ny))
    cases = [{'name': name, 'inputs': {'m': N(m)}} for name, m in [('positive', 1), ('negative', -1), ('scaled', 2)]]
    answers = {case['name']: {**_set('ha', lines, 'no_asymptote'), **_set('ra', rotated, 'no_asymptote'),
                             **_set('ea', [], 'no_asymptote'), **_set('pa', [], 'no_asymptote')} for case in cases}
    out.append((d, cases, answers))

    d = doc('conic_polar').free('P', 1, 0).equation('e', ellipse).equation('h', hyperbola).equation('p', parabola)
    for name, c in [('ep', 'e'), ('hp', 'h'), ('pp', 'p')]:
        polar(d, name, c)
    cases, answers = [], {}
    for name, x, y in [('inside', 1, 0), ('on_ellipse', 3, 0), ('outside', 5, 2), ('center', 0, 0), ('recovery', 1, 0)]:
        cases.append({'name': name, 'inputs': {'P': P(x, y)}})
        answers[name] = {'ep': _defined(_line(x/9, y/4, 1)) if x or y else _absent('no_finite_line'),
                         'hp': _defined(_line(x/4, -y/9, 1)) if x or y else _absent('no_finite_line'),
                         'pp': _defined(_line(-2, y, 2*x))}
    out.append((d, cases, answers))

    d = doc('conic_conjugate_diameter').free('A', 0, 0).free('B', 1, 1)
    d.op('op_d', 'vector.by_points', {'a': _ref('A'), 'b': _ref('B')}, [('vector', 'd', 'vector')])
    d.equation('e', ellipse).equation('h', hyperbola).equation('p', parabola)
    for name, c in [('ed', 'e'), ('hd', 'h'), ('pd', 'p')]:
        diameter(d, name, c)
    cases, answers = [], {}
    for name, dx, dy in [('diagonal', 1, 1), ('reversed', -1, -1), ('asymptotic', 2, 3), ('axis', 1, 0), ('zero', 0, 0), ('recovery', 1, 1)]:
        cases.append({'name': name, 'inputs': {'B': P(dx, dy)}})
        if not (dx or dy):
            answers[name] = {key: _absent('invalid_parameter') for key in ('ed', 'hd', 'pd')}
            continue
        s = 1 if dx > 0 else -1
        answers[name] = {'ed': _defined(_line(s*dx/9, s*dy/4, 0)),
                         'hd': _defined(_line(s*dx/4, -s*dy/9, 0)),
                         'pd': _defined(_line(0, 1, 2*dx/dy)) if dy else _absent('no_finite_line')}
    out.append((d, cases, answers))

    d = doc('conic_elements_transition').number('e', .5)
    d.equation('c', o('-', o('+', o('*', o('-', n(1), sq(r(0))), sq(X)), sq(Y)), o('*', n(4), X)), 'e')
    multiple(d, 'd', 'c', 'directrix'); multiple(d, 'a', 'c', 'asymptote')
    cases, answers = [], {}
    for name, e in [('ellipse', .5), ('near_parabola', .99), ('parabola', 1), ('hyperbola', 1.5),
                    ('parabola_return', 1), ('ellipse_return', .5), ('circle', 0), ('recovery', .5)]:
        cases.append({'name': name, 'inputs': {'e': N(e)}})
        if e == 0:
            directs = []
        elif e == 1:
            directs = [_line(1, 0, -1)]
        elif e < 1:
            directs = [_line(1, 0, 2/(1-e*e)*(1+1/e)), _line(1, 0, -2/(e*(1+e)))]
        else:
            directs = [_line(1, 0, -2/(e*(1+e))), _line(1, 0, 2/(1-e*e)*(1+1/e))]
        asym = []
        if e > 1:
            slope = math.sqrt(e*e-1)
            center = 2/(1-e*e)
            asym = [_line(slope, -1, slope*center), _line(slope, 1, slope*center)]
            asym[0]['dir'] = [1/math.sqrt(1+slope*slope), slope/math.sqrt(1+slope*slope)]
            asym[1]['dir'] = [-1/math.sqrt(1+slope*slope), slope/math.sqrt(1+slope*slope)]
        answers[name] = {**_set('d', directs, 'no_directrix'), **_set('a', asym, 'no_asymptote')}
    out.append((d, cases, answers))

    d = doc('circle_as_conic').free('O', 1, -2).free('R', 4, -2).circle('circle', 'O', 'R')
    d.op('op_c', 'conic.from_circle', {'circle': _ref('circle')}, [('conic', 'c', 'conic')])
    d.op('op_foci', 'conic.foci', {'conic': _ref('c')}, [('first', 'F', 'point'), ('second', 'G', 'point')])
    multiple(d, 'd', 'circle', 'directrix')
    cases, answers = [], {}
    for name, x, y, radius in [('circle', 4, -2, 3), ('expanded', 6, -2, 5), ('zero_radius', 1, -2, 0), ('recovery', 4, -2, 3)]:
        cases.append({'name': name, 'inputs': {'R': P(x, y)}})
        answers[name] = {'c': _defined({'kind': 'ellipse', 'c': [1, -2], 'axis': [1, 0], 'a': radius, 'b': radius}, type_='conic') if radius else _absent('upstream', type_='conic', cause='circle'),
                         **{k: _defined({'x': 1, 'y': -2}, type_='point') if radius else _absent('upstream', type_='point', cause='circle') for k in ('F', 'G')},
                         **_set('d', [], 'no_directrix' if radius else 'upstream', cause=None if radius else 'circle')}
    out.append((d, cases, answers))

    d = doc('conic_elements_numeric_limits').number('s', 1).equation('e', ellipse).equation('p', parabola)
    tiny = call('exp', o('*', n(-720), r(0)))
    refs = {'kind': 'list', 'items': [_ref('s')]}
    d.op('op_P', 'point.expression', {'expr': {'kind': 'expr', 'ast': {'pair': [tiny, n(0)]}}, 'refs': refs}, [('point', 'P', 'point')])
    d.op('op_d', 'vector.expression', {'expr': {'kind': 'expr', 'ast': {'pair': [n(1), tiny]}}, 'refs': refs}, [('vector', 'd', 'vector')])
    polar(d, 'polar', 'e'); diameter(d, 'diameter', 'p')
    cases, answers = [], {}
    for name, s in [('overflow', 1), ('finite', 0), ('distant', .01), ('recovery', 0)]:
        cases.append({'name': name, 'inputs': {'s': N(s)}})
        answers[name] = ({'polar': _absent('non_finite'), 'diameter': _absent('non_finite')} if s == 1 else
                         {'polar': _defined(_line(1, 0, 9/math.exp(-720*s))),
                          'diameter': _defined(_line(0, 1, 2/math.exp(-720*s)))})
    out.append((d, cases, answers))
    return out


def build_fixtures():
    from .curves_fixtures import _rounded
    from .parity import PARITY_FORMAT, generate_scene, verify_fixture
    out = {}
    for d, cases, answers in scenes():
        fixture = _rounded(generate_scene({'format': PARITY_FORMAT, 'id': d.doc['documentId'], 'document': d.doc, 'cases': cases}))
        for case in fixture['cases']:
            case['expect'].update(_rounded(answers[case['name']]))
        problems = verify_fixture(fixture)
        if problems:
            raise ValueError(f"{fixture['id']}: analytical answers differ: {problems}")
        out[fixture['id']+'.json'] = fixture
    return out
