"""Document and expression builders shared by function-analysis tests."""
from tests.native.conftest import DocBuilder, num, ref

X = {'var': 'x'}


def n(v):
    return {'num': v}


def o(name, *args):
    return {'op': name, 'args': list(args)}


def power(a, k):
    return o('^', a, n(k))


def fn(name, *args):
    return {'fn': name, 'args': list(args)}


class Doc(DocBuilder):
    def __init__(self, name='function_analysis', bounds=(-10, -10, 10, 10)):
        super().__init__(name, bounds, registry_version='1.11')

    def function(self, ast, *refs, lo=None, hi=None):
        args = {'expr': {'kind': 'expr', 'ast': ast},
                'refs': {'kind': 'list', 'items': [ref(i) for i in refs]}}
        if lo is not None:
            args['min'] = num(lo)
        if hi is not None:
            args['max'] = num(hi)
        return self.op('op_f', 'function.expr', args, [('function', 'f', 'function')])

    def search(self, name='roots_polynomial', count=3, slots=None):
        base = 'extremum' if name == 'extrema_polynomial' else 'root'
        args = {'function': ref('f')}
        if count is not None:
            args['count'] = num(count)
        slots = slots if slots is not None else range(1, (count or 3) + 1)
        return self.op('op_result', 'function.' + name, args,
                       [(f'{base}.{k}', f'P{k}', 'point') for k in slots])
