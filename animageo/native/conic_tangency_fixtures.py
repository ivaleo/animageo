"""Analytic finite contacts and slot order for conic tangency curves."""
import math


def _defined(type_, value, found=None):
    rec = {'state': 'defined', 'type': type_, 'value': value}
    if found is not None:
        rec['detail'] = {'found': found}
    return rec


def _absent(type_, reason, cause=None):
    rec = {'state': 'undefined', 'type': type_, 'reason': reason}
    if cause is not None:
        rec['cause'] = cause
    return rec


def _line(x, y, nx, ny, direction=None):
    if direction is None:
        norm = math.hypot(nx, ny)
        nx, ny = nx/norm, ny/norm
        dx, dy = -ny, nx
    else:
        norm = math.hypot(*direction)
        dx, dy = [v/norm for v in direction]
        nx, ny = dy, -dx
    offset = nx*x+ny*y
    return {'p': [offset*nx, offset*ny], 'dir': [dx, dy]}


def _set(prefix, contacts, *, count=2, direction=None, reason='no_tangent', cause=None):
    out = {}
    for k in range(1, count+1):
        line_key, point_key = f'{prefix}{k}', f'{prefix}_touch{k}'
        if k <= len(contacts):
            x, y, nx, ny = contacts[k-1]
            out[line_key] = _defined('line', _line(x, y, nx, ny, direction), len(contacts))
            out[point_key] = _defined('point', {'x': x, 'y': y}, len(contacts))
        else:
            why = 'branch_absent' if contacts else reason
            out[line_key] = _absent('line', why, cause)
            out[point_key] = _absent('point', why, cause)
    return out


def scenes():
    from .curves_fixtures import _Doc, _ref, _num, P, N, X, Y, n, o, r, sq
    ellipse = o('-', o('+', o('/', sq(X), n(4)), sq(Y)), n(1))
    parabola = o('-', sq(X), Y)
    hyperbola = o('-', o('-', sq(X), sq(Y)), n(1))

    def strict(d, prefix, conic, point):
        return d.op('op_'+prefix, 'line.tangent_conic_at', {'point': _ref(point), 'conic': _ref(conic)},
                    [('line', prefix, 'line')])

    def multiple(d, prefix, conic, point='P', *, count=2, parallel=False):
        args = {'conic': _ref(conic), 'base' if parallel else 'point': _ref('base' if parallel else point),
                'count': _num(count)}
        return d.op('op_'+prefix, 'line.tangents_parallel_conic' if parallel else 'line.tangents_from_point_conic', args,
                    [(f'tangent.{k}', f'{prefix}{k}', 'line') for k in range(1, count+1)]+
                    [(f'touch.{k}', f'{prefix}_touch{k}', 'point') for k in range(1, count+1)])

    def point_contacts(kind, points):
        return [(x, y, x/4 if kind == 'ellipse' else x, -.5 if kind == 'parabola' else -y if kind == 'hyperbola' else y)
                for x, y in points]

    out = []
    d = _Doc('conic_tangent_at').free('P', 2, 0).free('A', 1, 1).free('B', 1, 0)
    d.equation('e', ellipse).equation('p', parabola).equation('h', hyperbola)
    strict(d, 'et', 'e', 'P'); strict(d, 'pt', 'p', 'A'); strict(d, 'ht', 'h', 'B')
    cases, answers = [], {}
    for name, x, y, normal in [('vertical', 2, 0, (.5, 0)), ('horizontal', 0, 1, (0, 1)),
                              ('off_curve', 4, 0, None), ('recovery', 2, 0, (.5, 0))]:
        cases.append({'name': name, 'inputs': {'P': P(x, y)}})
        answers[name] = {'et': _defined('line', _line(x, y, *normal)) if normal else _absent('line', 'not_on_curve'),
                         'pt': _defined('line', _line(1, 1, 1, -.5)), 'ht': _defined('line', _line(1, 0, 1, 0))}
    out.append((d, cases, answers))

    d = _Doc('conic_tangents_from_point').free('P', 4, 0).equation('e', ellipse)
    multiple(d, 't', 'e')
    cases, answers = [], {}
    for name, x, reason in [('right', 4, None), ('left', -4, None), ('on', 2, None),
                             ('inside', 0, 'point_inside'), ('recovery', 4, None)]:
        cases.append({'name': name, 'inputs': {'P': P(x, 0)}})
        points = ([(math.copysign(1, x), math.copysign(math.sqrt(3)/2, x)),
                   (math.copysign(1, x), -math.copysign(math.sqrt(3)/2, x))] if abs(x) == 4 else [(2, 0)] if x == 2 else [])
        answers[name] = _set('t', point_contacts('ellipse', points), reason=reason)
    out.append((d, cases, answers))

    d = _Doc('conic_tangents_parallel').free('O', 0, 0).free('R', 2, 0).free('A', 0, 0).free('B', -1, 0)
    d.circle('circle', 'O', 'R').equation('e', ellipse).equation('p', parabola).equation('h', hyperbola).line('base', 'A', 'B')
    for prefix, conic in [('ct', 'circle'), ('et', 'e'), ('pt', 'p'), ('ht', 'h')]:
        multiple(d, prefix, conic, parallel=True)
    cases, answers = [], {}
    for name, direction in [('left', (-1, 0)), ('right', (1, 0)), ('up', (0, 1)), ('diagonal', (1, 1))]:
        cases.append({'name': name, 'inputs': {'B': P(*direction)}})
        dx, dy = direction
        length = math.hypot(dx, dy); nx, ny = dy/length, -dx/length
        circle_points = [(2*nx, 2*ny), (-2*nx, -2*ny)]
        support = math.hypot(2*nx, ny)
        ellipse_points = [(4*nx/support, ny/support), (-4*nx/support, -ny/support)]
        hyperbola_points = [(-1, 0), (1, 0)] if dx == 0 else []
        parabola_points = [] if dx == 0 else [(0, 0)] if dy == 0 else [(.5, .25)]
        answers[name] = {}
        for prefix, kind, points in [('ct', 'circle', circle_points), ('et', 'ellipse', ellipse_points),
                                      ('pt', 'parabola', parabola_points), ('ht', 'hyperbola', hyperbola_points)]:
            answers[name].update(_set(prefix, point_contacts(kind, points), direction=direction))
    out.append((d, cases, answers))

    d = _Doc('conic_tangent_degeneracy').number('b', 1).free('P', 2, 0).free('S', 0, 1)
    d.equation('c', o('-', o('+', o('*', r(0), sq(X)), sq(Y)), n(1)), 'b')
    d.free('A', 0, 0).free('B', -1, 0).line('base', 'A', 'B')
    multiple(d, 't', 'c'); multiple(d, 'parallel', 'c', parallel=True); strict(d, 'at', 'c', 'S')
    cases, answers = [], {}
    for name, b in [('ellipse', 1), ('degenerate', 0), ('hyperbola', -1), ('recovery', 1)]:
        cases.append({'name': name, 'inputs': {'b': N(b)}})
        if b == 0:
            answers[name] = {**_set('t', [], reason='upstream', cause='c'),
                             **_set('parallel', [], reason='upstream', cause='c'), 'at': _absent('line', 'upstream', 'c')}
        else:
            points = [(.5, math.sqrt(3)/2), (.5, -math.sqrt(3)/2)] if b == 1 else [(-.5, -math.sqrt(5)/2), (-.5, math.sqrt(5)/2)]
            contacts = [(x, y, b*x, y) for x, y in points]
            parallel_points = [(0, 1), (0, -1)] if b == 1 else [(0, -1), (0, 1)]
            answers[name] = {**_set('t', contacts), **_set('parallel', [(x, y, 0, y) for x, y in parallel_points], direction=(-1, 0)),
                             'at': _defined('line', _line(0, 1, 0, 1))}
    out.append((d, cases, answers))

    d = _Doc('conic_tangent_infinite_contact').free('P', 1, 1).equation('h', hyperbola)
    d.equation('p', parabola)
    multiple(d, 't', 'h')
    multiple(d, 'distant', 'p')
    cases, answers = [], {}
    for name, point, points in [('one_finite', (1, 1), [(1, 0)]), ('empty', (0, 0), []),
                                ('on', (1, 0), [(1, 0)]), ('two', (0, 2), [(math.sqrt(5)/2, -.5), (-math.sqrt(5)/2, -.5)]),
                                ('overflow', (1e200, 0), []),
                                ('recovery', (1, 1), [(1, 0)])]:
        cases.append({'name': name, 'inputs': {'P': P(*point)}})
        answers[name] = _set('t', point_contacts('hyperbola', points))
        px, py = point
        if name == 'overflow':
            # The second graph contact would have y=4e400.
            answers[name].update(_set('distant', [], reason='non_finite'))
            continue
        # Contact roots t=px±sqrt(px²-py) of y=x² through (px,py).
        discriminant = px*px-py
        roots = [px+math.sqrt(discriminant), px-math.sqrt(discriminant)] if discriminant > 0 else [px] if discriminant == 0 else []
        # Polar direction ranks t by px for these finite exact cases.
        roots = sorted(set(roots), reverse=True)
        answers[name].update(_set('distant', [(x, x*x, x, -.5) for x in roots]))
    out.append((d, cases, answers))

    d = _Doc('conic_tangent_numeric_limits').free('O', 1.45e308, 1.45e308)
    angle = math.pi/8
    d.free('A', 1.45e308, 1.45e308)
    d.free('B', 1.45e308-math.sin(angle)*1e307, 1.45e308+math.cos(angle)*1e307).line('base', 'A', 'B')
    d.op('op_c', 'circle.center_radius', {'center': _ref('O'), 'radius': _num(1e307)}, [('circle', 'c', 'circle')])
    multiple(d, 't', 'c', parallel=True)
    out.append((d, [{'name': 'projection_overflow'}], {'projection_overflow': _set('t', [], reason='non_finite')}))

    d = _Doc('tangent_slot_changes').free('P', 7, -2)
    U, V = o('-', X, n(3)), o('+', Y, n(2))
    d.equation('c', o('-', o('+', o('/', sq(U), n(4)), sq(V)), n(1)))
    multiple(d, 't', 'c')
    cases, answers = [], {}
    for name, x, points in [('right', 7, [(4, -2+math.sqrt(3)/2), (4, -2-math.sqrt(3)/2)]),
                            ('left', -1, [(2, -2-math.sqrt(3)/2), (2, -2+math.sqrt(3)/2)]),
                            ('merge', 5, [(5, -2)]), ('inside', 3, []),
                            ('recovery', 7, [(4, -2+math.sqrt(3)/2), (4, -2-math.sqrt(3)/2)])]:
        cases.append({'name': name, 'inputs': {'P': P(x, -2)}})
        answers[name] = _set('t', [(qx, qy, (qx-3)/4, qy+2) for qx, qy in points], reason='point_inside')
    out.append((d, cases, answers))

    d = _Doc('tangent_found_capacity').free('P', 0, -1).equation('c', parabola)
    for count in (1, 2, 4):
        multiple(d, 'capacity'+str(count)+'_', 'c', count=count)
    cases, answers = [], {}
    for name, y, points in [('two', -1, [(1, 1), (-1, 1)]), ('one', 0, [(0, 0)]),
                            ('none', 1, []), ('recovery', -1, [(1, 1), (-1, 1)])]:
        cases.append({'name': name, 'inputs': {'P': P(0, y)}})
        answers[name] = {}
        for count in (1, 2, 4):
            answers[name].update(_set('capacity'+str(count)+'_', point_contacts('parabola', points), count=count))
    out.append((d, cases, answers))
    return out


def build_fixtures():
    from .curves_fixtures import _rounded
    from .parity import PARITY_FORMAT, generate_scene, verify_fixture
    out = {}
    for d, cases, answers in scenes():
        fixture = _rounded(generate_scene({'format': PARITY_FORMAT, 'id': d.doc['documentId'],
                                          'document': d.doc, 'cases': cases}))
        fixture['document'] = d.doc
        for case in fixture['cases']:
            case['expect'].update(_rounded(answers[case['name']]))
        problems = verify_fixture(fixture)
        if problems:
            raise ValueError(f"{fixture['id']}: analytical answers differ: {problems}")
        out[fixture['id']+'.json'] = fixture
    return out
