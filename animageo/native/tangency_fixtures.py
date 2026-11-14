"""Graph tangency curves with independently written analytic expectations."""
import math


def _defined(type_, value):
    return {'state': 'defined', 'type': type_, 'value': value}


def _absent(type_, reason, cause=None):
    result = {'state': 'undefined', 'type': type_, 'reason': reason}
    if cause is not None:
        result['cause'] = cause
    return result


def _line(x, y, slope):
    # Solve ax+by+c=0 from its analytic slope/intercept. This uses the
    # normal projection, independently of the kernel's direction projection.
    length = math.hypot(1, slope)
    a, b = -slope / length, 1 / length
    c = -(a*x + b*y)
    return _defined('line', {'p': [-c*a, -c*b], 'dir': [b, -a]})


def _answer(prefix, x, y=0, slope=0, *, reason=None, cause=None):
    if reason:
        return {prefix: _absent('line', reason, cause), prefix+'_touch': _absent('point', reason, cause)}
    return {prefix: _line(x, y, slope), prefix+'_touch': _defined('point', {'x': x, 'y': y})}


def scenes():
    from .curves_fixtures import _Doc, _ref, _num, X, n, o, r, sq, call

    def tangent(d, f='f', prefix='t', x='x'):
        arg = _ref(x) if isinstance(x, str) else _num(x)
        return d.op('op_'+prefix, 'line.tangent_function_at', {'function': _ref(f), 'x': arg},
                    [('line', prefix, 'line'), ('touch', prefix+'_touch', 'point')])

    def branch(then, other=None, sign='<', at=0):
        return {'if': [{'cmp': sign, 'args': [X, n(at)]}, then] + ([] if other is None else [other])}

    def frame(name, **inputs):
        return {'name': name, 'inputs': {k: _num(v) for k, v in inputs.items()}}

    out = []
    d = _Doc('graph_tangent_abscissa').number('x', 1)
    for key, tree in [('square', sq(X)), ('cube', o('^', X, n(3))), ('sine', call('sin', X))]:
        d.function(key, tree)
        tangent(d, key, key+'_t')
    cases, answers = [], {}
    for name, x in [('positive', 1), ('negative', -1), ('origin', 0), ('recovery', 1)]:
        cases.append(frame(name, x=x))
        answers[name] = {**_answer('square_t', x, x*x, 2*x), **_answer('cube_t', x, x**3, 3*x*x),
                         **_answer('sine_t', x, math.sin(x), math.cos(x))}
    out.append((d, cases, answers))

    d = _Doc('graph_tangent_domain').number('x', 0)
    d.function('closed', sq(X), lo=0, hi=2)
    guard = {'and': [{'cmp': '>', 'args': [X, n(0)]}, {'cmp': '<', 'args': [X, n(2)]}]}
    d.function('open', {'if': [guard, sq(X)]}).function('root', call('sqrt', X))
    d.function('guarded', branch(sq(X), sign='>='))
    for key in ('closed', 'open', 'root', 'guarded'):
        tangent(d, key, key+'_t')
    cases, answers = [], {}
    for name, x in [('left', 0), ('right', 2), ('outside', -1), ('interior', 1), ('beyond', 3), ('recovery', 0)]:
        cases.append(frame(name, x=x))
        root_reason = 'out_of_domain' if x < 0 else 'not_differentiable' if x == 0 else None
        answers[name] = {
            **_answer('closed_t', x, x*x, 2*x, reason=None if 0 <= x <= 2 else 'out_of_domain'),
            **_answer('open_t', x, x*x, 2*x, reason=None if 0 < x < 2 else 'out_of_domain'),
            **_answer('guarded_t', x, x*x, 2*x, reason=None if x >= 0 else 'out_of_domain'),
            **_answer('root_t', x, math.sqrt(x) if x >= 0 else 0,
                      .5/math.sqrt(x) if x > 0 else 0, reason=root_reason)}
    out.append((d, cases, answers))

    d = _Doc('graph_tangent_corner_join').number('x', 0)
    for key, tree in [('corner', call('abs', X)), ('cusp', o('^', call('abs', X), n(2/3))),
                      ('smooth', branch(sq(X), o('+', sq(X), o('^', X, n(3))))),
                      ('jump', branch(X, o('+', X, n(1))))]:
        d.function(key, tree)
        tangent(d, key, key+'_t')
    cases, answers = [], {}
    for name, x in [('join', 0), ('left', -1), ('right', 1), ('recovery', 0)]:
        cases.append(frame(name, x=x))
        reason = 'not_differentiable' if x == 0 else None
        answers[name] = {**_answer('corner_t', x, abs(x), -1 if x < 0 else 1, reason=reason),
                         **_answer('cusp_t', x, abs(x)**(2/3), (-1 if x < 0 else 1)*2/3, reason=reason),
                         **_answer('smooth_t', x, x*x+(x**3 if x >= 0 else 0), 2*x+(3*x*x if x >= 0 else 0)),
                         **_answer('jump_t', x, x+(1 if x >= 0 else 0), 1, reason=reason)}
    out.append((d, cases, answers))

    d = _Doc('graph_tangent_hole_pole').number('x', 1)
    d.function('hole', o('/', o('-', sq(X), n(1)), o('-', X, n(1))))
    d.function('pole', o('/', n(1), X))
    tangent(d, 'hole', 'hole_t')
    tangent(d, 'pole', 'pole_t')
    cases, answers = [], {}
    for name, x in [('hole', 1), ('pole', 0), ('negative', -1), ('regular', 2), ('recovery', 1)]:
        cases.append(frame(name, x=x))
        answers[name] = {**_answer('hole_t', x, x+1, 1, reason='out_of_domain' if x == 1 else None),
                         **_answer('pole_t', x, 1/x if x else 0, -1/x**2 if x else 0,
                                   reason='out_of_domain' if x == 0 else None)}
    out.append((d, cases, answers))

    d = _Doc('graph_tangent_live_parameter').number('x', 1).number('a', 1)
    d.function('f', o('*', r(0), sq(X)), 'a')
    tangent(d)
    cases, answers = [], {}
    for name, a, x in [('initial', 1, 1), ('flat', 0, 1), ('coefficient', -1, 1),
                       ('abscissa', -1, 2), ('recovery', 1, 1)]:
        cases.append(frame(name, a=a, x=x))
        answers[name] = _answer('t', x, a*x*x, 2*a*x)
    out.append((d, cases, answers))

    d = _Doc('graph_tangent_numeric_limits')
    d.function('f', branch(n(0), call('sin', o('/', n(1), X)), sign='<='))
    d.function('missing', branch(o('/', n(1), n(0)), sq(X)))
    d.function('overflow', o('*', n(1e308), o('*', n(2), X)))
    tangent(d, x=0)
    tangent(d, 'missing', 'missing_t', x=0)
    tangent(d, 'overflow', 'overflow_t', x=0)
    out.append((d, [{'name': 'unconfirmed'}], {'unconfirmed': {
        **_answer('t', 0, reason='no_convergence'), **_answer('missing_t', 0, reason='no_convergence'),
        **_answer('overflow_t', 0, reason='non_finite')}}))

    d = _Doc('line_slope_normal').number('x', 1).function('f', sq(X))
    tangent(d)
    d.op('op_normal', 'line.perpendicular', {'point': _ref('t_touch'), 'base': _ref('t')},
         [('line', 'normal', 'line')])
    for key in ('t', 'normal'):
        d.op('op_'+key+'_slope', 'line.slope', {'line': _ref(key)}, [('number', key+'_slope', 'number')])
    cases, answers = [], {}
    for name, x in [('positive', 1), ('horizontal', 0), ('negative', -1), ('recovery', 1)]:
        cases.append(frame(name, x=x))
        # The perpendicular operation rotates the oriented tangent by +90°.
        m = 2*x
        length = math.hypot(1, m)
        dx, dy = -m/length, 1/length
        nx, ny = dy, -dx
        offset = nx*x + ny*x*x
        answers[name] = {**_answer('t', x, x*x, m),
            'normal': _defined('line', {'p': [offset*nx, offset*ny], 'dir': [dx, dy]}),
            't_slope': _defined('number', {'value': m, 'unit': 'scalar'}),
            'normal_slope': (_defined('number', {'value': -1/m, 'unit': 'scalar'}) if m else
                             _absent('number', 'vertical_line'))}
    out.append((d, cases, answers))
    return out


def build_fixtures():
    from .curves_fixtures import _rounded, case_samples
    from .parity import PARITY_FORMAT, generate_scene, verify_fixture

    out = {}
    for d, cases, answers in scenes():
        raw = generate_scene({'format': PARITY_FORMAT, 'id': d.doc['documentId'],
                              'document': d.doc, 'cases': cases})
        for case in raw['cases']:
            case['samples'] = case_samples(d.doc, case['expect'])
        fixture = _rounded(raw)
        fixture['document'] = d.doc
        for original, case in zip(raw['cases'], fixture['cases']):
            if 'inputs' in original:
                case['inputs'] = original['inputs']
            for key, rec in case['expect'].items():
                if rec['state'] == 'defined' and rec['type'] == 'function':
                    rec['value'] = original['expect'][key]['value']
            case['expect'].update(_rounded(answers[case['name']]))
        problems = verify_fixture(fixture)
        if problems:
            raise ValueError(f"{fixture['id']}: analytical answers differ: {problems}")
        out[fixture['id']+'.json'] = fixture
    return out
